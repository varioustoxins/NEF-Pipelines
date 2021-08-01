from textwrap import dedent

from freezegun import freeze_time

import pytest
from icecream import ic

from typer.testing import CliRunner

from lib.sequence_lib import translate_1_to_3, BadResidue
from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

MOLECULAR_SYSTEM_NMRVIEW = 'nef_molecular_system_nmrview'
METADATA_NMRVIEW ='nef_nmr_meta_data'
NMRVIEW_IMPORT_SEQUENCE = ['nmrview', 'import', 'sequence']

runner = CliRunner()


@pytest.fixture
def using_nmrview():
    # register the module under test
    import transcoders.nmrview


EXPECTED_3AA = '''\
save_nef_molecular_system_nmrview
   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system_nmrview

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

save_'''

EXPECTED_3AA10 = '''\
save_nef_molecular_system_nmrview
   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system_nmrview

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

save_'''


# noinspection PyUnusedLocal
def test_3aa(typer_app, using_nmrview, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, '3aa.seq')
    result = runner.invoke(typer_app, [*NMRVIEW_IMPORT_SEQUENCE, path], input=HEADER)

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, '%s' % MOLECULAR_SYSTEM_NMRVIEW)

    assert_lines_match(EXPECTED_3AA, mol_sys_result)

# noinspection PyUnusedLocal
def test_3aa10(typer_app, using_nmrview, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, '3aa10.seq')
    result = runner.invoke(typer_app, [*NMRVIEW_IMPORT_SEQUENCE, path], input=HEADER)

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, '%s' % MOLECULAR_SYSTEM_NMRVIEW)

    assert_lines_match(EXPECTED_3AA10, mol_sys_result)

HEADER = open('test_data/test_header_entry.txt').read()

EXPECTED_HEADER = '''\
save_nef_nmr_meta_data
   _nef_nmr_meta_data.sf_category      nef_nmr_meta_data
   _nef_nmr_meta_data.sf_framecode     nef_nmr_meta_data
   _nef_nmr_meta_data.format_name      nmr_exchange_format
   _nef_nmr_meta_data.format_version   1.1
   _nef_nmr_meta_data.program_name     NEFPipelines
   _nef_nmr_meta_data.script_name      util.py
   _nef_nmr_meta_data.program_version  0.0.1
   _nef_nmr_meta_data.creation_date    2012-01-14T12:00:01.123456
   _nef_nmr_meta_data.uuid             NEFPipelines-2012-01-14T12:00:01.123456-1043321819
   _nef_nmr_meta_data.creation_time    2012-01-14T12:00:01.123456

   loop_
      _nef_run_history.run_number
      _nef_run_history.program_name
      _nef_run_history.program_version
      _nef_run_history.script_name

     1   NEFPipelines   0.0.1   header.py

   stop_

save_
'''


# noinspection PyUnusedLocal
@freeze_time("2012-01-14 12:00:01.123456")
def test_pipe_header(typer_app, using_nmrview, monkeypatch, fixed_seed):

    monkeypatch.setattr('sys.stdin.isatty', lambda: True)

    path = path_in_test_data(__file__, '3aa10.seq')
    path_header = path_in_test_data(__file__,'test_header_entry.txt',local=False)
    result = runner.invoke(typer_app, [*NMRVIEW_IMPORT_SEQUENCE, '--pipe', path_header, path])
    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, '%s' % MOLECULAR_SYSTEM_NMRVIEW)
    meta_data_result = isolate_frame(result.stdout, '%s' % METADATA_NMRVIEW)

    assert_lines_match(EXPECTED_3AA10, mol_sys_result)
    assert_lines_match(EXPECTED_HEADER, meta_data_result, display=True)


# noinspection PyUnusedLocal
@freeze_time("2012-01-14 12:00:01.123456")
def test_header(typer_app, using_nmrview, monkeypatch, fixed_seed):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, '3aa10.seq')
    result = runner.invoke(typer_app, [*NMRVIEW_IMPORT_SEQUENCE, path], input=HEADER)

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, '%s' % MOLECULAR_SYSTEM_NMRVIEW)

    assert_lines_match(EXPECTED_3AA10, mol_sys_result)

def test_1let_3let():
    EXPECTED = [
        'ALA',
        'CYS',
        'ASP',
        'GLU',
        'PHE',
        'GLY',
        'HIS',
        'ILE',
        'LYS',
        'LEU',
        'MET',
        'ASN',
        'PRO',
        'GLN',
        'ARG',
        'SER',
        'THR',
        'VAL',
        'TRP',
        'TYR'
    ]
    GOOD_SEQUENCE = 'acdefghiklmnpqrstvwy'

    assert len(GOOD_SEQUENCE) == 20

    assert EXPECTED == translate_1_to_3(GOOD_SEQUENCE)



def test_bad_1let_3let():
    BAD_SEQUENCE = 'acdefghiklmonpqrstvwy'

    msgs = '''\
              unknown residue O
              at residue 12
              sequence: acdefghiklmonpqrstvwy
              ^
              '''

    msgs = dedent(msgs)
    msgs = msgs.split('\n')

    with pytest.raises(BadResidue) as exc_info:
        translate_1_to_3(BAD_SEQUENCE)

    for msg in msgs:
        assert msg in exc_info.value.args[0]


if __name__ == '__main__':
    pytest.main([f'{__file__}', '-vv'])
