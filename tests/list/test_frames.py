from lib.structures import  ShiftList, ShiftData, AtomLabel
from textwrap import dedent
from transcoders.nmrview.nmrview_lib import  parse_shifts
import pytest
from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

from typer.testing import CliRunner
runner = CliRunner()

SHIFTS_NMRPIPE = 'nef_chemical_shift_list_nmrview'
METADATA_NMRVIEW ='nef_nmr_meta_data'
LIST_FRAMES = ['list', 'frames']


@pytest.fixture
def using_list():
    # register the module under test
    import tools.list

# noinspection PyUnusedLocal
def test_frame_basic(typer_app, using_list, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, 'frames.nef')
    result = runner.invoke(typer_app, [*LIST_FRAMES, '--pipe', path])

    if result.exit_code != 0:
        print('INFO: stdout from failed read:\n', result.stdout)

    assert result.exit_code == 0

    EXPECTED =  '''\
        entry test

        nef_nmr_meta_data  nef_molecular_system
    '''

    assert_lines_match (EXPECTED, result.stdout)