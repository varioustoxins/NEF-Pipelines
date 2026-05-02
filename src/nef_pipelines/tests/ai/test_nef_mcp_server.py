"""
Tests for AI server tool functions in server_lib.py.
"""

import sys

import pytest

from nef_pipelines.lib.test_lib import read_test_data
from nef_pipelines.tools.ai.mcp_commands_lib import (
    nef_download_file,
    nef_execute_pipeline,
    nef_get_command_help,
    nef_list_commands,
    nef_list_files,
    nef_read_me_first,
    nef_read_resource,
    nef_upload_file,
)

if sys.version_info < (3, 10):
    pytest.skip("MCP server requires Python 3.10 or later", allow_module_level=True)

pytest.importorskip("fastmcp")

# Expected structure constants
EXPECTED_COMMON_COMMANDS = ["frames", "save", "help"]
EXPECTED_README_SECTIONS = [
    "NEF-Pipelines",
]
EXPECTED_HELP_SECTIONS = ["Usage:", "Options", "General"]
EXPECTED_FRAMES_IN_UBIQUITIN = [
    "nef_nmr_meta_data",
    "nef_molecular_system",
    "nef_chemical_shift_list",
]


@pytest.fixture
def simple_nef_data():
    """\
    Simple NEF data for testing.
    """
    return read_test_data("ubiquitin_short.nef", __file__)


def test_nef_list_commands_all():
    """\
    Test nef_list_commands returns complete table with all expected commands.
    """
    result = nef_list_commands()

    # Verify response structure
    assert isinstance(result, dict)
    assert result["exit_code"] == 0
    assert isinstance(result["commands_table"], str)

    table = result["commands_table"]

    # Verify it's a table (contains pipe characters)
    assert "|" in table

    # Verify all expected common commands are present
    for command in EXPECTED_COMMON_COMMANDS:
        assert command in table.lower(), f"Missing command: {command}"

    # Verify table has headers
    assert "Command" in table or "command" in table
    assert "Category" in table or "category" in table


def test_nef_list_commands_filtered():
    """\
    Test nef_list_commands with pattern filter returns only matching commands.
    """
    result = nef_list_commands(command_pattern="*frames*")

    # Verify response structure
    assert isinstance(result, dict)
    assert result["exit_code"] == 0

    table = result["commands_table"]

    # Should contain frames command
    assert "frames" in table.lower()

    # Should be a valid table
    assert "|" in table


def test_nef_list_commands_sparky_filter():
    """\
    Test nef_list_commands filtering for sparky commands returns sparky tools.
    """
    result = nef_list_commands(command_pattern="*sparky*")

    # Verify response structure
    assert isinstance(result, dict)
    assert result["exit_code"] == 0

    table = result["commands_table"]

    # Should contain sparky commands
    assert "sparky" in table.lower()

    # Should be a valid table
    assert "|" in table


def test_nef_get_command_help_single_command():
    """\
    Test nef_get_command_help for single command returns complete help.
    """
    result = nef_get_command_help(command_pattern="save")

    # Verify response structure
    assert isinstance(result, dict)
    assert result["exit_code"] == 0
    assert isinstance(result["help_text"], str)

    help_text = result["help_text"]

    # Should contain command name
    assert "save" in help_text.lower()

    # Should contain help sections
    assert "usage" in help_text.lower() or "arguments" in help_text.lower()

    # Should be substantial
    assert len(help_text) > 200


def test_nef_get_command_help_wildcard():
    """\
    Test nef_get_command_help with wildcard pattern returns matching commands.
    """
    result = nef_get_command_help(command_pattern="*frames*")

    # Verify response structure
    assert isinstance(result, dict)
    assert result["exit_code"] == 0

    help_text = result["help_text"]

    # Should contain frames command help
    assert "frames" in help_text.lower()

    # Should be substantial
    assert len(help_text) > 100


def test_nef_get_command_help_grouped():
    """\
    Test nef_get_command_help with category grouping organizes by category.
    """
    result = nef_get_command_help(command_pattern="*", group_by_category=True)

    # Verify response structure
    assert isinstance(result, dict)
    assert result["exit_code"] == 0

    help_text = result["help_text"]

    # Should contain category headers or be organized
    assert len(help_text) > 500  # Should be comprehensive


def test_nef_read_me_first():
    """\
    Test nef_read_me_first returns orientation content with skip header.
    """
    result = nef_read_me_first()

    assert isinstance(result, dict)
    assert result["success"] is True
    assert isinstance(result["content"], str)
    assert "Already oriented" in result["content"]
    assert "NEF" in result["content"]
    assert len(result["content"]) > 200


