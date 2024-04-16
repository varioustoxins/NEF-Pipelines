from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import sequence_from_entry_or_exit
from nef_pipelines.lib.structures import Residue
from nef_pipelines.lib.util import STDIN, parse_comma_separated_options
from nef_pipelines.tools.frames import frames_app

FRAMES_HELP = """\
    the names of the  frames to use, this can be a comma separated list of name or the option can be called
    called multiple times. Wild cards are allowed. If no match is found wild cards are checked as well unless
    --exact is set
"""


@frames_app.command()
def filter(
    frame_selectors: List[str] = typer.Option(["default"], help=FRAMES_HELP),
    input: Path = typer.Option(
        STDIN,
        "--in",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
    unassigned: bool = typer.Option(
        False,
        help="if set lines which do not contain complete chemical shift assignments are deleted",
    ),
):
    """-  filter the lines in one or more save frames"""

    frame_selectors = parse_comma_separated_options(frame_selectors)

    # TODO add a check that we have some shift frames

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    entry = pipe(entry, frame_selectors, unassigned)

    print(entry)


# def _update_spectra_with_groups(spectra):
#     if ExperimentType.TRIPLE in spectra:
#         spectra.update(TRIPLE_SPECTRA)
#         spectra.remove(ExperimentType.TRIPLE)
#
#     return spectra
#
#
# def _exit_bad_spectrum_type(spectrum, known_spectra):
#     msg = """
#         the spectrum type {spectrum} is not know, available spectrum types are
#
#         {spectrum_types}
#     """
#     msg = dedent(msg)
#
#     spectrum_types = strings_to_tabulated_terminal_sensitive(known_spectra)
#     spectrum_types = indent(spectrum_types, FOUR_SPACES)
#
#     exit_error(f(msg))
#
#


def pipe(
    entry: Entry,
    frame_selectors: List[str],
    unassigned=False,
) -> Entry:

    if unassigned:
        sequence = sequence_from_entry_or_exit(entry)

        sequence_set = set(
            [Residue.from_sequence_residue(residue) for residue in sequence]
        )

        all_frames = entry.frame_dict.values()

        for frame in all_frames:
            for loop in frame.loops:

                rows_to_remove = set()
                tags = loop.tags

                loop_has_tags = {}
                for tag_name in (
                    "chain_code",
                    "sequence_code",
                    "residue_name",
                    "atom_name",
                ):
                    loop_has_tags[tag_name] = [tag.startswith(tag_name) for tag in tags]

                are_assignables = [any(has_tag) for has_tag in loop_has_tags.values()]
                is_assignable = all(are_assignables)

                tag_sets_by_end = {}
                if is_assignable:
                    for tag_name in (
                        "chain_code",
                        "sequence_code",
                        "residue_name",
                        "atom_name",
                    ):
                        for tag, is_chain_code in zip(tags, loop_has_tags[tag_name]):
                            if is_chain_code:
                                end = tag[len(tag_name) :]
                                tag_and_index = (tag, loop.tag_index(tag))
                                tag_sets_by_end.setdefault(end, []).append(
                                    tag_and_index
                                )

                    for i, row in enumerate(loop):
                        chain_code = None
                        sequence_code = None
                        residue_name = None
                        atom_name = None
                        for tag_set in tag_sets_by_end.values():
                            for tag, tag_index in tag_set:
                                value = row[tag_index]

                                if tag.startswith("chain_code"):
                                    chain_code = value
                                elif tag.startswith("sequence_code"):
                                    sequence_code = value
                                elif tag.startswith("residue_name"):
                                    residue_name = value
                                elif tag.startswith("atom_name"):
                                    atom_name = value

                        residue = Residue(
                            chain_code=chain_code,
                            sequence_code=sequence_code,
                            residue_name=residue_name,
                        )

                        residue_in_sequence = residue in sequence_set

                        # TODO:  this is a hack it needs proper atom identification
                        atom_name_ok = atom_name is not UNUSED

                        if not atom_name_ok or not residue_in_sequence:
                            rows_to_remove.add(i)

                for row_index in reversed(sorted(rows_to_remove)):
                    del loop.data[row_index]
    return entry


#
#     selected_shift_list_frames = select_frames_by_name(
#         all_shift_list_frames, shift_frame_selectors, exact=exact_frame_selectors
#     )
#
#     shifts = nef_frames_to_shifts(selected_shift_list_frames)
#
#     for spectrum in spectra:
#
#         spectrum = spectrum.lower()
#
#         if spectrum not in EXPERIMENT_INFO:
#             _exit_bad_spectrum_type(spectrum, list(EXPERIMENT_INFO.keys()))
#         spectrum_info = EXPERIMENT_INFO[spectrum]
#
#         peaks = make_spectrum(shifts, spectrum_info)
#
#         if len(peaks) == 0:
#             continue
#
#         frame_name = f(name_template_string)
#
#         dimensions = [
#             {"axis_code": dimension} for dimension in spectrum_info.dimensions
#         ]
#
#         # TODO add info about frames for errors
#         spectrum_classification = SPECTRUM_TYPE_TO_CLASSIFICATION[spectrum]
#         extra_tags = {
#             EXPERIMENT_CLASSIFICATION: spectrum_classification,
#             EXPERIMENT_TYPE: EXPERIMENT_CLASSIFICATION_TO_SYNONYM[
#                 spectrum_classification
#             ],
#         }
#         frame = peaks_to_frame(
#             peaks, dimensions, spectrometer_frequency, frame_name, extra_tags=extra_tags
#         )
#
#         entry.add_saveframe(frame)
#
#     return entry
#
#
# def make_spectrum(
#     shifts: List[ShiftData], info: PeakInfo, height: int = 1_000_000
# ) -> List[NewPeak]:
#
#     # note this is not very sophisticated and doesn't cover side-chains... we ought to port the ccpn code
#     relevant_shifts = []
#
#     for atom_name in info.atoms:
#         for shift in shifts:
#             shift_atom_name = shift.atom.atom_name.upper()
#             shift_atom_name = shift_atom_name.strip("1")
#             shift_atom_name = shift_atom_name.strip("-")
#
#             if shift_atom_name in atom_name:
#                 relevant_shifts.append(shift)
#
#     shifts_by_residue = {}
#
#     for shift in relevant_shifts:
#         residue = str(shift.atom.residue.sequence_code).split("-")[0]
#         shifts_by_residue.setdefault(residue, []).append(shift)
#
#     peaks = []
#
#     for residue_shifts in shifts_by_residue.values():
#
#         for atom_set, sign in zip(info.atom_sets, info.atom_set_signs):
#
#             atom_set_shifts = []
#             for number_sequence_code_fields_required, atom_name_required in atom_set:
#                 for shift in residue_shifts:
#
#                     # these are errors for the spectra we are interested in currently
#                     # maybe add a warning?
#                     if "+" in str(shift.atom.residue.sequence_code):
#                         continue
#
#                     number_sequence_code_fields = len(
#                         str(shift.atom.residue.sequence_code).split("-")
#                     )
#                     atom_name = shift.atom.atom_name
#
#                     number_fields_ok = (
#                         number_sequence_code_fields
#                         == number_sequence_code_fields_required
#                     )
#                     atom_name_ok = atom_name_required in atom_name
#
#                     if number_fields_ok and atom_name_ok:
#                         atom_set_shifts.append(shift)
#
#             if len(atom_set_shifts) == len(info.atoms):
#                 new_peak = NewPeak(
#                     atom_set_shifts, height=height * sign, volume=height * sign
#                 )
#                 peaks.append(new_peak)
#
#     return peaks
