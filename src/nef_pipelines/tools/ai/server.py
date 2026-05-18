import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Annotated, Callable, Optional

import typer

from nef_pipelines.lib.preferences_storage_lib import get_config_file_path
from nef_pipelines.lib.util import exit_error, info, warn
from nef_pipelines.tools.ai import ai_app
from nef_pipelines.tools.ai.mcp_lib import create_nef_pipelines_app
from nef_pipelines.tools.ai.sandbox_audit import install_audit_hook
from nef_pipelines.tools.ai.sandbox_lib import (
    get_sandbox_preference,
    validate_sandbox_path,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP

NEF_MCP_SANDBOX_ENV_VAR_NAME = "NEF_MCP_SANDBOX"
NEF_MCP_SANDBOX_PATH_OPTION = "--sandbox-path"


@dataclass
class SandboxPathResult:
    """\
    Result of _get_sandbox_path.

    path        - resolved sandbox Path, or None when is_temp is True (caller must create a temp dir)
    warning     - non-None when a fallback occurred
    is_temp     - True when the caller must create and later clean up a temporary directory
    path_source - human-readable description of where the path came from (e.g. '--sandbox-path option')
    """

    path: Optional[Path] = None
    warning: Optional[str] = None
    is_temp: bool = False
    path_source: str = ""


@ai_app.command(name="server")
def server(
    transport: Annotated[
        str,
        typer.Option(
            "-t",
            "--transport",
            help="transport to use [stdio, sse, streamable-http]",
            metavar="<TRANSPORT>",
        ),
    ] = "stdio",
    host: Annotated[
        str,
        typer.Option(
            "--host", help="host to bind to for HTTP transports", metavar="<HOST>"
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            "-p", "--port", help="port to bind to for HTTP transports", metavar="<PORT>"
        ),
    ] = 8000,
    path: Annotated[
        Optional[str],
        typer.Option(
            "--sandbox-path",
            help=f"""sandbox directory for MCP server operations; overrides {NEF_MCP_SANDBOX_ENV_VAR_NAME}
                    environment variable; if not specified, creates a temporary directory""",
            metavar="<PATH>",
        ),
    ] = None,
    preserve: Annotated[
        bool,
        typer.Option(
            "--preserve",
            help=f"""\
                preserve the auto-created temporary sandbox directory on exit; has no effect when
                {NEF_MCP_SANDBOX_PATH_OPTION} or the environment variable selects the sandbox
            """,
        ),
    ] = False,
):
    """- start the NEF MCP server"""

    _exit_error_if_python_lees_than_3_10()

    _build = _get_build_server_or_exit_error_if_fast_mcp_is_missing()

    sandbox = _get_sandbox_path(path)

    sandbox_dir = None
    if sandbox.is_temp:
        sandbox_dir = tempfile.TemporaryDirectory(prefix="nef_mcp_")
        sandbox_path = Path(sandbox_dir.name)
        sandbox_warning = sandbox.warning
        if sandbox_warning:
            sandbox_warning += f" — falling back to temporary directory: {sandbox_path}"
    else:
        # is_temp=False implies path is not None (enforced by _get_sandbox_path)
        if sandbox.path is None:
            exit_error(
                "sandbox.path must not be None when is_temp=False, contact the developers this is a bug"
            )
        sandbox_path = sandbox.path
        sandbox_warning = sandbox.warning

    if sandbox_warning:
        warn(sandbox_warning)

    info(f"Sandbox directory: {sandbox_path}")

    os.chdir(sandbox_path)

    server_transport_args = _get_transport_args(host, port, transport)

    import nef_pipelines.tools.ai.mcp_lib as _mcp_lib

    _mcp_lib._STARTUP_CONTEXT = _mcp_lib.StartupContext(
        sandbox_path=str(sandbox_path),
        is_temporary=sandbox.is_temp,
        will_be_cleaned=sandbox.is_temp and not preserve,
        path_source=sandbox.path_source,
        warning=sandbox_warning or "",
    )

    # Install audit hook to monitor file writes during pipeline execution
    install_audit_hook()

    create_nef_pipelines_app()

    try:
        _build().run(show_banner=False, **server_transport_args)
    finally:
        if sandbox_dir is not None and not preserve:
            sandbox_dir.cleanup()


def _get_transport_args(host: str, port: int, transport: str) -> dict[str, str]:
    kwargs = {"transport": transport}
    if transport != "stdio":
        kwargs["host"] = host
        kwargs["port"] = port
    return kwargs


def _get_sandbox_path(path_arg: Optional[str]) -> SandboxPathResult:
    """\
    Determine the sandbox path from (in priority order):
    1. --sandbox-path command line argument
    2. Persistent TOML preference
    3. NEF_MCP_SANDBOX environment variable
    4. Temporary directory (fallback)

    If a sandbox is specified but invalid: warns and uses it anyway (allows user to fix without restart).
    Only falls back to next priority if current priority is NOT specified.
    When is_temp is True in the result, path is None — the caller must create a temporary directory.
    """
    result = _try_command_line_sandbox(path_arg)

    if result is None:
        result = _try_preference_sandbox()

    if result is None:
        result = _try_environment_sandbox()

    if result is None:
        result = SandboxPathResult(is_temp=True)

    return result


def _try_command_line_sandbox(path_arg: Optional[str]) -> Optional[SandboxPathResult]:
    """Check if sandbox path was provided via command line argument."""
    result = None
    if path_arg is not None:
        try:
            sandbox = Path(path_arg).expanduser().resolve()
            error = validate_sandbox_path(sandbox)
            warning = None
            if error:
                warning = f"Specified {NEF_MCP_SANDBOX_PATH_OPTION} {error}"

            result = SandboxPathResult(
                path=sandbox,
                warning=warning,
                path_source=f"{NEF_MCP_SANDBOX_PATH_OPTION} option",
            )
        except Exception as e:
            result = SandboxPathResult(
                path=None,
                warning=f"Invalid {NEF_MCP_SANDBOX_PATH_OPTION} argument: {e}",
                is_temp=True,
                path_source="",
            )
    return result


def _try_preference_sandbox() -> Optional[SandboxPathResult]:
    """Check if sandbox path exists in persistent preferences."""
    pref_path = get_sandbox_preference()
    result = None
    if pref_path:
        error = validate_sandbox_path(pref_path)
        env_path = os.environ.get(NEF_MCP_SANDBOX_ENV_VAR_NAME)
        note = ""
        warning = None
        if env_path:
            config_file = get_config_file_path()
            env_var_name = NEF_MCP_SANDBOX_ENV_VAR_NAME
            note = f" (Note: {env_var_name}={env_path} is set but overridden by saved preference in {config_file})"
        if error:
            if note:
                warning = f"""\
                    Saved preference is invalid: {error}
                    {note}
                """
                warning = dedent(warning.strip())
            else:
                warning = f"Saved preference is invalid: {error}"
        elif note:
            warning = note.strip()

        result = SandboxPathResult(
            path=pref_path,
            warning=warning,
            path_source="saved preference (use 'nef ai sandbox' to change)",
        )
    return result


def _try_environment_sandbox() -> Optional[SandboxPathResult]:
    """Check if sandbox path is specified via environment variable."""
    env_path = os.environ.get(NEF_MCP_SANDBOX_ENV_VAR_NAME)
    result = None
    if env_path:
        try:
            sandbox = Path(env_path).expanduser().resolve()
            error = validate_sandbox_path(sandbox)
            warning = None
            if error:
                warning = f"{NEF_MCP_SANDBOX_ENV_VAR_NAME} is invalid: {error}"

            result = SandboxPathResult(
                path=sandbox,
                warning=warning,
                path_source=f"{NEF_MCP_SANDBOX_ENV_VAR_NAME} environment variable",
            )
        except Exception as e:
            result = SandboxPathResult(
                warning=f"Invalid {NEF_MCP_SANDBOX_ENV_VAR_NAME}: {e}", is_temp=True
            )
    return result


def _get_build_server_or_exit_error_if_fast_mcp_is_missing() -> Callable[[], "FastMCP"]:
    try:
        from nef_pipelines.tools.ai.server_lib import _build_server as _build
    except ImportError:
        msg = """
                ERROR: fastmcp is not installed
                when using the install script use the --mcp-server option
                when installing using uv use uv tool install nef-pipelines[mcp]
                if using pip pip install nef-pipelines[mcp]
            """
        exit_error(msg)
    return _build


def _exit_error_if_python_lees_than_3_10():
    if sys.version_info < (3, 10):
        msg = f"""
            The NEF-Pipelines MCP server requires Python 3.10 or later.
            You are running Python {sys.version_info.major}.{sys.version_info.minor}.
            Please upgrade your Python version.
        """
        exit_error(msg)
