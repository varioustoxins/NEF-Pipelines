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


EXPECTED_R1_DATA_SINGLE_R2 = """
   loop_
      _nefpls_relaxation.index
      _nefpls_relaxation.data_id
      _nefpls_relaxation.data_combination_id
      _nefpls_relaxation.value
      _nefpls_relaxation.value_error
      _nefpls_relaxation.chain_code_1
      _nefpls_relaxation.sequence_code_1
      _nefpls_relaxation.residue_name_1
      _nefpls_relaxation.atom_name_1
      _nefpls_relaxation.chain_code_2
      _nefpls_relaxation.sequence_code_2
      _nefpls_relaxation.residue_name_2
      _nefpls_relaxation.atom_name_2

     1   1   .   1.300000   .   A   18   LYS   H   A   18   LYS   N

   stop_
"""

EXPECTED_R1_DATA_SINGLE_R2_MC_NO_1 = """
   loop_
      _nefpls_relaxation.index
      _nefpls_relaxation.data_id
      _nefpls_relaxation.data_combination_id
      _nefpls_relaxation.value
      _nefpls_relaxation.value_error
      _nefpls_relaxation.chain_code_1
      _nefpls_relaxation.sequence_code_1
      _nefpls_relaxation.residue_name_1
      _nefpls_relaxation.atom_name_1
      _nefpls_relaxation.chain_code_2
      _nefpls_relaxation.sequence_code_2
      _nefpls_relaxation.residue_name_2
      _nefpls_relaxation.atom_name_2

     1   1   .   1.300000   0.137731   A   18   LYS   H   A   18   LYS   N

   stop_
"""


def test_exponential_r1_data_single():
    """Test exponential fitting with test_1_exponential.nef test data."""

    test_data = open(path_in_test_data(__file__, "test_1_exponential.nef")).read()

    # Test that function exits with error when no noise level provided
    result = run_and_report(app, ["T2", "--cycles", "1"], input=test_data)

    r1_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_r1", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_SINGLE_R2, r1_loop)


def test_exponential_with_no_cycles():
    """Test exponential fitting with no noise level provided, it should still run
    but with no error analysis!"""

    test_data = open(path_in_test_data(__file__, "test_1_exponential.nef")).read()

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

    test_data = open(path_in_test_data(__file__, "test_1_exponential.nef")).read()

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

    test_data = open(path_in_test_data(__file__, "test_1_exponential.nef")).read()

    # Test that function exits with error when no noise level provided
    result = run_and_report(
        app, ["T2", "--noise-level", "0.1", "--cycles", "10"], input=test_data
    )

    r1_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_r1", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_SINGLE_R2_MC_NO_1, r1_loop)


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
