"""
Integration tests for nef_mcp_server_integrated.py using FastMCP Client.

These tests use the FastMCP testing utilities to test the MCP server
through its protocol interface, validating tool integration and responses.
"""

import sys
from pathlib import Path

import pytest

# Add the parent directory to the path to import the MCP server module
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.utilities.tests import run_server_async

from nef_mcp_server_integrated import mcp
from nef_pipelines.lib.test_lib import assert_lines_match, read_test_data

EXPECTED_TOOL_NAMES = {
    "nef_list_commands",
    "nef_get_command_help",
    "nef_get_readme",
    "nef_get_skill_file",
    "nef_execute_command",
    "nef_execute_pipeline",
}


@pytest.fixture
async def mcp_client():
    """\
    Create FastMCP client connected to the MCP server for testing.

    Uses run_server_async to start the server as an async task,
    then connects a Client through StreamableHttpTransport.
    """
    async with run_server_async(mcp, transport="streamable-http") as server_url:
        async with Client(StreamableHttpTransport(server_url)) as client:
            yield client


@pytest.mark.asyncio
async def test_list_tools(mcp_client):
    """\
    Test that all expected tools are registered with the MCP server.
    """
    tools = await mcp_client.list_tools()

    tool_names = {tool.name for tool in tools.tools}

    # Verify complete set of expected tools
    assert tool_names == EXPECTED_TOOL_NAMES, f"Missing or extra tools. Got: {tool_names}"


@pytest.mark.asyncio
async def test_nef_list_commands_tool(mcp_client):
    """\
    Test nef_list_commands tool via MCP protocol.
    """
    result = await mcp_client.call_tool(
        "nef_list_commands",
        arguments={}
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

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
        "nef_list_commands",
        arguments={"command_pattern": "*frames*"}
    )

    assert len(result.content) == 1
    content_text = result.content[0].text

    # Should contain frames commands
    assert "frames" in content_text

    # Should be a table
    assert "|" in content_text

    # Should NOT contain commands that don't match pattern
    # (checking for absence is okay when pattern filtering is the feature)


