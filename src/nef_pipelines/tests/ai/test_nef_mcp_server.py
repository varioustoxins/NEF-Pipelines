"""
Tests for AI server tool functions in server_lib.py.
"""

import pytest

from nef_pipelines.lib.test_lib import read_test_data
from nef_pipelines.tools.ai.mcp_commands_lib import (
    nef_execute_command,
    nef_execute_pipeline,
    nef_get_command_help,
    nef_list_commands,
    nef_read_me_first,
    nef_read_resource,
)

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
    assert result["success"] is True
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
    assert result["success"] is True
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
    assert result["success"] is True
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
    assert result["success"] is True
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
    assert result["success"] is True
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
    assert result["success"] is True
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


def test_nef_execute_command_version():
    """\
    Test nef_execute_command with version command.
    """
    result = nef_execute_command(args=["version"])

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert len(result["stdout"]) > 0


def test_nef_execute_command_help():
    """\
    Test nef_execute_command with help returns complete help structure.
    """
    result = nef_execute_command(args=["--help"])

    # Verify response structure
    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["exit_code"] == 0

    stdout = result["stdout"]

    # Verify all expected help sections are present
    for section in EXPECTED_HELP_SECTIONS:
        assert section in stdout, f"Missing section: {section}"

    # Should be substantial
    assert len(stdout) > 200


def test_nef_execute_command_with_nef_input(simple_nef_data):
    """\
    Test nef_execute_command with NEF input returns complete frame list.
    """
    result = nef_execute_command(args=["frames", "list"], nef_input=simple_nef_data)

    # Verify response structure
    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["exit_code"] == 0

    stdout = result["stdout"]

    # Verify all expected frames are listed
    for frame in EXPECTED_FRAMES_IN_UBIQUITIN:
        assert frame in stdout, f"Missing frame: {frame}"


def test_nef_execute_command_frames_list(simple_nef_data):
    """\
    Test frames list command via nef_execute_command returns all frames.
    """
    result = nef_execute_command(args=["frames", "list"], nef_input=simple_nef_data)

    # Verify response structure
    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["exit_code"] == 0

    stdout = result["stdout"]

    # Should list frames
    for frame in EXPECTED_FRAMES_IN_UBIQUITIN:
        assert frame in stdout, f"Missing frame: {frame}"


def test_nef_execute_command_invalid():
    """\
    Test nef_execute_command with invalid command.
    """
    result = nef_execute_command(args=["nonexistent", "command"])

    assert result["success"] is False
    assert result["exit_code"] != 0


def test_nef_execute_pipeline_empty_steps():
    """\
    Test nef_execute_pipeline with no steps.
    """
    result = nef_execute_pipeline(steps=[])

    assert result["success"] is False
    assert result["exit_code"] == -1
    assert "No steps provided" in result["stderr"]
    assert result["failed_step"] is None


def test_nef_execute_pipeline_single_step(simple_nef_data):
    """\
    Test nef_execute_pipeline with single step executes successfully.
    """
    steps = [{"args": ["frames", "list"]}]

    result = nef_execute_pipeline(steps=steps, nef_input=simple_nef_data)

    # Verify complete response structure
    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["exit_code"] == 0
    assert len(result["step_results"]) == 1
    assert result["failed_step"] is None

    # Verify step result structure
    step_result = result["step_results"][0]
    assert step_result["success"] is True
    assert step_result["step"] == 1


def test_nef_execute_pipeline_multiple_steps(simple_nef_data):
    """\
    Test nef_execute_pipeline with multiple steps using NEF data.
    """
    # Commands that accept and pass through NEF data
    steps = [
        {"args": ["frames", "list"]},
    ]

    result = nef_execute_pipeline(steps=steps, nef_input=simple_nef_data)

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert len(result["step_results"]) == 1
    assert result["failed_step"] is None

    # Check step succeeded
    assert result["step_results"][0]["success"] is True


def test_nef_execute_pipeline_step_failure():
    """\
    Test nef_execute_pipeline stops on step failure and reports which step failed.
    """
    steps = [
        {"args": ["version"]},
        {"args": ["nonexistent", "command"]},  # This will fail
    ]

    result = nef_execute_pipeline(steps=steps)

    # Verify complete error response structure
    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["exit_code"] != 0
    assert result["failed_step"] == 2  # Second step (1-indexed)
    assert len(result["step_results"]) == 2  # Should have results for first 2 steps

    # Verify first step succeeded
    assert result["step_results"][0]["success"] is True

    # Verify second step failed
    assert result["step_results"][1]["success"] is False
    assert result["step_results"][1]["step"] == 2


