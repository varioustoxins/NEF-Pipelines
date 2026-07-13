from pathlib import Path
from textwrap import dedent

import pytest
import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.display import display

runner = CliRunner()
app = typer.Typer()
app.command()(display)

#             1
#   01234567890123456789
EXPECTED_BASIC_SEQUENCE = """\
    # save_nef_molecular_system

        # frame tags ...

        loop_
            _nef_sequence.chain_code
            _nef_sequence.residue_name
            # more columns...

            A   ALA
            A   GLY
            A   VAL

        stop_


    # save_

    # frame ccpn_additional_data_1 ...
    # frame ccpn_additional_data_2 ...
"""


def test_basic_selector():
    """Test basic selection with frame.loop:tags syntax, verifying content and exact indentation."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        ["--in", path, "molecular_system.nef_sequence:chain_code,residue_name"],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    # In CliRunner (pipe mode), display goes to stderr
    assert_lines_match(EXPECTED_BASIC_SEQUENCE, result.stderr)
    # squash_spaces=False verifies exact indentation from _indent_frame_content
    assert_lines_match(
        dedent(EXPECTED_BASIC_SEQUENCE), result.stderr, squash_spaces=False
    )


EXPECTED_RESIDUE_NAME = """\
    # save_nef_molecular_system

    # frame tags ...

    loop_
       _nef_sequence.residue_name
       # more columns...

       ALA
       GLY
       VAL

    stop_

    # save_

    # frame ccpn_additional_data_1 ...
    # frame ccpn_additional_data_2 ...
    """


def test_wildcard_in_tags():
    """Test wildcard matching in tag names."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    # *name should match residue_name but not chain_code
    result = run_and_report(
        app, ["--in", path, "molecular_system.sequence:*name"], merge_stderr=False
    )

    assert_lines_match(EXPECTED_RESIDUE_NAME, result.stderr)


EXPECTED_SEQUENCE_WITH_INDEX = """\
# save_nef_molecular_system

# frame tags ...

loop_
   _nef_sequence.index
   _nef_sequence.chain_code
   _nef_sequence.residue_name
   # more columns...

   1   A   ALA
   2   A   GLY
   3   A   VAL

stop_

# save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...

    """


def test_multiple_tags_with_index():
    """Test selecting multiple tags including index."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        ["--in", path, "molecular_system.sequence:index,chain_code,residue_name"],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_SEQUENCE_WITH_INDEX, result.stderr)


EXPECTED_CCPN_DATA_KEY = """\
# frame nef_molecular_system ...

# save_ccpn_additional_data_1

# frame tags ...

loop_
   _ccpn_data.key
   # more columns...

  frame1_key1
  frame1_key2

stop_

# save_

# save_ccpn_additional_data_2

# frame tags ...

loop_
   _ccpn_data.key
   # more columns...

  frame2_key1
  frame2_key2

stop_

# save_

    """


def test_wildcard_in_frame():
    """Test wildcard matching in frame names."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app, ["--in", path, "*ccpn*.ccpn_data:key"], merge_stderr=False
    )

    assert_lines_match(EXPECTED_CCPN_DATA_KEY, result.stderr)


# Original: molecular system is missing
EXPECTED_COMBINED_KEYS_VALUES = """\
# frame nef_molecular_system ...

# save_ccpn_additional_data_1

# frame tags ...

loop_
   _ccpn_data.key
   _ccpn_data.value

  frame1_key1   frame1_value1
  frame1_key2   frame1_value2

stop_

# save_

# save_ccpn_additional_data_2

# frame tags ...

loop_
   _ccpn_data.key
   _ccpn_data.value

  frame2_key1   frame2_value1
  frame2_key2   frame2_value2

stop_

# save_

    """


def test_multiple_selectors_same_loop():
    """Test combining multiple selectors for the same loop."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "ccpn_additional_data_1.ccpn_data:key",
            "ccpn_additional_data_1.ccpn_data:value",
            "ccpn_additional_data_2.ccpn_data:key",
            "ccpn_additional_data_2.ccpn_data:value",
        ],
        merge_stderr=False,
    )

    # Original: shouldn't EXPECTED_COMBINED_KEYS_VALUES have commenst for missing frames
    assert_lines_match(EXPECTED_COMBINED_KEYS_VALUES, result.stderr)


def test_polymorphic_file_first():
    """Test polymorphic argument with file path first."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [str(path), "molecular_system.sequence:chain_code,residue_name"],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_BASIC_SEQUENCE, result.stderr)


