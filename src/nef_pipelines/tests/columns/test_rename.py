import pytest
import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.columns.rename import rename

EXIT_ERROR = 1

app = typer.Typer()
app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)(rename)

NEF_WITH_SHIFT_LOOP = read_test_data("nef_with_shift_loop.nef", __file__)

EXPECTED_SINGLE_RENAME = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.chemical_shift_value

      A   2   GLN   N   123.22
      A   2   GLN   H   8.90

    stop_
"""

EXPECTED_MULTI_RENAME = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.seq_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.shift_value

      A   2   GLN   N   123.22
      A   2   GLN   H   8.90

    stop_
"""

EXPECTED_SWAP_RENAME = """\
    loop_
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      A   2   GLN   N   123.22
      A   2   GLN   H   8.90

    stop_
"""

EXPECTED_ERROR_COLUMN_NOT_FOUND = """\
ERROR [in: rename]: column 'nonexistent' not found in loop nef_chemical_shift

exiting...
"""

EXPECTED_ERROR_UNPAIRED_BARE_NAME = """\
ERROR [in: rename]: unpaired tag 'no_equals_sign' - tags must come in pairs [entry 'test']

exiting...
"""

EXPECTED_ERROR_EMPTY_OLD = """\
ERROR [in: rename]: tag name is empty in rename spec '=missing_old' [entry 'test']

exiting...
"""

EXPECTED_ERROR_EMPTY_NEW = """\
ERROR [in: rename]: new name is empty in rename spec 'missing_new=' [entry 'test']

exiting...
"""


@pytest.mark.parametrize(
    "rename_specs, expected",
    [
        (["value=chemical_shift_value"], EXPECTED_SINGLE_RENAME),
        (["sequence_code=seq_code", "value=shift_value"], EXPECTED_MULTI_RENAME),
        (
            ["chain_code=sequence_code", "sequence_code=chain_code"],
            EXPECTED_SWAP_RENAME,
        ),
    ],
    ids=["single", "multiple", "swap"],
)
def test_rename(rename_specs, expected):
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift"] + rename_specs,
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(expected, loop_text)


@pytest.mark.parametrize(
    "rename_spec, expected_error",
    [
        ("no_equals_sign", EXPECTED_ERROR_UNPAIRED_BARE_NAME),
        ("=missing_old", EXPECTED_ERROR_EMPTY_OLD),
        ("missing_new=", EXPECTED_ERROR_EMPTY_NEW),
        ("nonexistent=new_name", EXPECTED_ERROR_COLUMN_NOT_FOUND),
    ],
    ids=["unpaired-bare", "empty-old", "empty-new", "not-found"],
)
def test_rename_errors(rename_spec, expected_error):
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", rename_spec],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    assert_lines_match(expected_error, result.stdout)
