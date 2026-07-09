import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.columns.list_ import list_

app = typer.Typer()
app.command("list")(list_)


NEF_WITH_SHIFT_LOOP = read_test_data("nef_with_shift_loop.nef", __file__)


def test_list_all_columns():
    EXPECTED = """\
        nef_chemical_shift_list_myshifts.nef_chemical_shift: chain_code, sequence_code, residue_name, atom_name, value
    """

    result = run_and_report(
        app,
        ["--in", "-", "myshifts.chemical_shift"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    assert_lines_match(EXPECTED, result.stderr)


def test_list_specific_column():
    EXPECTED = """\
        nef_chemical_shift_list_myshifts.nef_chemical_shift: value
    """

    result = run_and_report(
        app,
        ["--in", "-", "myshifts.chemical_shift:value"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    assert_lines_match(EXPECTED, result.stderr)


def test_list_wildcard_column_filter():
    EXPECTED = """\
        nef_chemical_shift_list_myshifts.nef_chemical_shift: chain_code, sequence_code
    """

    result = run_and_report(
        app,
        ["--in", "-", "myshifts.chemical_shift:code"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    assert_lines_match(EXPECTED, result.stderr)


def test_list_no_match_produces_no_column_output():
    result = run_and_report(
        app,
        ["--in", "-", "nonexistent.loop"],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )
    assert result.stderr.strip() == ""
    assert_lines_match(NEF_WITH_SHIFT_LOOP, result.stdout)
