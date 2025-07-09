import sys
from math import sqrt
from textwrap import dedent
from typing import Dict, List

import typer
from pynmrstar import Loop, Saveframe
from pynmrstar.entry import Entry

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    create_nef_save_frame,
    loop_row_dict_iter,
    read_entry_from_stdin_or_exit,
    select_frames_by_name,
)
from nef_pipelines.lib.peak_lib import frame_to_peaks
from nef_pipelines.lib.structures import AtomLabel, NewPeak, SequenceResidue, ShiftData
from nef_pipelines.lib.util import exit_error, flatten
from nef_pipelines.tools.peaks import peaks_app
from nef_pipelines.transcoders.nmrview.importers.shifts import add_frames_to_entry

# CF M P Williamson PROGRESS IN NUCLEAR MAGNETIC RESONANCE SPECTROSCOPY 2014
# Using chemical shift perturbation to characterise ligand binding” [Prog. Nucl. Magn. Reson. Spectrosc. 73C (2013) 1–16
DEFAULT_ISOTOPE_WEIGHTS = weights = {"1H": 1.0, "15N": 7.0, "13C": 3.333333}


@peaks_app.command()
def match(
    # ignore_amide_shifts: bool = typer.Option(False, help='ignore amides when matching'),
    # amide_weight: float = typer.Option(1.0, help='weight for the amide shifts'),
    # amide_search_region: Tuple[float,float] = typer.Option((0.2, 0.2*7), help='region to search for amide shifts in
    # the order H N'),
    assign: bool = typer.Option(
        False,
        "--assign",
        help="assign the second peak list using closest matches from the first",
    ),
    names: List[str] = typer.Argument(
        ..., help="pairs of shift frame names for the chemical shifts to compare"
    ),
):
    """- match one list of peaks against another [alpha]"""

    print(
        "*** WARNING *** this command [peaks match] is only lightly tested use at your own risk!",
        file=sys.stderr,
    )

    if len(names) != 2:
        exit_error("i currently need pairs of peaks")

    entry = read_entry_from_stdin_or_exit()

    name_1, name_2 = names

    frame_1 = _select_single_frame_or_exit(entry, name_1)
    frames_2 = _select_single_frame_or_exit(entry, name_2)

    # amide_search_region = {'H': amide_search_region[0], 'N': amide_search_region[1]}

    entry = pipe(entry, frame_1, frames_2, assign)

    print(entry)


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

            atom_shifts[index - 1] = shift

    return peak_atom_shifts


def _find_best_match(
    shifts: Dict[str, float],
    match_shifts: Dict[str, Dict[str, float]],
    weights=Dict[str, float],
):

    weighted_values_1 = _get_weighted_terms(shifts, weights)

    result = {}

    for peak_id, match_shifts in match_shifts.items():
        weighted_values_2 = _get_weighted_terms(match_shifts, weights)

        terms = []

        for dim in weighted_values_1:
            terms.append((weighted_values_1[dim] - weighted_values_2[dim]) ** 2)
        distance = sqrt(sum(terms))

        result.setdefault(distance, []).append(peak_id)

    min_distance = min(result.keys())
    return result[min_distance], min_distance


def _get_weighted_terms(shifts, weights):

    return {dim: shift / weights[dim] for dim, shift in shifts.items()}


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


def _get_peak_frame_dimension_mapping(peak_frame_1, peak_frame_2):
    axis_codes_1 = _get_spectrum_axis_codes(peak_frame_1)
    axis_codes_2 = _get_spectrum_axis_codes(peak_frame_2)

    mapping = []
    for axis_code_1 in axis_codes_1:
        mapping.append(
            [i for i, code in enumerate(axis_codes_2) if code == axis_code_1]
        )
    return mapping


def _get_spectrum_axis_codes(peak_frame):
    return peak_frame.get_loop("nef_spectrum_dimension").get_tag("axis_code")


