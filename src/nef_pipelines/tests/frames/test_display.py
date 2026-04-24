from pathlib import Path

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


EXPECTED_BASIC_SEQUENCE = """\
        # save_nef_molecular_system

        loop_
           _nef_sequence.chain_code
           _nef_sequence.residue_name

          A   ALA
          A   GLY
          A   VAL

        stop_

        # save_

    """


EXPECTED_SEQUENCE_WITH_INDEX = """\
        # save_nef_molecular_system

        loop_
           _nef_sequence.index
           _nef_sequence.chain_code
           _nef_sequence.residue_name

          1   A   ALA
          2   A   GLY
          3   A   VAL

        stop_

        # save_

    """


EXPECTED_CCPN_DATA_KEY = """\
        # save_ccpn_additional_data_1

        loop_
           _ccpn_data.key

          frame1_key1
          frame1_key2

        stop_

        # save_

        # save_ccpn_additional_data_2

        loop_
           _ccpn_data.key

          frame2_key1
          frame2_key2

        stop_

        # save_

    """


EXPECTED_COMBINED_KEYS_VALUES = """\
        # save_ccpn_additional_data_1

        loop_
           _ccpn_data.key
           _ccpn_data.value

          frame1_key1   frame1_value1
          frame1_key2   frame1_value2

        stop_

        # save_

        # save_ccpn_additional_data_2

        loop_
           _ccpn_data.key
           _ccpn_data.value

          frame2_key1   frame2_value1
          frame2_key2   frame2_value2

        stop_

        # save_

    """


def test_basic_selector():
    """Test basic selection with frame.loop:tags syntax."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        ["--in", path, "molecular_system.nef_sequence:chain_code,residue_name"],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    # In CliRunner (pipe mode), display goes to stderr
    assert_lines_match(EXPECTED_BASIC_SEQUENCE, result.stderr)


def test_wildcard_in_tags():
    """Test wildcard matching in tag names."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    # *name should match residue_name but not chain_code
    result = run_and_report(
        app, ["--in", path, "molecular_system.sequence:*name"], merge_stderr=False
    )

    expected_residue_name = """\
        # save_nef_molecular_system

        loop_
           _nef_sequence.residue_name

          ALA
          GLY
          VAL

        stop_

        # save_

        """
    assert_lines_match(expected_residue_name, result.stderr)


def test_multiple_tags_with_index():
    """Test selecting multiple tags including index."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        ["--in", path, "molecular_system.sequence:index,chain_code,residue_name"],
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_SEQUENCE_WITH_INDEX, result.stderr)


def test_wildcard_in_frame():
    """Test wildcard matching in frame names."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app, ["--in", path, "*ccpn*.ccpn_data:key"], merge_stderr=False
    )

    assert_lines_match(EXPECTED_CCPN_DATA_KEY, result.stderr)


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


def test_default_selector():
    """Test default selector (*.*:*) shows all loops with all tags."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(app, ["--in", path], merge_stderr=False)

    assert result.exit_code == 0

    # Should have molecular_system frame content
    EXPECTED_MOLECULAR_SYSTEM = "nef_molecular_system"
    assert EXPECTED_MOLECULAR_SYSTEM in result.stderr

    # Should have sequence loop
    EXPECTED_SEQUENCE_LOOP = "_nef_sequence"
    assert EXPECTED_SEQUENCE_LOOP in result.stderr

    # Should have ccpn data
    EXPECTED_CCPN_DATA = "_ccpn_data"
    assert EXPECTED_CCPN_DATA in result.stderr


EXPECTED_SAVEFRAME_TAG = """\
            # save_nef_molecular_system

            _nef_molecular_system.sf_category   nef_molecular_system
            _nef_molecular_system.sf_framecode  nef_molecular_system

            # save_

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


def test_saveframe_tag_all_frames():
    """Test :tag syntax for saveframe tags across all frames."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(app, ["--in", path, ":sf_category"], merge_stderr=False)

    EXPECTED_ALL_SF_CATEGORIES = """\
        # save_nef_molecular_system

           _nef_molecular_system.sf_category   nef_molecular_system


        # save_

        # save_ccpn_additional_data_1

           _ccpn_additional_data.sf_category   ccpn_additional_data


        # save_

        # save_ccpn_additional_data_2

           _ccpn_additional_data.sf_category   ccpn_additional_data


        # save_
        """

    assert_lines_match(EXPECTED_ALL_SF_CATEGORIES, result.stderr)


def test_wildcard_in_frame_tags():
    """Test wildcard matching in saveframe tag names."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app, ["--in", path, "molecular_system:*category*"], merge_stderr=False
    )

    EXPECTED_WILDCARD_CATEGORY = """\
        # save_nef_molecular_system

           _nef_molecular_system.sf_category   nef_molecular_system


        # save_
        """

    assert_lines_match(EXPECTED_WILDCARD_CATEGORY, result.stderr)


