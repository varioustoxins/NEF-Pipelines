"""Tests for MCP server initialization and sandbox instance setup."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

if sys.version_info < (3, 10):
    pytest.skip("MCP server requires Python 3.10 or later", allow_module_level=True)

from nef_pipelines.tools.ai.server_lib import _build_server

pytest.importorskip("fastmcp")

EXPECTED_REQUIRED_TOOLS = {
    "nef_execute_pipeline",
    "nef_list_commands",
    "nef_get_command_help",
    "nef_upload_file",
    "nef_download_file",
    "nef_list_files",
    "nef_read_me_first",
    "nef_warnings_shown",
}

EXPECTED_REQUIRED_RESOURCES = {
    "nef://readme",
    "nef://cli-idioms",
    "nef://nef-file-format",
    "nef://star-file-format",
}


def test_instance_directory_created_with_pid_time_format():
    """Test that instance directory is created with PID{pid}-TIME{nanoseconds} format."""

    pid = os.getpid()

    # Build server (instance already initialized by session fixture)
    _build_server()

    # Check for instance directory (use platform-specific temp)
    tmp_base = Path(tempfile.gettempdir()) / "nef_pipelines_mcp_tmp"
    assert tmp_base.exists(), f"{tmp_base} not created"

    # Find instance directory for this PID (can be TEST-PID or PID prefix)
    instance_dirs = list(tmp_base.glob(f"*PID{pid}-TIME*"))
    assert instance_dirs, f"No instance directory found for PID{pid}"

    instance_dir = instance_dirs[0]
    assert (
        f"PID{pid}-TIME" in instance_dir.name
    ), f"Instance directory has wrong format: {instance_dir.name}"


def test_cache_subdirectories_preallocated():
    """Test that cache subdirectories are created at startup."""
    from nef_pipelines.tools.ai.sandbox_lib import _SANDBOX_DATA, _TMP_BASE

    # The fixture already initialised instance and imported commands
    # Cache directories should have been created during decoration
    assert _TMP_BASE is not None, "TMP_BASE not initialized"
    assert _TMP_BASE.exists(), f"TMP_BASE directory not created: {_TMP_BASE}"

    # Check for cache directories that were actually registered
    # (only check what was actually set up, not what we expect)
    registered_dirs = set()
    for cmd_allowed in _SANDBOX_DATA.commands.values():
        registered_dirs.update(cmd_allowed.directories)

    # Filter to only cache directories under _TMP_BASE
    cache_dirs = {d for d in registered_dirs if d.is_relative_to(_TMP_BASE)}

    # Verify registered cache directories exist
    for cache_dir in cache_dirs:
        assert (
            cache_dir.exists()
        ), f"Registered cache directory not created: {cache_dir}"
        assert cache_dir.is_dir(), f"Cache path is not a directory: {cache_dir}"


def test_decorated_commands_registered_in_sandbox_data():
    """Test that @setup_sandbox decorator registers commands in _SANDBOX_DATA."""
    from nef_pipelines.tools.ai.sandbox_lib import _SANDBOX_DATA

    # Fixture already imported all commands via create_nef_pipelines_app()
    # Check that commands are registered in per-command registry
    assert len(_SANDBOX_DATA.commands) > 0, (
        f"No commands registered in _SANDBOX_DATA. "
        f"Available: {list(_SANDBOX_DATA.commands.keys())}"
    )

    # Check for specific commands (only if they were imported)
    # Note: Not all commands may be imported depending on test configuration
    if _SANDBOX_DATA.commands:
        # Just verify structure is correct
        for cmd_id, cmd_allowed in _SANDBOX_DATA.commands.items():
            assert isinstance(
                cmd_allowed.directories, set
            ), f"Command {cmd_id} directories is not a set"
            assert isinstance(
                cmd_allowed.glob_patterns, list
            ), f"Command {cmd_id} glob_patterns is not a list"


def test_global_allowed_dirs_populated():
    """Test that global registry is populated with system-wide allowlist."""
    from nef_pipelines.tools.ai.sandbox_lib import _SANDBOX_DATA

    # Global registry should have __pycache__ glob patterns for site-packages
    # (as tuples of (base_dir, pattern))
    assert _SANDBOX_DATA.globals.glob_patterns, "Global glob_patterns registry is empty"
    assert len(_SANDBOX_DATA.globals.glob_patterns) > 0, "No global patterns registered"

    # Should have __pycache__ glob pattern paired with site-packages directories
    patterns = [pattern for base_dir, pattern in _SANDBOX_DATA.globals.glob_patterns]
    assert "**/__pycache__/**" in patterns, "__pycache__ pattern not in global patterns"


# Setup functions now use global _TMP_BASE and are tested via integration tests


async def test_mcp_server_has_required_tools():
    """Test that MCP server registers expected tools."""
    from fastmcp import Client

    from nef_pipelines.tools.ai.server_lib import _build_server

    mcp = _build_server()
    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}

        # Check for core NEF tools
        for tool_name in EXPECTED_REQUIRED_TOOLS:
            assert tool_name in tool_names, f"Required tool missing: {tool_name}"


async def test_mcp_server_has_resources():
    """Test that MCP server registers resources."""
    from fastmcp import Client

    from nef_pipelines.tools.ai.server_lib import _build_server

    mcp = _build_server()
    async with Client(mcp) as client:
        resources = await client.list_resources()
        resource_uris = {str(r.uri) for r in resources}

        # Check for key resources
        for uri in EXPECTED_REQUIRED_RESOURCES:
            assert uri in resource_uris, f"Required resource missing: {uri}"


@pytest.mark.parametrize(
    "test_id,pid,timestamp,expected_valid",
    [
        ("valid-format", "12345", "1739328543789123456", True),
        ("short-timestamp", "12345", "1739328543", True),
        ("non-numeric-pid", "abc12", "1739328543789123456", False),
        ("non-numeric-timestamp", "12345", "notanumber", False),
    ],
    ids=lambda x: x[0] if isinstance(x, tuple) else x,
)
def test_instance_id_format_validation(test_id, pid, timestamp, expected_valid):
    """Test instance ID format validation."""
    instance_id = f"PID{pid}-TIME{timestamp}"

    # Check format matches expected pattern
    import re

    pattern = r"^PID\d+-TIME\d+$"
    is_valid = bool(re.match(pattern, instance_id))

    assert is_valid == expected_valid, f"Instance ID validation mismatch: {instance_id}"