def _exit_if_mappings_bad(mapping, peak_frame_1, peak_frame_2):
    mappings_ok = [len(dim_mapping) == 1 for dim_mapping in mapping]

    if not all(mappings_ok):
        mapping_offset_by_1 = [
            [str(dim_mapping + 1) for dim_mapping in mapping_list]
            for mapping_list in mapping
        ]
        mapping_offset_by_1_joined = [
            f"{', '.join(dim_mapping)}" for dim_mapping in mapping_offset_by_1
        ]
        mapping_by_dim = [
            f"{dim} -> {dim_mapping}"
            for dim, dim_mapping in enumerate(mapping_offset_by_1_joined, start=1)
        ]
        mappings_by_dim = "\n".join(mapping_by_dim)

        msg = f"""
            The dimension mappings of dimensions in {peak_frame_1.name} -> {peak_frame_2.name}
            is not unique and singular, the mapping is:
        """
        msg = dedent(msg).strip()
        msg = f"{msg}\n\n{mappings_by_dim}"

        exit_error(msg)


def _map_peak_shifts(shifts, mapping):

    for peak_id, shifts_by_dim in shifts.items():

        mapped_shifts = {mapping[dim]: shift for dim, shift in shifts_by_dim.items()}
        shifts[peak_id] = mapped_shifts

    return shifts


def _get_dim_isotopes(peak_frame):

    result = []
    if "_nef_spectrum_dimension" in peak_frame:
        spectrum_dimension_loop = peak_frame.get_loop("nef_spectrum_dimension")
        if "axis_code" in spectrum_dimension_loop.tags:
            result = spectrum_dimension_loop.get_tag("axis_code")

    if not result:
        result = [
            None,
        ] * int(peak_frame.get_tag("num_dimensions")[0])

    return result


def _get_dim_weights(peak_frame):
    return {
        dim: DEFAULT_ISOTOPE_WEIGHTS.get(isotope, None)
        for dim, isotope in enumerate(_get_dim_isotopes(peak_frame))
    }


def _exit_if_dim_weights_not_defined(dim_weights, peak_frame_1, peak_frame_2):

    bad_dim_indices = [
        str(dim_index + 1)
        for dim_index, weight in dim_weights.items()
        if weight is None
    ]
    if bad_dim_indices:
        bad_dim_indices = ", ".join(bad_dim_indices)

        msg = f"""
            for the frames {peak_frame_1.name} and {peak_frame_2.name} appropiate isotope weigts couldn't
            be determined for the following dims {bad_dim_indices}
        """
        msg = dedent(msg).strip()
        exit_error(msg)


def _build_dim_assignments(peak):
    result = {}
    for dim_index, shift in enumerate(peak.shifts, start=1):
        result["chain_code"] = shift.atom.residue.chain_code
        result["sequence_code"] = shift.atom.residue.sequence_code
        result["residue_name"] = shift.atom.residue.residue_name

        # TODO this is hack because some internal routines use ? for unassigned not . [UNUSED]
        atom_name = shift.atom.atom_name
        atom_name = atom_name if atom_name != "?" else UNUSED
        result["atom_name"] = atom_name

    return result


def _assign_frame(result, peak_frame_2):
    for key, value in result.items():
        print(key, value)


