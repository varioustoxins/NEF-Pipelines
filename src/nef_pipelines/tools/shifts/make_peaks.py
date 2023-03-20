import sys
from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import List, Tuple

import typer
from pynmrstar import Entry
from strenum import LowercaseStrEnum

from nef_pipelines.lib.isotope_lib import Isotope
from nef_pipelines.lib.nef_lib import (
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.peak_lib import peaks_to_frame
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.structures import NewPeak, ShiftData
from nef_pipelines.lib.util import FStringTemplate, parse_comma_separated_options
from nef_pipelines.tools.shifts import shifts_app


class SpectraTypes(LowercaseStrEnum):
    N_HSQC = auto()
    C_HSQC = auto()

    HNCA = auto()
    HNcoCA = auto()

    HNCACB = auto()
    HNcoCACB = auto()
    CBCAcoNH = auto()

    HNCO = auto()
    HNcaCO = auto()

    TRIPLE = auto()


TRIPLE_SPECTRA = {
    SpectraTypes.N_HSQC,
    SpectraTypes.HNCA,
    SpectraTypes.HNcoCA,
    SpectraTypes.HNCACB,
    SpectraTypes.HNcoCACB,
    SpectraTypes.HNCO,
    SpectraTypes.HNcaCO,
}
#

ATOMS_TO_DIMENSIONS = {"H", "1H"}
ATOMS = "atoms"
DIMENSIONS = "dimensions"
RESIDUE_OFFSETS = "residue_offsets"


@dataclass
class ShiftInfo:
    atoms: List[str]
    dimensions: List[Isotope]
    atom_sets: List[List[Tuple[int, str]]]
    atom_set_signs: List[int]


@dataclass
class AtomInfo:
    n_field: int
    atom_type: str


# TODO much of this is ugly!
SPECTRA_INFO = {
    SpectraTypes.N_HSQC: ShiftInfo(
        atoms={"H", "N"},
        dimensions=(Isotope.H1, Isotope.N15),
        atom_sets=[
            [(1, "H"), (1, "N")],
        ],
        atom_set_signs=[1],
    ),
    # SpectraTypes.C_HSQC: ShiftInfo(
    #     atoms = {'H', 'C'},
    #     dimensions= (Isotope.H1, Isotope.N15),
    #     atom_sets = [[(1, 'H'), (1, 'C')],],
    #     atom_set_signs=[1]
    # ),
    SpectraTypes.HNCA: ShiftInfo(
        atoms={"H", "N", ("CA",)},
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=[
            [(1, "H"), (1, "N"), (1, "CA")],
            [(1, "H"), (1, "N"), (2, "CA")],
        ],
        atom_set_signs=[1, 1],
    ),
    SpectraTypes.HNcoCA: ShiftInfo(
        atoms={"H", "N", ("CA",)},
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=[
            [(1, "H"), (1, "N"), (2, "CA")],
        ],
        atom_set_signs=[1],
    ),
    SpectraTypes.HNCACB: ShiftInfo(
        atoms={"H", "N", ("CA", "CB")},
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=[
            [(1, "H"), (1, "N"), (1, "CA")],
            [(1, "H"), (1, "N"), (2, "CA")],
            [(1, "H"), (1, "N"), (1, "CB")],
            [(1, "H"), (1, "N"), (2, "CB")],
        ],
        atom_set_signs=[1, 1, -1, -1],
    ),
    SpectraTypes.HNcoCACB: ShiftInfo(
        atoms={"H", "N", ("CA", "CB")},
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=[
            [(1, "H"), (1, "N"), (2, "CA")],
            [(1, "H"), (1, "N"), (2, "CB")],
        ],
        atom_set_signs=[1, -1],
    ),
    SpectraTypes.CBCAcoNH: ShiftInfo(
        atoms={"H", "N", ("CA", "CB")},
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=[
            [(1, "H"), (1, "N"), (2, "CA")],
            [(1, "H"), (1, "N"), (2, "CB")],
        ],
        atom_set_signs=[1, 1],
    ),
    SpectraTypes.HNCO: ShiftInfo(
        atoms={"H", "N", ("C",)},
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=([(1, "H"), (1, "N"), (2, "C")],),
        atom_set_signs=[1],
    ),
    SpectraTypes.HNcaCO: ShiftInfo(
        atoms={"H", "N", ("C",)},
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=[
            [(1, "H"), (1, "N"), (1, "C")],
            [(1, "H"), (1, "N"), (2, "C")],
        ],
        atom_set_signs=[1, 1],
    ),
}


SHIFT_FRAMES_HELP = """\
    the names of the shift frames to use, this can be a comma separated list of name or the option can be called
    called multiple times. Wild cards are allowed. If no match is found wild cards are checked as well unless
    --exact is set
"""

SPECTRA_HELP = f"""
    the names of the spectra to create, this can be a comma separated list of options or
    called multiple times. Possible values are: {', '.join(SpectraTypes)}
"""


@shifts_app.command()
def make_peaks(
    shift_frame_selectors: List[str] = typer.Option(
        ["default"], help=SHIFT_FRAMES_HELP
    ),
    exact: bool = typer.Option(
        False, help="if set frames are selected by exact matches"
    ),
    spectra: List[str] = typer.Option([SpectraTypes.N_HSQC], help=SPECTRA_HELP),
    name_template: str = typer.Option("synthetic_{spectrum}"),
    spectrometer_frequency: float = typer.Option("600.12345678"),
    input: Path = typer.Option(
        Path("-"),
        "--input",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
):
    """-  make a set of peaks for triple resonance and hsqc spectra from a list of shifts [alpha!]"""

    print(
        "*** WARNING *** this command [shifts make_peaks] is only lightly tested use at your own risk!",
        file=sys.stderr,
    )

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
    if SpectraTypes.TRIPLE in spectra:
        spectra.update(TRIPLE_SPECTRA)
        spectra.remove(SpectraTypes.TRIPLE)

    return spectra


def pipe(
    entry: Entry,
    shift_frame_selectors: List[str],
    exact_frame_selectors: bool,
    spectra: List[SpectraTypes],
    name_template_string: str,
    spectrometer_frequency: float = 600.123456789,
) -> Entry:
    all_shift_list_frames = entry.get_saveframes_by_category("nef_chemical_shift_list")

    selected_shift_list_frames = select_frames_by_name(
        all_shift_list_frames, shift_frame_selectors, exact=exact_frame_selectors
    )

    shifts = nef_frames_to_shifts(selected_shift_list_frames)

    name_template = FStringTemplate(name_template_string)

    for spectrum in spectra:

        frame_name = str(name_template)

        spectrum_info = SPECTRA_INFO[spectrum]
        peaks = make_spectrum(shifts, spectrum_info)

        dimensions = [
            {"axis_code": dimension} for dimension in spectrum_info.dimensions
        ]

        # TODO add info about frames for errors
        frame = peaks_to_frame(peaks, dimensions, spectrometer_frequency, frame_name)

        entry.add_saveframe(frame)

    return entry


def make_spectrum(
    shifts: List[ShiftData], info: ShiftInfo, height: int = 1_000_000
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


# def make_triple_resonance(shifts: List[ShiftData], info: Dict[str, Any], height: int =1_000_000) -> List[NewPeak]:
#
#     # note this is not very sophisticated and doesn't cover sidechains... we ought to port the ccpn code
#     relevant_shifts = []
#
#
#     for atom_name in info.atom_names:
#         for shift in shifts:
#             if shift.atom.atom_name.upper() in atom_name:
#                 relevant_shifts.append(shift)
#
#
#     shifts_by_residue = {}
#
#     for shift in relevant_shifts:
#         residue = shift.atom.residue.sequence_code.split('-')[0]
#         shifts_by_residue.setdefault(residue, []).append(shift)
#
#     print(shifts_by_residue)
#
#     # for shift in hsqc_shifts:
#     #     shifts_by_residue.setdefault(shift.atom.residue, []).append(shift)
#     #
#     # peaks = []
#     # for shifts_by_residue in shifts_by_residue.values():
#     #     if len(shifts_by_residue) != 2:
#     #         continue
#     #
#     #     dimension_shifts = []
#     #     for atom_name in atom_names:
#     #         for shift in shifts_by_residue:
#     #             if shift.atom.atom_name == atom_name:
#     #                 dimension_shifts.append(shift)
#     #
#     #     if len(dimension_shifts) != 2:
#     #         continue
#     #
#     #     peaks.append(NewPeak(dimension_shifts, height=height))
#
#     return peaks
