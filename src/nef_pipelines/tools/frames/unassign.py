import itertools
import string
import sys
from copy import copy
from dataclasses import dataclass, replace
from datetime import time
from enum import auto
from itertools import product
from pathlib import Path
from random import seed as set_random_seed
from random import shuffle
from typing import Dict, List

import typer
from ordered_set import OrderedSet
from pynmrstar import Saveframe
from strenum import KebabCaseStrEnum, LowercaseStrEnum

from nef_pipelines.lib.nef_lib import (
    SELECTORS_LOWER,
    UNUSED,
    SelectionType,
    loop_row_dict_iter,
    read_or_create_entry_exit_error_on_bad_file,
    select_frames,
)
from nef_pipelines.lib.sequence_lib import atom_sort_key
from nef_pipelines.lib.structures import AtomLabel, Residue
from nef_pipelines.lib.util import (
    STDIN,
    chunks,
    exit_error,
    is_int,
    parse_comma_separated_options,
    strip_characters_left,
)
from nef_pipelines.tools.frames import frames_app

# TODO: add the ability to do inverted assignments with ^
RESIDUE_RANGES_HELP = """
    residue ranges to unassign, can be defined as comma separated pairs of ranges e.g 1-10,11-24
    or can also have a colon separated chain_code e.g A:1-10,B:14-32. Multiple selections are combined
    additively. Multiple copies of the option can be used to add extra values [default is all]
"""

SELECTOR_HELP = """
    limit changes to a a particular frame by a selector which can be a frame name or category
    note: wildcards [*] are allowed. Frames are selected by name and subsequently by category if the name
    doesn't match [-t /--selector-type allows you to force which selection type to use]. If no frame
    names or categories are provided all frames are unassigned.
"""

ATOM_LABEL_FIELDS = "chain_code sequence_code residue_name atom_name".split()


class Targets(KebabCaseStrEnum):
    CHAIN_CODE = auto()
    SEQUENCE_CODE = auto()
    RESIDUE_NAME = auto()
    # RESIDUE = auto()  #TODO add..
    ATOM_NAME = auto()
    ALL = auto()
    NOT_ATOM = auto()


ALL_COMPONENTS = {
    Targets.CHAIN_CODE,
    Targets.SEQUENCE_CODE,
    Targets.RESIDUE_NAME,
    Targets.ATOM_NAME,
}
NOT_ATOM_COMPONENTS = copy(ALL_COMPONENTS)
NOT_ATOM_COMPONENTS.remove(Targets.ATOM_NAME)

TARGET_LOOKUP = {
    str(Targets.CHAIN_CODE).replace("_", "-"): {
        Targets.CHAIN_CODE,
    },
    str(Targets.SEQUENCE_CODE).replace("_", "-"): {
        Targets.SEQUENCE_CODE,
    },
    str(Targets.RESIDUE_NAME).replace("_", "-"): {
        Targets.RESIDUE_NAME,
    },
    str(Targets.ATOM_NAME).replace("_", "-"): {
        Targets.ATOM_NAME,
    },
    str(Targets.ALL): ALL_COMPONENTS,
    str(Targets.NOT_ATOM).replace("_", "-"): NOT_ATOM_COMPONENTS,
    # str(Targets.RESIDUE): { #TODO add
    #     Targets.SEQUENCE_CODE,
    #     Targets.RESIDUE_NAME,
    # },
}

# TODO allow residue as an unassignment
# TARGETS_HELP = f"""
#     choose what to de-assign it can be a comma separated list or called multiple times. Possible values are:
#     {', '.join([e.value for e in Targets])}.
#     all, residue and not_atom are combinations, all is: chain_code + sequence_code + residue_name + atom_name and
#     residue is sequence_code + residue_name, not_atom is: chain_code + sequence_code + residue_name.
# """

# TODO: allow unique abbreviations
TARGETS_HELP = f"""
    choose what to de-assign it can be a comma separated list or called multiple times. Possible values are:
    {', '.join([e.value for e in Targets])}.
    all and not_atom are combinations, all is: chain_code + sequence_code + residue_name + atom_name and
    not_atom is: chain_code + sequence_code + residue_name.
"""


