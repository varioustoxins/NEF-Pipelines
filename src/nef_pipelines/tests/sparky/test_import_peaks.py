import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.sparky.importers.peaks import peaks

app = typer.Typer()
app.command()(peaks)


EXPECTED = """
loop_
  _nef_peak.index
  _nef_peak.peak_id
  _nef_peak.chain_code_1
  _nef_peak.sequence_code_1
  _nef_peak.residue_name_1
  _nef_peak.atom_name_1
  _nef_peak.chain_code_2
  _nef_peak.sequence_code_2
  _nef_peak.residue_name_2
  _nef_peak.atom_name_2
  _nef_peak.position_1
  _nef_peak.position_uncertainty_1
  _nef_peak.position_2
  _nef_peak.position_uncertainty_2
  _nef_peak.height
  _nef_peak.height_uncertainty
  _nef_peak.volume
  _nef_peak.volume_uncertainty


     0   0   A   16   DG    H3'   A   16   DG    H8    4.905   .   8.01    .   .   .   .   .
     1   1   A   16   DG    H4'   A   16   DG    H8    4.439   .   8.013   .   .   .   .   .
     2   2   A   17   DT    H6    A   16   DG    H8    7.205   .   8.004   .   .   .   .   .
     3   3   A   17   DT    H7    A   16   DG    H8    1.459   .   8.008   .   .   .   .   .
     4   4   A   17   DT    H2"   A   17   DT    H1'   2.509   .   5.84    .   .   .   .   .

stop_
"""


def test_basic():

    path = path_in_test_data(__file__, "sparky_manual_basic.peaks")

    data_sequence = open(
        path_in_test_data(__file__, "sparky_manual_basic_sequence.nef")
    ).read()

    result = run_and_report(app, ["--molecule-type", "dna", path], input=data_sequence)

    loop = isolate_loop(result.stdout, "sparky_sparky_manual_basic", "nef_peak")

    assert_lines_match(EXPECTED, str(loop))


def test_basic_no_sequence():

    path = path_in_test_data(__file__, "sparky_manual_basic.peaks")

    result = run_and_report(app, ["--molecule-type", "dna", path])

    loop = isolate_loop(result.stdout, "sparky_sparky_manual_basic", "nef_peak")

    assert_lines_match(EXPECTED, str(loop))