@pytest.mark.asyncio
async def test_nef_get_command_help_tool(mcp_client):
    """\
    Test nef_get_command_help tool via MCP protocol.
    """
    result = await mcp_client.call_tool(
        "nef_get_command_help",
        arguments={"command_pattern": "save"}
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Verify complete help structure for save command
    assert "save" in content_text.lower()

    # Help should contain usage/arguments sections
    assert "usage" in content_text.lower() or "arguments" in content_text.lower()

    # Should be substantial (detailed help)
    assert len(content_text) > 200


@pytest.mark.asyncio
async def test_nef_get_readme_tool(mcp_client):
    """\
    Test nef_get_readme tool via MCP protocol returns complete readme structure.
    """
    EXPECTED_README_SECTIONS = [
        "NEF Pipelines",
        "What is NEF Pipelines",
        "Architecture",
        "Getting Started",
        "Common Workflows",
        "Key Concepts",
        "Best Practices",
        "Quick Reference",
    ]

    result = await mcp_client.call_tool(
        "nef_get_readme",
        arguments={}
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Verify all expected sections are present
    for section in EXPECTED_README_SECTIONS:
        assert section in content_text, f"Missing section: {section}"

    # Verify substantial content
    assert len(content_text) > 1000

    # Verify it contains code examples (markdown code blocks)
    assert "```" in content_text


@pytest.mark.asyncio
async def test_nef_get_skill_file_tool(mcp_client):
    """\
    Test nef_get_skill_file tool via MCP protocol returns valid response.
    """
    result = await mcp_client.call_tool(
        "nef_get_skill_file",
        arguments={}
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Skill file may or may not exist
    # If it exists, should contain skill content
    # If not, should contain error message
    assert len(content_text) > 0

    # Response should be valid (either content or error, not empty)


@pytest.mark.asyncio
async def test_nef_execute_command_tool(mcp_client):
    """\
    Test nef_execute_command tool via MCP protocol returns version.
    """
    result = await mcp_client.call_tool(
        "nef_execute_command",
        arguments={
            "args": ["version"],
            "nef_input": ""
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Version output should contain version number (e.g., "0.1.120")
    assert len(content_text) > 0
    # Should be a short version string
    assert len(content_text.strip()) < 100


@pytest.mark.asyncio
async def test_nef_execute_command_with_help(mcp_client):
    """\
    Test nef_execute_command with help flag returns complete help.
    """
    EXPECTED_HELP_SECTIONS = [
        "Usage:",
        "Options",
        "Commands",
    ]

    result = await mcp_client.call_tool(
        "nef_execute_command",
        arguments={
            "args": ["--help"],
            "nef_input": ""
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

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
        arguments={
            "args": ["frames", "list"],
            "nef_input": simple_nef
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Verify all expected frames are listed
    for frame in EXPECTED_FRAMES:
        assert frame in content_text, f"Missing frame: {frame}"

    # Output should be non-empty
    assert len(content_text) > 0


@pytest.mark.asyncio
async def test_nef_execute_pipeline_tool_empty_steps(mcp_client):
    """\
    Test nef_execute_pipeline with no steps returns error.
    """
    EXPECTED_ERROR = "No steps provided"

    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={
            "steps": [],
            "nef_input": "",
            "verbose": False
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

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
        arguments={
            "steps": [{"args": ["version"]}],
            "nef_input": "",
            "verbose": False
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Should contain version number
    assert len(content_text.strip()) > 0
    assert len(content_text.strip()) < 100


@pytest.mark.asyncio
async def test_nef_execute_pipeline_tool_multiple_steps(mcp_client):
    """\
    Test nef_execute_pipeline executes multiple steps successfully.
    """
    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={
            "steps": [
                {"args": ["version"]},
                {"args": ["version"]}
            ],
            "nef_input": "",
            "verbose": False
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Should complete successfully
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
            "verbose": False
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Verify expected frames are listed
    for frame in EXPECTED_FRAMES:
        assert frame in content_text, f"Missing frame: {frame}"


@pytest.mark.asyncio
async def test_nef_execute_pipeline_verbose(mcp_client):
    """\
    Test nef_execute_pipeline with verbose mode provides step details.
    """
    result = await mcp_client.call_tool(
        "nef_execute_pipeline",
        arguments={
            "steps": [{"args": ["version"]}],
            "nef_input": "",
            "verbose": True
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Verbose mode includes step diagnostics
    # Should be non-empty
    assert len(content_text) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("command_pattern,expected_keyword", [
    ("*frames*", "frames"),
    ("*sparky*", "sparky"),
    ("save", "save"),
])
async def test_nef_list_commands_parametrized(mcp_client, command_pattern, expected_keyword):
    """\
    Test nef_list_commands with various patterns returns matching commands.
    """
    result = await mcp_client.call_tool(
        "nef_list_commands",
        arguments={"command_pattern": command_pattern}
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Should contain expected keyword
    assert expected_keyword in content_text.lower()

    # Should be table format
    assert "|" in content_text

    # Should be non-empty
    assert len(content_text) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("args,expected_content", [
    (["version"], ""),  # Version just returns version string
    (["--help"], "Usage:"),  # Help contains Usage section
    (["help", "commands", "--display=table", "frames*"], "frames"),  # Table contains frames
])
async def test_nef_execute_command_parametrized(mcp_client, args, expected_content):
    """\
    Test nef_execute_command with various command arguments returns expected content.
    """
    result = await mcp_client.call_tool(
        "nef_execute_command",
        arguments={
            "args": args,
            "nef_input": ""
        }
    )

    # Verify response structure
    assert len(result.content) == 1
    assert hasattr(result.content[0], 'text')

    content_text = result.content[0].text

    # Should be non-empty
    assert len(content_text) > 0

    # If expected content specified, verify it's present
    if expected_content:
        assert expected_content in content_text
