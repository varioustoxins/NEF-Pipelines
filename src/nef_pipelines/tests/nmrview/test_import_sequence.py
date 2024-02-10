import typer
from freezegun import freeze_time

from nef_pipelines.lib.nef_lib import NEF_METADATA, NEF_MOLECULAR_SYSTEM
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.lib.util import get_version
from nef_pipelines.transcoders.nmrview.importers.sequence import sequence

app = typer.Typer()
app.command()(sequence)


EXPECTED_3AA = """\
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
     2   A   2   ALA   middle   .   .
     3   A   3   ALA   end      .   .

   stop_

save_"""

EXPECTED_3AA10 = """\
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

     1   A   10   ALA   start    .   .
     2   A   11   ALA   middle   .   .
     3   A   12   ALA   end      .   .

   stop_

save_"""


# noinspection PyUnusedLocal
def test_3aa():

    path = path_in_test_data(__file__, "3aa.seq")
    result = run_and_report(app, [path], input=HEADER)

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3AA, mol_sys_result)


# noinspection PyUnusedLocal
def test_3aa10():

    path = path_in_test_data(__file__, "3aa10.seq")
    result = run_and_report(app, [path], input=HEADER)

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3AA10, mol_sys_result)


HEADER = open(path_in_test_data(__file__, "test_header_entry.txt")).read()

EXPECTED_HEADER = f"""\
save_nef_nmr_meta_data
   _nef_nmr_meta_data.sf_category      nef_nmr_meta_data
   _nef_nmr_meta_data.sf_framecode     nef_nmr_meta_data
   _nef_nmr_meta_data.format_name      nmr_exchange_format
   _nef_nmr_meta_data.format_version   1.1
   _nef_nmr_meta_data.program_name     NEFPipelines
   _nef_nmr_meta_data.script_name      sequence.py
   _nef_nmr_meta_data.program_version  {get_version()}
   _nef_nmr_meta_data.creation_date    2012-01-14T12:00:01.123456
   _nef_nmr_meta_data.uuid             NEFPipelines-2012-01-14T12:00:01.123456-1043321819

   loop_
      _nef_run_history.run_number
      _nef_run_history.program_name
      _nef_run_history.program_version
      _nef_run_history.script_name

     1   NEFPipelines   0.0.1   header.py

   stop_

save_
"""


# noinspection PyUnusedLocal
@freeze_time("2012-01-14 12:00:01.123456")
def test_pipe_header(fixed_seed):

    path = path_in_test_data(__file__, "3aa10.seq")
    path_header = path_in_test_data(__file__, "test_header_entry.txt")
    result = run_and_report(app, ["--in", path_header, path])

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)
    meta_data_result = isolate_frame(result.stdout, "%s" % NEF_METADATA)

    assert_lines_match(EXPECTED_3AA10, mol_sys_result)
    assert_lines_match(EXPECTED_HEADER, meta_data_result)


# noinspection PyUnusedLocal
@freeze_time("2012-01-14 12:00:01.123456")
def test_header(fixed_seed):

    path = path_in_test_data(__file__, "3aa10.seq")
    result = run_and_report(app, [path], input=HEADER)

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3AA10, mol_sys_result)