def test_nef_read_resource_readme():
    """\
    Test nef_read_resource returns readme content with expected sections.
    """
    result = nef_read_resource("readme")

    assert isinstance(result, dict)
    assert result["success"] is True
    assert isinstance(result["content"], str)
    assert isinstance(result["available_resources"], list)

    for section in EXPECTED_README_SECTIONS:
        assert section in result["content"], f"Missing section: {section}"

    assert len(result["content"]) > 1000


def test_nef_read_resource_skill():
    """\
    Test nef_read_resource returns skill content.
    """
    result = nef_read_resource("skill")

    assert isinstance(result, dict)
    assert result["success"] is True
    assert isinstance(result["content"], str)


def test_nef_read_resource_not_found():
    """\
    Test nef_read_resource returns failure with available list for unknown name.
    """
    result = nef_read_resource("nonexistent")

    assert isinstance(result, dict)
    assert result["success"] is False
    assert isinstance(result["available_resources"], list)
    assert len(result["available_resources"]) > 0


def test_nef_execute_pipeline_empty_steps():
    """\
    Test nef_execute_pipeline with no steps is a no-op.
    """
    result = nef_execute_pipeline(steps=[])

    assert result.success is True
    assert result.exit_code == 0
    assert result.steps_completed == 0
    assert result.stdout == ""


def test_nef_execute_pipeline_single_step(simple_nef_data):
    """\
    Test nef_execute_pipeline with single step executes successfully.
    """
    result = nef_execute_pipeline(steps=[["frames", "list"]], nef_input=simple_nef_data)

    assert result.success is True
    assert result.exit_code == 0
    assert result.steps_completed == 1
    assert len(result.stderr) == 1


def test_nef_execute_pipeline_multiple_steps(simple_nef_data):
    """\
    Test nef_execute_pipeline chains stdout→stdin across steps.
    """
    result = nef_execute_pipeline(
        steps=[["save", "-"], ["frames", "list"]], nef_input=simple_nef_data
    )

    assert result.success is True
    assert result.exit_code == 0
    assert result.steps_completed == 2
    assert "nef_molecular_system" in result.stdout


def test_nef_execute_pipeline_step_failure():
    """\
    Test nef_execute_pipeline stops on step failure.
    """
    result = nef_execute_pipeline(steps=[["version"], ["nonexistent", "command"]])

    assert result.success is False
    assert result.exit_code != 0
    assert result.steps_completed == 1
    assert len(result.stderr) == 2


def test_nef_execute_pipeline_with_nef_data_passthrough(simple_nef_data):
    """\
    Test that pipeline can process NEF data through save command.
    """
    result = nef_execute_pipeline(steps=[["save", "-"]], nef_input=simple_nef_data)

    assert result.success is True
    assert len(result.stdout) > 0
    assert "data_" in result.stdout


def test_nef_execute_pipeline_step_with_no_args():
    """\
    Test nef_execute_pipeline with empty inner list is a silent no-op.
    """
    result = nef_execute_pipeline(steps=[[]])

    assert result.success is True
    assert result.exit_code == 0
    assert result.steps_completed == 0
    assert result.stderr == [""]


def test_nef_execute_pipeline_stderr_is_list(simple_nef_data):
    """\
    Test nef_execute_pipeline stderr is a list with one entry per step.
    """
    result = nef_execute_pipeline(
        steps=[["frames", "list"], ["save", "-"]], nef_input=simple_nef_data
    )

    assert isinstance(result.stderr, list)
    assert len(result.stderr) == 2


def test_nef_execute_pipeline_help():
    """\
    Test nef_execute_pipeline with --help returns complete help structure.
    """
    result = nef_execute_pipeline(steps=[["--help"]])

    assert result.success is True
    assert result.exit_code == 0

    for section in EXPECTED_HELP_SECTIONS:
        assert section in result.stdout, f"Missing section: {section}"

    assert len(result.stdout) > 200


def test_nef_execute_pipeline_returns_dataclass_structure():
    """\
    Test that nef_execute_pipeline returns a PipelineResult dataclass.
    """
    from nef_pipelines.tools.ai.mcp_lib import PipelineResult

    result = nef_execute_pipeline(steps=[["version"]])

    assert isinstance(result, PipelineResult)
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, list)
    assert isinstance(result.exit_code, int)
    assert isinstance(result.steps, list)
    assert isinstance(result.steps_completed, int)
    assert isinstance(result.success, bool)


