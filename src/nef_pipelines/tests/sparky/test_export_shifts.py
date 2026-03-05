import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
    select_tagged_lines,
)
from nef_pipelines.transcoders.sparky.exporters.shifts import shifts

app = typer.Typer()
app.command()(shifts)

INPUT_NEF_SHIFTS = read_test_data("ubiquitin_short_assigned.nef", __file__)

EXPECTED_BASIC_EXPORT = """\
    Group    Atom    Nuc      Shift    SDev    Assignments
    A10      H       1H       8.111   0.002              1
    A10      N       15N    102.454   0.093              1
    A10      C       13C    177.262   0.013              1
    A10      CA      13C     52.491   0                  1
    A10      CB      13C     16.428   0.114              1
"""

EXPECTED_MINIMAL_EXPORT = """\
    Group    Atom    Nuc      Shift    SDev    Assignments
    A1       CA      13C       52.5     0.1              1
"""

MINIMAL_NEF_INPUT = """\
data_test

save_nef_molecular_system
   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system

   loop_
      _nef_sequence.index
      _nef_sequence.chain_code
      _nef_sequence.sequence_code
      _nef_sequence.residue_name
      _nef_sequence.linking
      _nef_sequence.residue_variant
      _nef_sequence.cis_peptide

      1   A   1   ALA   start    .   .

   stop_

save_

save_nef_chemical_shift_list_test
   _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
   _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test

   loop_
      _nef_chemical_shift.chain_code
      _nef_chemical_shift.sequence_code
      _nef_chemical_shift.residue_name
      _nef_chemical_shift.atom_name
      _nef_chemical_shift.value
      _nef_chemical_shift.value_uncertainty
      _nef_chemical_shift.element
      _nef_chemical_shift.isotope_number

      A   1   ALA   CA   52.5   0.1   C   13

   stop_

save_
"""


def test_basic_export_to_stdout():
    """Test basic shift export from NEF to Sparky format to stdout."""

    result = run_and_report(
        app, ["-o", "-", "nef_chemical_shift_list_default"], input=INPUT_NEF_SHIFTS
    )

    assert_lines_match(EXPECTED_BASIC_EXPORT, result.stdout)


def test_export_all_shift_frames_with_wildcard():
    """Test exporting all chemical shift frames using wildcard."""

    result = run_and_report(app, ["-o", "-", "*def*"], input=INPUT_NEF_SHIFTS)

    assert_lines_match(EXPECTED_BASIC_EXPORT, result.stdout)


def test_export_default_selector():
    """Test export with default frame selector exports all shift frames."""

    result = run_and_report(app, ["-o", "-"], input=INPUT_NEF_SHIFTS)

    assert_lines_match(EXPECTED_BASIC_EXPORT, result.stdout)


def test_export_minimal_single_shift():
    """Test export with minimal NEF file containing single shift."""

    result = run_and_report(app, ["-o", "-"], input=MINIMAL_NEF_INPUT)

    assert_lines_match(EXPECTED_MINIMAL_EXPORT, result.stdout)


def test_no_shift_frames_warning():
    """Test warning when no shift frames match selectors."""

    result = run_and_report(
        app,
        ["-o", "-", "nonexistent_frame"],
        input=INPUT_NEF_SHIFTS,
        expected_exit_code=0,
    )

    warnings, _ = select_tagged_lines(result.stdout)

    assert len(warnings) == 1

    EXPECTED_NO_FRAMES_WARNING = (
        "WARNING: No chemical shift frames found matching selectors nonexistent_frame"
    )

    assert warnings[0] == EXPECTED_NO_FRAMES_WARNING