# could do with an ordered mode which would sort assignments
# but would require a shift sorter
class SequenceMode(LowercaseStrEnum):
    UNUSED = auto()
    INDEX = auto()
    ORDERED = auto()
    RANDOM = auto()
    PRESERVE = auto()


# TODO: how do you decide whether its a selection within a chain or the file
SEQUENCE_MODE_HELP = f"""
    value to deassign the sequence code to [one of {', '.join([e for e in SequenceMode])}] UNUSED is .,
    INDEX is the index of the assignment in its chain, RANDOM is a random index for the assignment
    within its chain, ORDERED retains the order of the residues when deassigned to pseudo residues, PRESERVE deassigns
    residues to pseudo residues with the same number as the assigned residue any clashes are disambiguated by renaming
    existing pseudo residues.
"""

CHAIN_VALUE_HELP = """
    value to deassign chains to [note @- is the default nmr chain and . is no chain] if more than one value is specified
    [using multiple options or a comma separated list] they will be treated as old and new value pairs, with old values
    being reassigned to the new values. Current values which are not in the new values will be left untouched.
"""

RANDOM_SEED_HELP = """
    set the random seed to an integer, any value less than zero will set the seed from the current clock and
    note the value
"""
ANY = "*"

SELECTION_TYPE_HELP = f"""
    how to select frames to unassign, can be one of: {SELECTORS_LOWER}.
    Any will match on frame name first and then if there is no match attempt to match on category
"""

USE_RESIDUE_OFFSETS_HELP = """
if the experiment is a triple resonance experiment don't offset residues so that assignment from the previous frame
are labelled as CA-1 and CB-1 [compatability with CCPN]
"""
# TODO: add the ability to unassign a particular dimension
# TODO: add the ability specify the pseudo residue prefix


@dataclass
class ResidueRange:
    chain_code: str
    start: int
    end: int


def _build_residue_ranges(raw_residue_ranges: List[str]) -> List[ResidueRange]:

    results = []
    for elem in raw_residue_ranges:
        if ":" in elem:
            chain_code, range_str = elem.split(":")
        else:
            chain_code = ANY
            range_str = elem

        range_fields = range_str.split("-")

        if len(range_fields) != 2:
            msg = f"""
                residue ranges must be in the form <START>-<END> [2 elements], i got {elem} [{len(range_fields)}]
            """
            exit_error(msg)

        for i, field in enumerate(range_fields):
            if not is_int(field):
                msg = f"""
                    residue ranges must be integers, i got {field} for element {i} in {elem}
                """
                exit_error(msg)

            range_fields[i] = int(field)

        start, end = range_fields

        if end >= start:
            results.append(ResidueRange(chain_code, start, end))

    if not results:
        results.append(ResidueRange(ANY, -sys.maxsize, sys.maxsize))
    return results


