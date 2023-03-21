import sys
from math import sqrt
from typing import Dict, List

import typer
from pynmrstar import Saveframe
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    loop_row_dict_iter,
    read_entry_from_stdin_or_exit,
    select_frames_by_name,
)
from nef_pipelines.lib.structures import AtomLabel, NewPeak, SequenceResidue, ShiftData
from nef_pipelines.lib.util import exit_error
from nef_pipelines.tools.peaks import peaks_app


@peaks_app.command()
def match(
    # ignore_amide_shifts: bool = typer.Option(False, help='ignore amides when matching'),
    # amide_weight: float = typer.Option(1.0, help='weight for the amide shifts'),
    # amide_search_region: Tuple[float,float] = typer.Option((0.2, 0.2*7), help='region to search for amide shifts in
    # the order H N'),
    names: List[str] = typer.Argument(
        ..., help="pairs of shift frame names for the chemical shifts to compare"
    ),
):
    """- match one list of peaks against another [alpha]"""

    print(
        "*** WARNING *** this command [shifts make_peaks] is only lightly tested use at your own risk!",
        file=sys.stderr,
    )

    if len(names) != 2:
        exit_error("i currently need pairs of peaks")

    entry = read_entry_from_stdin_or_exit()

    name_1, name_2 = names

    frame_1 = _select_single_frame_or_exit(entry, name_1)
    frames_2 = _select_single_frame_or_exit(entry, name_2)

    # amide_search_region = {'H': amide_search_region[0], 'N': amide_search_region[1]}

    match_peaks(frame_1, frames_2)


def _nef_frames_to_peak_shifts(frame: Saveframe) -> Dict[str, Dict[str, float]]:
    loop = frame.get_loop("nef_peak")

    indices = [
        int(tag.split("_")[-1]) for tag in loop.tags if tag.startswith("atom_name")
    ]

    peak_atom_shifts = {}
    for row in loop_row_dict_iter(loop):
        key = row["peak_id"]

        atom_shifts = {}
        peak_atom_shifts[key] = atom_shifts
        for index in indices:
            shift = row[f"position_{index}"]
            atom_name = row[f"atom_name_{index}"]

            atom_shifts[atom_name] = shift

    return peak_atom_shifts


def _find_best_match(
    shifts: Dict[str, float],
    match_shifts: Dict[str, Dict[str, float]],
    weights=Dict[str, float],
):

    weight_values_1 = _get_weighted_terms(shifts, weights)

    result = {}

    for peak_id, match_shifts in match_shifts.items():
        weight_values_2 = _get_weighted_terms(match_shifts, weights)

        len_values_1 = len(weight_values_1)
        len_values_2 = len(weight_values_2)

        if len_values_1 != len_values_2:
            continue

        names_1 = set(weight_values_1.keys())
        names_2 = set(weight_values_2.keys())

        if names_1 != names_2:
            continue

        axis_distances = []

        for atom_name in names_1:
            axis_distances.append(
                (weight_values_1[atom_name] - weight_values_2[atom_name]) ** 2
            )
        distance = sqrt(sum(axis_distances))

        result.setdefault(distance, []).append(peak_id)

    return result
    #     distances = []
    #     value_2
    #     distances.append(value_1**2)


def _get_weighted_terms(shifts, weights):

    result = {}
    for name, value in shifts.items():
        weight_key = name[0]
        weight = weights[weight_key]
        result[name] = value / weight
    return result


def _nef_frames_to_peak_by_id(frame):
    loop = frame.get_loop("nef_peak")

    indices = [
        int(tag.split("_")[-1]) for tag in loop.tags if tag.startswith("atom_name")
    ]

    peak_by_id = {}
    for row in loop_row_dict_iter(loop):
        peak_id = row["peak_id"]

        shifts = []
        for index in indices:
            chain_code = row[f"chain_code_{index}"]
            sequence_code = row[f"sequence_code_{index}"]
            residue_name = row[f"residue_name_{index}"]
            atom_name = row[f"atom_name_{index}"]
            position = row[f"position_{index}"]

            residue = SequenceResidue(chain_code, sequence_code, residue_name)
            atom = AtomLabel(residue, atom_name)

            shifts.append(ShiftData(atom, position))

        peak_by_id[peak_id] = NewPeak(shifts, peak_id)

    return peak_by_id


def _get_assignment_tuple(peak: NewPeak):
    result = []
    for shift in peak.shifts:
        residue = shift.atom.residue
        result.extend(
            (
                residue.chain_code,
                residue.sequence_code,
                residue.residue_name,
                shift.atom.atom_name,
            )
        )

    return tuple(result)


def _get_assignment_string(peak: NewPeak):
    result = []
    for shift in peak.shifts:
        residue = shift.atom.residue
        result.append(
            f"#{residue.chain_code}:{residue.sequence_code}[{residue.residue_name}]@{shift.atom.atom_name}"
        )

    return "-".join(result)


