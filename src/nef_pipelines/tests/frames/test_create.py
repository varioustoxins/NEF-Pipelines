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


def test_create_single_frame():
    result = run_and_report(app, ["nef_chemical_shift_list", "myshifts"])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    assert "nef_chemical_shift_list_myshifts" in frame_names
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
    frame_names = list(entry.frame_dict.keys())

    assert "nef_chemical_shift_list_myshifts" in frame_names
    assert "nef_rdc_restraint_list_myrdcs" in frame_names


def test_create_duplicate_errors_without_force():
    first = run_and_report(app, ["nef_chemical_shift_list", "myshifts"])

    result = run_and_report(
        app,
        ["--in", "-", "nef_chemical_shift_list", "myshifts"],
        input=first.stdout,
        expected_exit_code=EXIT_ERROR,
    )

    assert "already exists" in result.stdout


def test_create_force_overwrites_duplicate():
    first = run_and_report(app, ["nef_chemical_shift_list", "myshifts"])

    # Add a marker tag to the frame to verify it gets replaced
    entry = Entry.from_string(first.stdout)
    frame = entry.get_saveframe_by_name("nef_chemical_shift_list_myshifts")
    frame.add_tag("test_marker", "original_frame")
    modified_input = str(entry)

    # Recreate with --force
    result = run_and_report(
        app,
        ["--in", "-", "--force", "nef_chemical_shift_list", "myshifts"],
        input=modified_input,
    )

    # Verify frame exists and marker tag is gone (frame was replaced)
    final_entry = Entry.from_string(result.stdout)
    final_frame = final_entry.get_saveframe_by_name("nef_chemical_shift_list_myshifts")

    assert final_frame is not None
    assert "test_marker" not in final_frame.tags


def test_create_singleton_from_bare_category():
    result = run_and_report(app, ["nef_chemical_shift_list"])

    entry = Entry.from_string(result.stdout)
    frame = entry.get_saveframe_by_name("nef_chemical_shift_list")

    assert frame is not None
    assert frame.get_tag("sf_category")[0] == "nef_chemical_shift_list"
    assert frame.get_tag("sf_framecode")[0] == "nef_chemical_shift_list"


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
        # Odd number of args: last becomes singleton
        (
            ["nef_chemical_shift_list", "shifts1", "nef_rdc_restraint_list"],
            ["nef_chemical_shift_list_shifts1", "nef_rdc_restraint_list"],
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
    ],
)
def test_create_format_errors(args, expected_error):
    """Test error handling for invalid format specifications."""
    result = run_and_report(app, args, expected_exit_code=EXIT_ERROR)
    assert expected_error in result.stdout.lower()


def test_create_singleton_produces_correct_framecode():
    """Verify singleton frames have category == framecode (no trailing underscore)."""
    result = run_and_report(app, ["nef_molecular_system."])
    entry = Entry.from_string(result.stdout)

    frame = entry.get_saveframe_by_name("nef_molecular_system")
    # tag_prefix includes leading underscore per STAR format
    assert frame.tag_prefix == "_nef_molecular_system"
    assert frame.get_tag("sf_category")[0] == "nef_molecular_system"
    assert frame.get_tag("sf_framecode")[0] == "nef_molecular_system"


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
