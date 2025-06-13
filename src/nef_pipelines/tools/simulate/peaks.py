from collections import Counter
from dataclasses import replace
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
    UNUSED,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.peak_lib import peaks_to_frame
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.spectra_lib import (
    EXPERIMENT_CLASSIFICATION_TO_SYNONYM,
    EXPERIMENT_GROUPS,
    EXPERIMENT_INFO,
    FAKE_SPECTROMETER_FREQUENCY_600,
    SPECTRUM_TYPE_TO_CLASSIFICATION,
    ExperimentType,
    PeakInfo,
)
from nef_pipelines.lib.structures import NewPeak, ShiftData
from nef_pipelines.lib.util import (
    FOUR_SPACES,
    STDIN,
    exit_error,
    flatten,
    is_int,
    parse_comma_separated_options,
    strings_to_tabulated_terminal_sensitive,
)
from nef_pipelines.tools.simulate import simulate_app

SPECTRUM_NAME_TEMPLATE = "synthetic_{spectrum}"

SHIFT_FRAMES_HELP = """\
    the names of the shift frames to use, this can be a comma separated list of name or the option can be called
    called multiple times. Wild cards are allowed. If no match is found wild cards are checked as well unless
    --exact is set. If no shift frames are selected the default chemical shift list frame is used
"""

SPECTRA_HELP = f"""
    the names of the spectra to create, this can be a comma separated list of options or
    called multiple times. Possible values are: {', '.join(ExperimentType)}
"""
NAME_TEMPLATE_HELP = """
    the name template for the new peak lists the placeholder {spectrum} will get replaced with the spectrum type
"""


