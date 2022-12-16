import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.delete import delete

runner = CliRunner()
app = typer.Typer()
app.command()(delete)

EXPECTED_DELETE_CATEGORY = """\
        data_pales_test

        save_nef_rdc_restraint_list_test_1
           _nef_rdc_restraint_list.sf_category     nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode    nef_rdc_restraint_list_test_1
           _nef_rdc_restraint_list.potential_type  log-normal

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

             1   1   .   A   2   TRP   H   A   21   TRP   N   2   -5.2   0.33
             2   2   .   A   3   GLY   H   A   22   GLY   N   3   3.1    0.4

           stop_

        save_
    """


# noinspection PyUnusedLocal
def test_delete_type(clear_cache):

    path = path_in_test_data(__file__, "pales_test_1.nef")

    input_stream = open(path).read()

    result = run_and_report(app, ["-c", "mol"], input=input_stream)

    assert_lines_match(EXPECTED_DELETE_CATEGORY, result.stdout)


EXPECTED_DELETE_NAME = """\
    data_pales_test

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide

         1   A   1   ALA   start    .   .
         2   A   2   TRP   middle   .   .
         3   A   3   GLY   middle   .   .

       stop_

    save_

"""


# noinspection PyUnusedLocal
def test_delete_name(clear_cache):

    path = path_in_test_data(__file__, "pales_test_1.nef")

    input_stream = open(path).read()

    result = run_and_report(app, ["test_1"], input=input_stream)

    assert_lines_match(EXPECTED_DELETE_NAME, result.stdout)
