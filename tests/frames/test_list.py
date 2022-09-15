from lib.structures import  ShiftList, ShiftData, AtomLabel
from textwrap import dedent
from transcoders.nmrview.nmrview_lib import  parse_shifts
import pytest
from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data, run_and_report

LIST_FRAMES = ['frames', 'list']


@pytest.fixture
def using_list():
    # register the module under test
    import tools.frames

# noinspection PyUnusedLocal
def test_frame_basic(typer_app, using_list, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, 'frames.nef')
    result = run_and_report(typer_app, [*LIST_FRAMES, '--in', path])

    if result.exit_code != 0:
        print('INFO: stdout from failed read:\n', result.stdout)

    assert result.exit_code == 0

    EXPECTED =  '''\
        entry test

        nef_nmr_meta_data  nef_molecular_system
    '''

    assert_lines_match (EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_frame_file_first(typer_app, using_list, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, 'frames.nef')
    result = run_and_report(typer_app, [*LIST_FRAMES, path])

    if result.exit_code != 0:
        print('INFO: stdout from failed read:\n', result.stdout)

    assert result.exit_code == 0

    EXPECTED =  '''\
        entry test

        nef_nmr_meta_data  nef_molecular_system
    '''

    assert_lines_match (EXPECTED, result.stdout)

# noinspection PyUnusedLocal
def test_frame_file_first_and_select(typer_app, using_list, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, 'frames.nef')
    result = run_and_report(typer_app, [*LIST_FRAMES, path, 'meta_data'])

    print('result',f'-{result.stdout}-')

    EXPECTED =  '''\
        entry test

        nef_nmr_meta_data
    '''

    assert_lines_match (EXPECTED, result.stdout)