# TODO: add a flag to list spectra and groups...
@simulate_app.command()
def peaks(
    shift_frame_selectors: List[str] = typer.Option(
        None, "--shift-frames", help=SHIFT_FRAMES_HELP
    ),
    exact: bool = typer.Option(
        False, help="if set frames are selected by exact matches"
    ),
    name_template: str = typer.Option(SPECTRUM_NAME_TEMPLATE, help=NAME_TEMPLATE_HELP),
    spectrometer_frequency: float = typer.Option(FAKE_SPECTROMETER_FREQUENCY_600),
    input: Path = typer.Option(
        STDIN,
        "--in",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
    spectra: List[str] = typer.Argument(None, help=SPECTRA_HELP),
):
    """-  make a set of peaks for an hsqc, 13C direct detect or triple resonance spectrum from a list of shifts
    [alpha for non ccpn peak lists and 13C detect]"""

    spectra = [spectrum.replace("-", "_") for spectrum in spectra]
    if not spectra:
        spectra = [
            ExperimentType.N_HSQC,
        ]

    shift_frame_selectors = (
        [
            "nef_chemical_shift_list_default",
        ]
        if not shift_frame_selectors
        else parse_comma_separated_options(shift_frame_selectors)
    )

    shift_frames = parse_comma_separated_options(shift_frame_selectors)

    spectra = set(parse_comma_separated_options(spectra))

    spectra = _strs_to_experiment_types_or_exit_error(spectra)

    spectra = _update_spectra_with_groups(spectra)

    # TODO add a check that we have some shift frames

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    entry = pipe(
        entry, shift_frames, exact, spectra, name_template, spectrometer_frequency
    )

    print(entry)


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

        spectrum_info = EXPERIMENT_INFO[spectrum.upper()]

        peaks = _make_peak_list(shifts, spectrum_info)

        if len(peaks) == 0:
            continue

        frame_name = f(name_template_string)

        dimensions = [
            {"axis_code": dimension} for dimension in spectrum_info.dimensions
        ]

        # TODO add info about frames for errors
        if spectrum not in SPECTRUM_TYPE_TO_CLASSIFICATION:
            _exit_bad_spectrum_type(spectrum, SPECTRUM_TYPE_TO_CLASSIFICATION.keys())

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


def _sign_of_value(value):
    result = ""
    result = "+" if value > 0 else result
    result = "-" if value < 0 else result
    return result


def _average_atom_set_shifts(atom_set_shifts):
    shifts_by_atom = {}
    for atom_set_shift in atom_set_shifts:
        residue = atom_set_shift.atom.residue
        atom_key = (
            residue.chain_code,
            residue.sequence_code,
            residue.offset,
            atom_set_shift.atom.atom_name,
        )
        shifts_by_atom.setdefault(atom_key, []).append(atom_set_shift)

    result = []
    for key, values in shifts_by_atom.items():
        if len(values) == 1:
            result.append(values[0])
            continue
        else:
            value = sum([shift.value for shift in values]) / len(values)
            result.append(ShiftData(values[0].atom, round(value, 3), UNUSED))

    return result


def _make_peak_list(
    shifts: List[ShiftData], info: PeakInfo, height: int = 1_000_000
) -> List[NewPeak]:

    # note this is not very sophisticated and doesn't cover side-chains... we ought to port the ccpn code

    updated_shifts = []

    for shift in shifts:

        sequence_code = str(shift.atom.residue.sequence_code)
        prefix = sequence_code[0] if sequence_code.startswith("@") else ""
        sequence_code = sequence_code.lstrip("@")

        # TODO not sure this is the best way to do it, separators are only relevant if the sequence code starts with @
        found_separator = False
        for separator in ["-", "+"]:
            if sequence_code.startswith(separator):
                sequence_sign = sequence_code[0]
                sequence_code = sequence_code[1:]
            else:
                sequence_sign = ""

            if separator in sequence_code and not sequence_code[0] == separator:
                sequence_code_fields = sequence_code.split(separator)
                if len(sequence_code_fields) != 2:
                    updated_shifts.append(shift)
                    continue

                sequence_code, offset = sequence_code_fields

                if sequence_code[0] == "@":
                    sequence_code = sequence_code[1:]
                    prefix = "@"

                sequence_code_int = (
                    int(f"{sequence_sign}{sequence_code}")
                    if is_int(sequence_code)
                    else None
                )
                offset_int = int(offset) if is_int(offset) else None

                if not sequence_code_int and not offset_int:
                    updated_shifts.append(shift)
                    continue

                if separator == "+":
                    sequence_code_int = sequence_code_int + offset_int
                elif separator == "-":
                    sequence_code_int = sequence_code_int - offset_int

                residue = shift.atom.residue
                residue = replace(residue, sequence_code=sequence_code_int)
                residue = replace(residue, offset=offset_int)
                if prefix:
                    residue = replace(residue, sequence_code_prefix=prefix)

                atom = replace(shift.atom, residue=residue)
                shift = replace(shift, atom=atom)
                updated_shifts.append(shift)
                found_separator = True

        if not found_separator:
            sequence_code = str(shift.atom.residue.sequence_code)
            if sequence_code.startswith("@"):
                prefix = "@"
                sequence_code = sequence_code[1:]
                if is_int(sequence_code):
                    sequence_code = int(sequence_code)
                    residue = shift.atom.residue
                    residue = replace(residue, sequence_code=sequence_code)
                    residue = replace(residue, sequence_code_prefix=prefix)
                    atom = replace(shift.atom, residue=residue)
                    shift = replace(shift, atom=atom)
            updated_shifts.append(shift)

    shifts = updated_shifts

    relevant_shifts = []

    for atom_name in flatten(info.atoms):
        for shift in shifts:
            if shift.atom.atom_name.upper() in atom_name:
                relevant_shifts.append(shift)

    shifts_by_chain_prefix_and_residue = {}

    for shift in relevant_shifts:
        residue = shift.atom.residue.sequence_code
        chain = shift.atom.residue.chain_code
        prefix = shift.atom.residue.sequence_code_prefix
        shifts_by_chain_prefix_and_residue.setdefault(
            (chain, prefix, residue), []
        ).append(shift)

    chains_prefix_residues = list(shifts_by_chain_prefix_and_residue.keys())

    peaks = []

    for i, (chain, prefix, residue_number) in enumerate(sorted(chains_prefix_residues)):

        if not is_int(residue_number):
            continue

        for atom_set, sign in zip(info.atom_sets, info.atom_set_signs):

            atom_set_shifts = []
            for j, (offset, atom_name_required) in enumerate(atom_set):
                targeted_residue = residue_number + offset

                per_residue_shifts = shifts_by_chain_prefix_and_residue.get(
                    (chain, prefix, targeted_residue), []
                )
                for k, shift in enumerate(per_residue_shifts):
                    if shift.atom.atom_name == atom_name_required:
                        atom_set_shifts.append(shift)

            atom_set_shifts = _average_atom_set_shifts(atom_set_shifts)

            if len(atom_set_shifts) > len(atom_set):
                continue

            for i, shift in enumerate(atom_set_shifts):
                sequence_code = shift.atom.residue.sequence_code
                sequence_code_prefix = shift.atom.residue.sequence_code_prefix
                sequence_code_offset = shift.atom.residue.offset

                if sequence_code_offset and sequence_code_prefix == "@":
                    sequence_code = int(sequence_code) + sequence_code_offset
                    sign_of_offset = _sign_of_value(-sequence_code_offset)
                    sequence_code = (
                        f"{sequence_code}{sign_of_offset}{sequence_code_offset}"
                    )

                if sequence_code_prefix:
                    sequence_code = f"{sequence_code_prefix}{sequence_code}"
                    residue = shift.atom.residue
                    residue = replace(
                        residue, sequence_code=sequence_code, sequence_code_prefix=""
                    )
                    atom = replace(shift.atom, residue=residue)
                    shift = replace(shift, atom=atom)
                    atom_set_shifts[i] = shift

            if len(atom_set_shifts) == len(info.dimensions):
                new_peak = NewPeak(
                    atom_set_shifts, height=height * sign, volume=height * sign
                )
                peaks.append(new_peak)

    return peaks


def _strs_to_experiment_types_or_exit_error(spectra):
    result = []
    spectrum_names = set([experiment.value for experiment in ExperimentType])
    for spectum in spectra:

        found = False
        if spectum in spectrum_names:
            result.append(ExperimentType[spectum])
            found = True

        experiment_types_upper = [
            experiment_type.name.upper() for experiment_type in ExperimentType
        ]
        upper_experiments_to_experiments = {
            experiment_type.name.upper(): experiment_type
            for experiment_type in ExperimentType
        }
        counts = Counter(experiment_types_upper)

        if not found:
            spectrum_upper = spectum.upper()
            if spectrum_upper in experiment_types_upper and counts[spectrum_upper] == 1:
                result.append(upper_experiments_to_experiments[spectrum_upper])
                found = True
            if spectrum_upper in experiment_types_upper and counts[spectrum_upper] > 1:
                degenerate_spectra = [
                    experiment_type.name
                    for experiment_type in ExperimentType
                    if experiment_type.upper() == spectrum_upper
                ]
                _exit_degnerate_spectrum_type(
                    spectum, list(ExperimentType), degenerate_spectra
                )

        if not found:
            _exit_bad_spectrum_type(spectum, list(ExperimentType))

    return result


def _update_spectra_with_groups(spectra):

    spectra = set(spectra)
    to_update = []
    for experiment_type in spectra:
        if experiment_type in EXPERIMENT_GROUPS:
            to_update.append(experiment_type)

    for experiment_type in to_update:
        spectra.update(EXPERIMENT_GROUPS[experiment_type])
        spectra.remove(experiment_type)

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


def _exit_degnerate_spectrum_type(spectrum, known_spectra, degenerate_spectra):
    degenerate_spectra = ", ".join(degenerate_spectra)

    spectrum_types = strings_to_tabulated_terminal_sensitive(known_spectra)
    spectrum_types = indent(spectrum_types, FOUR_SPACES)

    msg = f"""
            the spectrum type {spectrum} doesn't exactly match a spectrum type in the list below
            and has more than possible match when case is ignored [{degenerate_spectra}]

            {spectrum_types}
        """
    msg = dedent(msg)

    exit_error(f(msg))
