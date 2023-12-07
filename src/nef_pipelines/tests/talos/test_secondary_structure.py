import typer
from fyeah import f

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.talos.importers.secondary_structure import (
    secondary_structure,
)

app = typer.Typer()
app.command()(secondary_structure)

EXPECTED = """
save_nefpls_secondary_structure_A_talos                                                                     # noqa: E501
   _nefpls_secondary_structure.sf_category   nefpls_secondary_structure
   _nefpls_secondary_structure.sf_framecode  nefpls_secondary_structure_A_talos
   _nefpls_secondary_structure.method        talos
   _nefpls_secondary_structure.version       .

   loop_
      _nefpls_secondary_structure.index
      _nefpls_secondary_structure.chain_code
      _nefpls_secondary_structure.sequence_code
      _nefpls_secondary_structure.residue_name
      _nefpls_secondary_structure.secondary_structure
      _nefpls_secondary_structure.merit
      _nefpls_secondary_structure.comment

     1   A   1   MET   coil         0.0     .
     2   A   2   GLN   beta_sheet   0.5     .
     3   A   3   ILE   beta_sheet   0.94    .
     4   A   4   PHE   beta_sheet   0.94    .

   stop_

save_
""".replace(
    NOQA_E501, ""
)


def test_ss_4(clear_cache):

    pred_4_path = path_in_test_data(__file__, "predSS_4.tab")
    pred_4_nef_path = path_in_test_data(__file__, "pred_4_seq.nef")

    STREAM = open(pred_4_nef_path).read()

    result = run_and_report(
        app,
        [
            pred_4_path,
        ],
        input=STREAM,
    )

    phi_psi = isolate_frame(result.stdout, "nefpls_secondary_structure_A_talos")

    PATCHED_EXPECTED = f(EXPECTED)
    assert_lines_match(PATCHED_EXPECTED, phi_psi)


EXPECTED_FIRST_RESID_2 = """
save_nefpls_secondary_structure_A_talos                                                                     # noqa: E501
   _nefpls_secondary_structure.sf_category   nefpls_secondary_structure
   _nefpls_secondary_structure.sf_framecode  nefpls_secondary_structure_A_talos
   _nefpls_secondary_structure.method        talos
   _nefpls_secondary_structure.version       .

   loop_
      _nefpls_secondary_structure.index
      _nefpls_secondary_structure.chain_code
      _nefpls_secondary_structure.sequence_code
      _nefpls_secondary_structure.residue_name
      _nefpls_secondary_structure.secondary_structure
      _nefpls_secondary_structure.merit
      _nefpls_secondary_structure.comment

     1   A   2   MET   coil         0.0     .
     2   A   3   GLN   beta_sheet   0.5     .
     3   A   4   ILE   beta_sheet   0.94    .
     4   A   5   PHE   beta_sheet   0.94    .

   stop_

save_
""".replace(
    NOQA_E501, ""
)


def test_ss_4_first_resid_2(clear_cache):

    pred_4_path = path_in_test_data(__file__, "predSS_4_first_resid_2.tab")
    pred_4_nef_path = path_in_test_data(__file__, "pred_4_seq_first_resid_2.nef")

    STREAM = open(pred_4_nef_path).read()

    result = run_and_report(
        app,
        [
            pred_4_path,
        ],
        input=STREAM,
    )

    phi_psi = isolate_frame(result.stdout, "nefpls_secondary_structure_A_talos")

    PATCHED_EXPECTED = f(EXPECTED_FIRST_RESID_2)
    assert_lines_match(PATCHED_EXPECTED, phi_psi)