EXPECTED_DEFAULT_OUTPUT = """\
    save_nef_molecular_system

       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system
    loop_
       _nef_sequence.index
       _nef_sequence.chain_code
       _nef_sequence.sequence_code
       _nef_sequence.residue_name
       _nef_sequence.linking

      1   A   1   ALA   start
      2   A   2   GLY   middle
      3   A   3   VAL   end

    stop_


    save_

    save_ccpn_additional_data_1

       _ccpn_additional_data.sf_category   ccpn_additional_data
       _ccpn_additional_data.sf_framecode  ccpn_additional_data_1

    loop_
       _ccpn_data.key
       _ccpn_data.value

      frame1_key1   frame1_value1
      frame1_key2   frame1_value2

    stop_

    save_

    save_ccpn_additional_data_2

       _ccpn_additional_data.sf_category   ccpn_additional_data
       _ccpn_additional_data.sf_framecode  ccpn_additional_data_2

    loop_
       _ccpn_data.key
       _ccpn_data.value

      frame2_key1   frame2_value1
      frame2_key2   frame2_value2

    stop_

    save_
    """


def test_default_selector():
    """Test default selector (*) shows all complete frames."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(app, ["--in", path], merge_stderr=False)

    assert result.exit_code == 0

    # Original: shouldn't this just be the same as the contents of multi_frame_test.nef with the first two
    # lines or so missing
    assert_lines_match(EXPECTED_DEFAULT_OUTPUT, result.stderr)


# Original: missing other saveframes as comments
EXPECTED_SAVEFRAME_TAG = """\
    # save_nef_molecular_system

    _nef_molecular_system.sf_category   nef_molecular_system
    _nef_molecular_system.sf_framecode  nef_molecular_system

    # loop nef_sequence ...

    # save_

    # frame ccpn_additional_data_1 ...

    # frame ccpn_additional_data_2 ...

        """


def test_saveframe_tag_selection():
    """Test selecting saveframe-level tags with name:tag syntax."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        ["--in", path, "molecular_system:sf_category,sf_framecode"],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_SAVEFRAME_TAG, result.stderr)


EXPECTED_ALL_SF_CATEGORIES = """\
    # save_nef_molecular_system

       _nef_molecular_system.sf_category   nef_molecular_system

       # more frame tags...

    # loop nef_sequence ...

    # save_

    # save_ccpn_additional_data_1

       _ccpn_additional_data.sf_category   ccpn_additional_data

       # more frame tags...

    # loop ccpn_data ...

    # save_

    # save_ccpn_additional_data_2

       _ccpn_additional_data.sf_category   ccpn_additional_data

       # more frame tags...

    # loop ccpn_data ...

    # save_
    """


def test_saveframe_tag_all_frames():
    """Test :tag syntax for saveframe tags across all frames."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(app, ["--in", path, ":sf_category"], merge_stderr=False)

    assert_lines_match(EXPECTED_ALL_SF_CATEGORIES, result.stderr)


EXPECTED_WILDCARD_CATEGORY = """\
    # save_nef_molecular_system

       _nef_molecular_system.sf_category   nef_molecular_system

       # more frame tags...

    # loop nef_sequence ...

    # save_

    # frame ccpn_additional_data_1 ...
    # frame ccpn_additional_data_2 ...
    """


def test_wildcard_in_frame_tags():
    """Test wildcard matching in saveframe tag names."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app, ["--in", path, "molecular_system:*category*"], merge_stderr=False
    )

    assert_lines_match(EXPECTED_WILDCARD_CATEGORY, result.stderr)


EXPECTED_BARE_FRAME_COMPLETE = """\
save_nef_molecular_system

   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system
loop_
   _nef_sequence.index
   _nef_sequence.chain_code
   _nef_sequence.sequence_code
   _nef_sequence.residue_name
   _nef_sequence.linking

  1   A   1   ALA   start
  2   A   2   GLY   middle
  3   A   3   VAL   end

stop_


save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...

"""