def test_nef_execute_pipeline_verbose_mode(simple_nef_data):
    """\
    Test nef_execute_pipeline with verbose mode provides complete step diagnostics.
    """
    EXPECTED_VERBOSE_FIELDS = ["stdout", "input_length", "output_length"]

    steps = [{"args": ["frames", "list"]}]

    result = nef_execute_pipeline(steps=steps, nef_input=simple_nef_data, verbose=True)

    # Verify response structure
    assert isinstance(result, dict)
    assert result["success"] is True
    assert len(result["step_results"]) == 1

    # Verify verbose mode includes all expected diagnostic fields
    step_result = result["step_results"][0]
    for field in EXPECTED_VERBOSE_FIELDS:
        assert field in step_result, f"Missing verbose field: {field}"

    # Verify diagnostic values are reasonable
    assert step_result["input_length"] > 0
    assert step_result["output_length"] >= 0


def test_nef_execute_pipeline_with_nef_data_passthrough(simple_nef_data):
    """\
    Test that pipeline can process NEF data through save command.
    """
    # save - outputs to stdout, which becomes next step's input
    steps = [
        {"args": ["save", "-"]},
    ]

    result = nef_execute_pipeline(steps=steps, nef_input=simple_nef_data)

    # Should succeed - save outputs NEF to stdout
    assert result["success"] is True
    assert result["exit_code"] == 0
    assert len(result["stdout"]) > 0
    assert "data_" in result["stdout"]  # NEF files start with data_


def test_nef_execute_pipeline_step_with_no_args():
    """\
    Test nef_execute_pipeline with step missing args.
    """
    steps = [{}]  # No args field

    result = nef_execute_pipeline(steps=steps)

    assert result["success"] is False
    assert result["failed_step"] == 1
    assert "no args" in result["stderr"].lower()


def test_nef_execute_command_returns_dict_structure():
    """\
    Test that nef_execute_command returns complete expected dict structure.
    """
    EXPECTED_FIELDS = {"stdout", "stderr", "exit_code", "success"}

    result = nef_execute_command(args=["version"])

    # Verify complete field set
    assert isinstance(result, dict)
    assert (
        set(result.keys()) == EXPECTED_FIELDS
    ), f"Fields mismatch. Got: {set(result.keys())}"

    # Verify field types
    assert isinstance(result["stdout"], str)
    assert isinstance(result["stderr"], str)
    assert isinstance(result["exit_code"], int)
    assert isinstance(result["success"], bool)


def test_nef_execute_pipeline_returns_dict_structure():
    """\
    Test that nef_execute_pipeline returns complete expected dict structure.
    """
    EXPECTED_FIELDS = {
        "stdout",
        "stderr",
        "exit_code",
        "success",
        "step_results",
        "failed_step",
    }

    result = nef_execute_pipeline(steps=[{"args": ["version"]}])

    # Verify complete field set
    assert isinstance(result, dict)
    assert (
        set(result.keys()) == EXPECTED_FIELDS
    ), f"Fields mismatch. Got: {set(result.keys())}"

    # Verify field types
    assert isinstance(result["stdout"], str)
    assert isinstance(result["stderr"], str)
    assert isinstance(result["exit_code"], int)
    assert isinstance(result["success"], bool)
    assert isinstance(result["step_results"], list)
    assert result["failed_step"] is None or isinstance(result["failed_step"], int)


def test_nef_list_commands_returns_dict_structure():
    """\
    Test that nef_list_commands returns complete expected dict structure.
    """
    EXPECTED_FIELDS = {"commands_table", "success", "exit_code", "stderr"}

    result = nef_list_commands()

    # Verify complete field set
    assert isinstance(result, dict)
    assert (
        set(result.keys()) == EXPECTED_FIELDS
    ), f"Fields mismatch. Got: {set(result.keys())}"

    # Verify field types
    assert isinstance(result["commands_table"], str)
    assert isinstance(result["success"], bool)
    assert isinstance(result["exit_code"], int)
    assert isinstance(result["stderr"], str)


def test_nef_get_command_help_returns_dict_structure():
    """\
    Test that nef_get_command_help returns complete expected dict structure.
    """
    EXPECTED_FIELDS = {"help_text", "success", "exit_code", "stderr"}

    result = nef_get_command_help()

    # Verify complete field set
    assert isinstance(result, dict)
    assert (
        set(result.keys()) == EXPECTED_FIELDS
    ), f"Fields mismatch. Got: {set(result.keys())}"

    # Verify field types
    assert isinstance(result["help_text"], str)
    assert isinstance(result["success"], bool)
    assert isinstance(result["exit_code"], int)
    assert isinstance(result["stderr"], str)