def test_entire_frame_vs_frame_tags():
    """Test distinction between 'name' (entire frame) and 'name:tag' (frame tags)."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    # Entire frame should include loops
    result_entire = run_and_report(
        app, ["--in", path, "molecular_system"], merge_stderr=False
    )

    EXPECTED_ENTIRE_FRAME = """\
        # save_nef_molecular_system

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


        # save_
        """

    assert_lines_match(EXPECTED_ENTIRE_FRAME, result_entire.stderr)

    # Frame tags should NOT include loops
    result_tags = run_and_report(
        app, ["--in", path, "molecular_system:sf_category"], merge_stderr=False
    )

    EXPECTED_FRAME_TAGS_ONLY = """\
        # save_nef_molecular_system

           _nef_molecular_system.sf_category   nef_molecular_system


        # save_
        """

    assert_lines_match(EXPECTED_FRAME_TAGS_ONLY, result_tags.stderr)


def test_head_option():
    """Test --head option shows first N rows with ellipsis."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:chain_code,sequence_code,atom_name,value",
            "--head",
            "--count",
            "5",
        ],
        merge_stderr=False,
    )

    EXPECTED_HEAD_OUTPUT = """\
        # save_nef_chemical_shift_list_default

          loop_
             _nef_chemical_shift.chain_code
             _nef_chemical_shift.sequence_code
             _nef_chemical_shift.atom_name
             _nef_chemical_shift.value
             _nef_chemical_shift.value_uncertainty

            '#2 '   @1     C    174.078751   .
            '#2 '   @1     H    8.507345     0.0031493880
            '#2 '   @1-1   C    175.947447   0.08720577414
            '#2 '   @1-1   CA   56.689055    0.0499432144
            '#1'    @2     C    17.078751    .

        # ... 21 rows omitted ...


          stop_


        # save_
        """

    assert_lines_match(EXPECTED_HEAD_OUTPUT, result.stderr)


def test_middle_option():
    """Test --middle option shows middle N rows with ellipsis."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:chain_code,sequence_code,atom_name,value",
            "--middle",
            "--count",
            "5",
        ],
        merge_stderr=False,
    )

    EXPECTED_MIDDLE_OUTPUT = """\
        # save_nef_chemical_shift_list_default

          loop_
             _nef_chemical_shift.chain_code
             _nef_chemical_shift.sequence_code
             _nef_chemical_shift.atom_name
             _nef_chemical_shift.value
             _nef_chemical_shift.value_uncertainty


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

    assert_lines_match(EXPECTED_MIDDLE_OUTPUT, result.stderr)


