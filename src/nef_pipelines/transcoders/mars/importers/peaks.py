import string
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import List

import typer
from fyeah import f

from nef_pipelines.lib.isotope_lib import Isotope
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.peak_lib import peaks_to_frame
from nef_pipelines.lib.sequence_lib import (
    MoleculeTypes,
    get_residue_name_from_lookup,
    sequence_from_entry_or_exit,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.translation_lib import translate_new_peak
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.transcoders.mars import import_app
from nef_pipelines.transcoders.sparky.importers.peaks import (
    _guess_dimensions_if_not_defined_or_throw,
)
from nef_pipelines.transcoders.sparky.sparky_lib import (
    parse_peaks as parse_sparky_peaks,
)

MAKE_SPECTA_HELP = """
    if true merge relevant files to give spectra frames [e.g combine Ca and Ca-1 to get an HNCA frame and select Ca-1 to
    get an HNcoCA frame...] files with CA/CB/CB and CA-1/CB-1/CO-1 in their names are combined, spectra without these
    selectors in their names are read as individual spectra [not filenames will be replaced by spectrum names in the
    saveframe template]
"""


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
    chain_code: str = typer.Option(
        "A",
        "--chain",
        help="chain code to use, as mars can only assign a single chain a single chaincode is assumed here",
        metavar="<CHAIN-CODE>",
    ),
    frame_name: str = typer.Option(
        "mars_{file_name}",
        "-f",
        "--frame-name",
        help="a templated name for the frame {file_name} will be replaced by input filename",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type peaks.txt", metavar="<MARS-peaks>.txt"
    ),
    spectrometer_frequency: float = typer.Option(
        600.123456789, help="spectrometer frequency in MHz"
    ),
    include_unassigned: bool = typer.Option(False, help="include unassigned peaks"),
    make_spectra: bool = typer.Option(True, help=MAKE_SPECTA_HELP),
    dont_sort_peaks: bool = typer.Option(
        False, help="don't sort the peaks [by isotopes 1H and then 13C]"
    ),
):
    """- import MARS [sparkyish] peaks files sparky_<NAME>.out"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    sequence = sequence_from_entry_or_exit(entry)

    file_names_and_lines = {}
    for file_name in file_names:

        try:
            with open(file_name, "r") as fp:
                lines = fp.readlines()
        except IOError as e:
            msg = f"""
                    while reading sparky peaks file {file_name} there was an error reading the file
                    the error was: {e}
                """
            exit_error(msg, e)

        file_names_and_lines[file_name] = lines

    entry = pipe(
        entry,
        frame_name,
        file_names_and_lines,
        chain_code,
        sequence,
        spectrometer_frequency=spectrometer_frequency,
        include_unassigned=include_unassigned,
        make_spectra=make_spectra,
        sort_peaks=not dont_sort_peaks,
    )

    print(entry)


def pipe(
    entry,
    frame_code_template,
    file_names_and_lines,
    chain_code,
    sequence,
    spectrometer_frequency,
    include_unassigned=False,
    make_spectra=True,
    sort_peaks=True,
):
    delete_unassigned = not include_unassigned

    if make_spectra:
        spectra_sets = _combine_filenames_into_spectra(file_names_and_lines.keys())
    else:
        spectra_sets = {
            file_name.stem: [
                file_name,
            ]
            for file_name in file_names_and_lines.keys()
        }

    peaks_by_filename = {}
    for file_name, lines in file_names_and_lines.items():
        peaks = _parse_peaks(chain_code, delete_unassigned, file_name, lines, sequence)
        peaks = [translate_new_peak(peak) for peak in peaks]
        peaks_by_filename[file_name] = peaks

    peaks_by_frame_name = {}
    for frame_name, file_names in spectra_sets.items():
        for file_name in file_names:
            peaks_by_frame_name.setdefault(frame_name, []).extend(
                peaks_by_filename[file_name]
            )

    mars_frames = []

    for frame_name, peaks in peaks_by_frame_name.items():
        peaks = list(peaks)

        # peaks.sort() # need to sort peaks on amides...

        dimensions = _guess_dimensions_if_not_defined_or_throw(peaks, [])

        dimensions = [{"axis_code": dimension} for dimension in dimensions]

        if sort_peaks:
            sort_isotopes = [Isotope.H1, Isotope.C13]
            peaks = _sort_by_isotopes(peaks, dimensions, sort_isotopes)

        file_name = frame_name  # used in f method...

        frame_code = f(frame_code_template)

        frame = peaks_to_frame(
            peaks, dimensions, spectrometer_frequency, frame_code=frame_code
        )

        mars_frames.append(frame)

    return add_frames_to_entry(entry, mars_frames)


def _sort_by_isotopes(peaks, dimensions, sort_isotopes):
    axis_dimensions = {axis["axis_code"]: i for i, axis in enumerate(dimensions)}
    sort_dimensions = [axis_dimensions[isotope] for isotope in sort_isotopes]

    def sort_function(value, dimensions):
        result = []
        for dimension in dimensions:
            residue = value.shifts[dimension].atom.residue
            result.append(residue.chain_code)
            result.append(int(residue.sequence_code))
        return result

    sort_curry = partial(sort_function, dimensions=sort_dimensions)

    return sorted(peaks, key=sort_curry)


def _parse_peaks(chain_code, delete_unassigned, file_name, lines, sequence):

    lookup = sequence_to_residue_name_lookup(sequence)

    new_lines = []
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()

        if len(line) == 0:
            continue

        fields = line.split()

        if line_no == 1:
            number_fields = len(fields)
            shifts = " ".join([f"w{i}" for i in range(1, number_fields)])
            new_lines.append(f"Assignment {shifts}")

        is_assignment = False
        for quality in "LMH":
            if f"({quality})" in line:
                is_assignment = True

        assignment = fields[0].replace("(", "|").replace(")", "|")
        assignment = assignment.strip("|")
        assignment_fields = assignment.split("|")

        if is_assignment:
            fields[0] = f"{assignment_fields[0]}{assignment_fields[1]}"
        else:
            pseudo_number = "".join(
                [char for char in assignment_fields[0] if char.isdigit()]
            )
            if len(pseudo_number) == 0:
                pseudo_number = hash(assignment_fields[0])
            fields.append(f"PSEUDO_RESIDUE={assignment_fields[0]}")
            fields[0] = f"PR{pseudo_number}{assignment_fields[1]}"

        if is_assignment:
            fields.append(f"merit={assignment_fields[-1]}")

        new_line = " ".join(fields)

        new_lines.append(new_line)

    peaks = parse_sparky_peaks(
        new_lines,
        file_name=file_name,
        molecule_type=MoleculeTypes.PROTEIN,
        chain_code=chain_code,
        sequence=sequence,
        allow_pseudo_atoms=True,
    )
    modified_peaks = []
    for peak in peaks:
        if "PSEUDO_RESIDUE" in peak.comment:

            if delete_unassigned:
                continue

            pseudo_residue = peak.comment.split("=")[1]
            peak = replace(peak, comment="")
            new_shifts = []
            for shift in peak.shifts:
                residue = shift.atom.residue
                # is this the best thing to do?
                residue = replace(
                    residue,
                    chain_code="@-",
                    residue_name=UNUSED,
                    sequence_code=f"@{pseudo_residue}",
                )
                atom = replace(shift.atom, residue=residue)
                shift = replace(shift, atom=atom)
                new_shifts.append(shift)
            peak = replace(peak, shifts=new_shifts)

        modified_peaks.append(peak)
    peaks = modified_peaks
    modified_peaks = []
    for peak in peaks:
        new_shifts = []
        for shift in peak.shifts:
            if shift.atom.atom_name[-1] in string.ascii_lowercase:

                residue = shift.atom.residue
                if residue.residue_name == UNUSED:
                    residue = replace(
                        residue, sequence_code=f"{residue.sequence_code}-1"
                    )
                else:
                    offset_sequence_code = int(residue.sequence_code) - 1
                    chain_code = residue.chain_code

                    offset_residue_name = get_residue_name_from_lookup(
                        chain_code, offset_sequence_code, lookup
                    )
                    residue = replace(
                        residue,
                        sequence_code=f"{offset_sequence_code}",
                        residue_name=offset_residue_name,
                    )

                atom = replace(shift.atom, atom_name=shift.atom.atom_name.upper())
                atom = replace(atom, residue=residue)
                shift = replace(shift, atom=atom)
            new_shifts.append(shift)

        modified_peaks.append(replace(peak, shifts=new_shifts))
    peaks = modified_peaks
    modified_peaks = []
    MERITS = {"L": 0.50, "M": 0.75, "H": 1.00}
    for peak in peaks:
        if "merit" in peak.comment:
            merit_letter = peak.comment[-1]

            peak = replace(peak, figure_of_merit=MERITS[merit_letter])
        modified_peaks.append(peak)
    peaks = modified_peaks
    return peaks


def _combine_filenames_into_spectra(file_names):

    used_filenames = set()

    spectra_and_selectors = {
        "HNCA": ["_CA.", "_CA-1."],
        "HNcoCA": ["_CA-1."],
        "HNCACB": ["_CA.", "_CA-1.", "_CB.", "_CB-1."],
        "HNcoCACB": ["_CA-1.", "_CB-1."],
        "HNCO": ["_CO-1."],
        "HNcaCO": ["_CO.", "_CO-1."],
    }

    combinations = {}

    for spectrum_name, selectors in spectra_and_selectors.items():
        selected = []
        for selector in selectors:
            for file_name in file_names:
                if selector in file_name.name:
                    selected.append(file_name)
                    used_filenames.add(file_name)
                    break

        if len(selected) == len(selectors):
            combinations[spectrum_name] = selected

    unused_filenames = set(file_names) - used_filenames
    for unused_filename in unused_filenames:
        combinations[unused_filename.stem] = [
            unused_filename,
        ]

    return combinations
