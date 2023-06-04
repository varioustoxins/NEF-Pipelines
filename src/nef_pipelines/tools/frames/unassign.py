import itertools
import string
import sys
from copy import copy
from dataclasses import replace
from datetime import time
from enum import auto
from itertools import product
from pathlib import Path
from random import seed as set_random_seed
from random import shuffle
from typing import Dict, List

import typer
from ordered_set import OrderedSet
from strenum import LowercaseStrEnum

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

SELECTOR_HELP = """
    limit changes to a a particular frame by a selector which can be a frame name or category
    note: wildcards [*] are allowed. Frames are selected by name and subsequently by category if the name
    doesn't match [-t /--selector-type allows you to force which selection type to use]. If no frame
    names or categories are provided all frames are unassigned.
"""

ATOM_LABEL_FIELDS = "chain_code sequence_code residue_name atom_name".split()


class Targets(LowercaseStrEnum):
    CHAIN_CODE = auto()
    SEQUENCE_CODE = auto()
    RESIDUE_NAME = auto()
    ATOM_NAME = auto()
    OFFSETS = auto()
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
    str(Targets.CHAIN_CODE): {
        Targets.CHAIN_CODE,
    },
    str(Targets.SEQUENCE_CODE): {
        Targets.SEQUENCE_CODE,
    },
    str(Targets.RESIDUE_NAME): {
        Targets.RESIDUE_NAME,
    },
    str(Targets.ATOM_NAME): {
        Targets.ATOM_NAME,
    },
    str(Targets.ALL): ALL_COMPONENTS,
    str(Targets.NOT_ATOM): NOT_ATOM_COMPONENTS,
}

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
    value to deassign the sequence code to [one of {', '.join([e.value for e in SequenceMode])}] UNUSED is .,
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
    how to select frames to renumber, can be one of: {SELECTORS_LOWER}.
    Any will match on frame name first and then if there is no match attempt to match on category
"""

# TODO: add the ability to unassign a particular dimension
# TODO: add the ability specify the pseudo residue prefix


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
    frame_selectors: List[str] = typer.Argument(
        None,
        help=SELECTOR_HELP,
    ),
):
    """- unassign frames in the current input"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

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
        for frame in select_frames(entry, selector_type, frame_selectors)
    }

    entry = pipe(entry, frame_selectors, targets, sequence_mode, chain_mappings)

    print(entry)


# noinspection PyUnusedLocal
def _build_targets(raw_targets: List[Targets]) -> List[Targets]:
    result = set()

    for raw_target in raw_targets:
        result.update(TARGET_LOOKUP[raw_target])

    return result


def pipe(entry, frame_selectors, targets, sequence_mode, chain_mappings):

    current_assignments = OrderedSet()
    for frame in entry:
        if (frame.category, frame.name) in frame_selectors:
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
                            current_assignments.add(label)

    if sequence_mode == SequenceMode.ORDERED:
        current_assignments = sorted(current_assignments, key=atom_sort_key)

    assignment_map = _map_assignments(
        current_assignments, targets, sequence_mode, chain_mappings
    )

    for frame in entry:
        if (frame.category, frame.name) in frame_selectors:
            for loop in frame:
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

                        if old_label is not None:

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
                                        new_value = new_label.residue.sequence_code
                                    elif atom_label_field == "residue_name":
                                        new_value = new_label.residue.residue_name
                                    elif atom_label_field == "atom_name":
                                        new_value = new_label.atom_name

                                    loop.data[row_index][tag_index] = new_value

    return entry


def _dict_to_label(assignment):
    result = None
    if "atom_name" in assignment:
        atom_name = assignment["atom_name"]
        residue_values = {
            key: assignment[key]
            for key in assignment
            if key != "atom_name" and key in ATOM_LABEL_FIELDS
        }
        residue = Residue(**residue_values)
        result = AtomLabel(residue, atom_name)
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
            for _, new_assignment in assignments:

                sequence_code = str(new_assignment.residue.sequence_code)
                if "-" in sequence_code:
                    sequence_code = "-".join(sequence_code.split("-")[:-1])
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

                            possible_new_sequence_codes[
                                used_sequence_code
                            ] = new_sequence_code
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