def test_tail_option():
    """Test --tail option shows last N rows with ellipsis."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift.chemical_shift:chain_code,sequence_code,atom_name,value",
            "--tail",
            "--count",
            "5",
        ],
        merge_stderr=False,
    )

    EXPECTED_TAIL_OUTPUT = """\
        # save_nef_chemical_shift_list_default

          loop_
             _nef_chemical_shift.chain_code
             _nef_chemical_shift.sequence_code
             _nef_chemical_shift.atom_name
             _nef_chemical_shift.value
             _nef_chemical_shift.value_uncertainty


        # ... 21 rows omitted ...

            B   2-1   CB   4.570846   0.0514681685
            B   3     H    5.111256   0.0019229051
            B   3     N    6.453575   0.0925289285
            B   3-1   C    7.261980   0.0133395288
            B   3-1   CB   8.427729   0.1141368283

          stop_


        # save_
        """

    assert_lines_match(EXPECTED_TAIL_OUTPUT, result.stderr)


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

    EXPECTED_COUNT_OUTPUT = """\
        # save_nef_chemical_shift_list_default

          loop_
             _nef_chemical_shift.chain_code
             _nef_chemical_shift.sequence_code
             _nef_chemical_shift.atom_name
             _nef_chemical_shift.value
             _nef_chemical_shift.value_uncertainty

            '#2 '   @1     C   174.078751   .
            '#2 '   @1     H   8.507345     0.0031493880
            '#2 '   @1-1   C   175.947447   0.08720577414

        # ... 23 rows omitted ...


          stop_


        # save_
        """

    assert_lines_match(EXPECTED_COUNT_OUTPUT, result.stderr)


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

    EXPECTED_NO_TRUNCATION = """\
        # save_nef_molecular_system

        loop_
           _nef_sequence.chain_code
           _nef_sequence.residue_name

          A   ALA
          A   GLY
          A   VAL

        stop_


        # save_
        """

    assert_lines_match(EXPECTED_NO_TRUNCATION, result.stderr)


def test_default_behaviour_in_cli_runner():
    """\
    Test default behaviour in CLI runner (CliRunner makes stdout non-TTY).

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

    EXPECTED_ADDITIVE_OUTPUT = """\
        # save_nef_chemical_shift_list_default

          loop_
             _nef_chemical_shift.chain_code
             _nef_chemical_shift.sequence_code
             _nef_chemical_shift.atom_name
             _nef_chemical_shift.value
             _nef_chemical_shift.value_uncertainty

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

    assert_lines_match(EXPECTED_ADDITIVE_OUTPUT, result.stderr)


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
    EXPECTED_OUTPUT = """\
        # save_nef_molecular_system

        loop_
           _nef_sequence.chain_code
           _nef_sequence.sequence_code
           _nef_sequence.residue_name

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

    """

    assert_lines_match(EXPECTED_OUTPUT, result.stderr)


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
    EXPECTED_OUTPUT = """\
        # save_nef_molecular_system

        loop_
           _nef_sequence.chain_code
           _nef_sequence.sequence_code
           _nef_sequence.residue_name

          A   1   ALA

         # ... 1 rows omitted ...

          A   3   VAL

        stop_

        # save_

    """

    assert_lines_match(EXPECTED_OUTPUT, result.stderr)


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

    # Should have loop structure but no comments
    EXPECTED_NO_SAVE_COMMENTS = """\
        loop_
           _nef_sequence.chain_code
           _nef_sequence.residue_name

          A   ALA
          A   GLY
          A   VAL

        stop_
        """
    assert_lines_match(EXPECTED_NO_SAVE_COMMENTS, result.stderr)


def test_tags_only():
    """Test --tags-only shows only saveframe tags."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system:*",
            "--tags-only",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0

    # Should have saveframe tags but not loops
    EXPECTED_TAGS_ONLY = """\
        # save_nef_molecular_system

        _nef_molecular_system.sf_category   nef_molecular_system
        _nef_molecular_system.sf_framecode  nef_molecular_system

        # save_
        """
    assert_lines_match(EXPECTED_TAGS_ONLY, result.stderr)


def test_tags_only_with_loop_selector():
    """Test --tags-only with loop selector shows placeholder comment."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system.sequence:*",
            "--tags-only",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0

    # Should have placeholder comment (no frame comments for placeholder-only output)
    EXPECTED_LOOP_NOT_SHOWN = "# loop not shown: _nef_sequence"
    assert_lines_match(EXPECTED_LOOP_NOT_SHOWN, result.stderr)


def test_loops_only():
    """Test --loops-only shows only loop data."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "molecular_system.sequence:*",
            "--loops-only",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0

    # Should have loop structure with frame comments
    EXPECTED_LOOPS_ONLY = """\
        # save_nef_molecular_system

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
        """
    assert_lines_match(EXPECTED_LOOPS_ONLY, result.stderr)


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

    EXPECTED_NO_COMMENTS_OUTPUT = """\
        loop_
           _nef_chemical_shift.chain_code
           _nef_chemical_shift.sequence_code

          '#2 '   @1
          '#2 '   @1
          '#2 '   @1-1

        stop_
        """

    assert_lines_match(EXPECTED_NO_COMMENTS_OUTPUT, result.stderr)


