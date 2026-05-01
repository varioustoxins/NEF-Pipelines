from fastmcp import FastMCP

from nef_pipelines.lib.util import get_version
from nef_pipelines.tools.ai.mcp_commands_lib import (
    nef_execute_command,
    nef_execute_pipeline,
    nef_get_command_help,
    nef_list_commands,
    nef_read_me_first,
    nef_read_resource,
)
from nef_pipelines.tools.ai.mcp_lib import (
    _RESOURCES,
    resource_description,
    resource_name,
)

_MCP_TOOLS = [
    nef_list_commands,
    nef_get_command_help,
    nef_read_me_first,
    nef_read_resource,
    nef_execute_command,
    nef_execute_pipeline,
]


def _build_server() -> FastMCP:
    """\
    Build and return a configured FastMCP server with all NEF tools and resources registered.
    """
    preamble = (_RESOURCES / "preamble.md").read_text()
    mcp_server = FastMCP("nef-pipelines", version=get_version(), instructions=preamble)

    for md_file in sorted(_RESOURCES.iterdir(), key=lambda f: f.name):
        if not md_file.name.endswith(".md") or md_file.name == "preamble.md":
            continue
        name = resource_name(md_file.name)
        description = resource_description(md_file.name)
        uri = f"nef://{name}"

        def _make_reader(f):
            def _reader() -> str:
                return f.read_text()

            return _reader

        mcp_server.resource(uri, mime_type="text/markdown", description=description)(
            _make_reader(md_file)
        )

    for tool_fn in _MCP_TOOLS:
        mcp_server.tool()(tool_fn)

    return mcp_server
