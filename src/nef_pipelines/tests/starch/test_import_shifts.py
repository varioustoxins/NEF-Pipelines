import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.starch.importers.shifts import (
    ColumnSelector,
    SequenceSource,
    _select_column,
    shifts,
)

app = typer.Typer()
app.command()(shifts)


def test_shifts_basic():
    """Test basic STARCH shift import with single chain."""

    EXPECTED = """\
        save_nef_chemical_shift_list_starch
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_starch

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   1   ASP   CA     52.0      .   .   .
              A   1   ASP   HA     4.22      .   .   .
              A   1   ASP   CB     38.7      .   .   .
              A   2   VAL   CA     60.883    .   .   .
              A   2   VAL   HA     4.249     .   .   .
              A   2   VAL   CB     30.92     .   .   .
              A   3   GLN   CA     53.706    .   .   .
              A   3   GLN   HA     4.581     .   .   .
              A   3   GLN   CB     29.114    .   .   .

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    starch_file = path_in_test_data(__file__, "simple.str")

    result = run_and_report(
        app,
        ["-i", sequence_file, starch_file],
        expected_exit_code=0,
    )

    starch_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_starch")

    assert_lines_match(EXPECTED, starch_frame)


def test_shifts_custom_frame_name():
    """Test STARCH shift import with custom frame name."""

    EXPECTED = """\
        save_nef_chemical_shift_list_my_shifts
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_my_shifts

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   1   ASP   CA     52.0      .   .   .
              A   1   ASP   HA     4.22      .   .   .
              A   1   ASP   CB     38.7      .   .   .
              A   2   VAL   CA     60.883    .   .   .
              A   2   VAL   HA     4.249     .   .   .
              A   2   VAL   CB     30.92     .   .   .
              A   3   GLN   CA     53.706    .   .   .
              A   3   GLN   HA     4.581     .   .   .
              A   3   GLN   CB     29.114    .   .   .

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    starch_file = path_in_test_data(__file__, "simple.str")

    result = run_and_report(
        app,
        ["-i", sequence_file, "--frame-name", "my_shifts", starch_file],
        expected_exit_code=0,
    )

    custom_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_my_shifts")

    assert_lines_match(EXPECTED, custom_frame)


def test_shifts_custom_chain():
    """Test STARCH shift import with custom chain code."""

    EXPECTED = """\
        save_nef_chemical_shift_list_starch
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_starch

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              B   1   ASP   CA     52.0      .   .   .
              B   1   ASP   HA     4.22      .   .   .
              B   1   ASP   CB     38.7      .   .   .
              B   2   VAL   CA     60.883    .   .   .
              B   2   VAL   HA     4.249     .   .   .
              B   2   VAL   CB     30.92     .   .   .
              B   3   GLN   CA     53.706    .   .   .
              B   3   GLN   HA     4.581     .   .   .
              B   3   GLN   CB     29.114    .   .   .

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    starch_file = path_in_test_data(__file__, "simple.str")

    result = run_and_report(
        app,
        ["-i", sequence_file, "--chains", "B", starch_file],
        expected_exit_code=0,
    )

    starch_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_starch")

    assert_lines_match(EXPECTED, starch_frame)


def test_shifts_rna():
    """Test STARCH shift import with RNA (auto-detected molecule type).

    Note: Test data is synthetic and not related to any specific source file.
    """
    EXPECTED = """\
        save_nef_chemical_shift_list_starch
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_starch

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   1   G   C1'    92.2      0.01   C   13
              A   1   G   C2'    64.522    0.01   C   13
              A   1   G   C3'    78.431    0.01   C   13
              A   1   G   C4'    85.649    0.01   C   13
              A   1   G   C5'    73.283    0.01   C   13
              A   2   C   C1'    94.992    0.01   C   13
              A   2   C   C2'    76.343    0.01   C   13
              A   2   C   C3'    73.118    0.01   C   13
              A   2   C   C4'    88.408    0.01   C   13
              A   2   C   C5     100.487   0.01   C   13
              A   3   A   C1'    104.103   0.01   C   13
              A   3   A   C2     155.239   0.01   C   13
              A   3   A   C2'    74.469    0.01   C   13
              A   3   A   C3'    71.858    0.01   C   13
              A   3   A   C4'    76.867    0.01   C   13
              A   4   U   C1'    95.488    0.01   C   13
              A   4   U   C2'    69.942    0.01   C   13
              A   4   U   C3'    91.197    0.01   C   13
              A   4   U   C4'    98.323    0.01   C   13
              A   4   U   C5     122.826   0.01   C   13

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    rna_file = path_in_test_data(__file__, "rna.str")

    result = run_and_report(
        app,
        ["-i", sequence_file, rna_file],
        expected_exit_code=0,
    )

    starch_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_starch")

    assert_lines_match(EXPECTED, starch_frame)


