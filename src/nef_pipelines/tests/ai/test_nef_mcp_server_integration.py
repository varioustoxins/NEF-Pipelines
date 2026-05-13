"""
Integration tests for the NEF AI server using FastMCP Client in-process.

Tests use the FastMCP Client directly against the server object (no HTTP server
needed), which avoids event-loop binding issues and subprocess coordination.
"""

import json
import re
import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip("MCP server requires Python 3.10 or later", allow_module_level=True)

fastmcp = pytest.importorskip("fastmcp")
import nef_pipelines.tools.ai.mcp_lib as mcp_lib  # noqa E402

Client = fastmcp.Client

from nef_pipelines.lib.test_lib import assert_lines_match, read_test_data  # noqa: E402
from nef_pipelines.tools.ai.mcp_commands import _MCP_TOOLS  # noqa: E402
from nef_pipelines.tools.ai.mcp_lib import (  # noqa: E402
    _RESOURCE_NAME_SEPARATOR,
    _RESOURCES,
    _get_resource_name_from_filename,
)
from nef_pipelines.tools.ai.server_lib import _build_server  # noqa: E402

EXPECTED_TOOL_NAMES = {fn.__name__ for fn in _MCP_TOOLS} | {
    "nef_resources_list",
    "nef_resources_read",
}

EXPECTED_RESOURCE_URIS = {
    f"nef://{_get_resource_name_from_filename(f.name)}"
    for f in _RESOURCES.iterdir()
    if f.name.endswith(".md") and _RESOURCE_NAME_SEPARATOR in f.name
}

EXPECTED_HELP_SECTIONS = ["Usage:", "Options", "General"]

EXPECTED_FRAMES_LIST = """\
nef_nmr_meta_data                    nef_molecular_system
nef_chemical_shift_list_default      nef_nmr_spectrum_k_ubi_n_hsqc`1`
nef_nmr_spectrum_k_ubi_hnca`1`       nef_nmr_spectrum_k_ubi_hncoca`1`
nef_nmr_spectrum_k_ubi_hncaco`1`     nef_nmr_spectrum_k_ubi_hnco`1`
nef_nmr_spectrum_k_ubi_hncacb`1`     nef_nmr_spectrum_k_ubi_cbcaconh`1`
nef_nmr_spectrum_mars_ubi_n_hsqc`1`  ccpn_substance_1D3Z_1|Chain.None
ccpn_substance_mySubstance.None      ccpn_assignment
"""


@pytest.fixture
async def mcp_client(tmp_path, monkeypatch):
    """\
    Create FastMCP client connected in-process to a fresh server, with cwd
    set to a temporary sandbox directory (matching the real server behaviour).
    Calls nef_read_me_first and nef_warnings_shown to satisfy the orientation guard.
    """

    # Initialize startup context with the temp sandbox
    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(tmp_path),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    monkeypatch.chdir(tmp_path)
    async with Client(_build_server()) as client:
        result = await client.call_tool("nef_read_me_first", arguments={})
        data = json.loads(result.content[0].text)
        token_match = re.search(
            r"ORIENTATION-TOKEN: (\S+)", data.get("information", "")
        )
        if token_match:
            await client.call_tool(
                "nef_warnings_shown", arguments={"token": token_match.group(1)}
            )
        yield client


@pytest.mark.asyncio
async def test_list_tools(mcp_client):
    """\
    Test that all expected tools are registered with the MCP server.
    """
    tools = await mcp_client.list_tools()
    tool_names = {tool.name for tool in tools}
    assert (
        tool_names == EXPECTED_TOOL_NAMES
    ), f"Missing or extra tools. Got: {tool_names}"


@pytest.mark.asyncio
async def test_list_resources(mcp_client):
    """\
    Test that all documentation resources are registered as MCP resources.
    """
    resources = await mcp_client.list_resources()
    resource_uris = {str(r.uri) for r in resources}
    assert (
        EXPECTED_RESOURCE_URIS == resource_uris
    ), f"Missing or extra resources. Got: {resource_uris}"


@pytest.mark.asyncio
async def test_nef_read_me_first_tool(mcp_client):
    """\
    Test nef_read_me_first tool via MCP protocol returns orientation text.
    """
    result = await mcp_client.call_tool("nef_read_me_first", arguments={})
    content_text = result.content[0].text

    assert "Already oriented" in content_text
    assert "nef_resources_list" in content_text
    assert "nef_resources_read" in content_text
    # Experimental notice is in the 'information' field of the JSON output
    assert "EXPERIMENTAL" in content_text
    assert "AI: You MUST show" in content_text


@pytest.mark.asyncio
async def test_nef_readme_resource(mcp_client):
    """\
    Test nef://readme resource returns complete readme structure.
    """
    content = await mcp_client.read_resource("nef://readme")
    text = content[0].text
    assert "NEF-Pipelines" in text
    assert len(text) > 1000
    assert "```" in text


@pytest.mark.asyncio
async def test_nef_skill_resource(mcp_client):
    """\
    Test nef://skill resource returns non-empty content.
    """
    content = await mcp_client.read_resource("nef://skills")
    text = content[0].text
    assert len(text) > 0


@pytest.mark.asyncio
async def test_nef_list_commands_tool(mcp_client):
    """\
    Test nef_list_commands tool via MCP protocol returns a markdown table.
    """
    result = await mcp_client.call_tool("nef_list_commands", arguments={})
    content_text = result.content[0].text

    assert "Command" in content_text or "command" in content_text
    assert "Category" in content_text or "category" in content_text
    assert "frames" in content_text
    assert "save" in content_text
    assert "|" in content_text


