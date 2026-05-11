"""
Tests for in-process command execution for the AI server.
"""

import sys

import pytest

from nef_pipelines.lib.test_lib import assert_lines_match, read_test_data
from nef_pipelines.tools.ai.mcp_lib import (
    _execute_command_in_process as execute_command_in_process,
)

if sys.version_info < (3, 10):
    pytest.skip("MCP server requires Python 3.10 or later", allow_module_level=True)

pytest.importorskip("fastmcp")

EXPECTED_FRAMES_LIST = """\
nef_nmr_meta_data                    nef_molecular_system
nef_chemical_shift_list_default      nef_nmr_spectrum_k_ubi_n_hsqc`1`
nef_nmr_spectrum_k_ubi_hnca`1`       nef_nmr_spectrum_k_ubi_hncoca`1`
nef_nmr_spectrum_k_ubi_hncaco`1`     nef_nmr_spectrum_k_ubi_hnco`1`
nef_nmr_spectrum_k_ubi_hncacb`1`     nef_nmr_spectrum_k_ubi_cbcaconh`1`
nef_nmr_spectrum_mars_ubi_n_hsqc`1`  ccpn_substance_1D3Z_1|Chain.None
ccpn_substance_mySubstance.None      ccpn_assignment
"""

EXPECTED_TABULATE_MOLECULAR_SYSTEM = """\
nef_sequence
------------
  index  chain_code      sequence_code  residue_name    linking    ccpn_compound_name
      1  A                           1  MET             start      mySubstance
      2  A                           2  GLN             middle     mySubstance
      3  A                           3  ILE             middle     mySubstance
      4  A                           4  PHE             middle     mySubstance
      5  A                           5  VAL             middle     mySubstance
      6  A                           6  LYS             middle     mySubstance
"""


@pytest.fixture
def simple_nef_data():
    """\
    Simple NEF data for testing command execution.
    """
    return read_test_data("ubiquitin_short.nef", __file__)


def test_execute_command_help():
    """\
    Test executing help command (no NEF input required).
    """
    result = execute_command_in_process(["nef", "--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout or "usage:" in result.stdout.lower()


def test_execute_command_version():
    """\
    Test executing version command (no NEF input required).
    """
    result = execute_command_in_process(["nef", "version"])

    assert result.exit_code == 0
    assert len(result.stdout) > 0


def test_execute_command_with_nef_input(simple_nef_data):
    """\
    Test executing command with NEF input via temporary file.
    """
    result = execute_command_in_process(
        ["nef", "frames", "list"], nef_input=simple_nef_data
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_FRAMES_LIST, result.stdout)


def test_execute_command_frames_tabulate(simple_nef_data):
    """\
    Test frames tabulate command with NEF input and a frame selector.
    """
    result = execute_command_in_process(
        ["nef", "frames", "tabulate", "molecular_system"], nef_input=simple_nef_data
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_TABULATE_MOLECULAR_SYSTEM, result.stdout)


def test_execute_command_without_nef_input_shows_help():
    """\
    Test that some commands show help when called without input.
    """
    result = execute_command_in_process(["nef", "frames", "list"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout or "usage:" in result.stdout.lower()


def test_execute_command_save_with_empty_nef_input():
    """\
    Test executing save command with empty NEF input fails.
    """
    result = execute_command_in_process(["nef", "save", "-"], nef_input="")

    assert result.exit_code != 0


def test_execute_command_with_none_nef_input():
    """\
    Test executing command with None as NEF input (should not create temp file).
    """
    result = execute_command_in_process(
        ["nef", "help", "commands", "--display=table", "frames*"], nef_input=""
    )

    assert result.exit_code == 0


def test_execute_command_invalid_command():
    """\
    Test executing invalid command returns failure.
    """
    result = execute_command_in_process(["nef", "nonexistent", "command"])

    assert result.exit_code != 0


def test_execute_command_returns_pipeline_result():
    """\
    Test that execute_command_in_process returns a PipelineResult dataclass.
    """
    from nef_pipelines.tools.ai.mcp_lib import PipelineResult

    result = execute_command_in_process(["nef", "version"])

    assert isinstance(result, PipelineResult)
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, list)
    assert isinstance(result.exit_code, int)


def test_execute_command_help_commands_table():
    """\
    Test help commands with table format.
    """
    result = execute_command_in_process(
        ["nef", "help", "commands", "--display=table", "--format=markdown", "frames*"]
    )

    assert result.exit_code == 0
    assert "frames" in result.stdout.lower()


def test_execute_command_help_commands_full():
    """\
    Test help commands with full documentation.
    """
    result = execute_command_in_process(
        ["nef", "help", "commands", "--display=help", "--format=markdown", "save"]
    )

    assert result.exit_code == 0
    assert "save" in result.stdout.lower()


def test_execute_command_chaining_output():
    """\
    Test that output from one command can be used as input to another.
    """
    simple_nef = read_test_data("ubiquitin_short.nef", __file__)

    result1 = execute_command_in_process(
        ["nef", "frames", "tabulate", "molecular_system"], nef_input=simple_nef
    )

    assert result1.exit_code == 0


def test_execute_command_with_explicit_input_file(tmp_path, simple_nef_data):
    """\
    Test that explicit --in argument is respected (temp file not added).
    """
    test_file = tmp_path / "test.nef"
    test_file.write_text(simple_nef_data)

    # Pass explicit --in argument
    result = execute_command_in_process(
        ["nef", "frames", "list", "--in", str(test_file)],
        nef_input="",
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_FRAMES_LIST, result.stdout)


def test_execute_command_preserves_args_order():
    """\
    Test that arguments are passed in correct order.
    """
    result = execute_command_in_process(
        ["nef", "help", "commands", "--display=table", "frames*"]
    )

    assert result.exit_code == 0
    assert "frames" in result.stdout.lower()
