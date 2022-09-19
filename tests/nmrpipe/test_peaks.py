import traceback
from textwrap import dedent

import pytest
from icecream import ic

from typer.testing import CliRunner

from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data, run_and_report

HEADER = open(path_in_test_data(__file__,'test_header_entry.txt', local=False)).read()

PEAKS_NMRPIPE = 'nef_nmr_spectrum_nmrpipe'
METADATA_NMRPIPE = 'nef_nmr_meta_data'
NMRPIPE_IMPORT_PEAKS = ['nmrpipe', 'import', 'peaks']

runner = CliRunner()

@pytest.fixture
def using_nmrpipe():
    # register the module under test
    import transcoders.nmrpipe


# noinspection PyUnusedLocal
def test_peaks(typer_app, using_nmrpipe, monkeypatch):
    EXPECTED = open(path_in_test_data(__file__, 'gb3_assigned_trunc_expected.tab')).read()
    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, 'gb3_assigned_trunc.tab')
    result = run_and_report(typer_app, [*NMRPIPE_IMPORT_PEAKS, path], input=HEADER)

    assert result.exit_code == 0
    peaks_result = isolate_frame(result.stdout, '%s' % PEAKS_NMRPIPE)

    assert_lines_match(EXPECTED, peaks_result)


if __name__ == '__main__':
    pytest.main(['--disable-warnings', '-vv', f'{__file__}'])
