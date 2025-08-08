import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.fit.mean import mean

runner = CliRunner()
app = typer.Typer()
app.command()(mean)


EXPECTED_DATA_MEAN = """
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

     1   1   .   1.000000  0.244949   A   18   LYS   H   A   18   LYS   N

   stop_
"""


def test_mean_data_single():
    """Test exponential fitting with test_1_exponential.nef test data."""

    test_data = open(path_in_test_data(__file__, "test_1_mean.nef")).read()

    # Test that function exits with error when no noise level provided
    result = run_and_report(app, ["MEAN"], input=test_data)

    mean_loop = isolate_loop(
        result.stdout, "nefpls_relaxation_list_mean", "nefpls_relaxation"
    )
    assert_lines_match(EXPECTED_DATA_MEAN, mean_loop)
