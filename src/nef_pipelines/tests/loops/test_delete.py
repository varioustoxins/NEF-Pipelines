from textwrap import dedent

import typer

from nef_pipelines.lib.test_lib import assert_lines_match, run_and_report
from nef_pipelines.tools.loops.delete import delete

EXIT_ERROR = 1

app = typer.Typer()
app.command()(delete)

NEF_WITH_TWO_LOOPS = """\
data_test

save_nef_chemical_shift_list_myshifts
   _nef_chemical_shift_list.sf_category  nef_chemical_shift_list
   _nef_chemical_shift_list.sf_framecode nef_chemical_shift_list_myshifts

   loop_
      _nef_chemical_shift.chain_code
      _nef_chemical_shift.sequence_code
      _nef_chemical_shift.residue_name
      _nef_chemical_shift.atom_name
      _nef_chemical_shift.value

     A  2  GLN  N  123.22
     A  2  GLN  H  8.90

   stop_

   loop_
      _nef_peak_restraint.index
      _nef_peak_restraint.peak_id
      _nef_peak_restraint.restraint_id

     1  100  200
     2  101  201

   stop_

save_
"""

EXPECTED_AFTER_DELETE_SHIFT_LOOP = """\
data_test

save_nef_chemical_shift_list_myshifts
   _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
   _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_myshifts

   loop_
      _nef_peak_restraint.index
      _nef_peak_restraint.peak_id
      _nef_peak_restraint.restraint_id

      1   100   200
      2   101   201

   stop_

save_
"""

EXPECTED_AFTER_DELETE_PEAK_LOOP = """\
data_test

save_nef_chemical_shift_list_myshifts
   _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
   _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_myshifts

   loop_
      _nef_chemical_shift.chain_code
      _nef_chemical_shift.sequence_code
      _nef_chemical_shift.residue_name
      _nef_chemical_shift.atom_name
      _nef_chemical_shift.value

      A   2   GLN   N   123.22
      A   2   GLN   H   8.90

   stop_

save_
"""

EXPECTED_AFTER_DELETE_BOTH_LOOPS = """\
data_test

save_nef_chemical_shift_list_myshifts
   _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
   _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_myshifts

save_
"""


def test_delete_single_loop():
    result = run_and_report(
        app,
        ["--in", "-", "myshifts.chemical_shift"],
        input=NEF_WITH_TWO_LOOPS,
    )
    assert_lines_match(EXPECTED_AFTER_DELETE_SHIFT_LOOP, result.stdout)


def test_delete_loop_by_wildcard():
    result = run_and_report(
        app,
        ["--in", "-", "myshifts.peak"],
        input=NEF_WITH_TWO_LOOPS,
    )
    assert_lines_match(EXPECTED_AFTER_DELETE_PEAK_LOOP, result.stdout)


def test_delete_by_substring_pattern_matches_both():
    """Pattern 'nef' matches both loops due to substring matching."""
    result = run_and_report(
        app,
        ["--in", "-", "myshifts.nef"],
        input=NEF_WITH_TWO_LOOPS,
    )
    assert_lines_match(EXPECTED_AFTER_DELETE_BOTH_LOOPS, result.stdout)


def test_delete_multiple_loops_separate_args():
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "myshifts.chemical_shift",
            "myshifts.peak",
        ],
        input=NEF_WITH_TWO_LOOPS,
    )
    assert_lines_match(EXPECTED_AFTER_DELETE_BOTH_LOOPS, result.stdout)


def test_delete_loop_all_frames_wildcard():
    result = run_and_report(
        app,
        ["--in", "-", ".chemical_shift"],
        input=NEF_WITH_TWO_LOOPS,
    )
    assert_lines_match(EXPECTED_AFTER_DELETE_SHIFT_LOOP, result.stdout)


def test_delete_unknown_loop_warns():
    """Attempting to delete non-existent loop should succeed with unchanged output."""
    result = run_and_report(
        app,
        ["--in", "-", "myshifts.nonexistent_loop"],
        input=NEF_WITH_TWO_LOOPS,
    )
    # Entry should be unchanged when loop doesn't exist
    assert_lines_match(NEF_WITH_TWO_LOOPS, result.stdout)


def test_delete_multiple_loops_slash_separated():
    """Slash-separated selectors in a single argument."""
    result = run_and_report(
        app,
        ["--in", "-", "myshifts.chemical_shift/myshifts.peak"],
        input=NEF_WITH_TWO_LOOPS,
    )
    assert_lines_match(EXPECTED_AFTER_DELETE_BOTH_LOOPS, result.stdout)


def test_delete_rejects_invalid_selectors():
    """Invalid selectors should be rejected. Tests all error paths in parse_frame_loop_selectors_and_get_errors."""
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "myshifts",  # bare frame - no loop
            "myshifts:tag1,tag2",  # frame tags
            "myshifts.chemical_shift:chain_code,sequence_code",  # loop columns
            "myshifts.peak",  # valid - should work
            "myshifts.chemical_shift:value,atom_name",  # loop columns
            "myshifts:another_tag",  # frame tags
            "myshifts:*",  # wildcard frame tags - no loop
            "*:*",  # wildcard everything - no loop
            "myshifts..",  # bad syntax - double dot
        ],
        input=NEF_WITH_TWO_LOOPS,
        expected_exit_code=EXIT_ERROR,
    )

    EXPECTED_ERROR = """\
        ERROR [in: delete]:

        There was a problem parsing the following selectors to loop selections:

        the 1st selector myshifts is bad because does not have
        a loop name, use the frame.loop syntax with a loop to select loops.

        the 2nd selector myshifts:tag1,tag2 is bad because its is selecting the frame
        tags: tag1, tag2. Use the frame.loop syntax without frame tags.

        the 3rd selector myshifts.chemical_shift:chain_code,sequence_code is bad because it is selecting
        selecting the columns: chain_code, sequence_code. Use the frame.loop syntax without columns.

        the 5th selector myshifts.chemical_shift:value,atom_name is bad because it is selecting
        selecting the columns: value, atom_name. Use the frame.loop syntax without columns.

        the 6th selector myshifts:another_tag is bad because its is selecting the frame
        tags: another_tag. Use the frame.loop syntax without frame tags.

        the 7th selector myshifts:* is bad because does not have
        a loop name, use the frame.loop syntax with a loop to select loops.

        the 8th selector *:* is bad because does not have
        a loop name, use the frame.loop syntax with a loop to select loops.

        the 9th selector: myshifts.. is invalid because
        invalid syntax: Expected end of text, found '.'  (at char 9), (line:1, col:10).

        Did you forget --use-escapes?
        (I found .. which looks like an escape sequence for . when --use-escapes is active),
        the format should be frame.loop.

        exiting...
    """
    EXPECTED_ERROR = dedent(EXPECTED_ERROR)

    assert result.exit_code == EXIT_ERROR
    assert_lines_match(EXPECTED_ERROR, result.stderr)
