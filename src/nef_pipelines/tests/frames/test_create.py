import pytest
import typer
from pynmrstar import Entry

from nef_pipelines.lib.test_lib import assert_lines_match, isolate_frame, run_and_report
from nef_pipelines.tools.frames.create import create

EXIT_ERROR = 1

app = typer.Typer()
app.command()(create)


EXPECTED_SHIFT_LIST_FRAME = """\
    save_nef_chemical_shift_list_myshifts
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_myshifts

    save_
"""

EXPECTED_RDC_RESTRAINT_LIST_FRAME = """\
    save_nef_rdc_restraint_list_myrdcs
       _nef_rdc_restraint_list.sf_category   nef_rdc_restraint_list
       _nef_rdc_restraint_list.sf_framecode  nef_rdc_restraint_list_myrdcs

    save_
"""

EXPECTED_SINGLETON_FRAME = """\
    save_nef_chemical_shift_list
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list

    save_
"""

EXPECTED_MOLECULAR_SYSTEM_FRAME = """\
    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

    save_
"""

EXPECTED_DUPLICATE_WARNING = (
    "WARNING: frame nef_chemical_shift_list_myshifts already exists, replacing it"
)


def test_create_single_frame():
    result = run_and_report(app, ["nef_chemical_shift_list", "myshifts"])

    entry = Entry.from_string(result.stdout)
    frame_names = set(entry.frame_dict.keys())

    # Complete set: metadata + created frame
    expected_frames = {"nef_nmr_meta_data", "nef_chemical_shift_list_myshifts"}
    assert frame_names == expected_frames

    # Verify frame structure
    assert_lines_match(
        EXPECTED_SHIFT_LIST_FRAME,
        isolate_frame(result.stdout, "nef_chemical_shift_list_myshifts"),
    )


def test_create_multiple_frames():
    result = run_and_report(
        app,
        [
            "nef_chemical_shift_list",
            "myshifts",
            "nef_rdc_restraint_list",
            "myrdcs",
        ],
    )

    entry = Entry.from_string(result.stdout)
    frame_names = set(entry.frame_dict.keys())

    # Complete set of frames: metadata + the two created frames
    expected_frames = {
        "nef_nmr_meta_data",
        "nef_chemical_shift_list_myshifts",
        "nef_rdc_restraint_list_myrdcs",
    }
    assert frame_names == expected_frames

    # Verify complete structure of both frames
    assert_lines_match(
        EXPECTED_SHIFT_LIST_FRAME,
        isolate_frame(result.stdout, "nef_chemical_shift_list_myshifts"),
    )
    assert_lines_match(
        EXPECTED_RDC_RESTRAINT_LIST_FRAME,
        isolate_frame(result.stdout, "nef_rdc_restraint_list_myrdcs"),
    )


def test_create_duplicate_warns_by_default():
    """By default, creating a duplicate frame succeeds with a warning."""
    first = run_and_report(app, ["nef_chemical_shift_list", "myshifts"])

    result = run_and_report(
        app,
        ["--in", "-", "nef_chemical_shift_list", "myshifts"],
        input=first.stdout,
        merge_stderr=False,
    )

    # Should succeed (not error)
    assert result.exit_code == 0

    # Complete stderr check - exactly the warning, nothing else
    assert result.stderr.strip() == EXPECTED_DUPLICATE_WARNING

    # Verify complete NEF structure
    assert_lines_match(
        EXPECTED_SHIFT_LIST_FRAME,
        isolate_frame(result.stdout, "nef_chemical_shift_list_myshifts"),
    )


def test_create_quiet_suppresses_warning():
    """Using --quiet suppresses the replacement warning."""
    first = run_and_report(app, ["nef_chemical_shift_list", "myshifts"])

    # Add a marker tag to the frame to verify it gets replaced
    entry = Entry.from_string(first.stdout)
    frame = entry.get_saveframe_by_name("nef_chemical_shift_list_myshifts")
    frame.add_tag("test_marker", "original_frame")
    modified_input = str(entry)

    # Recreate with --quiet
    result = run_and_report(
        app,
        ["--in", "-", "--quiet", "nef_chemical_shift_list", "myshifts"],
        input=modified_input,
        merge_stderr=False,
    )

    # Should succeed
    assert result.exit_code == 0

    # Complete stderr check - should be empty (--quiet suppresses)
    assert result.stderr.strip() == ""

    # Verify complete NEF structure (frame was replaced)
    assert_lines_match(
        EXPECTED_SHIFT_LIST_FRAME,
        isolate_frame(result.stdout, "nef_chemical_shift_list_myshifts"),
    )

    # Verify marker tag is gone (confirms replacement happened)
    final_entry = Entry.from_string(result.stdout)
    final_frame = final_entry.get_saveframe_by_name("nef_chemical_shift_list_myshifts")
    assert "test_marker" not in final_frame.tags


