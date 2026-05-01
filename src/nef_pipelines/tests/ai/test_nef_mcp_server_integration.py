"""
Integration tests for the NEF AI server using FastMCP Client in-process.

Tests use the FastMCP Client directly against the server object (no HTTP server
needed), which avoids event-loop binding issues and subprocess coordination.
"""

import sys

import pytest

from nef_pipelines.lib.test_lib import read_test_data
from nef_pipelines.tools.ai.mcp_lib import _RESOURCES, _get_resource_name_from_filename
from nef_pipelines.tools.ai.server import _build_server

if sys.version_info < (3, 10):
    pytest.skip("MCP server requires Python 3.10 or later", allow_module_level=True)

pytest.importorskip("fastmcp.Client")

EXPECTED_TOOL_NAMES = {
    "nef_read_me_first",
    "nef_read_resource",
    "nef_list_commands",
    "nef_get_command_help",
    "nef_execute_command",
    "nef_execute_pipeline",
}

EXPECTED_RESOURCE_URIS = {
    f"nef://{_get_resource_name_from_filename(f.name)}"
    for f in _RESOURCES.iterdir()
    if f.name.endswith(".md") and f.name != "preamble.md"
}


@pytest.fixture
async def mcp_client():
    """\
    Create FastMCP client connected in-process to a fresh MCP server per test.
    """
    async with Client(_build_server()) as client:  # noqa: F821
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
    Test that readme and skill are registered as MCP resources.
    """
    resources = await mcp_client.list_resources()
    resource_uris = {str(r.uri) for r in resources}
    assert (
        EXPECTED_RESOURCE_URIS == resource_uris
    ), f"Missing or extra resources. Got: {resource_uris}"


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
    content = await mcp_client.read_resource("nef://skill")
    text = content[0].text
    assert len(text) > 0


@pytest.mark.asyncio
async def test_nef_list_commands_tool(mcp_client):
    """\
    Test nef_list_commands tool via MCP protocol.
    """
    result = await mcp_client.call_tool("nef_list_commands", arguments={})

    content_text = result.content[0].text

    # Verify it's a markdown table with expected columns
    assert "Command" in content_text or "command" in content_text
    assert "Category" in content_text or "category" in content_text

    # Verify some known commands are present
    assert "frames" in content_text
    assert "save" in content_text
    assert "help" in content_text

    # Verify it's a table format (has pipe characters)
    assert "|" in content_text


@pytest.mark.asyncio
async def test_nef_list_commands_with_filter(mcp_client):
    """\
    Test nef_list_commands with pattern filter returns only matching commands.
    """
    result = await mcp_client.call_tool(
        "nef_list_commands", arguments={"command_pattern": "*frames*"}
    )

    content_text = result.content[0].text

    # Should contain frames commands
    assert "frames" in content_text

    # Should be a table
    assert "|" in content_text


@pytest.mark.asyncio
async def test_nef_get_command_help_tool(mcp_client):
    """\
    Test nef_get_command_help tool via MCP protocol.
    """
    result = await mcp_client.call_tool(
        "nef_get_command_help", arguments={"command_pattern": "save"}
    )

    content_text = result.content[0].text

    # Verify complete help structure for save command
    assert "save" in content_text.lower()

    # Help should contain usage/arguments sections
    assert "usage" in content_text.lower() or "arguments" in content_text.lower()

    # Should be substantial (detailed help)
    assert len(content_text) > 200


@pytest.mark.asyncio
async def test_nef_execute_command_tool(mcp_client):
    """\
    Test nef_execute_command tool via MCP protocol returns version.
    """
    result = await mcp_client.call_tool(
        "nef_execute_command", arguments={"args": ["version"], "nef_input": ""}
    )

    content_text = result.content[0].text

    assert len(content_text) > 0
    assert len(content_text.strip()) < 100


@pytest.mark.asyncio
async def test_nef_execute_command_with_help(mcp_client):
    """\
    Test nef_execute_command with help flag returns complete help.
    """
    EXPECTED_HELP_SECTIONS = [
        "Usage:",
        "Options",
        "General",
    ]

    result = await mcp_client.call_tool(
        "nef_execute_command", arguments={"args": ["--help"], "nef_input": ""}
    )

    content_text = result.content[0].text

    # Verify all expected help sections are present
    for section in EXPECTED_HELP_SECTIONS:
        assert section in content_text, f"Missing section: {section}"

    # Should be substantial help text
    assert len(content_text) > 200


@pytest.mark.asyncio
async def test_nef_execute_command_with_nef_data(mcp_client):
    """\
    Test nef_execute_command with NEF input data returns complete frame list.
    """
    EXPECTED_FRAMES = [
        "nef_nmr_meta_data",
        "nef_molecular_system",
        "nef_chemical_shift_list",
    ]

    simple_nef = read_test_data("ubiquitin_short.nef", __file__)

    result = await mcp_client.call_tool(
        "nef_execute_command",
        arguments={"args": ["frames", "list"], "nef_input": simple_nef},
    )

    content_text = result.content[0].text

    # Verify all expected frames are listed
    for frame in EXPECTED_FRAMES:
        assert frame in content_text, f"Missing frame: {frame}"

    assert len(content_text) > 0


@pytest.mark.asyncio
async def test_nef_execute_pipeline_tool_empty_steps(mcp_client):
    """\
    Test nef_execute_pipeline with no steps returns error.
    """
    EXPECTED_ERROR = "No steps provided"

    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={"steps": [], "nef_input": "", "verbose": False},
    )

    content_text = result.content[0].text

    # Should contain error message
    assert EXPECTED_ERROR in content_text


@pytest.mark.asyncio
async def test_nef_execute_pipeline_tool_single_step(mcp_client):
    """\
    Test nef_execute_pipeline with single step returns version.
    """
    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={"steps": [{"args": ["version"]}], "nef_input": "", "verbose": False},
    )

    content_text = result.content[0].text

    assert len(content_text.strip()) > 0


@pytest.mark.asyncio
async def test_nef_execute_pipeline_tool_multiple_steps(mcp_client):
    """\
    Test nef_execute_pipeline executes multiple steps successfully.
    """
    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={
            "steps": [{"args": ["version"]}, {"args": ["version"]}],
            "nef_input": "",
            "verbose": False,
        },
    )

    content_text = result.content[0].text
    assert len(content_text) > 0


@pytest.mark.asyncio
async def test_nef_execute_pipeline_with_nef_data(mcp_client):
    """\
    Test nef_execute_pipeline with NEF input data returns frame list.
    """
    EXPECTED_FRAMES = [
        "nef_nmr_meta_data",
        "nef_molecular_system",
        "nef_chemical_shift_list",
    ]

    simple_nef = read_test_data("ubiquitin_short.nef", __file__)

    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={
            "steps": [{"args": ["frames", "list"]}],
            "nef_input": simple_nef,
            "verbose": False,
        },
    )

    content_text = result.content[0].text

    for frame in EXPECTED_FRAMES:
        assert frame in content_text, f"Missing frame: {frame}"


@pytest.mark.asyncio
async def test_nef_execute_pipeline_verbose(mcp_client):
    """\
    Test nef_execute_pipeline with verbose mode provides step details.
    """
    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={"steps": [{"args": ["version"]}], "nef_input": "", "verbose": True},
    )

    content_text = result.content[0].text
    assert len(content_text) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command_pattern,expected_keyword",
    [
        ("*frames*", "frames"),
        ("*sparky*", "sparky"),
        ("save", "save"),
    ],
)
async def test_nef_list_commands_parametrized(
    mcp_client, command_pattern, expected_keyword
):
    """\
    Test nef_list_commands with various patterns returns matching commands.
    """
    result = await mcp_client.call_tool(
        "nef_list_commands", arguments={"command_pattern": command_pattern}
    )

    content_text = result.content[0].text

    assert expected_keyword in content_text.lower()
    assert "|" in content_text
    assert len(content_text) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args,expected_content",
    [
        (["version"], ""),
        (["--help"], "Usage:"),
        (["help", "commands", "--display=table", "frames*"], "frames"),
    ],
)
async def test_nef_execute_command_parametrized(mcp_client, args, expected_content):
    """\
    Test nef_execute_command with various command arguments returns expected content.
    """
    result = await mcp_client.call_tool(
        "nef_execute_command", arguments={"args": args, "nef_input": ""}
    )

    content_text = result.content[0].text

    assert len(content_text) > 0

    if expected_content:
        assert expected_content in content_text
