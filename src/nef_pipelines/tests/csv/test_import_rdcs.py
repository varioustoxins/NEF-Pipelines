import typer
from pytest import fixture

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.csv.importers._rdcs_cli import rdcs

app = typer.Typer()
app.command()(rdcs)


@fixture
def INPUT_3A_AB_NEF():
    return read_test_data("3a_ab.neff", __file__)


# noinspection PyUnusedLocal
def test_short_csv(INPUT_3A_AB_NEF):
    csv_path = path_in_test_data(__file__, "short.csv")

    args = [csv_path, "--chain-code", "AAAA"]
    result = run_and_report(app, args, input=INPUT_3A_AB_NEF)

    EXPECTED = """\
        save_nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.sf_category           nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode          nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.restraint_origin      .
           _nef_rdc_restraint_list.tensor_magnitude      .
           _nef_rdc_restraint_list.tensor_rhombicity     .
           _nef_rdc_restraint_list.tensor_chain_code     .
           _nef_rdc_restraint_list.tensor_sequence_code  .
           _nef_rdc_restraint_list.tensor_residue_name   .

           loop_
              _nef_rdc_restraint.index
              _nef_rdc_restraint.restraint_id
              _nef_rdc_restraint.restraint_combination_id
              _nef_rdc_restraint.chain_code_1
              _nef_rdc_restraint.sequence_code_1
              _nef_rdc_restraint.residue_name_1
              _nef_rdc_restraint.atom_name_1
              _nef_rdc_restraint.chain_code_2
              _nef_rdc_restraint.sequence_code_2
              _nef_rdc_restraint.residue_name_2
              _nef_rdc_restraint.atom_name_2
              _nef_rdc_restraint.weight
              _nef_rdc_restraint.target_value
              _nef_rdc_restraint.target_value_uncertainty
              _nef_rdc_restraint.lower_linear_limit
              _nef_rdc_restraint.lower_limit
              _nef_rdc_restraint.upper_limit
              _nef_rdc_restraint.upper_linear_limit
              _nef_rdc_restraint.scale
              _nef_rdc_restraint.distance_dependent

             0   0   .   AAAA   1   ALA   H   AAAA   1   ALA   N   1.0   1.3   .   .   .   .   .   1.0   .
             1   1   .   AAAA   2   ALA   H   AAAA   2   ALA   N   1.0   4.6   .   .   .   .   .   1.0   .
             2   2   .   AAAA   3   ALA   H   AAAA   3   ALA   N   1.0   2.4   .   .   .   .   .   1.0   .

           stop_

        save_

    """

    print(result.stdout)
    result = isolate_frame(result.stdout, "nef_rdc_restraint_list_rdcs")

    assert_lines_match(EXPECTED, result)


def test_short_complete_csv(INPUT_3A_AB_NEF):
    csv_path = path_in_test_data(__file__, "short_complete.csv")

    args = [csv_path]
    result = run_and_report(app, args, input=INPUT_3A_AB_NEF)

    EXPECTED = """\
        save_nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.sf_category           nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode          nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.restraint_origin      .
           _nef_rdc_restraint_list.tensor_magnitude      .
           _nef_rdc_restraint_list.tensor_rhombicity     .
           _nef_rdc_restraint_list.tensor_chain_code     .
           _nef_rdc_restraint_list.tensor_sequence_code  .
           _nef_rdc_restraint_list.tensor_residue_name   .

           loop_
              _nef_rdc_restraint.index
              _nef_rdc_restraint.restraint_id
              _nef_rdc_restraint.restraint_combination_id
              _nef_rdc_restraint.chain_code_1
              _nef_rdc_restraint.sequence_code_1
              _nef_rdc_restraint.residue_name_1
              _nef_rdc_restraint.atom_name_1
              _nef_rdc_restraint.chain_code_2
              _nef_rdc_restraint.sequence_code_2
              _nef_rdc_restraint.residue_name_2
              _nef_rdc_restraint.atom_name_2
              _nef_rdc_restraint.weight
              _nef_rdc_restraint.target_value
              _nef_rdc_restraint.target_value_uncertainty
              _nef_rdc_restraint.lower_linear_limit
              _nef_rdc_restraint.lower_limit
              _nef_rdc_restraint.upper_limit
              _nef_rdc_restraint.upper_linear_limit
              _nef_rdc_restraint.scale
              _nef_rdc_restraint.distance_dependent

             0   0   .   AAAA   1   ALA   HA     AAAA   1   ALA   HN   1.0   1.3   1.0   .   .   .   .   1.0   .
             1   1   .   AAAA   1   ALA   HB     AAAA   1   ALA   HN   1.0   4.6   2.0   .   .   .   .   1.0   .
             2   2   .   AAAA   2   ALA   HG3#   AAAA   2   ALA   HN   1.0   2.4   3.0   .   .   .   .   1.0   .
             3   3   .   AAAA   3   ALA   HA     AAAA   3   ALA   HN   1.0   6.7   4.0   .   .   .   .   1.0   .

           stop_

        save_

    """

    result = isolate_frame(result.stdout, "nef_rdc_restraint_list_rdcs")

    assert_lines_match(EXPECTED, result)