def test_namespace_include():
    """Test --namespace +nef includes nef frames and frames with nef children (hierarchical)."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    EXPECTED_NEF_INCLUDE = """\
        # save_nef_molecular_system

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

        # save_ccpn_additional_data_1

        loop_
           _ccpn_data.key
           _ccpn_data.value

          frame1_key1   frame1_value1
          frame1_key2   frame1_value2

        stop_

        # save_

        # save_ccpn_additional_data_2

        loop_
           _ccpn_data.key
           _ccpn_data.value

          frame2_key1   frame2_value1
          frame2_key2   frame2_value2

        stop_

        # save_
        """

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


def test_namespace_exclude():
    """Test --namespace -nef with hierarchical logic.

    Hierarchical logic: Frames are excluded if namespace matches AND no children in other namespaces.
    ccpn frames have ccpn loops (_ccpn_data) with ccpn children (key, value inherit ccpn namespace),
    so they are included with -nef.
    """
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    # EXPECTED: ccpn frames shown because:
    # - nef_molecular_system is nef namespace -> excluded
    # - ccpn frames have ccpn children (_ccpn_data loop with key/value columns) -> included
    EXPECTED_NEF_EXCLUDE = """\
        # save_ccpn_additional_data_1

        loop_
           _ccpn_data.key
           _ccpn_data.value

          frame1_key1   frame1_value1
          frame1_key2   frame1_value2

        stop_

        # save_

        # save_ccpn_additional_data_2

        loop_
           _ccpn_data.key
           _ccpn_data.value

          frame2_key1   frame2_value1
          frame2_key2   frame2_value2

        stop_

        # save_
        """

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
    """Test --namespace -nef --no-initial-selection with hierarchical logic.

    --no-initial-selection starts with EMPTY, then -nef excludes nef from empty set.
    Result is empty (same as test_namespace_exclude).
    """
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    # EXPECTED: Empty output (start empty, exclude nef from nothing)
    EXPECTED_NEF_INVERT = ""

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "*.*:*",
            "--namespace",
            "-nef",
            "--no-initial-selection",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_NEF_INVERT, result.stderr)


def test_namespace_multiple():
    """Test --namespace with multiple selectors (-,+ccpn clears all then adds ccpn)."""
    path = path_in_test_data(__file__, "multi_frame_test.nef")

    EXPECTED_NAMESPACE_MULTIPLE = """\
        # save_ccpn_additional_data_1

           _ccpn_additional_data.sf_category   ccpn_additional_data
           _ccpn_additional_data.sf_framecode  ccpn_additional_data_1

        # save_

        # save_ccpn_additional_data_2

           _ccpn_additional_data.sf_category   ccpn_additional_data
           _ccpn_additional_data.sf_framecode  ccpn_additional_data_2

        # save_
    """

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


def test_namespace_filter_tags():
    """Test --namespace filters individual tags (ccpn tags should be excluded)."""
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    EXPECTED_NAMESPACE_FILTER_TAGS = """\
        # save_nef_chemical_shift_list_default

           _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_default

        # save_
    """

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift:*",
            "--tags-only",
            "--namespace",
            "-ccpn",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_NAMESPACE_FILTER_TAGS, result.stderr)


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

    EXPECTED_NAMESPACE_FILTERED = """\
        # save_nef_chemical_shift_list_default

          loop_
             _nef_chemical_shift.chain_code
             _nef_chemical_shift.sequence_code
             _nef_chemical_shift.residue_name
             _nef_chemical_shift.atom_name
             _nef_chemical_shift.value
             _nef_chemical_shift.value_uncertainty
             _nef_chemical_shift.element
             _nef_chemical_shift.isotope_number

            '#2 '   @1   .   C   174.078751   .              C   13
            '#2 '   @1   .   H   8.507345     0.0031493880   H   1

        # ... 24 rows omitted ...


          stop_


        # save_
        """

    assert_lines_match(EXPECTED_NAMESPACE_FILTERED, result.stderr)


def test_namespace_hierarchical_tags_only():
    """Test --namespace with hierarchical filtering in tags-only mode.

    With -,+ccpn (clear all, add ccpn), should show only ccpn-namespaced tags
    from the shift frame.
    """
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    EXPECTED_CCPN_TAGS = """\
        _nef_chemical_shift_list.ccpn_serial        1
        _nef_chemical_shift_list.ccpn_auto_update   true
        _nef_chemical_shift_list.ccpn_is_simulated  false
        _nef_chemical_shift_list.ccpn_comment       .
    """

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "shift:*",
            "--tags-only",
            "--namespace",
            "-,+ccpn",
            "--no-comments",
        ],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_CCPN_TAGS, result.stderr)


def test_frame_tags_selector_consistent_with_tags_only():
    """\
    Test that *:* (frame tags selector) produces same output with/without --tags-only.

    Since *:* selects only frame tags (not loops), the --tags-only flag should be
    redundant and produce identical output. This verifies the namespace filtering
    works correctly at the frame level even when --tags-only is specified.

    With --namespace -nef, only ccpn-namespaced tags should be shown from nef frames.
    """
    path = path_in_test_data(__file__, "ubiquitin_short_unassign.nef")

    EXPECTED_FRAME_TAGS_NO_NEF = """\
        # save_nef_chemical_shift_list_default

           _nef_chemical_shift_list.ccpn_serial        1
           _nef_chemical_shift_list.ccpn_auto_update   true
           _nef_chemical_shift_list.ccpn_is_simulated  false
           _nef_chemical_shift_list.ccpn_comment       .

        # save_
    """

    # Run without --tags-only
    result_without = run_and_report(
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

    # Run with --tags-only
    result_with = run_and_report(
        app,
        [
            "--in",
            path,
            "*:*",
            "--namespace",
            "-nef",
            "--tags-only",
        ],
        merge_stderr=False,
    )

    assert result_without.exit_code == 0
    assert result_with.exit_code == 0

    # Both should produce identical output
    assert (
        result_without.stderr == result_with.stderr
    ), "Output should be identical for *:* selector with/without --tags-only"

    # Check against expected output
    assert_lines_match(EXPECTED_FRAME_TAGS_NO_NEF, result_without.stderr)