@frames_app.command()
def unassign(
    selector_type: SelectionType = typer.Option(
        SelectionType.ANY, "-t", "--selector-type", help=SELECTION_TYPE_HELP
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    targets: List[Targets] = typer.Option(
        [Targets.NOT_ATOM], "-t", "--targets", help=TARGETS_HELP
    ),
    chain_values: List[str] = typer.Option(
        [], metavar="<CHAIN> | <OLD-CHAIN>: <NEW-CHAIN>...", help=CHAIN_VALUE_HELP
    ),
    sequence_mode: SequenceMode = typer.Option(
        SequenceMode.INDEX, metavar="<MODE>", help=SEQUENCE_MODE_HELP
    ),
    random_seed: int = typer.Option(42, metavar="<RANDOM-SEED>", help=RANDOM_SEED_HELP),
    no_residue_offsets: bool = typer.Option(
        False, "--no-residue-offsets", help=USE_RESIDUE_OFFSETS_HELP
    ),
    raw_residue_ranges: List[str] = typer.Option(
        None,
        "--residue-ranges",
        help=RESIDUE_RANGES_HELP,
    ),
    frame_selectors: List[str] = typer.Argument(
        None,
        help=SELECTOR_HELP,
    ),
):
    """- unassign frames in the current input [alpha]"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    raw_residue_ranges = parse_comma_separated_options(raw_residue_ranges)

    residue_ranges = _build_residue_ranges(raw_residue_ranges)

    use_residue_offsets = not no_residue_offsets

    if random_seed < 0:
        seed = int(time.time())
        set_random_seed(seed)
        print(f"SEED is set to: {seed}", file=sys.stderr)
    else:
        set_random_seed(random_seed)

    chain_values = parse_comma_separated_options(chain_values)
    num_chain_values = len(chain_values)
    if num_chain_values == 0:
        chain_mappings = {ANY: "@-"}
    elif num_chain_values > 1 and num_chain_values % 2 != 0:
        msg = f"""
            if there are more than two new chain_code values specified they must come in pairs i got
            {num_chain_values}, the values were {', '.join(chain_values)}
        """
        exit_error(msg)

    elif num_chain_values == 1:
        chain_mappings = {ANY: chain_values[0]}
    else:
        chain_mappings = {old: new for old, new in chunks(chain_values, 2)}

    raw_targets = parse_comma_separated_options(targets)

    targets = _build_targets(raw_targets)

    if Targets.CHAIN_CODE in targets and len(chain_mappings) == 0:
        chain_mappings_msg = ", ".join(
            [f"{first} -> {second}" for first, second in chain_mappings.items()]
        )

        msg = f"""\
            you can't have chain mappings and not target chains, you might want to add CHAIN_CODE to --targets!
            targets were: {', '.join([str(target) for target in targets])}
            chain mappings were: {chain_mappings_msg}
        """

        exit_error(msg)

    frame_selectors = {
        (frame.category, frame.name)
        for frame in select_frames(entry, frame_selectors, selector_type)
    }

    entry = pipe(
        entry,
        frame_selectors,
        targets,
        sequence_mode,
        chain_mappings,
        residue_ranges,
        use_residue_offsets,
    )

    print(entry)


# noinspection PyUnusedLocal


# todo move frame selectors to non pipe part
def pipe(
    entry,
    frame_selectors,
    targets,
    sequence_mode,
    chain_mappings,
    residue_ranges,
    use_residue_offsets,
):

    all_assignments = OrderedSet()

    target_frames = [
        frame for frame in entry if (frame.category, frame.name) in frame_selectors
    ]

    # this is a bit messy it uses the entry for storing data...
    for frame in target_frames:
        if use_residue_offsets:
            _offset_sequence_codes_in_triple(frame, targets)

    for frame in target_frames:
        all_assignments.update(_build_current_assignments_for_frame(frame))

    assignments_to_remove = _select_assignments_to_remove_by_residue_ranges(
        all_assignments, residue_ranges, use_residue_offsets
    )

    if sequence_mode == SequenceMode.ORDERED:
        assignments_to_remove = sorted(assignments_to_remove, key=atom_sort_key)

    assignment_map = _map_assignments(
        assignments_to_remove, targets, sequence_mode, chain_mappings
    )

    for frame in target_frames:
        for loop in frame:
            _reassign_loop(loop, assignment_map)

    for frame in target_frames:
        if use_residue_offsets:
            _unoffset_sequence_codes_in_triple(frame, targets)

    return entry


def _select_assignments_to_remove_by_residue_ranges(
    current_assignments, residue_ranges, use_residue_offsets
):
    assignments_to_remove = OrderedSet()

    current_assignments = OrderedSet(current_assignments)
    for assignment in current_assignments:
        for residue_range in residue_ranges:
            # TODO: add a specific function to check residue assignment status
            if (
                residue_range.chain_code == ANY
                or residue_range.chain_code == assignment.residue.chain_code
            ):
                if (
                    is_int(assignment.residue.sequence_code)
                    and residue_range.start
                    <= assignment.residue.sequence_code
                    <= residue_range.end
                ):
                    assignments_to_remove.add(assignment)
                    break
                elif (
                    assignment.residue.chain_code == "@-"
                    and isinstance(assignment.residue.sequence_code, str)
                    and assignment.residue.sequence_code[0] == "@"
                    and is_int(assignment.residue.sequence_code[1:])
                ):
                    break  # already fully unassigned ignore
                elif (
                    residue_range.start == -sys.maxsize
                    and residue_range.end == sys.maxsize
                    and assignment.residue.sequence_code[0] in "@#"
                ):
                    assignments_to_remove.add(assignment)
                    break

    return assignments_to_remove


def _reassign_loop(loop, assignment_map):
    tag_indices = {tag: index for index, tag in enumerate(loop.tags)}
    for row_index, row in enumerate(loop_row_dict_iter(loop)):
        assignments_by_index = {}
        for index, prefix in product(range(1, 16), ATOM_LABEL_FIELDS):

            if prefix in row:
                key = prefix
            else:
                key = f"{prefix}_{index}"

            if key not in row:
                break

            assignments_by_index.setdefault(index, {})[prefix] = row[key]

        for column_index, assignment in enumerate(
            assignments_by_index.values(), start=1
        ):

            old_label = _dict_to_label(assignment)

            if old_label is not None and old_label in assignment_map:

                new_label = assignment_map[old_label]

                for atom_label_field in ATOM_LABEL_FIELDS:
                    key = None
                    if atom_label_field in tag_indices:
                        key = atom_label_field
                    if not key:
                        possible_key = f"{atom_label_field}_{column_index}"
                        if possible_key in tag_indices:
                            key = possible_key

                    if key:
                        tag_index = tag_indices[key]

                        if atom_label_field == "chain_code":
                            new_value = new_label.residue.chain_code
                        elif atom_label_field == "sequence_code":
                            if new_label.residue.offset == 0:
                                new_value = new_label.residue.sequence_code
                            else:
                                if new_label.residue.sequence_code != UNUSED:
                                    new_value = f"{new_label.residue.sequence_code}{new_label.residue.offset}"
                                else:
                                    new_value = new_label.residue.sequence_code

                        elif atom_label_field == "residue_name":
                            new_value = new_label.residue.residue_name
                        elif atom_label_field == "atom_name":
                            new_value = new_label.atom_name

                        loop.data[row_index][tag_index] = new_value


def _build_current_assignments_for_frame(frame):

    result = OrderedSet()

    for loop in frame:
        for i, row in enumerate(loop_row_dict_iter(loop)):
            assignments_by_index = {}
            for index, prefix in product(range(1, 16), ATOM_LABEL_FIELDS):

                if prefix in row:
                    key = prefix
                else:
                    key = f"{prefix}_{index}"

                    if key not in row:
                        break

                assignments_by_index.setdefault(index, {})[prefix] = row[key]

            for assignment in assignments_by_index.values():
                label = _dict_to_label(assignment)

                if label:
                    result.add(label)

    return result


def _build_targets(raw_targets: List[Targets]) -> List[Targets]:
    result = set()

    for raw_target in raw_targets:
        result.update(TARGET_LOOKUP[raw_target])

    return result


def _dict_to_label(assignment):
    result = None
    if "atom_name" in assignment:
        atom_name = assignment["atom_name"]
        residue_values = {
            key: assignment[key]
            for key in assignment
            if key != "atom_name" and key in ATOM_LABEL_FIELDS
        }
        if "sequence_code" in residue_values:
            sequence_code = residue_values["sequence_code"]
            if is_int(sequence_code):
                residue_values["sequence_code"] = int(sequence_code)
            elif sequence_code_offset := _get_sequence_code_and_offset_or_none(
                sequence_code
            ):
                sequence_code, offset = sequence_code_offset
                residue_values["sequence_code"] = sequence_code
                residue_values["offset"] = offset
            else:
                residue_values["sequence_code"] = sequence_code

        residue = Residue(**residue_values)
        result = AtomLabel(residue, atom_name)
    return result


def _get_sequence_code_and_offset_or_none(sequence_code):

    result = None
    sequence_code_fields = sequence_code.split("-") if "-" in str(sequence_code) else []
    if len(sequence_code_fields) == 2:
        sequence_code, offset = sequence_code_fields
        if is_int(sequence_code) and is_int(offset):
            sequence_code = int(sequence_code)
            offset = -int(offset)

            result = sequence_code, offset
    return result


TRIPLE_RESONANCE_CLASSIFICATION = [
    "H[N[co[CA]]]",
    "H[N[CA[CB]]]",
    "H[N[co[CA[CB]]]]",
    "H[N[CA]]",
    "H[N[ca[CO]]]",
    "H[N[CO]]",
]


def _is_triple_resonance_frame(frame: Saveframe):
    result = False
    if frame.category == "nef_nmr_spectrum":
        experiment_classification = frame.get_tag("experiment_classification")
        experiment_classification = (
            experiment_classification[0] if experiment_classification else None
        )
        if experiment_classification in TRIPLE_RESONANCE_CLASSIFICATION:
            result = True
    return result


def _map_assignments(
    assignments: List[AtomLabel], targets, sequence_mode, chain_mappings
) -> Dict[AtomLabel, AtomLabel]:

    assignment_map = {}
    if Targets.CHAIN_CODE in targets:
        for assignment in assignments:

            if sequence_mode == SequenceMode.UNUSED:
                new_chain_code = "."
            elif len(chain_mappings) == 1 and list(chain_mappings.keys())[0] == ANY:
                new_chain_code = list(chain_mappings.values())[0]
            else:
                target_chain_code = assignment.residue.chain_code
                new_chain_code = target_chain_code
                if assignment.residue.chain_code in chain_mappings:
                    new_chain_code = chain_mappings[target_chain_code]

            new_residue = replace(assignment.residue, chain_code=new_chain_code)
            new_assignment = replace(assignment, residue=new_residue)

            assignment_map[assignment] = new_assignment

    if Targets.RESIDUE_NAME in targets:
        for assignment, new_assignment in assignment_map.items():

            new_residue = replace(new_assignment.residue, residue_name=UNUSED)
            new_assignment = replace(new_assignment, residue=new_residue)

            assignment_map[assignment] = new_assignment

    if Targets.ATOM_NAME in targets:
        for assignment, new_assignment in assignment_map.items():

            new_assignment = replace(new_assignment, atom_name=UNUSED)

            assignment_map[assignment] = new_assignment

    if Targets.SEQUENCE_CODE in targets:
        new_assignment_by_chain = {}
        for assignment, new_assignment in assignment_map.items():
            chain_code = new_assignment.residue.chain_code
            new_assignment_by_chain.setdefault(chain_code, []).append(
                (assignment, new_assignment)
            )

        sequence_code_map = {}

        if len(new_assignment_by_chain) > 1:
            msg = """
                !WARNING! there is more than one chain present, this code hasn't been tested with multiple chains...
            """
            print(msg, file=sys.stderr)

        for chain, assignments in new_assignment_by_chain.items():
            old_sequence_codes = OrderedSet()
            for old_assignment, new_assignment in assignments:

                sequence_code = str(new_assignment.residue.sequence_code)

                old_sequence_codes.add(sequence_code)

            if sequence_mode == SequenceMode.UNUSED:
                for old_sequence_code in old_sequence_codes:
                    sequence_code_map[old_sequence_code] = UNUSED

            elif sequence_mode in (
                SequenceMode.INDEX,
                SequenceMode.RANDOM,
                SequenceMode.ORDERED,
            ):
                # pull out unassigned sequence_codes
                used_pseudo_residue_sequence_codes = [
                    sequence_code
                    for sequence_code in old_sequence_codes
                    if sequence_code[0] not in string.digits
                ]
                old_sequence_codes = [
                    sequence_code
                    for sequence_code in old_sequence_codes
                    if sequence_code[0] in string.digits
                ]

                new_sequence_code_counter = itertools.count(1)
                new_sequence_codes = []
                for _ in old_sequence_codes:

                    putative_sequence_code = next(new_sequence_code_counter)
                    while (
                        f"@{putative_sequence_code}"
                        in used_pseudo_residue_sequence_codes
                    ):
                        putative_sequence_code = next(new_sequence_code_counter)

                    new_sequence_codes.append(f"@{putative_sequence_code}")

                if sequence_mode == SequenceMode.RANDOM:
                    shuffle(new_sequence_codes)

                for i, old_sequence_code in enumerate(old_sequence_codes):
                    sequence_code_map[old_sequence_code] = new_sequence_codes[i]

                for sequence_code in used_pseudo_residue_sequence_codes:
                    sequence_code_map[sequence_code] = sequence_code

            elif sequence_mode == SequenceMode.PRESERVE:

                # TODO: note there is a subtle difference here to above can this be removed
                used_pseudo_residue_sequence_codes = [
                    sequence_code
                    for sequence_code in old_sequence_codes
                    if not is_int(sequence_code)
                ]
                old_sequence_codes = [
                    sequence_code
                    for sequence_code in old_sequence_codes
                    if is_int(sequence_code)
                ]

                sequence_code_map = {}

                for sequence_code in old_sequence_codes:
                    sequence_code_map[sequence_code] = f"@{sequence_code}"

                possible_new_sequence_codes = {}
                for used_sequence_code in used_pseudo_residue_sequence_codes:
                    if used_sequence_code == UNUSED:
                        possible_new_sequence_codes[UNUSED] = UNUSED
                    else:
                        for i in itertools.chain(
                            [
                                "",
                            ],
                            itertools.count(1),
                        ):

                            prefix, sequence_code = strip_characters_left(
                                used_sequence_code, string.ascii_letters + "@#"
                            )

                            new_sequence_code = f"{prefix}PR_{i}{sequence_code}"
                            if new_sequence_code in sequence_code_map:
                                continue

                            possible_new_sequence_codes[used_sequence_code] = (
                                new_sequence_code
                            )
                            break

                sequence_code_map.update(possible_new_sequence_codes)

        for assignment, new_assignment in assignment_map.items():
            old_sequence_code = str(new_assignment.residue.sequence_code)
            offset = None
            if "-" in old_sequence_code:
                fields = old_sequence_code.split("-")
                if is_int(fields[-1]):
                    offset = fields[-1]
                    old_sequence_code = "-".join(fields[:-1])

            new_sequence_code = sequence_code_map[old_sequence_code]
            if sequence_mode == SequenceMode.UNUSED:
                new_sequence_code = UNUSED
            elif offset is not None:
                new_sequence_code = f"{new_sequence_code}-{offset}"

            updated_residue = replace(
                new_assignment.residue, sequence_code=new_sequence_code
            )

            if updated_residue.sequence_code == UNUSED:
                updated_residue = replace(updated_residue, chain_code=UNUSED)

            updated_atom_label = replace(new_assignment, residue=updated_residue)

            assignment_map[assignment] = updated_atom_label

    return assignment_map


def _offset_sequence_codes_in_triple(frame, targets):
    if _is_triple_resonance_frame(frame) and Targets.SEQUENCE_CODE in targets:
        peak_loop = frame.get_loop("nef_peak")

        sequence_codes = set()
        for row in loop_row_dict_iter(peak_loop):
            for i in range(1, 16):
                key = f"{'sequence_code'}_{i}"
                if key in row:
                    sequence_code = row[key]
                    if is_int(sequence_code):
                        sequence_codes.add(int(sequence_code))

            max_sequence_code = max(sequence_codes)
            max_sequence_code_m1 = max_sequence_code - 1

            for i in range(1, 16):
                key = f"{'sequence_code'}_{i}"
                if key in row:
                    sequence_code = row[key]
                    if is_int(sequence_code):
                        sequence_code = int(sequence_code)
                        if sequence_code == max_sequence_code_m1:
                            sequence_code = f"{max_sequence_code}-1"
                            row[key] = sequence_code


def _unoffset_sequence_codes_in_triple(frame, targets):
    if _is_triple_resonance_frame(frame) and Targets.SEQUENCE_CODE in targets:
        peak_loop = frame.get_loop("nef_peak")

        for row in loop_row_dict_iter(peak_loop):
            for i in range(1, 16):
                key = f"{'sequence_code'}_{i}"
                if key in row:
                    sequence_code = row[key]
                    is_assigned_residue = str(sequence_code)[0] != "@"
                    if is_assigned_residue:
                        if sequence_code_and_offset := _get_sequence_code_and_offset_or_none(
                            sequence_code
                        ):
                            sequence_code, offset = sequence_code_and_offset
                            sequence_code = sequence_code + offset
                            row[key] = sequence_code
