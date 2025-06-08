from dataclasses import replace
from enum import auto
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry
from strenum import LowercaseStrEnum

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.sequence_lib import sequence_from_entry_or_exit
from nef_pipelines.lib.structures import AtomLabel, Residue
from nef_pipelines.lib.util import STDIN, is_int, parse_comma_separated_options
from nef_pipelines.tools.frames import frames_app


class AssignmentState(LowercaseStrEnum):
    PARTIAL = auto()
    FULL = auto()


# TODO should be able decide if partial assignments are required and if the residue type need to be set
# also we do nothing with pseudo residues...
# also we don't check the atom name is compatible with the residue or chem_comp
# obvious we could filter on other fields such as values

FRAMES_HELP = """\
    the names of the  frames to use, this can be a comma separated list of name or the option can be called
    called multiple times. Wild cards are allowed. If no match is found wild cards are checked as well unless
    --exact is set
"""

ASSIGNED_HELP = """
    if set lines which are consider assigned [chain_code, sequence_code and atom_name set]
    are deleted, otherwise unassigned lines are deleted. Note the --state option controls
    if all assignments on need to be complete for the line to be considered assigned
"""

STATE_HELP = """
    how complete do the assignments in a row have to be for it to be considered assigned, the default depends on
    the option --assigned if assigned is false the value is full, else it is partial
"""


# rename from filter when api is changed, filter shadows a builtin
@frames_app.command()
def filter(
    frame_selectors: List[str] = typer.Option(["*"], help=FRAMES_HELP),
    input_path: Path = typer.Option(
        STDIN,
        "--in",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
    filter_assigned: bool = typer.Option(
        False,
        "--assigned",
        help=ASSIGNED_HELP,
    ),
    assignment_state: AssignmentState = typer.Option(None, "--state", help=STATE_HELP),
):
    """-  filter the lines in one or more save frames depending on assignment status
    [currently chain_code, sequence_code and atom_name must be set and the sequence code must be in molecular
    system for an atom to be assigned]
    """

    frame_selectors = parse_comma_separated_options(frame_selectors)

    if assignment_state is None:
        if filter_assigned:
            assignment_state = AssignmentState.PARTIAL
        else:
            assignment_state = AssignmentState.FULL

    entry = read_entry_from_file_or_stdin_or_exit_error(input_path)

    entry = pipe(entry, frame_selectors, filter_assigned, assignment_state)

    print(entry)


def pipe(
    entry: Entry,
    frame_selectors: List[str],
    filter_assigned=False,
    target_assignment_state=AssignmentState.FULL,
) -> Entry:

    sequence = sequence_from_entry_or_exit(entry)

    sequence_set = set([Residue.from_sequence_residue(residue) for residue in sequence])
    # currently we ignore residue types
    sequence_set = {replace(residue, residue_name="") for residue in sequence_set}

    selected_frames = select_frames(entry, frame_selectors)
    for frame in selected_frames:

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

            if is_assignable:

                tag_sets_by_end = {}

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
                            tag_sets_by_end.setdefault(end, []).append(tag_and_index)

                for row_index, row in enumerate(loop):

                    assignment_state = _get_assignment_state(
                        row, sequence_set, tag_sets_by_end
                    )

                    assigned = False
                    if target_assignment_state is AssignmentState.FULL:
                        assigned = assignment_state is AssignmentState.FULL
                    elif target_assignment_state is AssignmentState.PARTIAL:
                        assigned = assignment_state in {
                            AssignmentState.FULL,
                            AssignmentState.PARTIAL,
                        }

                    if filter_assigned and assigned:
                        rows_to_remove.add(row_index)
                    elif not filter_assigned and not assigned:
                        rows_to_remove.add(row_index)

            for row_index in reversed(sorted(rows_to_remove)):
                del loop.data[row_index]
    return entry


def _get_assignment_state(row, sequence_set, tag_sets_by_end):
    atom_labels_by_tag_set_end = _get_atom_labels_by_tag_set(row, tag_sets_by_end)

    assigned_by_end = {}
    for set_end, atom_label in atom_labels_by_tag_set_end.items():
        residue_in_sequence = atom_label.residue in sequence_set
        atom_name = atom_label.atom_name
        atom_name_ok = (
            atom_name is not None and len(atom_name) > 0 and atom_name != UNUSED
        )

        assigned_by_end[set_end] = residue_in_sequence and atom_name_ok

    result = None
    if all(assigned_by_end.values()):
        result = AssignmentState.FULL
    elif any(assigned_by_end.values()):
        result = AssignmentState.PARTIAL

    return result


def _get_atom_labels_by_tag_set(row, tag_sets_by_end):

    residues_by_tag_end = {}
    for tag_end, tag_set in tag_sets_by_end.items():

        chain_code = None
        sequence_code = None
        # residue_name = None
        atom_name = None

        for tag, tag_index in tag_set:

            value = row[tag_index]

            if tag.startswith("chain_code"):
                chain_code = value
            elif tag.startswith("sequence_code"):
                sequence_code = value
            # ignore this for now
            # elif tag.startswith("residue_name"):
            #     residue_name = value
            elif tag.startswith("atom_name"):
                atom_name = value

            if is_int(sequence_code):
                sequence_code = int(sequence_code)

            residue = Residue(
                chain_code=chain_code,
                sequence_code=sequence_code,
                residue_name="",
            )
            atom_label = AtomLabel(residue, atom_name)
            residues_by_tag_end[tag_end] = atom_label

    return residues_by_tag_end