EXPECTED_FRAME_TAGS_ONLY = """\
# save_nef_molecular_system

   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system

# loop nef_sequence ...

# save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...

        """

EXPECTED_LOOPS_WITH_CONTEXT = """\
# save_nef_molecular_system

# frame tags ...

loop_
   _nef_sequence.index
   _nef_sequence.chain_code
   _nef_sequence.sequence_code
   _nef_sequence.residue_name
   _nef_sequence.linking

  1   A   1   ALA   start
  2   A   2   GLY   middle
  3   A   3   VAL   end

stop_

# save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...

        """

EXPECTED_SPECIFIC_TAG = """\
# save_nef_molecular_system

   _nef_molecular_system.sf_category   nef_molecular_system
   # more frame tags...

# loop nef_sequence ...

# save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...

        """
# no spaces before the  final """


@pytest.mark.parametrize(
    "selector,expected_output",
    [
        ("molecular_system", EXPECTED_BARE_FRAME_COMPLETE),
        ("molecular_system:", EXPECTED_FRAME_TAGS_ONLY),
        ("molecular_system.", EXPECTED_LOOPS_WITH_CONTEXT),
        ("molecular_system:sf_category", EXPECTED_SPECIFIC_TAG),
        ("molecular_system.sequence:*", EXPECTED_LOOPS_WITH_CONTEXT),
    ],
    ids=[
        "bare_frame_complete",
        "frame_tags_only",
        "loops_with_context",
        "specific_tag",
        "all_columns_via_wildcard",
    ],
)
def test_entire_frame_vs_frame_tags(selector, expected_output):
    """Test selector syntax distinctions: bare frame, tags-only, loops-only, partial tag, all-columns wildcard."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")
    result = run_and_report(app, ["--in", path, selector], merge_stderr=False)
    assert_lines_match(expected_output, result.stderr)


# TODO these outputs don't look right this should be the first 5 lines of the loop surely
# also there shouldn't be a # more columns... as its all columns
# ah i see the bug the  ... 21 rows omitted ... shoudl be at the end!


EXPECTED_HEAD_OUTPUT = """\
# frame nef_nmr_meta_data ...
# frame nef_molecular_system ...

# save_nef_chemical_shift_list_default

# frame tags ...

  loop_
     _nef_chemical_shift.chain_code
     _nef_chemical_shift.sequence_code
     _nef_chemical_shift.atom_name
     _nef_chemical_shift.value
     _nef_chemical_shift.value_uncertainty
  # more columns...

    '#2 '   @1     C    174.078751   .
    '#2 '   @1     H    8.507345     0.0031493880
    '#2 '   @1-1   C    175.947447   0.08720577414
    '#2 '   @1-1   CA   56.689055    0.0499432144
    '#1'    @2     C    17.078751    .

# ... 21 rows omitted ...

  stop_


# save_
        """
# Original: ... 11 rows omitted ... should be at the end!
EXPECTED_MIDDLE_OUTPUT = """\
# frame nef_nmr_meta_data ...
# frame nef_molecular_system ...

# save_nef_chemical_shift_list_default

# frame tags ...

  loop_
     _nef_chemical_shift.chain_code
     _nef_chemical_shift.sequence_code
     _nef_chemical_shift.atom_name
     _nef_chemical_shift.value
     _nef_chemical_shift.value_uncertainty
  # more columns...


# ... 10 rows omitted ...

    A   2     C    7.090786    .
    A   2     N    12.714456   0.1199761464
    A   2-1   C    78.121295   0.3397487528
    A   2-1   CB   6.570846    0.0514681685
    A   3     H    88.111256   0.0019229051

# ... 11 rows omitted ...


  stop_


# save_
        """
# Original: this one is correct!
EXPECTED_TAIL_OUTPUT = """\
# frame nef_nmr_meta_data ...
# frame nef_molecular_system ...

# save_nef_chemical_shift_list_default

# frame tags ...

  loop_
     _nef_chemical_shift.chain_code
     _nef_chemical_shift.sequence_code
     _nef_chemical_shift.atom_name
     _nef_chemical_shift.value
     _nef_chemical_shift.value_uncertainty
  # more columns...