def test_create_singleton_from_bare_category():
    """Singleton requires explicit syntax (trailing . or empty string)."""
    result = run_and_report(app, ["nef_chemical_shift_list."])

    assert_lines_match(
        EXPECTED_SINGLETON_FRAME,
        isolate_frame(result.stdout, "nef_chemical_shift_list"),
    )


def test_create_with_entry_name():
    result = run_and_report(
        app,
        ["--entry", "my_project", "nef_chemical_shift_list", "myshifts"],
    )

    entry = Entry.from_string(result.stdout)
    assert entry.entry_id == "my_project"


@pytest.mark.parametrize(
    "args,expected_framecode",
    [
        # Dot notation - single frame
        (["nef_chemical_shift_list.myshifts"], "nef_chemical_shift_list_myshifts"),
        # Dot notation - multiple frames
        (
            ["nef_chemical_shift_list.shifts1", "nef_rdc_restraint_list.rdcs1"],
            ["nef_chemical_shift_list_shifts1", "nef_rdc_restraint_list_rdcs1"],
        ),
        # Comma-separated
        (
            ["nef_chemical_shift_list.shifts1,nef_rdc_restraint_list.rdcs1"],
            ["nef_chemical_shift_list_shifts1", "nef_rdc_restraint_list_rdcs1"],
        ),
        # Mixed: dot notation and pairs
        (
            ["nef_chemical_shift_list.shifts1", "nef_rdc_restraint_list", "rdcs1"],
            ["nef_chemical_shift_list_shifts1", "nef_rdc_restraint_list_rdcs1"],
        ),
        # Singleton with trailing dot
        (["nef_molecular_system."], "nef_molecular_system"),
        # Singleton with explicit empty string
        (["nef_molecular_system", ""], "nef_molecular_system"),
        # Multiple singletons with comma (use --force since nef_nmr_meta_data exists by default)
        # Skip this test - nef_nmr_meta_data already exists in default entry
        # Mixed: singleton and regular frame
        (
            ["nef_molecular_system.", "nef_chemical_shift_list.default"],
            ["nef_molecular_system", "nef_chemical_shift_list_default"],
        ),
    ],
)
def test_create_format_variations(args, expected_framecode):
    """Test all supported input format variations."""
    result = run_and_report(app, args)
    entry = Entry.from_string(result.stdout)

    expected = (
        [expected_framecode]
        if isinstance(expected_framecode, str)
        else expected_framecode
    )
    actual = sorted([name for name in entry.frame_dict if name in expected])

    assert actual == sorted(expected)


@pytest.mark.parametrize(
    "args,expected_error",
    [
        # Invalid dot notation - no category before dot
        ([".myshifts"], "invalid frame specification"),
        # Invalid dot notation - empty category
        ([".."], "invalid frame specification"),
        # Odd number of args - should error (no auto-singleton)
        (
            ["nef_chemical_shift_list", "shifts1", "nef_rdc_restraint_list"],
            "must come in pairs",
        ),
    ],
)
def test_create_format_errors(args, expected_error):
    """Test error handling for invalid format specifications."""
    result = run_and_report(app, args, expected_exit_code=EXIT_ERROR)
    assert expected_error in result.stdout.lower()


def test_create_singleton_produces_correct_framecode():
    """Verify singleton frames have category == framecode (no trailing underscore)."""
    result = run_and_report(app, ["nef_molecular_system."])

    assert_lines_match(
        EXPECTED_MOLECULAR_SYSTEM_FRAME,
        isolate_frame(result.stdout, "nef_molecular_system"),
    )


def test_create_with_escaped_dots():
    """Verify escaped dots (\\.) work in category and id components."""
    # Pair notation with escaped dot in id
    result = run_and_report(app, [r"test_category", r"id\.with\.dots"])
    entry = Entry.from_string(result.stdout)
    assert "test_category_id.with.dots" in entry.frame_dict

    # Dot notation with escaped dots in both parts
    result = run_and_report(app, [r"cat\.egory.id\.part"])
    entry = Entry.from_string(result.stdout)
    assert "cat.egory_id.part" in entry.frame_dict


def test_create_with_escaped_backslashes():
    """Verify escaped backslashes (\\\\) work correctly."""
    # Single escaped backslash in category name
    result = run_and_report(app, [r"cat\\egory", "test"])
    entry = Entry.from_string(result.stdout)
    assert r"cat\egory_test" in entry.frame_dict

    # Two escaped backslashes followed by unescaped dot (should split)
    result = run_and_report(app, [r"cat\\\\.egory"])
    entry = Entry.from_string(result.stdout)
    assert r"cat\\_egory" in entry.frame_dict

    # Escaped backslash followed by escaped dot (should not split)
    result = run_and_report(app, [r"cat\\\.egory", ""])
    entry = Entry.from_string(result.stdout)
    assert r"cat\.egory" in entry.frame_dict
