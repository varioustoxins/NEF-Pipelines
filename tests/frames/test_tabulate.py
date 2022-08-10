from lib.structures import  ShiftList, ShiftData, AtomLabel
from textwrap import dedent
from transcoders.nmrview.nmrview_lib import  parse_shifts
import pytest
from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

from typer.testing import CliRunner
runner = CliRunner()

TABULATE_FRAMES= ['frames', 'tabulate']


@pytest.fixture
def using_chains():
    # register the module under test
    import tools.chains

# noinspection PyUnusedLocal
def test_frame_basic(typer_app, using_chains, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, 'tailin_seq_short.nef')

    result = runner.invoke(typer_app, [*TABULATE_FRAMES, '--pipe', path])

    if result.exit_code != 0:
        print('INFO: stdout from failed read:\n', result.stdout)

    assert result.exit_code == 0

    EXPECTED =  '''\
      ind   chain       seq   resn     link
         1  A            182  GLU      start
         2  A            216  TYR      middle
         3  A           2236  ALA      middle
         4  A            349  GLN      middle
         5  A            545  SER      middle
         6  A            328  ARG      middle
         7  A           2515  LEU      middle
         8  A           2368  ARG      middle
         9  A            129  LEU      middle
        10  A            523  GLY      middle
        11  A             19  PHE      middle
        12  A            657  GLU      middle
        13  A           1277  ASP      end

    '''

    assert_lines_match (EXPECTED, result.stdout)