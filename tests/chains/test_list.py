from lib.structures import  ShiftList, ShiftData, AtomLabel
from textwrap import dedent
from transcoders.nmrview.nmrview_lib import  parse_shifts
import pytest
from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

from typer.testing import CliRunner
runner = CliRunner()


METADATA_NMRVIEW ='nef_nmr_meta_data'
LIST_CHAINS = ['chains', 'list']


@pytest.fixture
def using_chains():
    # register the module under test
    import tools.chains

# noinspection PyUnusedLocal
def test_frame_basic(typer_app, using_chains, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, 'multi_chain.nef')

    result = runner.invoke(typer_app, [*LIST_CHAINS, '--pipe', path])

    if result.exit_code != 0:
        print('INFO: stdout from failed read:\n', result.stdout)

    assert result.exit_code == 0

    EXPECTED =  'A B C'

    assert_lines_match (EXPECTED, result.stdout)