# ... 21 rows omitted ...

    B   2-1   CB   4.570846   0.0514681685
    B   3     H    5.111256   0.0019229051
    B   3     N    6.453575   0.0925289285
    B   3-1   C    7.261980   0.0133395288
    B   3-1   CB   8.427729   0.1141368283

  stop_


# save_
        """


@pytest.mark.parametrize(
    "display_mode_flag,expected_output",
    [
        ("--head", EXPECTED_HEAD_OUTPUT),
        ("--middle", EXPECTED_MIDDLE_OUTPUT),
        ("--tail", EXPECTED_TAIL_OUTPUT),
    ],
    ids=["head", "middle", "tail"],
)
def test_display_mode_options(display_mode_flag, expected_output):
    """Test display mode options (--head, --middle, --tail) show different row selections."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")
    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:chain_code,sequence_code,atom_name,value",
            display_mode_flag,
            "--count",
            "5",
        ],
        merge_stderr=False,
    )
    assert_lines_match(expected_output, result.stderr)


# Original: i presume these will be broken in the same way
# Original: it would be nice to say n more columns and possibly even xxxx...yyyy, add as a todo!
EXPECTED_COUNT_OUTPUT = """\
    # frame nef_nmr_meta_data ...
    # frame nef_molecular_system ...

    # save_nef_chemical_shift_list_default

    # frame tags ...

      loop_
         _nef_chemical_shift.chain_code
         _nef_chemical_shift.sequence_code
         _nef_chemical_shift.atom_name
         _nef_chemical_shift.value
         _nef_chemical_shift.value_uncertainty
      # more columns...
        '#2 '   @1     C   174.078751   .
        '#2 '   @1     H   8.507345     0.0031493880
        '#2 '   @1-1   C   175.947447   0.08720577414

    # ... 23 rows omitted ...

      stop_


    # save_
    """


def test_count_option():
    """Test --count option controls number of rows displayed."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:chain_code,sequence_code,atom_name,value",
            "--head",
            "--count",
            "3",
        ],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_COUNT_OUTPUT, result.stderr)


EXPECTED_NO_TRUNCATION = """\
    # save_nef_molecular_system

    # frame tags ...

    loop_
       _nef_sequence.chain_code
       _nef_sequence.residue_name
    # more columns...

      A   ALA
      A   GLY
      A   VAL

    stop_


    # save_

    # frame ccpn_additional_data_1 ...
    # frame ccpn_additional_data_2 ...
    """


def test_no_truncation_for_small_loops():
    """Test that loops smaller than count are not truncated."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system.sequence:chain_code,residue_name",
            "--head",
            "--count",
            "10",
        ],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_NO_TRUNCATION, result.stderr)


# Original: this is the wrong name running in cli_runner is the artifact that does it!
def test_pipe_mode_output_routing():
    """\
    Test pipe mode output routing (CliRunner makes stdout non-TTY).

    In CliRunner context, stdout is always non-TTY (pipe mode), so:
    - Display should go to stderr
    - Entry should go to stdout
    """
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        ["--in", path, "molecular_system.sequence:chain_code,residue_name"],
        merge_stderr=False,
    )

    # Display should be in stderr (pipe mode)
    assert_lines_match(EXPECTED_BASIC_SEQUENCE, result.stderr)

    # Entry should be in stdout
    assert_lines_match(Path(path).read_text(), result.stdout)


def test_explicit_display_file_streams_entry():
    """Test --out writes display to file and streams entry to stdout."""
    import os
    import tempfile

    path = path_in_test_data(__file__, "multi_frame_test.nef")

    # Create temp directory and construct a filename that doesn't exist yet
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "display_output.txt")

    try:
        result = run_and_report(
            app,
            [
                "--in",
                path,
                "molecular_system.sequence:chain_code,residue_name",
                "--out",
                tmp_path,
            ],
            merge_stderr=False,
        )

        # Display should be in file
        with open(tmp_path) as f:
            display_content = f.read()
        assert_lines_match(EXPECTED_BASIC_SEQUENCE, display_content)

        # Entry should be in stdout
        assert_lines_match(Path(path).read_text(), result.stdout)

    finally:
        import shutil

        shutil.rmtree(tmp_dir)


