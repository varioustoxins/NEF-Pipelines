"""
CLI command for managing persistent sandbox preference.
"""

import sys
from pathlib import Path
from typing import Optional

import typer
from strenum import LowercaseStrEnum

from nef_pipelines.lib.preferences_storage_lib import get_config_file_path
from nef_pipelines.lib.structures import NEFPipelinesException
from nef_pipelines.lib.util import exit_error, warn
from nef_pipelines.tools.ai import ai_app
from nef_pipelines.tools.ai.sandbox_lib import (
    get_sandbox_preference,
    set_sandbox_preference,
    validate_sandbox_path,
)


class SandBoxException(NEFPipelinesException):
    """Exception for sandbox preference operations."""


class SandboxStorageAction(LowercaseStrEnum):
    """Actions for sandbox preference storage."""

    GET = "get"
    SET = "set"
    CLEAR = "clear"
    SHOW = "show"


_PATH_OPTIONS = {SandboxStorageAction.SET}
_NO_PATH_OPTIONS = {
    SandboxStorageAction.GET,
    SandboxStorageAction.CLEAR,
    SandboxStorageAction.SHOW,
}


@ai_app.command(no_args_is_help=True)
def sandbox(
    action: SandboxStorageAction = typer.Argument(
        ...,
        help=f"Action to perform: {', '.join(SandboxStorageAction.__members__.keys())}",
    ),
    path: Optional[str] = typer.Argument(
        None, help=f"Directory path (required for {SandboxStorageAction.SET} action)"
    ),
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Check if sandbox is usable and give diagnostics on stderr (ignored by clear)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Show detailed sandbox allowlists (global and per-command); only for 'show' action",
    ),
):
    """- manage persistent sandbox directory preferences"""

    _exit_error_if_on_python_39()

    _exit_error_if_have_irrelevant_path(action, path)

    path_obj = Path(path) if path else None

    try:
        output_lines = command(action, path_obj, verbose=verbose)
    except SandBoxException as e:
        _exit_error_if_sanbox_command_fails(action, e)

    # Validate path if requested (Requirement 3)
    if validate and action != SandboxStorageAction.CLEAR:
        current_sandbox = get_sandbox_preference()
        if current_sandbox:
            _validate_sandbox_path_and_warn_if_bad(current_sandbox)
        else:
            warn("Sandbox is not set")

    # Print output
    for line in output_lines:
        print(line)


def command(
    action: SandboxStorageAction, path: Optional[Path] = None, verbose: bool = False
) -> list[str]:
    """Execute the sandbox preference command and return output lines."""

    output_lines = []
    config_file = get_config_file_path()

    # Execute the action
    if action == SandboxStorageAction.SET:
        if not path:
            raise SandBoxException("Error: Path required for 'set' action")

        error = set_sandbox_preference(str(path))
        if error:
            raise SandBoxException(error)

        # Success - get the resolved path from preferences
        saved_path = get_sandbox_preference()
        output_lines.append(f"Sandbox preference set to: {saved_path}")
        warn("this will not take effect until you restart your AI / MCP server")

    elif action == SandboxStorageAction.GET:
        current_path = get_sandbox_preference()
        if current_path:
            output_lines.append(str(current_path))

    elif action == SandboxStorageAction.CLEAR:
        set_sandbox_preference("")
        output_lines.append("Sandbox preference cleared")
        warn("this will not take effect until you restart your AI / MCP server")

    elif action == SandboxStorageAction.SHOW:
        current_path = get_sandbox_preference()
        if current_path:
            output_lines.append(f"Path: {current_path}")
        else:
            output_lines.append("Path: (not set)")
        output_lines.append(f"Config File: {config_file}")
        output_lines.append("Field: mcp_sandbox_path")

        if verbose:
            output_lines.extend(_get_verbose_sandbox_info())

    else:
        raise SandBoxException(
            f"Error: Unknown action '{action}'. Valid: {', '.join(SandboxStorageAction.__members__.keys())}"
        )

    return output_lines


def _validate_sandbox_path_and_warn_if_bad(path: Path):

    diag = validate_sandbox_path(path)
    if diag:
        warn(f"Sandbox validation failed: {diag}")


def _exit_error_if_sanbox_command_fails(
    action: SandboxStorageAction, e: SandBoxException
):
    error = " ".join(e.args)
    msg = f"""
            there was an error while trying to {action} the sandbox, it was:
            {error}
        """
    exit_error(msg)


def _exit_error_if_have_irrelevant_path(
    action: SandboxStorageAction, path: Optional[str]
):
    if action in _NO_PATH_OPTIONS and path:
        msg = f"The actions {', '.join(_NO_PATH_OPTIONS)} don't take paths"
        exit_error(msg)


def _exit_error_if_on_python_39():
    if sys.version_info < (3, 10):
        msg = f"""
            AI-related configuration features require Python 3.10 or later.
            You are running Python {sys.version_info.major}.{sys.version_info.minor}.
            Please upgrade your Python version.
        """
        exit_error(msg)


def _get_verbose_sandbox_info() -> list[str]:
    """Get detailed sandbox allowlist information.

    Returns:
        List of output lines describing global and per-command allowlists
    """
    lines = []

    try:
        import nef_pipelines.tools.ai.sandbox_lib as sandbox_lib

        # For plain CLI use (no `nef ai server` running), command modules were
        # imported but nothing ever drained their setups — @setup_sandbox only
        # records intent, never executes at import time. Run them for real here so
        # --verbose shows actual directories/descriptions rather than just function
        # names. Harmless: setup functions only mkdir(parents=True, exist_ok=True)
        # and set env vars for this one-shot process; nothing persists beyond it.
        # Each setup function self-reports what it did via SetupResult.description
        # (stored in AllowedDirs.descriptions below) rather than this command
        # inferring it by diffing os.environ.
        if sandbox_lib._PENDING_DIRECTORY_SETUPS and not sandbox_lib._INSTANCE_ID:
            sandbox_lib.init_sandbox_instance_with_generated_id(
                prefix="TEST-PID", test_mode=True
            )

        sandbox_data = sandbox_lib._SANDBOX_DATA

        lines.append("")
        msg = "Allow Lists"
        lines.append(msg)
        lines.append("-" * len(msg))

        # Global allowlist
        lines.append("")
        if sandbox_data.globals.directories or sandbox_data.globals.glob_patterns:
            lines.append("global directories:")
            lines.append("")
            for line in sorted(sandbox_data.globals.directories):
                lines.append(f"{line}")
            for line in sorted(sandbox_data.globals.glob_patterns):
                lines.append(f"{str(line[0])}/{line[1]}")
            lines.append("")

        if sandbox_data.commands:
            lines.append("per-command directories:")
            for cmd_id in sorted(sandbox_data.commands.keys()):
                lines.append("")
                cmd_allowed = sandbox_data.commands[cmd_id]
                cmd = f"  {cmd_id}:"
                lines.append(cmd.strip())
                for setup, descriptions in cmd_allowed.descriptions:
                    setup = " ".join(setup.split("_")[1:])
                    for description in descriptions:
                        lines.append(f"  {setup} - {description}")

        # Sandbox path
        if sandbox_data.sandbox_path:
            lines.append("")
            lines.append(f"User sandbox path: {sandbox_data.sandbox_path}")

    except ImportError:
        lines.append("")
        lines.append("Note: Sandbox runtime state not available")
        lines.append(
            "      (requires MCP server to be running or command modules imported)"
        )

    return lines