def pipe(entry: Entry, peak_frame_1: Saveframe, peak_frame_2: Saveframe, assign=False):

    num_dimensions_1 = int(peak_frame_1.get_tag("num_dimensions")[0])

    peak_list_1 = frame_to_peaks(peak_frame_1)

    peak_list_1_by_id = {peak.id: peak for peak in peak_list_1}

    # TODO move from frames to peak dataclass instances
    _exit_if_peak_frame_dimensions_dont_match(peak_frame_1, peak_frame_2)

    mapping = _get_peak_frame_dimension_mapping(peak_frame_1, peak_frame_2)

    _exit_if_mappings_bad(mapping, peak_frame_1, peak_frame_2)

    shifts_1 = _nef_frames_to_peak_shifts(peak_frame_1)
    shifts_2 = _nef_frames_to_peak_shifts(peak_frame_2)

    mapping = flatten(mapping)

    shifts_2 = _map_peak_shifts(shifts_2, mapping)

    dim_weights = _get_dim_weights(peak_frame_1)

    _exit_if_dim_weights_not_defined(dim_weights, peak_frame_1, peak_frame_2)

    results = {}
    for peak_1_id, target_shifts in shifts_1.items():

        best_matches, distance = _find_best_match(target_shifts, shifts_2, dim_weights)

        best_matches = [best_match for best_match in best_matches]

        results[peak_1_id] = best_matches, distance

    if assign:
        print("ere")
        _assign_frame(results, peak_frame_2)
        target_peak_loop = peak_frame_2.get_loop("nef_peak")
        print(target_peak_loop)
        source_peak_loop = peak_frame_1.get_loop("nef_peak")

        source_values_by_index = {
            row["index"]: row for row in loop_row_dict_iter(source_peak_loop)
        }

        target_peak_new_values = {}
        for list_1_index, [target_peaks, _] in results.items():
            source_values = source_values_by_index[list_1_index]
            source_values = {
                source_name: source_value
                for source_name, source_value in source_values.items()
                if source_name.startswith("chain_code")
                or source_name.startswith("sequence_code")
                or source_name.startswith("residue_name")
                or source_name.startswith("atom_name")
            }

            for target_peak in target_peaks:
                target_peak_new_values[target_peak] = source_values

        for target_peak in loop_row_dict_iter(target_peak_loop):
            target_peak_index = target_peak["index"]
            if target_peak_index in target_peak_new_values:
                new_values = target_peak_new_values[target_peak_index]
                for column_name, new_value in new_values.items():
                    target_peak[column_name] = new_value

    else:
        result_frame = _make_result_frame(
            num_dimensions_1, peak_frame_1, peak_frame_2, peak_list_1_by_id, results
        )
        add_frames_to_entry(entry, result_frame)

    return entry


def _make_result_frame(
    num_dimensions_1, peak_frame_1, peak_frame_2, peak_list_1_by_id, result
):
    frame_category = "nefpls_chemical_shift_perturbations"
    frame_id = f"from_{peak_frame_1.name}_to_{peak_frame_2.name}"
    result_frame = create_nef_save_frame(frame_category, frame_id)
    result_frame.add_tag("frame_name_1", peak_frame_1.name)
    result_frame.add_tag("frame_name_2", peak_frame_2.name)
    matches_loop = Loop.from_scratch("nefpls_perturbations")
    atom_id_tags = []
    for comparison_id in range(1, 3):
        for dimension_id in range(1, num_dimensions_1 + 1):
            for atom_name_component in []:
                atom_id_tags.append(
                    f"{atom_name_component}_{comparison_id}_{dimension_id}"
                )
    loop_tags = (
        "index",
        "match_index",
        "peak_id_1",
        "peak_id_2",
        "distance",
        "chain_code",
        "sequence_code",
        "residue_name",
        "atom_name",
    )
    matches_loop.add_tag(loop_tags)
    result_frame.add_loop(matches_loop)
    for index, (peak_1_id, (peak_2_ids, distance)) in enumerate(
        result.items(), start=1
    ):
        assignments_peak_1 = _build_dim_assignments(peak_list_1_by_id[peak_1_id])
        for match_index, peak_2_id in enumerate(peak_2_ids, start=1):
            data = {
                "index": index,
                "match_index": match_index,
                "peak_id_1": peak_1_id,
                "peak_id_2": peak_2_id,
                "distance": distance,
                **assignments_peak_1,
            }
            matches_loop.add_data(
                [
                    data,
                ]
            )
    return result_frame


def _exit_if_peak_frame_dimensions_dont_match(peak_frame_1, peak_frame_2):
    num_dimensions_1 = int(peak_frame_1.get_tag("num_dimensions")[0])
    num_dimensions_2 = int(peak_frame_2.get_tag("num_dimensions")[0])

    if num_dimensions_1 != num_dimensions_2:
        msg = f"""
            The number of dimensions in the peak lists to match mustbe the same I got

                {peak_frame_1.name}: {num_dimensions_1}
                {peak_frame_2.name}: {num_dimensions_2}
        """
        exit_error(dedent(msg).strip())


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