def match_peaks(peak_frame_1: Saveframe, peak_frame_2: Saveframe):

    num_dimensions = int(peak_frame_1.get_tag("num_dimensions")[0])

    shifts_1 = _nef_frames_to_peak_shifts(peak_frame_1)
    shifts_2 = _nef_frames_to_peak_shifts(peak_frame_2)

    peaks_by_id_1 = _nef_frames_to_peak_by_id(peak_frame_1)
    peaks_by_id_2 = _nef_frames_to_peak_by_id(peak_frame_2)

    info_by_assignment = {}
    no_matches = []
    for peak_1, target_shifts in shifts_1.items():
        matches = _find_best_match(
            target_shifts, shifts_2, weights={"H": 1.0, "N": 7.0, "C": 2.0, ".": 1.0}
        )

        if len(matches) > 0:
            best_match = sorted(matches)[0]
            peak_2 = matches[best_match]
            peak_2_str = [str(match) for match in matches[best_match]]
            info_string = [
                peak_1,
                ", ".join(peak_2_str),
                len(peak_2),
                best_match,
                "",
                *_get_assignment_tuple(peaks_by_id_1[peak_1]),
                "",
                *_get_assignment_tuple(peaks_by_id_2[peak_2[0]]),
            ]
            assignment = _get_assignment_tuple(peaks_by_id_2[peak_2[0]])

            info_by_assignment[assignment] = info_string
        else:
            no_matches.append(peak_1)

    table = []
    for key in sorted(info_by_assignment):
        table.append((info_by_assignment[key]))

    # TODO: move to peaks table
    # TODO: colorise matches?
    # TODO: add better sorting

    headings = "f1.pk f2.pks num dist".split()
    for peak in 1, 2:
        headings.append(f"f{peak}:")
        for dim in range(1, num_dimensions + 1):
            headings.extend(f"chn-{dim} seq-{dim} resn-{dim} atm-{dim}".split())

    print(f"frame 1: {peak_frame_1.name}")
    print(f"frame 2: {peak_frame_2.name}")
    print()
    if len(no_matches) > 0:
        no_matches = ", ".join([str(peak) for peak in no_matches])
        print(f"note no matches for the following peak-1's: {no_matches}")
        print()

    table.sort(key=lambda x: x[0])
    print(tabulate(table, tablefmt="plain", headers=headings))

    # residue_atom_shifts_1 = _peak_list_to_peak_shifts(shifts_1)
    # residue_atom_shifts_2 = _peak_list_to_peak_shifts(shifts_2)

    # table = []
    #
    # for (chain, residue), shifts in residue_atom_shifts_1.items():
    #
    #     ignored_atoms = set('H N'.split()) if ignore_amides else set()
    #     matches = _find_best_match(shifts, residue_atom_shifts_2, ignored_atoms, amide_weight, amide_search_region)
    #
    #     ordered_matches = []
    #     for key in sorted(matches.keys()):
    #         name = f'{matches[key][0]}{matches[key][1]}'
    #         value = f'{key:.3}'
    #
    #         ordered_matches.append(f'{name} {value}')
    #
    #     row = [f'{chain}{residue}', *ordered_matches[:5]]
    #     table.append(row)
    #
    # lengths = []
    # for row in table:
    #     for column in row[1:]:
    #         lengths.append(len(column))
    #
    # max_column_length = max(lengths) + 1
    #
    # for row in table:
    #     for i, column in enumerate(row[1:], start=1):
    #         column_length = len(column)
    #         column_fields = column.split()
    #         pad_length = max_column_length - column_length
    #         pad = ' ' * pad_length
    #         column = pad.join(column_fields)
    #         row[i] = column
    #
    #
    # print(tabulate(table, tablefmt='plain'))


def _shift_list_to_residue_atom_shifts(shifts_1):
    residue_shifts = {}

    for shift in shifts_1:
        chain_code = shift.atom.residue.chain_code
        sequence_code = shift.atom.residue.sequence_code
        atom_name = shift.atom.atom_name
        if "-" in sequence_code:
            sequence_code, neg_offset = sequence_code.split("-")
            atom_name = f"{atom_name}-{neg_offset}"

        key = chain_code, sequence_code
        shift_value = shift.value

        residue_shifts.setdefault(key, {})[atom_name] = shift_value

    return residue_shifts


def _select_single_frame_or_exit(entry, name):

    frames = select_frames_by_name(entry.frame_list, name)

    if len(frames) == 0:
        exit_error(
            f"no frames selected from entry: {entry.entry_id} by selector {name}"
        )

    if len(frames) > 1:

        msg = f"""\
            multiple frames selected from entry: {entry.entry_id} by selector {name}
            frames selected were {' '.join([frame.name for frame in frames])}
        """
        exit_error(msg)

        exit_error(msg)

    return frames[0]


# def _find_best_match(shifts_1, residue_atom_shifts_2, ignored_atoms, amide_weight, amide_search_region):
#     matches = {}
#     for key, shifts_2 in residue_atom_shifts_2.items():
#         atom_names_1 = set(shifts_1.keys())
#         atom_names_2 = set(shifts_2.keys())
#
#         common_atom_names = atom_names_1.intersection(atom_names_2)
#
#
#
#         if len(common_atom_names) != 0:
#
#             differences = {}
#             for atom_name in common_atom_names:
#                 diff = abs(shifts_1[atom_name] - shifts_2[atom_name])
#                 if atom_name in 'H N'.split():
#                     diff = diff * amide_weight
#                 differences[atom_name] = diff
#
#             ok = True
#
#             for amide_name in amide_search_region:
#                 if amide_name in differences:
#                     if differences[amide_name] > amide_search_region[amide_name]:
#                         ok = False
#
#             if ok:
#                 for name in ignored_atoms:
#                     if name in matches:
#                         del matches[name]
#
#                 matches[sum(differences.values())] = key
#
#     return matches
#
#
# def _squeeze_spaces_left(string):
#     pre_len = len(string)
#     string = string.replace(' ', '')
#     post_len = len(string)
#     pad = " " * (pre_len - post_len)
#     string = f'{pad}{string}'
#
#     return string
#
#
#
