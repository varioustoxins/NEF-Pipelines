import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.xeasy.importers.sequence import sequence

app = typer.Typer()
app.command()(sequence)

EXPECTED = """\
     loop_
      _nef_sequence.index
      _nef_sequence.chain_code
      _nef_sequence.sequence_code
      _nef_sequence.residue_name
      _nef_sequence.linking
      _nef_sequence.residue_variant
      _nef_sequence.cis_peptide

     1   A   1   HIS   start    .   .
     2   A   2   MET   middle   .   .
     3   A   3   ARG   middle   .   .
     4   A   4   GLN   middle   .   .
     5   A   5   THR   middle   .   .
     6   A   6   MET   middle   .   .
     7   A   7   LEU   middle   .   .
     8   A   8   VAL   middle   .   .
     9   A   9   THR   end      .   .

   stop_

"""


def test_basic():

    sequence_path = path_in_test_data(__file__, "basic.seq")

    result = run_and_report(app, [sequence_path])

    assert_lines_match(
        EXPECTED,
        isolate_loop(result.stdout, "nef_molecular_system", "nef_sequence"),
    )