def test_out_err_no_entry():
    """Test --out @err sends display to stderr and entry to stdout."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system.sequence:chain_code,residue_name",
            "--out",
            "@err",
        ],
        merge_stderr=False,
    )

    # Display should be in stderr
    assert_lines_match(EXPECTED_BASIC_SEQUENCE, result.stderr)

    # Entry should be in stdout (as documented in --out @err help text)
    assert_lines_match(Path(path).read_text(), result.stdout)


# Original: i assume these will be broken
# Original: add todo we should be able to specify indices as well 1...30,20..25 etc maybe useful for AIs
EXPECTED_ADDITIVE_OUTPUT = """\
    # frame nef_nmr_meta_data ...
    # frame nef_molecular_system ...

    # save_nef_chemical_shift_list_default

    # frame tags ...

      loop_
         _nef_chemical_shift.chain_code
         _nef_chemical_shift.sequence_code
         _nef_chemical_shift.atom_name
         _nef_chemical_shift.value
         _nef_chemical_shift.value_uncertainty
      # more columns...

        '#2 '   @1    C    174.078751   .
        '#2 '   @1    H    8.507345     0.0031493880

    # ... 10 rows omitted ...

        A       2-1   C    78.121295    0.3397487528
        A       2-1   CB   6.570846     0.0514681685

    # ... 10 rows omitted ...

        B       3-1   C    7.261980     0.0133395288
        B       3-1   CB   8.427729     0.1141368283

      stop_


    # save_
    """


def test_additive_head_middle_tail():
    """Test --head, --middle, and --tail are all additive."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:chain_code,sequence_code,atom_name,value",
            "--head",
            "--middle",
            "--tail",
            "--count",
            "2",
        ],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_ADDITIVE_OUTPUT, result.stderr)


# Original: i assume these will be broken
EXPECTED_ELLIPSIS_POSITIONING = """\
    # frame nef_nmr_meta_data ...

    # save_nef_molecular_system

    # frame tags ...

      loop_
         _nef_sequence.chain_code
         _nef_sequence.sequence_code
         _nef_sequence.residue_name
      # more columns...

      A   1   MET
      A   2   ILE

     # ... 1 rows omitted ...

      A   6   LYS
      B   1   MET

     # ... 1 rows omitted ...

      B   3   ALA
      B   6   LYS

    stop_

    # save_

    # frame nef_chemical_shift_list_default ...
    """


def test_ellipsis_positioning_with_head_middle_tail():
    """\
    Regression test for ellipsis positioning bug.

    When using --head --middle --tail together, ellipsis comments must appear
    BETWEEN each gap in the displayed rows, not at incorrect positions.

    This test ensures the fix for the bug where ellipsis comments were inserted
    at wrong positions due to incorrectly tracking insertion indices (output_idx
    was being incremented by 3 for each ellipsis, causing subsequent ellipses
    to be positioned incorrectly).

    The test uses a complete expected output to ensure ellipsis appear at the
    correct positions between row groups.
    """
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system.nef_sequence:chain_code,sequence_code,residue_name",
            "--head",
            "--middle",
            "--tail",
            "--count",
            "2",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0

    # Expected output with ellipsis positioned correctly between gaps
    # The test file has chains A and B with varying residues
    # With --head --middle --tail --count 2:
    # - Shows first 2 rows: A 1 MET, A 2 ILE
    # - Shows middle 2 rows (around row 3): A 6 LYS, B 1 MET
    # - Shows last 2 rows: B 3 ALA, B 6 LYS
    # The key test: ellipsis comments must be positioned BETWEEN row groups
    assert_lines_match(EXPECTED_ELLIPSIS_POSITIONING, result.stderr)


EXPECTED_ELLIPSIS_EDGE_CASE = """\
    # save_nef_molecular_system

    # frame tags ...

      loop_
         _nef_sequence.chain_code
         _nef_sequence.sequence_code
         _nef_sequence.residue_name
      # more columns...

      A   1   ALA

     # ... 1 rows omitted ...

      A   3   VAL

    stop_

    # save_

    # frame ccpn_additional_data_1 ...
    # frame ccpn_additional_data_2 ...
    """