def test_nef_list_commands_returns_dict_structure():
    """\
    Test that nef_list_commands returns complete expected dict structure.
    """
    EXPECTED_FIELDS = {"commands_table", "exit_code", "stderr"}

    result = nef_list_commands()

    # Verify complete field set
    assert isinstance(result, dict)
    assert (
        set(result.keys()) == EXPECTED_FIELDS
    ), f"Fields mismatch. Got: {set(result.keys())}"

    # Verify field types
    assert isinstance(result["commands_table"], str)
    assert isinstance(result["exit_code"], int)
    assert isinstance(result["stderr"], str)


def test_nef_get_command_help_returns_dict_structure():
    """\
    Test that nef_get_command_help returns complete expected dict structure.
    """
    EXPECTED_FIELDS = {"help_text", "exit_code", "stderr"}

    result = nef_get_command_help()

    # Verify complete field set
    assert isinstance(result, dict)
    assert (
        set(result.keys()) == EXPECTED_FIELDS
    ), f"Fields mismatch. Got: {set(result.keys())}"

    # Verify field types
    assert isinstance(result["help_text"], str)
    assert isinstance(result["exit_code"], int)
    assert isinstance(result["stderr"], str)


# --- nef_upload_file / nef_download_file / nef_list_files --------------------


def test_nef_upload_file(tmp_path, monkeypatch):
    """\
    Test nef_upload_file writes file content to the working directory.
    """
    monkeypatch.chdir(tmp_path)

    result = nef_upload_file("peaks.nef", "data_test\n")

    assert result["success"] is True
    assert result["name"] == "peaks.nef"
    assert result["bytes_written"] == len("data_test\n".encode("utf-8"))
    assert (tmp_path / "peaks.nef").read_text() == "data_test\n"


def test_nef_upload_file_absolute_path_rejected(tmp_path, monkeypatch):
    """\
    Test nef_upload_file rejects absolute paths.
    """
    monkeypatch.chdir(tmp_path)

    result = nef_upload_file("/etc/passwd", "x")

    assert result["success"] is False
    assert "error" in result


def test_nef_upload_file_traversal_rejected(tmp_path, monkeypatch):
    """\
    Test nef_upload_file rejects path traversal attempts.
    """
    monkeypatch.chdir(tmp_path)

    result = nef_upload_file("../../etc/passwd", "x")

    assert result["success"] is False
    assert "error" in result


def test_nef_upload_file_unicode_content(tmp_path, monkeypatch):
    """\
    Test nef_upload_file handles unicode content correctly.
    """
    monkeypatch.chdir(tmp_path)
    content = "naïve shifts: δ = 7.3 ppm\n"

    result = nef_upload_file("shifts.txt", content)

    assert result["success"] is True
    assert result["bytes_written"] == len(content.encode("utf-8"))
    assert (tmp_path / "shifts.txt").read_text(encoding="utf-8") == content


def test_nef_download_file(tmp_path, monkeypatch):
    """\
    Test nef_download_file reads file content from the working directory.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "result.nef").write_text("data_result\n")

    result = nef_download_file("result.nef")

    assert result["success"] is True
    assert result["name"] == "result.nef"
    assert result["content"] == "data_result\n"


def test_nef_download_file_not_found(tmp_path, monkeypatch):
    """\
    Test nef_download_file returns available files when file is missing.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "other.nef").write_text("x")

    result = nef_download_file("missing.nef")

    assert result["success"] is False
    assert "error" in result
    assert "available_files" in result
    assert "other.nef" in result["available_files"]


def test_nef_download_file_absolute_path_rejected(tmp_path, monkeypatch):
    """\
    Test nef_download_file rejects absolute paths.
    """
    monkeypatch.chdir(tmp_path)

    result = nef_download_file("/etc/passwd")

    assert result["success"] is False
    assert "error" in result


def test_nef_list_files_empty(tmp_path, monkeypatch):
    """\
    Test nef_list_files returns empty list for empty directory.
    """
    monkeypatch.chdir(tmp_path)

    result = nef_list_files()

    assert result["success"] is True
    assert result["files"] == []
    assert "cwd" in result


def test_nef_list_files_after_upload(tmp_path, monkeypatch):
    """\
    Test nef_list_files lists files written by nef_upload_file.
    """
    monkeypatch.chdir(tmp_path)
    nef_upload_file("a.nef", "x")
    nef_upload_file("b.nef", "y")

    result = nef_list_files()

    assert result["success"] is True
    assert sorted(result["files"]) == ["a.nef", "b.nef"]


def test_nef_upload_download_roundtrip(tmp_path, monkeypatch):
    """\
    Test upload followed by download returns identical content.
    """
    monkeypatch.chdir(tmp_path)
    content = "data_ubiquitin\n_nef_sequence.chain_code A\n"

    nef_upload_file("ubiquitin.nef", content)
    result = nef_download_file("ubiquitin.nef")

    assert result["success"] is True
    assert result["content"] == content
