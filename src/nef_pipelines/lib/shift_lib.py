import dataclasses
from enum import auto
from typing import Dict, Iterable, List, Tuple

from pynmrstar import Loop, Saveframe
from strenum import StrEnum

from nef_pipelines.lib.nef_lib import UNUSED, loop_row_namespace_iter
from nef_pipelines.lib.structures import (
    AtomLabel,
    Residue,
    SequenceResidue,
    ShiftData,
    ShiftList,
)
from nef_pipelines.lib.util import fnmatch_one_of

NEF_CHEMICAL_SHIFT_LOOP = "nef_chemical_shift"


class IntensityMeasurementType(StrEnum):
    HEIGHT = auto()
    VOLUME = auto()


def nef_frames_to_shifts(frames: List[Saveframe]) -> List[ShiftData]:
    """

    :param frames:
    :return:
    """
    shifts = []

    residue_field_names = [field.name for field in dataclasses.fields(SequenceResidue)]
    atom_field_names = [
        field.name for field in dataclasses.fields(AtomLabel) if field.name != "residue"
    ]
    for frame in frames:

        try:
            loop = frame.get_loop(NEF_CHEMICAL_SHIFT_LOOP)
        except KeyError:
            continue

        for i, row in enumerate(loop_row_namespace_iter(loop), start=1):

            residue_fields = {
                name: value
                for name, value in vars(row).items()
                if name in residue_field_names
            }
            atom_fields = {
                name: value
                for name, value in vars(row).items()
                if name in atom_field_names
            }
            residue = Residue(**residue_fields)
            label = AtomLabel(residue, **atom_fields)

            value_str = ", ".join([f"{value}" for value in vars(row).values()])
            name_str = ", ".join([f"{name}" for name in vars(row).keys()])

            line = f"{name_str}\n{value_str}"

            shift_data = ShiftData(
                label,
                row.value,
                row.value_uncertainty,
                frame_name=frame.name,
                frame_row=i,
                frame_line=line,
            )
            shifts.append(shift_data)

    return shifts


def shifts_to_nef_frame(shift_list: ShiftList, frame_name: str) -> Saveframe:
    """
    convert a shift list to a nef chemical shift list frame
    :param shift_list: the shifts
    :param frame_name: the name for the frame to appended to nef_chemical_shift_list
    :return: the shift list frame
    """
    SHIFT_LIST_FRAME_CATEGORY = "nef_chemical_shift_list"
    SHIFT_LOOP_CATEGORY = "nef_chemical_shift"

    frame_code = f"{SHIFT_LIST_FRAME_CATEGORY}_{frame_name}"

    frame = Saveframe.from_scratch(frame_code, SHIFT_LIST_FRAME_CATEGORY)

    frame.add_tag("sf_category", SHIFT_LIST_FRAME_CATEGORY)
    frame.add_tag("sf_framecode", frame_code)

    loop = Loop.from_scratch()
    frame.add_loop(loop)

    tags = (
        "chain_code",
        "sequence_code",
        "residue_name",
        "atom_name",
        "value",
        "value_uncertainty",
        "element",
        "isotope_number",
    )

    loop.set_category(SHIFT_LOOP_CATEGORY)
    loop.add_tag(tags)

    for shift in shift_list.shifts:
        value_uncertainty = (
            shift.value_uncertainty if shift.value_uncertainty else UNUSED
        )

        element = shift.atom.element if shift.atom.element else UNUSED

        isotope_number = (
            shift.atom.isotope_number if shift.atom.isotope_number else UNUSED
        )

        row_data = {
            "chain_code": shift.atom.residue.chain_code,
            "sequence_code": shift.atom.residue.sequence_code,
            "residue_name": shift.atom.residue.residue_name,
            "atom_name": shift.atom.atom_name,
            "value": shift.value,
            "value_uncertainty": value_uncertainty,
            "element": element,
            "isotope_number": isotope_number,
        }
        loop.add_data(
            [
                row_data,
            ]
        )

    return frame


def collapse_common_shifts(shift_list: ShiftList) -> ShiftList:
    """
    replace entries in the shift list which are in the same residue and are related by symmetry
    and have the same shift by the reduced form e.g. HA1 1.000 HA2 1.000 -> HA* 1.000
    :param shift_list:  shift list to collapse
    :return:  collapsed chemcial shifts
    """

    result = []
    by_residue = _cluster_shifts_by_residue(shift_list)
    for residue_shifts in by_residue.values():
        result.extend(_cluster_by_shift(residue_shifts))

    return ShiftList(result)


