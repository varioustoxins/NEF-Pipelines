import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.fit.t1noe import t1noe

runner = CliRunner()
app = typer.Typer()
app.command()(t1noe)


EXPECTED_R1_DATA_SINGLE_R1 = """
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

     1   1   .   1.300000   .   B   145   THR   H   B   145   THR   N

   stop_
"""

EXPECTED_R1_DATA_SINGLE_NOE = """
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

     1   1   .   1.000000   .   B   145   THR   H   B   145   THR   N

   stop_
"""


EXPECTED_R1_DATA_SINGLE_R1_MC = """
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

     1   1   .   1.300000   0.108797   B   145   THR   H   B   145   THR   N

   stop_
"""

EXPECTED_R1_DATA_SINGLE_NOE_MC = """
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

     1   1   .   1.000000   0.0170893   B   145   THR   H   B   145   THR   N

   stop_
"""


def test_t1noe_with_r1noe_data_single():
    """Test t1noe fitting with r1noe_data_single.nef test data."""

    test_data = open(path_in_test_data(__file__, "test_1_r1noe.nef")).read()

    # Test that function exits with error when no noise level provided
    result = run_and_report(app, ["T1_NOE_pos", "T1_NOE_neg"], input=test_data)

    r1_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_r1", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_SINGLE_R1, r1_loop)

    noe_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_noe", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_SINGLE_NOE, noe_loop)


def test_t1noe_with_r1noe_data_single_mc10_n0_1():
    """Test t1noe fitting with r1noe_data_single.nef test data."""

    test_data = open(path_in_test_data(__file__, "test_1_r1noe.nef")).read()

    # Test that function exits with error when no noise level provided
    result = run_and_report(
        app,
        ["T1_NOE_pos", "T1_NOE_neg", "--noise-level", "0.1", "--cycles", "10"],
        input=test_data,
    )

    r1_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_r1", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_SINGLE_R1_MC, r1_loop)

    noe_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_noe", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_R1_DATA_SINGLE_NOE_MC, noe_loop)
