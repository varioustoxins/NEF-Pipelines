from pathlib import Path
from textwrap import dedent, indent
from typing import List

import typer
from fyeah import f
from pynmrstar import Entry

from nef_pipelines.lib.nef_frames_lib import (
    EXPERIMENT_CLASSIFICATION,
    EXPERIMENT_TYPE,
    SHIFT_LIST_FRAME_CATEGORY,
)
from nef_pipelines.lib.nef_lib import (
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.peak_lib import peaks_to_frame
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.spectra_lib import (
    EXPERIMENT_CLASSIFICATION_TO_SYNONYM,
    EXPERIMENT_INFO,
    SPECTRUM_TYPE_TO_CLASSIFICATION,
    TRIPLE_SPECTRA,
    ExperimentType,
    PeakInfo,
)
from nef_pipelines.lib.structures import NewPeak, ShiftData
from nef_pipelines.lib.util import (
    FOUR_SPACES,
    STDIN,
    exit_error,
    parse_comma_separated_options,
    strings_to_tabulated_terminal_sensitive,
)
from nef_pipelines.tools.shifts import shifts_app

FAKE_SPECTROMETER_FREQUENCY_600 = 600.12345678
SPECTRUM_NAME_TEMPLATE = "synthetic_{spectrum}"

SHIFT_FRAMES_HELP = """\
    the names of the shift frames to use, this can be a comma separated list of name or the option can be called
    called multiple times. Wild cards are allowed. If no match is found wild cards are checked as well unless
    --exact is set
"""

SPECTRA_HELP = f"""
    the names of the spectra to create, this can be a comma separated list of options or
    called multiple times. Possible values are: {', '.join(ExperimentType)}
"""
NAME_TEMPLATE_HELP = """
    the name template for the new peak lists the placeholder {spectrum} will get replaced with the spectrum type
"""


@shifts_app.command()
def make_peaks(
    shift_frame_selectors: List[str] = typer.Option(
        ["default"], help=SHIFT_FRAMES_HELP
    ),
    exact: bool = typer.Option(
        False, help="if set frames are selected by exact matches"
    ),
    spectra: List[str] = typer.Option([ExperimentType.N_HSQC], help=SPECTRA_HELP),
    name_template: str = typer.Option(SPECTRUM_NAME_TEMPLATE, help=NAME_TEMPLATE_HELP),
    spectrometer_frequency: float = typer.Option(FAKE_SPECTROMETER_FREQUENCY_600),
    input: Path = typer.Option(
        STDIN,
        "--in",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
):
    """-  make a set of peaks for an hsqc or triple resonance spectrum from a list of shiftsdbxcli put rh"""

    shift_frames = parse_comma_separated_options(shift_frame_selectors)

    spectra = set(parse_comma_separated_options(spectra))

    spectra = _update_spectra_with_groups(spectra)

    # TODO add a check that we have some shift frames

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    entry = pipe(
        entry, shift_frames, exact, spectra, name_template, spectrometer_frequency
    )

    print(entry)


def _update_spectra_with_groups(spectra):
    if ExperimentType.TRIPLE in spectra:
        spectra.update(TRIPLE_SPECTRA)
        spectra.remove(ExperimentType.TRIPLE)

    return spectra


def _exit_bad_spectrum_type(spectrum, known_spectra):
    msg = """
        the spectrum type {spectrum} is not know, available spectrum types are

        {spectrum_types}
    """
    msg = dedent(msg)

    spectrum_types = strings_to_tabulated_terminal_sensitive(known_spectra)
    spectrum_types = indent(spectrum_types, FOUR_SPACES)

    exit_error(f(msg))


def pipe(
    entry: Entry,
    shift_frame_selectors: List[str],
    exact_frame_selectors: bool,
    spectra: List[ExperimentType],
    name_template_string: str,
    spectrometer_frequency: float = FAKE_SPECTROMETER_FREQUENCY_600,
) -> Entry:

    all_shift_list_frames = entry.get_saveframes_by_category(SHIFT_LIST_FRAME_CATEGORY)

    selected_shift_list_frames = select_frames_by_name(
        all_shift_list_frames, shift_frame_selectors, exact=exact_frame_selectors
    )

    shifts = nef_frames_to_shifts(selected_shift_list_frames)

    for spectrum in spectra:

        spectrum = spectrum.lower()

        frame_name = f(name_template_string)

        if spectrum not in EXPERIMENT_INFO:
            _exit_bad_spectrum_type(spectrum, list(EXPERIMENT_INFO.keys()))
        spectrum_info = EXPERIMENT_INFO[spectrum]

        peaks = make_spectrum(shifts, spectrum_info)

        dimensions = [
            {"axis_code": dimension} for dimension in spectrum_info.dimensions
        ]

        # TODO add info about frames for errors
        spectrum_classification = SPECTRUM_TYPE_TO_CLASSIFICATION[spectrum]
        extra_tags = {
            EXPERIMENT_CLASSIFICATION: spectrum_classification,
            EXPERIMENT_TYPE: EXPERIMENT_CLASSIFICATION_TO_SYNONYM[
                spectrum_classification
            ],
        }
        frame = peaks_to_frame(
            peaks, dimensions, spectrometer_frequency, frame_name, extra_tags=extra_tags
        )

        entry.add_saveframe(frame)

    return entry


def make_spectrum(
    shifts: List[ShiftData], info: PeakInfo, height: int = 1_000_000
) -> List[NewPeak]:

    # note this is not very sophisticated and doesn't cover side-chains... we ought to port the ccpn code
    relevant_shifts = []

    for atom_name in info.atoms:
        for shift in shifts:
            shift_atom_name = shift.atom.atom_name.upper()
            shift_atom_name = shift_atom_name.strip("1")
            shift_atom_name = shift_atom_name.strip("-")

            if shift_atom_name in atom_name:
                relevant_shifts.append(shift)

    shifts_by_residue = {}

    for shift in relevant_shifts:
        residue = str(shift.atom.residue.sequence_code).split("-")[0]
        shifts_by_residue.setdefault(residue, []).append(shift)

    peaks = []

    for residue_shifts in shifts_by_residue.values():

        for atom_set, sign in zip(info.atom_sets, info.atom_set_signs):

            atom_set_shifts = []
            for number_sequence_code_fields_required, atom_name_required in atom_set:
                for shift in residue_shifts:

                    # these are errors for the spectra we are interested in currently
                    # maybe add a warning?
                    if "+" in str(shift.atom.residue.sequence_code):
                        continue

                    number_sequence_code_fields = len(
                        str(shift.atom.residue.sequence_code).split("-")
                    )
                    atom_name = shift.atom.atom_name

                    number_fields_ok = (
                        number_sequence_code_fields
                        == number_sequence_code_fields_required
                    )
                    atom_name_ok = atom_name_required in atom_name

                    if number_fields_ok and atom_name_ok:
                        atom_set_shifts.append(shift)

            if len(atom_set_shifts) == len(info.atoms):
                new_peak = NewPeak(
                    atom_set_shifts, height=height * sign, volume=height * sign
                )
                peaks.append(new_peak)

    return peaks
