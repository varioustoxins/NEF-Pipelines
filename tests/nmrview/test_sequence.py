from pathlib import Path

import lib
import pytest

from typer.testing import CliRunner
from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

MOLECULAR_SYSTEM_NMRVIEW = 'nef_molecular_system_nmrview'
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

    monkeypatch.setattr(lib.util, 'get_pipe_file', lambda x: None)
    path = path_in_test_data(__file__, '3aa.seq')
    print('path', path)
    result = runner.invoke(typer_app, [*NMRVIEW_IMPORT_SEQUENCE, path])
    assert result.exit_code == 0

    result = isolate_frame(result, MOLECULAR_SYSTEM_NMRVIEW)

    assert_lines_match(EXPECTED_3AA, result)


# noinspection PyUnusedLocal
def test_3aa10(typer_app, using_nmrview, monkeypatch):

    monkeypatch.setattr(lib.util, 'get_pipe_file', lambda x: None)
    path = path_in_test_data(__file__, '3aa10.seq')
    result = runner.invoke(typer_app, [*NMRVIEW_IMPORT_SEQUENCE, path])
    assert result.exit_code == 0

    result = isolate_frame(result, '%s' % MOLECULAR_SYSTEM_NMRVIEW)

    assert_lines_match(EXPECTED_3AA10, result)


if __name__ == '__main__':
    pytest.main([__file__, '-vv'])