def test_ellipsis_edge_case_no_boundary_gaps():
    """\
    Test ellipsis positioning when there are NO gaps at boundaries.

    This tests the edge case where:
    - First displayed row is at index 0 (no gap at beginning)
    - Last displayed row is at last index (no gap at end)
    - Only middle gaps should have ellipsis

    Ensures the boundary conditions in the ellipsis insertion logic work correctly:
    - if indices_to_include[0] > 0: (should be False, no beginning ellipsis)
    - if indices_to_include[-1] < total_rows - 1: (should be False, no ending ellipsis)
    """
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    # With 3 rows total and --head --tail --count 1:
    # HEAD: row 0
    # TAIL: row 2
    # There's a gap in the middle (row 1), but no gaps at boundaries
    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system.nef_sequence:chain_code,sequence_code,residue_name",
            "--head",
            "--tail",
            "--count",
            "1",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0

    # Expected: First row (index 0), gap, last row (index 2)
    # Should have ellipsis ONLY for the middle gap, NOT at beginning or end
    assert_lines_match(EXPECTED_ELLIPSIS_EDGE_CASE, result.stderr)


EXPECTED_NO_SAVE_COMMENTS = """\
    loop_
       _nef_sequence.chain_code
       _nef_sequence.residue_name

      A   ALA
      A   GLY
      A   VAL

    stop_
    """


def test_no_comments():
    """Test --no-comments suppresses all comments."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system.sequence:chain_code,residue_name",
            "--no-comments",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_NO_SAVE_COMMENTS, result.stderr)


# Original: is --tags-only still needed? I think it was written before we had a comprehensive selection syntax...
EXPECTED_TAGS_ONLY = """\
    # save_nef_molecular_system

    _nef_molecular_system.sf_category   nef_molecular_system
    _nef_molecular_system.sf_framecode  nef_molecular_system

    # loop nef_sequence ...

    # save_

    # frame ccpn_additional_data_1 ...
    # frame ccpn_additional_data_2 ...
    """


def test_tags_only():
    """Test selector syntax 'molecular_system:' shows only saveframe tags (no loops)."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system:",  # Colon with no tags = all frame tags, no loops
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_TAGS_ONLY, result.stderr)


EXPECTED_NO_COMMENTS_OUTPUT = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code

      '#2 '   @1
      '#2 '   @1
      '#2 '   @1-1

    stop_
    """


# Original: i assume these will be broken
def test_no_comments_with_head():
    """Test --no-comments suppresses ellipsis comments."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:chain_code,sequence_code",
            "--head",
            "--count",
            "3",
            "--no-comments",
        ],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_NO_COMMENTS_OUTPUT, result.stderr)


EXPECTED_NEF_INCLUDE = """\
    save_nef_molecular_system

       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system
    loop_
       _nef_sequence.index
       _nef_sequence.chain_code
       _nef_sequence.sequence_code
       _nef_sequence.residue_name
       _nef_sequence.linking

      1   A   1   ALA   start
      2   A   2   GLY   middle
      3   A   3   VAL   end

    stop_

    save_

    save_ccpn_additional_data_1

       _ccpn_additional_data.sf_category   ccpn_additional_data
       _ccpn_additional_data.sf_framecode  ccpn_additional_data_1
    loop_
       _ccpn_data.key
       _ccpn_data.value

      frame1_key1   frame1_value1
      frame1_key2   frame1_value2

    stop_

    save_

    save_ccpn_additional_data_2

       _ccpn_additional_data.sf_category   ccpn_additional_data
       _ccpn_additional_data.sf_framecode  ccpn_additional_data_2
    loop_
       _ccpn_data.key
       _ccpn_data.value

      frame2_key1   frame2_value1
      frame2_key2   frame2_value2

    stop_

    save_
    """


