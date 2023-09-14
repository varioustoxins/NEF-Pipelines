import typer
from fyeah import f

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.talos.importers.restraints import restraints

app = typer.Typer()
app.command()(restraints)

EXPECTED = """
save_nef_dihedral_restraint_list_talos_restraints::chain_A                                                  # noqa: E501
   _nef_dihedral_restraint_list.sf_category     nef_dihedral_restraint_list
   _nef_dihedral_restraint_list.sf_framecode    nef_dihedral_restraint_list_talos_restraints::chain_A
   _nef_dihedral_restraint_list.potential_type  square-well-parabolic
   _nef_dihedral_restraint_list.ccpn_comment    'file: {pred_4_path}'

   loop_
      _nef_dihedral_restraint.index
      _nef_dihedral_restraint.restraint_id
      _nef_dihedral_restraint.restraint_combination_id
      _nef_dihedral_restraint.name
      _nef_dihedral_restraint.chain_code_1
      _nef_dihedral_restraint.sequence_code_1
      _nef_dihedral_restraint.residue_name_1
      _nef_dihedral_restraint.atom_name_1
      _nef_dihedral_restraint.chain_code_2
      _nef_dihedral_restraint.sequence_code_2
      _nef_dihedral_restraint.residue_name_2
      _nef_dihedral_restraint.atom_name_2
      _nef_dihedral_restraint.chain_code_3
      _nef_dihedral_restraint.sequence_code_3
      _nef_dihedral_restraint.residue_name_3
      _nef_dihedral_restraint.atom_name_3
      _nef_dihedral_restraint.chain_code_4
      _nef_dihedral_restraint.sequence_code_4
      _nef_dihedral_restraint.residue_name_4
      _nef_dihedral_restraint.atom_name_4
      _nef_dihedral_restraint.target_value
      _nef_dihedral_restraint.target_value_error
      _nef_dihedral_restraint.ccpn_comment
      _nef_dihedral_restraint.np_merit

     1   1   .   PHI   A   3   ILE   C   A   2   GLN   N    A   2   GLN   CA   A   2   GLN   CA   -101.524   15.07    'class: Dyn'        0.0
     2   2   .   PSI   A   2   GLN   N   A   2   GLN   CA   A   2   GLN   C    A   3   ILE   C    139.087    15.435   'class: Dyn'        0.0
     3   3   .   PHI   A   4   PHE   C   A   3   ILE   N    A   3   ILE   CA   A   3   ILE   CA   -145.993   11.455   'class: Strong'     1.0
     4   4   .   PSI   A   3   ILE   N   A   3   ILE   CA   A   3   ILE   C    A   4   PHE   C    159.239    9.155    'class: Strong'     1.0
     5   5   .   PHI   A   5   VAL   C   A   4   PHE   N    A   4   PHE   CA   A   4   PHE   CA   -118.216   7.883    'class: Generous'   0.6
     6   6   .   PSI   A   4   PHE   N   A   4   PHE   CA   A   4   PHE   C    A   5   VAL   C    137.017    9.702    'class: Generous'   0.6

   stop_

save_
""".replace(
    NOQA_E501, ""
)


def test_pred4tab(clear_cache):

    pred_4_path = path_in_test_data(__file__, "pred_4.tab")
    pred_4_nef_path = path_in_test_data(__file__, "pred_4.nef")

    STREAM = open(pred_4_nef_path).read()

    result = run_and_report(
        app,
        [
            pred_4_path,
        ],
        input=STREAM,
    )

    phi_psi = isolate_frame(
        result.stdout, "nef_dihedral_restraint_list_talos_restraints::chain_A"
    )

    PATCHED_EXPECTED = f(EXPECTED)
    assert_lines_match(PATCHED_EXPECTED, phi_psi)


# TODO check filtering & bad inputs