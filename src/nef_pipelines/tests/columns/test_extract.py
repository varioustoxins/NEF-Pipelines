import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.columns.extract import extract

EXIT_ERROR = 1

app = typer.Typer()
app.command()(extract)

NEF_WITH_SHIFT_LOOP = read_test_data("nef_with_shift_loop.nef", __file__)

EXPECTED_EXTRACT_CSV_VALUE = """\
    value
    123.22
    8.90
"""

EXPECTED_EXTRACT_CSV_TWO_COLUMNS = """\
    atom_name,value
    N,123.22
    H,8.90
"""


def test_extract_single_column_to_file(tmp_path):
    out_path = tmp_path / "extracted.dat"
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--out",
            str(out_path),
            "myshifts.chemical_shift:value",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    assert result.exit_code == 0
    assert_lines_match(EXPECTED_EXTRACT_CSV_VALUE, out_path.read_text())

    assert_lines_match(NEF_WITH_SHIFT_LOOP, result.stdout)


def test_extract_two_columns(tmp_path):
    out_path = tmp_path / "extracted.csv"
    run_and_report(
        app,
        [
            "--in",
            "-",
            "--out",
            str(out_path),
            "myshifts.chemical_shift:atom_name,value",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    assert_lines_match(EXPECTED_EXTRACT_CSV_TWO_COLUMNS, out_path.read_text())