def test_namespace_include():
    """Test --namespace +nef includes nef frames and frames with nef children (hierarchical)."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "*.*:*",
            "--namespace",
            "+nef",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_NEF_INCLUDE, result.stderr)


EXPECTED_NEF_EXCLUDE = """\
    # frame nef_molecular_system ...

    save_ccpn_additional_data_1

       _ccpn_additional_data.sf_category   ccpn_additional_data
       _ccpn_additional_data.sf_framecode  ccpn_additional_data_1
    loop_
       _ccpn_data.key
       _ccpn_data.value

      frame1_key1   frame1_value1
      frame1_key2   frame1_value2

    stop_

    save_

    save_ccpn_additional_data_2

       _ccpn_additional_data.sf_category   ccpn_additional_data
       _ccpn_additional_data.sf_framecode  ccpn_additional_data_2
    loop_
       _ccpn_data.key
       _ccpn_data.value

      frame2_key1   frame2_value1
      frame2_key2   frame2_value2

    stop_

    save_
    """


def test_namespace_exclude():
    """Test --namespace -nef with hierarchical logic.

    Hierarchical logic: Frames are excluded if namespace matches AND no children in other namespaces.
    ccpn frames have ccpn loops (_ccpn_data) with ccpn children (key, value inherit ccpn namespace),
    so they are included with -nef.
    """
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    # EXPECTED: ccpn frames shown because:
    # - nef_molecular_system is nef namespace -> excluded
    # TODO: logic a little flawed as the top levels are in the ccpn namespace
    # you would need a non ccpn frame or loop wirh ccpn tags etc for this test to work...
    # - ccpn frames have ccpn children (_ccpn_data loop with key/value columns) -> included
    result = run_and_report(
        app,
        [
            "--in",
            path,
            "*.*:*",
            "--namespace",
            "-nef",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_NEF_EXCLUDE, result.stderr)


def test_namespace_invert():
    """Test --namespace -nef --no-initial-namespace-selection with hierarchical logic.

    --no-initial-namespace-selection starts with EMPTY, then -nef excludes nef from empty set.
    Result is empty (same as test_namespace_exclude).
    """
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    EXPECTED_NEF_INVERT = ""

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "*.*:*",
            "--namespace",
            "-nef",
            "--no-initial-namespace-selection",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_NEF_INVERT, result.stderr)


EXPECTED_NAMESPACE_MULTIPLE = """\
    # frame nef_molecular_system ...

    # save_ccpn_additional_data_1

       _ccpn_additional_data.sf_category   ccpn_additional_data
       _ccpn_additional_data.sf_framecode  ccpn_additional_data_1

    # loop ccpn_data ...

    # save_

    # save_ccpn_additional_data_2

       _ccpn_additional_data.sf_category   ccpn_additional_data
       _ccpn_additional_data.sf_framecode  ccpn_additional_data_2

    # loop ccpn_data ...

    # save_
    """


def test_namespace_multiple():
    """Test --namespace with multiple selectors (-,+ccpn clears all then adds ccpn)."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "*:*",
            "--namespace",
            "-,+ccpn",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_NAMESPACE_MULTIPLE, result.stderr)


# Original: see comment about tags-only
EXPECTED_NAMESPACE_FILTER_TAGS = """\
    # frame nef_nmr_meta_data ...
    # frame nef_molecular_system ...

    # save_nef_chemical_shift_list_default

       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_default

       # more frame tags...

    # loop nef_chemical_shift ...

    # save_
    """


def test_namespace_filter_tags():
    """Test --namespace filters individual tags (ccpn tags should be excluded)."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift:",  # Colon with no tags = tags only
            "--namespace",
            "-ccpn",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_NAMESPACE_FILTER_TAGS, result.stderr)


EXPECTED_NAMESPACE_FILTERED = """\
    # frame nef_nmr_meta_data ...
    # frame nef_molecular_system ...

    # save_nef_chemical_shift_list_default

    # frame tags ...

      loop_
         _nef_chemical_shift.chain_code
         _nef_chemical_shift.sequence_code
         _nef_chemical_shift.residue_name
         _nef_chemical_shift.atom_name
         _nef_chemical_shift.value
         _nef_chemical_shift.value_uncertainty
         _nef_chemical_shift.element
         _nef_chemical_shift.isotope_number
      # more columns...

        '#2 '   @1   .   C   174.078751   .              C   13
        '#2 '   @1   .   H   8.507345     0.0031493880   H   1

    # ... 24 rows omitted ...

      stop_


    # save_
    """


def test_namespace_filter_loop_columns():
    """Test --namespace filters loop columns."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:*",
            "--head",
            "--count",
            "2",
            "--namespace",
            "-ccpn",
        ],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_NAMESPACE_FILTERED, result.stderr)


