import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Callable, Optional

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.table import Table

from nef_pipelines.lib.util import exit_error
from nef_pipelines.tools.ai import ai_app

if TYPE_CHECKING:
    from fastmcp import FastMCP

NEF_MCP_SANDBOX_ENV_VAR_NAME = "NEF_MCP_SANDBOX"

EXPERIMENTAL_BANNER_HEADING = (
    "[bold red]⚠  EXPERIMENTAL - USE WITH CAUTION  ⚠[/bold red]"
)

EXPERIMENTAL_BANNER_BODY = """
The NEF MCP server is EXPERIMENTAL software.
It is still under Development!

It grants an AI model direct, unsupervised access to your filesystem and
[bold red]READ, WRITE and OVERWRITE[/bold red] files on your disk without further confirmation.

[bold]BEFORE starting this server you should:[/bold]
  • Run only in a sandboxed or restricted directory
  • Understand which AI model and client will connect
  • Never expose this server on a public network interface
  • Review the commands available via: [cyan]nef help commands[/cyan]

[bold red]THE AUTHORS ACCEPT NO LIABILITY FOR DATA LOSS OR UNINTENDED FILE ACCESS.[/bold red]
"""


@dataclass
class SandboxPathResult:
    """\
    Result of _get_sandbox_path.

    path     - resolved sandbox Path, or None when is_temp is True (caller must create a temp dir)
    warning  - non-None when a fallback occurred
    is_temp  - True when the caller must create and later clean up a temporary directory
    """

    path: Optional[Path] = None
    warning: Optional[str] = None
    is_temp: bool = False


def _build_server():
    from nef_pipelines.tools.ai.server_lib import _build_server as _build

    return _build()


@ai_app.command(name="server")
def server(
    transport: Annotated[
        str,
        typer.Option("-t", "--transport", help="transport to use [stdio, sse, streamable-http]", metavar="<TRANSPORT>"),
    ] = "stdio",
    host: Annotated[
        str,
        typer.Option("--host", help="host to bind to for HTTP transports", metavar="<HOST>"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("-p", "--port", help="port to bind to for HTTP transports", metavar="<PORT>"),
    ] = 8000,
    path: Annotated[
        Optional[str],
        typer.Option(
            "--path",
            help=f"sandbox directory for MCP server operations; overrides {NEF_MCP_SANDBOX_ENV_VAR_NAME} environment variable; if not specified, creates a temporary directory",
            metavar="<PATH>",
        ),
    ] = None,
    preserve: Annotated[
        bool,
        typer.Option(
            "--preserve",
            help="""\
                preserve the auto-created temporary sandbox directory on exit; has no effect when 
                --path or the environment variable selects the sandbox
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
        warning = sandbox.warning
        if warning:
            warning += f" — falling back to temporary directory: {sandbox_path}"
    else:
        sandbox_path = sandbox.path
        warning = sandbox.warning

    _issue_experimental_warning()
    if warning:
        _print_sandbox_warning(warning)
    _print_sandbox_location(sandbox_path)

    server_transport_args = _get_transport_args(host, port, transport)

    os.chdir(sandbox_path)
    try:
        _build().run(**server_transport_args)
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
    Determine the sandbox path from command line arg or environment variable.
    Priority: --path > NEF_MCP_SANDBOX env var > temporary directory.

    When is_temp is True in the result, path is None — the caller must create a temporary directory.
    If path_arg is invalid, falls back to env var or signals temp needed, with a warning.
    """
    warning = None

    # 1. Command line takes priority (with fallback on error)
    if path_arg is not None:
        try:
            sandbox = Path(path_arg).resolve()
            if not sandbox.exists():
                warning = f"Specified --path does not exist: {sandbox}"
            elif not sandbox.is_dir():
                warning = f"Specified --path is not a directory: {sandbox}"
            else:
                return SandboxPathResult(path=sandbox)
        except Exception as e:
            warning = f"Invalid --path argument: {e}"

        # Fall through to check env var or signal temp needed

    # 2. Check environment variable
    env_path = os.environ.get(NEF_MCP_SANDBOX_ENV_VAR_NAME)
    if env_path:
        try:
            sandbox = Path(env_path).resolve()
            if sandbox.exists() and sandbox.is_dir():
                if warning:
                    warning += f" — falling back to {NEF_MCP_SANDBOX_ENV_VAR_NAME}: {sandbox}"
                return SandboxPathResult(path=sandbox, warning=warning)
        except Exception:
            pass  # Fall through to temp dir

    # 3. Signal that a temporary directory is needed; caller creates it
    return SandboxPathResult(warning=warning, is_temp=True)


def _print_sandbox_location(sandbox_path: Path):
    """Print the sandbox location to stderr."""
    console = Console(stderr=True)
    console.print(f"\n[cyan]Sandbox directory:[/cyan] {sandbox_path}\n", style="bold")


def _print_sandbox_warning(warning: str):
    """Print a warning about sandbox path issues to stderr."""
    console = Console(stderr=True)
    console.print(
        f"\n[yellow]⚠  WARNING:[/yellow] {warning}\n",
        style="bold yellow",
    )


def _issue_experimental_warning():
    console = Console(stderr=True)

    table = Table(
        box=box.DOUBLE,
        show_header=False,
        show_edge=True,
        border_style="bold red",
        padding=(1, 2),
        expand=False,
    )

    table.add_row(Align.center(EXPERIMENTAL_BANNER_HEADING))
    table.add_section()
    table.add_row(EXPERIMENTAL_BANNER_BODY.strip())

    console.print(Align.center(table))


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
