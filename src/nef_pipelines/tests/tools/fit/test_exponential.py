from pathlib import Path

import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.fit.exponential import exponential

runner = CliRunner()
app = typer.Typer()
app.command()(exponential)


EXPECTED_CYCLES_1_WARNING = "WARNING: cycles=1 is the same as cycles=0 (no Monte Carlo error analysis); use cycles=0 to disable MC or cycles >= 2 to enable it\n"

EXPECTED_R1_DATA_SINGLE_R2 = """
   loop_
      _nefpls_relaxation.index
      _nefpls_relaxation.data_id
      _nefpls_relaxation.data_combination_id
      _nefpls_relaxation.value
      _nefpls_relaxation.value_error
      _nefpls_relaxation.fit_status
      _nefpls_relaxation.chain_code_1
      _nefpls_relaxation.sequence_code_1
      _nefpls_relaxation.residue_name_1
      _nefpls_relaxation.atom_name_1
      _nefpls_relaxation.chain_code_2
      _nefpls_relaxation.sequence_code_2
      _nefpls_relaxation.residue_name_2
      _nefpls_relaxation.atom_name_2

     1   1   .   1.300000   .   success   A   18   LYS   H   A   18   LYS   N

   stop_
"""

EXPECTED_R1_DATA_CYCLES_0 = """
   loop_
      _nefpls_relaxation.index
      _nefpls_relaxation.data_id
      _nefpls_relaxation.data_combination_id
      _nefpls_relaxation.value
      _nefpls_relaxation.value_error
      _nefpls_relaxation.fit_status
      _nefpls_relaxation.chain_code_1
      _nefpls_relaxation.sequence_code_1
      _nefpls_relaxation.residue_name_1
      _nefpls_relaxation.atom_name_1
      _nefpls_relaxation.chain_code_2
      _nefpls_relaxation.sequence_code_2
      _nefpls_relaxation.residue_name_2
      _nefpls_relaxation.atom_name_2

     1   1   .   1.300000   .   success   A   18   LYS   H   A   18   LYS   N

   stop_
"""

# value_error (MC stddev of rate over 10 cycles with seed=42, noise=0.1):
# With bounds rate >= 0.0: 0.137726 (current)
# Without bounds: 0.137731 (lmfit reparametrization effect, ~3.6e-5 difference)
EXPECTED_R1_DATA_SINGLE_R2_MC_NO_1 = """
   loop_
      _nefpls_relaxation.index
      _nefpls_relaxation.data_id
      _nefpls_relaxation.data_combination_id
      _nefpls_relaxation.value
      _nefpls_relaxation.value_error
      _nefpls_relaxation.fit_status
      _nefpls_relaxation.mc_failed_cycles
      _nefpls_relaxation.chain_code_1
      _nefpls_relaxation.sequence_code_1
      _nefpls_relaxation.residue_name_1
      _nefpls_relaxation.atom_name_1
      _nefpls_relaxation.chain_code_2
      _nefpls_relaxation.sequence_code_2
      _nefpls_relaxation.residue_name_2
      _nefpls_relaxation.atom_name_2

     1   1   .   1.300000   0.137726   success   0   A   18   LYS   H   A   18   LYS   N

   stop_
"""


def test_exponential_r1_data_single():
    """Test exponential fitting with test_1_exponential.nef test data."""

    test_data = Path(path_in_test_data(__file__, "test_1_exponential.nef")).read_text()

    # Test that function exits with error when no noise level provided
    result = run_and_report(
        app, ["T2", "--cycles", "1"], input=test_data, merge_stderr=False
    )

    # Should warn about cycles=1
    assert result.stderr == EXPECTED_CYCLES_1_WARNING

    r1_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_T2", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_SINGLE_R2, r1_loop)


def test_exponential_with_no_cycles():
    """Test exponential fitting with no noise level provided, it should still run
    but with no error analysis!"""

    test_data = Path(path_in_test_data(__file__, "test_1_exponential.nef")).read_text()

    # Test that function exits with error when no noise level provided
    run_and_report(
        app,
        [
            "T2",
        ],
        input=test_data,
    )


def test_t1noe_with_no_cycles():
    """Test exponential fitting with no noise level provided, it should still run
    but with no error analysis!"""

    test_data = Path(path_in_test_data(__file__, "test_1_exponential.nef")).read_text()

    # Test that function exits with error when no noise level provided
    run_and_report(
        app,
        [
            "T2",
        ],
        input=test_data,
    )


def test_t1noe_with_r1noe_data_single_mc10_n0_1():
    """Test t1noe fitting with r1noe_data_single.nef test data."""

    test_data = Path(path_in_test_data(__file__, "test_1_exponential.nef")).read_text()

    # Test that function exits with error when no noise level provided
    result = run_and_report(
        app, ["T2", "--noise-level", "0.1", "--cycles", "10"], input=test_data
    )

    r1_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_T2", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_SINGLE_R2_MC_NO_1, r1_loop)


def test_exponential_cycles_0():
    """--cycles 0 skips Monte Carlo; fit value should be present, value_error absent."""

    test_data = Path(path_in_test_data(__file__, "test_1_exponential.nef")).read_text()

    result = run_and_report(app, ["T2", "--cycles", "0"], input=test_data)

    r1_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_T2", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_CYCLES_0, r1_loop)


def test_exponential_cycles_0_with_noise_level():
    """--cycles 0 with explicit --noise-level: still no MC, value_error absent."""

    test_data = Path(path_in_test_data(__file__, "test_1_exponential.nef")).read_text()

    result = run_and_report(
        app, ["T2", "--cycles", "0", "--noise-level", "0.1"], input=test_data
    )

    r1_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_T2", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_CYCLES_0, r1_loop)


#
# def test_t1noe_bad_input():
#     """Test exponential fitting with no noise level provided, it should still run
#     but with no error analysis!"""
#
#     test_data = open(path_in_test_data(__file__, "r1noe_data_single.nef")).read()
#
#     # Test that function exits with error when no noise level provided
#     run_and_report(
#         app,
#         ["T1_NOE_pos", "T1_NOE_neg"],
#         input=test_data,
#     )