# Original: see my comments about tags only
EXPECTED_CCPN_TAGS = """\
_nef_chemical_shift_list.ccpn_serial        1
_nef_chemical_shift_list.ccpn_auto_update   true
_nef_chemical_shift_list.ccpn_is_simulated  false
_nef_chemical_shift_list.ccpn_comment       .
    """


def test_namespace_hierarchical_tags_only():
    """Test --namespace with hierarchical filtering in tags-only mode.

    With -,+ccpn (clear all, add ccpn), should show only ccpn-namespaced tags
    from the shift frame.
    """
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift:",  # Colon with no tags = tags only
            "--namespace",
            "-,+ccpn",
            "--no-comments",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_CCPN_TAGS, result.stderr)


EXPECTED_FRAME_TAGS_NO_NEF = """\
# frame nef_nmr_meta_data ...
# frame nef_molecular_system ...

# save_nef_chemical_shift_list_default

   _nef_chemical_shift_list.ccpn_serial        1
   _nef_chemical_shift_list.ccpn_auto_update   true
   _nef_chemical_shift_list.ccpn_is_simulated  false
   _nef_chemical_shift_list.ccpn_comment       .

   # more frame tags...

# loop nef_chemical_shift ...

# save_
    """


def test_frame_tags_selector_consistent_with_tags_only():
    """\
    Test that *:* and *: (both frame tags selectors) produce same output.

    Both *:* (all tags) and *: (tags only, no loops) should select frame tags.
    This verifies the namespace filtering works correctly at the frame level
    with different selector syntaxes.

    With --namespace -nef, only ccpn-namespaced tags should be shown from nef frames.
    """
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    # Run with *:* selector (all tags from all frames)
    result_all_tags = run_and_report(
        app,
        [
            "--in",
            path,
            "*:*",
            "--namespace",
            "-nef",
        ],
        merge_stderr=False,
    )

    # Run with *: selector (tags only, no loops)
    result_tags_only = run_and_report(
        app,
        [
            "--in",
            path,
            "*:",
            "--namespace",
            "-nef",
        ],
        merge_stderr=False,
    )

    assert result_all_tags.exit_code == 0
    assert result_tags_only.exit_code == 0

    # Both should produce identical output
    assert (
        result_all_tags.stderr == result_tags_only.stderr
    ), "Output should be identical for *:* and *: selectors"

    # Check against expected output
    assert_lines_match(EXPECTED_FRAME_TAGS_NO_NEF, result_all_tags.stderr)


EXPECTED_EXACT_FLAG_WILDCARD_COLUMNS = """\
    loop_
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty

      174.078751   .
      8.507345     0.0031493880

    stop_
    """

EXPECTED_EXACT_FLAG_EXACT_COLUMNS = """\
    loop_
       _nef_chemical_shift.value

      174.078751
      8.507345

    stop_
    """


def test_exact_flag_disables_wildcards():
    """\
    Test --exact flag disables wildcard matching in selectors.

    Without --exact (default):
      - Loop: 'chemical_shift' → '*chemical_shift*' → matches 'nef_chemical_shift'
      - Tag: 'value' → '*value*' → matches 'value' AND 'value_uncertainty'

    With --exact:
      - Loop: must use full name 'nef_chemical_shift' (not 'chemical_shift')
      - Tag: 'value' → 'value' → matches only 'value' exactly (not 'value_uncertainty')
    """
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    # Without --exact: 'value' should match both 'value' and 'value_uncertainty'
    result_wildcard = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:value",
            "--head",
            "--count",
            "2",
            "--no-comments",
        ],
        merge_stderr=False,
    )

    # With --exact: must use full loop name 'nef_chemical_shift' and exact tag 'value'
    result_exact = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.nef_chemical_shift:value",
            "--exact",
            "--head",
            "--count",
            "2",
            "--no-comments",
        ],
        merge_stderr=False,
    )

    # Wildcard mode: should have both 'value' and 'value_uncertainty' columns
    assert_lines_match(EXPECTED_EXACT_FLAG_WILDCARD_COLUMNS, result_wildcard.stderr)

    # Exact mode: should have only 'value' column (no 'value_uncertainty')
    assert_lines_match(EXPECTED_EXACT_FLAG_EXACT_COLUMNS, result_exact.stderr)
