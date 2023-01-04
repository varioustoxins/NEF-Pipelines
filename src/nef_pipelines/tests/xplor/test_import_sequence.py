import typer
from typer.testing import CliRunner

from nef_pipelines.lib.nef_lib import NEF_MOLECULAR_SYSTEM
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.xplor.importers.sequence import sequence

runner = CliRunner()
app = typer.Typer()
app.command()(sequence)

EXPECTED_3A_AB = """\
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

     1   AAAA  1   ALA   start    .   .
     2   AAAA  2   ALA   middle   .   .
     3   AAAA  3   ALA   end      .   .
     4   BBBB  11  ALA   start    .   .
     5   BBBB  12  ALA   middle   .   .
     6   BBBB  13  ALA   end      .   .

   stop_

save_"""


# noinspection PyUnusedLocal
def test_3ab(clear_cache):

    path = path_in_test_data(__file__, "3a_ab.psf")
    result = run_and_report(app, [path])

    result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_AB, result)


def test_no_sequence_files(clear_cache):

    result = run_and_report(app, [], expected_exit_code=1)

    assert "no psf files provided to read sequences from" in result.stdout
