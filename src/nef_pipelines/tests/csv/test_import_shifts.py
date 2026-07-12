import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.csv.importers.shifts import shifts

EXIT_ERROR = 1

app = typer.Typer()
app.command()(shifts)


EXPECTED_SHIFT_LOOP_DEFAULT_CHAIN = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      A   2   GLN   N   123.22
      A   2   GLN   H   8.90
      A   3   ILE   N   115.34
      A   3   ILE   H   8.32

    stop_
"""

EXPECTED_SHIFT_LOOP_WITH_CHAIN = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty

      A   2   GLN   N   123.22   0.1
      A   2   GLN   H   8.90     0.05
      A   3   ILE   N   115.34   0.1
      A   3   ILE   H   8.32     0.05

    stop_
"""


def test_shifts_import_default_chain():
    csv_path = path_in_test_data(__file__, "shifts_basic.csv")

    result = run_and_report(app, ["myshifts", csv_path])

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP_DEFAULT_CHAIN, loop_text)


def test_shifts_import_with_chain_in_csv():
    csv_path = path_in_test_data(__file__, "shifts_with_chain.csv")

    result = run_and_report(app, ["myshifts", csv_path])

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP_WITH_CHAIN, loop_text)


def test_shifts_import_explicit_chain():
    csv_path = path_in_test_data(__file__, "shifts_basic.csv")

    result = run_and_report(app, ["-c", "B", "myshifts", csv_path])

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert "B" in loop_text
    assert "A" not in loop_text.split("loop_")[1]


def test_shifts_import_missing_value_column_errors():
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write("sequence_code,atom_name\n")
        tmp.write("2,N\n")
        bad_csv = Path(tmp.name)

    try:
        result = run_and_report(
            app,
            ["myshifts", str(bad_csv)],
            expected_exit_code=EXIT_ERROR,
        )
        assert "value" in result.stdout
    finally:
        bad_csv.unlink(missing_ok=True)


def test_shifts_import_odd_args_errors():
    result = run_and_report(
        app,
        ["myshifts"],
        expected_exit_code=EXIT_ERROR,
    )

    assert "pairs" in result.stdout


def test_shifts_import_with_comment_filter():
    csv_path = path_in_test_data(__file__, "shifts_with_comments.csv")

    result = run_and_report(app, ["--comment", "#", "myshifts", csv_path])

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP_DEFAULT_CHAIN, loop_text)


def test_shifts_import_with_skip():
    csv_path = path_in_test_data(__file__, "shifts_with_skip.csv")

    result = run_and_report(app, ["--skip", "1", "myshifts", csv_path])

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP_DEFAULT_CHAIN, loop_text)
