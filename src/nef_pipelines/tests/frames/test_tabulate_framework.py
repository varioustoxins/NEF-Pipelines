"""Meta tests for tabulate framework behavior.

Tests that verify the tabulate command's framework-level functionality,
such as frame selection logic and multi-frame processing.
"""

import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.tabulate import tabulate

runner = CliRunner()
app = typer.Typer()
app.command()(tabulate)


def test_tabulate_all_frames():
    """Test that tabulate with no selectors shows ALL frames and loops.

    This tests the fix for the bug where only the first frame was being processed
    due to inappropriate 'break' statements in _select_chosen_frames_and_loops.
    """

    EXPECTED = """\
        nef_sequence
        ------------

          index  chain_code      sequence_code  residue_name    linking
              1  A                           1  ALA             start
              2  A                           2  GLY             middle
              3  A                           3  VAL             end

        1 [ccpn_data]
        -------------

        key          value
        frame1_key1  frame1_value1
        frame1_key2  frame1_value2

        2 [ccpn_data]
        -------------

        key          value
        frame2_key1  frame2_value1
        frame2_key2  frame2_value2
    """

    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(app, ["--in", path])

    assert_lines_match(EXPECTED, result.stdout)


def test_tabulate_selector_matches_multiple_frames():
    """Test that a selector matching multiple frames returns all matches.

    This is the primary regression test for the bug where 'break' statements
    caused only the first matching frame to be processed.
    """

    EXPECTED = """\
        1 [ccpn_data]
        -------------

        key          value
        frame1_key1  frame1_value1
        frame1_key2  frame1_value2

        2 [ccpn_data]
        -------------

        key          value
        frame2_key1  frame2_value1
        frame2_key2  frame2_value2
    """

    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(app, ["--in", path, "additional_data"])

    assert_lines_match(EXPECTED, result.stdout)