@pytest.mark.asyncio
async def test_nef_get_command_help_tool(mcp_client):
    """\
    Test nef_get_command_help tool via MCP protocol returns help text.
    """
    result = await mcp_client.call_tool(
        "nef_get_command_help", arguments={"command_pattern": "save"}
    )
    content_text = result.content[0].text

    assert "save" in content_text.lower()
    assert "usage" in content_text.lower() or "arguments" in content_text.lower()
    assert len(content_text) > 200


@pytest.mark.asyncio
async def test_nef_execute_pipeline_tool_empty_steps(mcp_client):
    """\
    Test nef_execute_pipeline with no steps is a no-op returning success.
    """
    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={"steps": [], "nef_input": ""},
    )
    content_text = result.content[0].text

    assert '"exit_code":0' in content_text


@pytest.mark.asyncio
async def test_nef_execute_pipeline_tool_help(mcp_client):
    """\
    Test nef_execute_pipeline with --help returns complete help structure.
    """
    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={"steps": [["nef", "--help"]], "nef_input": ""},
    )
    content_text = result.content[0].text

    for section in EXPECTED_HELP_SECTIONS:
        assert section in content_text, f"Missing section: {section}"
    assert len(content_text) > 200


@pytest.mark.asyncio
async def test_nef_execute_pipeline_with_nef_data(mcp_client):
    """\
    Test nef_execute_pipeline with NEF input data returns frame list.
    """
    simple_nef = read_test_data("ubiquitin_short.nef", __file__)

    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={"steps": [["nef", "frames", "list"]], "nef_input": simple_nef},
    )
    content_text = result.content[0].text
    stdout = json.loads(content_text)["stdout"]

    assert_lines_match(EXPECTED_FRAMES_LIST, stdout)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command_pattern,expected_keyword",
    [
        ("*frames*", "frames"),
        ("*sparky*", "sparky"),
        ("save", "save"),
    ],
)
async def test_nef_list_commands(mcp_client, command_pattern, expected_keyword):
    """\
    Test nef_list_commands with various patterns returns matching commands.
    """
    result = await mcp_client.call_tool(
        "nef_list_commands", arguments={"command_pattern": command_pattern}
    )
    content_text = result.content[0].text

    assert expected_keyword in content_text.lower()
    assert "|" in content_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args,expected_content",
    [
        (["nef", "version"], ""),
        (["nef", "--help"], "Usage:"),
        (["nef", "help", "commands", "--display=table", "frames*"], "frames"),
    ],
)
async def test_nef_execute_pipeline(mcp_client, args, expected_content):
    """\
    Test nef_execute_pipeline with various commands returns expected content.
    """
    result = await mcp_client.call_tool(
        "nef_execute_pipeline", arguments={"steps": [args], "nef_input": ""}
    )
    content_text = result.content[0].text

    assert len(content_text) > 0
    if expected_content:
        assert expected_content in content_text


@pytest.mark.asyncio
async def test_nef_upload_file_tool(mcp_client):
    """\
    Test nef_upload_file writes a file via MCP protocol.
    """
    result = await mcp_client.call_tool(
        "nef_upload_file", arguments={"name": "test.nef", "content": "data_test\n"}
    )
    data = json.loads(result.content[0].text)

    assert not data["error"]
    assert data["name"] == "test.nef"


@pytest.mark.asyncio
async def test_nef_download_file_tool(mcp_client):
    """\
    Test nef_download_file reads back a file written by nef_upload_file.
    """
    content = "data_ubiquitin\n_nef_sequence.chain_code A\n"
    await mcp_client.call_tool(
        "nef_upload_file", arguments={"name": "round_trip.nef", "content": content}
    )

    result = await mcp_client.call_tool(
        "nef_download_file", arguments={"name": "round_trip.nef"}
    )
    data = json.loads(result.content[0].text)

    assert not data["error"]
    assert "data_ubiquitin" in data["content"]


@pytest.mark.asyncio
async def test_nef_list_files_tool(mcp_client):
    """\
    Test nef_list_files returns files written by nef_upload_file.
    """
    await mcp_client.call_tool(
        "nef_upload_file", arguments={"name": "a.nef", "content": "x"}
    )
    await mcp_client.call_tool(
        "nef_upload_file", arguments={"name": "b.nef", "content": "y"}
    )

    result = await mcp_client.call_tool("nef_list_files", arguments={})
    content_text = result.content[0].text

    assert "a.nef" in content_text
    assert "b.nef" in content_text


@pytest.mark.asyncio
async def test_nef_upload_file_rejected_absolute(mcp_client):
    """\
    Test nef_upload_file rejects absolute paths via MCP protocol.
    """
    result = await mcp_client.call_tool(
        "nef_upload_file", arguments={"name": "/etc/passwd", "content": "x"}
    )
    data = json.loads(result.content[0].text)

    assert bool(data["error"])


@pytest.mark.asyncio
async def test_orientation_guard_blocks_tool_in_integration(tmp_path, monkeypatch):
    """\
    Test that the guard error is surfaced via MCP protocol before nef_warnings_shown.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_WARNINGS_SHOWN", False)
    async with Client(_build_server()) as client:
        result = await client.call_tool("nef_list_files", arguments={})
        data = json.loads(result.content[0].text)
        assert "nef_warnings_shown" in data["error"]
