import pytest
from typer.testing import CliRunner

from lib.test_lib import assert_lines_match, path_in_test_data

runner = CliRunner()

TABULATE_FRAMES = ["frames", "tabulate"]


@pytest.fixture
def using_chains():
    # register the module under test
    import tools.chains  # noqa: F401


# noinspection PyUnusedLocal
def test_frame_basic(typer_app, using_chains, monkeypatch, clear_cache):

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    path = path_in_test_data(__file__, "tailin_seq_short.nef")

    result = runner.invoke(typer_app, [*TABULATE_FRAMES, "--pipe", path])

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

    EXPECTED = """\
      ind   chain       seq   resn     link
         1  A             10  GLU      start
         2  A             11  TYR      middle
         3  A             12  ALA      middle
         4  A             13  GLN      middle
         5  A             14  PRO      middle
         6  A             15  ARG      middle
         7  A             16  LEU      middle
         8  A             17  ARG      middle
         9  A             18  LEU      middle
        10  A             19  GLY      middle
        11  A             20  PHE      middle
        12  A             21  GLU      middle
        13  A             22  ASP      end

    """

    for line in zip(EXPECTED.split("\n"), result.stdout.split("\n")):
        print(line)

    assert_lines_match(EXPECTED, result.stdout)
