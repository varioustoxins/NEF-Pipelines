from fastmcp import FastMCP

from nef_pipelines.lib.util import get_version
from nef_pipelines.tools.ai.mcp_commands_lib import (
    _RESOURCES,
    nef_execute_command,
    nef_execute_pipeline,
    nef_get_command_help,
    nef_list_commands,
    nef_read_me_first,
    nef_read_resource,
    resource_description,
    resource_name,
)


def _build_server() -> FastMCP:
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

    mcp_server.tool()(nef_read_me_first)
    mcp_server.tool()(nef_read_resource)
    mcp_server.tool()(nef_list_commands)
    mcp_server.tool()(nef_get_command_help)
    mcp_server.tool()(nef_execute_command)
    mcp_server.tool()(nef_execute_pipeline)

    return mcp_server
