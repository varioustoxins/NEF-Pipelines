import typer
from fyeah import f

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.talos.importers.order_parameters import order_parameters

app = typer.Typer()
app.command()(order_parameters)

EXPECTED = """
save_nefpls_order_data_A_N15_H1
   _nefpls_order_data.sf_category         nefpls_order_data
   _nefpls_order_data.sf_framecode        nefpls_order_data_A_N15_H1
   _nefpls_order_data.data_type           model_free
   _nefpls_order_data.relaxation_atom_id  2
   _nefpls_order_data.source              estimate
   _nefpls_order_data.diffusion_model     .

   loop_
      _nefpls_order_values.index
      _nefpls_order_values.chain_code_1
      _nefpls_order_values.sequence_code_1
      _nefpls_order_values.residue_name_1
      _nefpls_order_values.atom_name_1
      _nefpls_order_values.chain_code_2
      _nefpls_order_values.sequence_code_2
      _nefpls_order_values.residue_name_2
      _nefpls_order_values.atom_name_2
      _nefpls_order_values.s2
      _nefpls_order_values.s2_err

     1   A   1   MET   N   A   1   MET   H   0.884   .
     2   A   2   GLN   N   A   2   GLN   H   0.892   .
     3   A   3   ILE   N   A   3   ILE   H   0.903   .
     4   A   4   PHE   N   A   4   PHE   H   0.911   .

   stop_

save_


""".replace(
    NOQA_E501, ""
)


def test_ss_4():

    pred_4_path = path_in_test_data(__file__, "predS2_4.tab")
    pred_4_nef_path = path_in_test_data(__file__, "pred_4_seq.nef")

    STREAM = read_test_data(pred_4_nef_path)

    result = run_and_report(
        app,
        [
            pred_4_path,
        ],
        input=STREAM,
    )

    phi_psi = isolate_frame(result.stdout, "nefpls_order_data_A_N15_H1")

    PATCHED_EXPECTED = f(EXPECTED)
    assert_lines_match(PATCHED_EXPECTED, phi_psi)