def _cluster_shifts_by_residue(
    shift_list: ShiftList,
) -> Dict[SequenceResidue, List[ShiftData]]:
    """
    put all the shifts from the same residue in an entry in a dictionary keyed by residue

    :param shift_list: the ShiftList to cluster
    :return: the dictionary of shifts with the same residue
    """
    by_residue = {}
    for shift in shift_list.shifts:
        atom = shift.atom
        residue = SequenceResidue(
            shift.atom.chain_code, atom.sequence_code, atom.residue_name
        )
        by_residue.setdefault(residue, []).append(shift)

    return by_residue


def _cluster_by_shift(shifts: List[ShiftData]) -> List[List[ShiftData]]:
    """
    build a list lists where each child list contains ShiftData entries
    which all have the same chemicl shifts
    :param shifts: a list of shifts to cluster
    :return: ShiftData clustered by shifts
    """
    shift_map = {}

    for shift in shifts:
        shift_map.setdefault(shift.value, []).append(shift)

    result = []
    for entry in shift_map.values():

        if len(entry) > 1:
            result.extend(_collapse_cluster(entry))
        else:
            result.append(entry[0])

    return result


def _collapse_cluster(shifts: List[ShiftData]) -> List[ShiftData]:
    """
    collapse a cluster of atoms with the same shift which are symmetry related (currently in the nef style)
    HA1 / HA2 -> HA*, HG11, HG12, HG13, HG21, HG22, HG23 -> HG* [not HG**] Note all symmetry related shifts
    should have the same shift else information will be lost

    :param shifts: a list of shifts to cluster
    :return: the clusted shifts as a new list
    """

    by_stem = {}
    for shift in shifts:
        last_character = shift.atom.atom_name[-1]
        if last_character.isnumeric() or last_character == "*":
            by_stem.setdefault(shift.atom.atom_name[:-1], []).append(shift)

    result = []
    for stem, shifts in by_stem.items():
        if len(shifts) > 1:
            first_shift = shifts[0]
            first_atom = first_shift.atom

            residue = SequenceResidue(
                first_atom.chain_code, first_atom.sequence_code, first_atom.residue_name
            )
            new_atom = AtomLabel(residue, f"{stem}*")
            new_shift = ShiftData(
                new_atom, first_shift.value, first_shift.value_uncertainty
            )

            result.append(new_shift)
        else:
            result.append(shifts[0])

    if len(result) != len(shifts):
        result = _collapse_cluster(_collapse_cluster(result))

    return result


def shifts_to_chains(
    all_shifts: Iterable[ShiftData], filter: Tuple[str, ...] = ("#*,", "@*")
) -> List[str]:
    """
    get the chain codes from a list of shifts
    :param all_shifts: the shifts
    :param filter: a tuple of patterns used to exclude chains from the result [default '#*,', '@*']
                   which are the nef conventions for the unassigned chains
    :return: the matching chain codes
    """
    chain_codes = {shift.atom.residue.chain_code for shift in all_shifts}
    chain_codes = [
        chain_code
        for chain_code in chain_codes
        if not fnmatch_one_of(chain_code, filter)
    ]
    return chain_codes


def _select_unassigned_shifts(all_shifts):
    unassigned_shifts = []
    for shift in all_shifts:
        chain_code = str(shift.atom.residue.chain_code)
        sequence_code = str(shift.atom.residue.sequence_code)

        if (
            chain_code.startswith("@") or chain_code.startswith("#")
        ) and sequence_code.startswith("@"):
            unassigned_shifts.append(shift)

    return unassigned_shifts


def frames_to_assigned_and_unassigned_shift_lists(
    frames: List[Saveframe],
) -> Tuple[List[ShiftData], List[ShiftData]]:
    """
    split a list of frames into assigned and unassigned shifts
    :param frames: the frames
    :return: a tuple of assigned and unassigned shifts
    """
    all_shifts = set(nef_frames_to_shifts(frames))

    unassigned_shifts = _select_unassigned_shifts(all_shifts)

    assigned_shifts = all_shifts - set(unassigned_shifts)

    return assigned_shifts, unassigned_shifts
