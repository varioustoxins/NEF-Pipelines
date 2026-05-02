import os
import sys
import tempfile
from typing import TYPE_CHECKING, Callable

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.table import Table

from nef_pipelines.lib.util import exit_error
from nef_pipelines.tools.ai import ai_app

if TYPE_CHECKING:
    from fastmcp import FastMCP

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


def _build_server():
    from nef_pipelines.tools.ai.server_lib import _build_server as _build

    return _build()


@ai_app.command(name="server")
def server(
    transport: str = typer.Option(
        "stdio",
        "-t",
        "--transport",
        help="transport to use [stdio, sse, streamable-http]",
        metavar="<TRANSPORT>",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="host to bind to for HTTP transports",
        metavar="<HOST>",
    ),
    port: int = typer.Option(
        8000,
        "-p",
        "--port",
        help="port to bind to for HTTP transports",
        metavar="<PORT>",
    ),
):
    """- start the NEF MCP server"""

    _exit_error_if_python_lees_than_3_10()

    _build = _get_build_server_or_exit_error_if_fast_mcp_is_missing()

    _issue_experimental_warning()

    server_transport_args = _get_transport_args(host, port, transport)

    sandbox = tempfile.TemporaryDirectory(prefix="nef_mcp_")
    os.chdir(sandbox.name)
    _build().run(**server_transport_args)
    sandbox.cleanup()


def _get_transport_args(host: str, port: int, transport: str) -> dict[str, str]:
    kwargs = {"transport": transport}
    if transport != "stdio":
        kwargs["host"] = host
        kwargs["port"] = port
    return kwargs


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
