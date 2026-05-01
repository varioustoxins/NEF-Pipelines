from fastmcp import FastMCP

from nef_pipelines.lib.util import get_version
from nef_pipelines.tools.ai.mcp_commands_lib import (  # noqa: F401 — import triggers @mcp_tool decorations
    _MCP_TOOLS,
)
from nef_pipelines.tools.ai.mcp_lib import (
    _RESOURCES,
    _get_resource_description_from_filename,
    _get_resource_name_from_filename,
)


def _build_server() -> FastMCP:
    """\
    Build and return a configured FastMCP server with all NEF tools and resources registered.

    Tools are discovered automatically from mcp_commands via the @mcp_tool decorator,
    in declaration order.
    """
    preamble = (_RESOURCES / "preamble.md").read_text()
    mcp_server = FastMCP("nef-pipelines", version=get_version(), instructions=preamble)

    for md_file in sorted(_RESOURCES.iterdir(), key=lambda f: f.name):
        if not md_file.name.endswith(".md") or md_file.name == "preamble.md":
            continue
        name = _get_resource_name_from_filename(md_file.name)
        description = _get_resource_description_from_filename(md_file.name)
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