def test_shifts_auth_numbering():
    """Test STARCH shift import with Auth_* columns (author numbering)."""

    EXPECTED = """\
        save_nef_chemical_shift_list_starch
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_starch

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   100   ASP   CA    52.0    .   .   .
              A   100   ASP   HA    4.22    .   .   .
              A   101   VAL   CA    60.8    .   .   .
              A   101   VAL   HA    4.25    .   .   .
              A   102   GLN   CA    53.7    .   .   .
              A   102   GLN   HA    4.58    .   .   .

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    auth_file = path_in_test_data(__file__, "auth_numbering.str")

    result = run_and_report(
        app,
        ["-i", sequence_file, auth_file],
        expected_exit_code=0,
    )

    starch_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_starch")

    assert_lines_match(EXPECTED, starch_frame)


def test_shifts_mixed_auth_system_columns():
    """Test STARCH shift import with mixed Auth_* and standard columns (should prefer Auth).

    When both Auth_* and standard columns are present, the importer should prefer Auth_*
    columns for sequence_code, residue_name, and atom_name.
    """

    EXPECTED = """\
        save_nef_chemical_shift_list_starch
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_starch

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   100   ASP   CA    52.0    .   .   .
              A   100   ASP   HA    4.22    .   .   .
              A   101   VAL   CA    60.8    .   .   .
              A   101   VAL   HA    4.25    .   .   .

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    mixed_file = path_in_test_data(__file__, "mixed_auth_system.str")

    result = run_and_report(
        app,
        ["-i", sequence_file, "--molecule-type", "protein", mixed_file],
        expected_exit_code=0,
    )

    starch_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_starch")

    assert_lines_match(EXPECTED, starch_frame)


# Column selection unit tests


def test_select_column_auth_mode_finds_auth():
    """Test AUTH mode prefers Auth_* column when available."""
    tag_to_index = {"Auth_seq_ID": 0, "Seq_ID": 1, "Comp_index_ID": 2}

    result = _select_column(
        tag_to_index, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.AUTH
    )

    EXPECTED = ColumnSelector(name="Auth_seq_ID", index=0)
    assert result == EXPECTED


def test_select_column_auth_mode_falls_back_to_system():
    """Test AUTH mode falls back to system column when Auth_* missing."""
    tag_to_index = {"Seq_ID": 1, "Comp_index_ID": 2}

    result = _select_column(
        tag_to_index, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.AUTH
    )

    EXPECTED = ColumnSelector(name="Seq_ID", index=1)
    assert result == EXPECTED


def test_select_column_auth_mode_falls_back_to_fallback():
    """Test AUTH mode falls back to fallback when Auth_* and system missing."""
    tag_to_index = {"Comp_index_ID": 2}

    result = _select_column(
        tag_to_index, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.AUTH
    )

    EXPECTED = ColumnSelector(name="Comp_index_ID", index=2)
    assert result == EXPECTED


def test_select_column_auth_mode_returns_none_when_all_missing():
    """Test AUTH mode returns None when all columns missing."""
    tag_to_index = {"Val": 0}

    result = _select_column(
        tag_to_index, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.AUTH
    )

    EXPECTED = ColumnSelector(name=None, index=None)
    assert result == EXPECTED


def test_select_column_system_mode_skips_auth():
    """Test SYSTEM mode skips Auth_* column even when available."""
    tag_to_index = {"Auth_seq_ID": 0, "Seq_ID": 1, "Comp_index_ID": 2}

    result = _select_column(
        tag_to_index, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.SYSTEM
    )

    EXPECTED = ColumnSelector(name="Seq_ID", index=1)
    assert result == EXPECTED


def test_select_column_system_mode_uses_fallback():
    """Test SYSTEM mode uses fallback when system column missing."""
    tag_to_index = {"Auth_seq_ID": 0, "Comp_index_ID": 2}

    result = _select_column(
        tag_to_index, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.SYSTEM
    )

    EXPECTED = ColumnSelector(name="Comp_index_ID", index=2)
    assert result == EXPECTED


def test_select_column_system_mode_returns_none_when_missing():
    """Test SYSTEM mode returns None when system and fallback missing (Auth present but skipped)."""
    tag_to_index = {"Auth_seq_ID": 0}

    result = _select_column(
        tag_to_index, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.SYSTEM
    )

    EXPECTED = ColumnSelector(name=None, index=None)
    assert result == EXPECTED


def test_select_column_no_fallback_auth_mode():
    """Test column selection without fallback in AUTH mode."""
    tag_to_index = {"Auth_comp_ID": 0, "Comp_ID": 1}

    result = _select_column(
        tag_to_index, "Auth_comp_ID", "Comp_ID", None, SequenceSource.AUTH
    )

    EXPECTED = ColumnSelector(name="Auth_comp_ID", index=0)
    assert result == EXPECTED


def test_select_column_no_fallback_system_mode():
    """Test column selection without fallback in SYSTEM mode."""
    tag_to_index = {"Auth_comp_ID": 0, "Comp_ID": 1}

    result = _select_column(
        tag_to_index, "Auth_comp_ID", "Comp_ID", None, SequenceSource.SYSTEM
    )

    EXPECTED = ColumnSelector(name="Comp_ID", index=1)
    assert result == EXPECTED


def test_select_column_no_fallback_returns_none():
    """Test column selection returns None when no fallback and primary columns missing."""
    tag_to_index = {"Val": 0}

    result = _select_column(
        tag_to_index, "Auth_comp_ID", "Comp_ID", None, SequenceSource.AUTH
    )

    EXPECTED = ColumnSelector(name=None, index=None)
    assert result == EXPECTED
