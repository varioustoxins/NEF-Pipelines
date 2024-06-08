import sys
from pathlib import Path
from typing import List, Tuple

import typer
from pynmrstar import Entry
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.shift_lib import (
    frames_to_assigned_and_unassigned_shift_lists,
    shifts_to_chains,
)
from nef_pipelines.lib.util import STDIN, STDOUT, exit_if_file_has_bytes_and_no_force
from nef_pipelines.transcoders.mars import export_app
from nef_pipelines.transcoders.mars.util import (
    _exit_if_no_frames_selected,
    _filter_shifts_by_chain,
    _select_target_chain_from_sequence_if_not_defined,
)

app = typer.Typer()


# noinspection PyUnusedLocal
@export_app.command()
def fixed(
    input_path: Path = typer.Option(
        STDIN,
        "--input",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
    shift_frame_selectors: List[str] = typer.Argument(
        None,
        help="selector for the shift restraint frames to use, can be called multiple times and include wild cards",
    ),
    target_chain: str = typer.Option(
        None,
        "-c",
        "--chain",
        help="chain to export [# and @ and the 1st chain code in the project if the is only one]",
        metavar="<CHAIN-CODE>",
    ),
    output_file: str = typer.Option(
        None,
        "-o",
        "--out",
        help="file name to output to [default <entry_id>_fix_ass.tab] for stdout use -",
        metavar="<MARS-FIXED-ASSIGNMENT>",
    ),
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="force overwrite of output file if it exists and isn't empty",
    ),
):
    """- convert chemical shifts and restraints to fixed assignments"""

    if not shift_frame_selectors:
        shift_frame_selectors = ["*"]

    entry = read_entry_from_file_or_stdin_or_exit_error(input_path)

    output_file = (
        f"{entry.entry_id}_fix_ass.tab" if output_file is None else output_file
    )
    output_file = Path(output_file)

    entry = pipe(entry, shift_frame_selectors, target_chain, output_file, force)

    if entry:
        print(entry)


def pipe(
    entry: Entry,
    shift_frame_selectors: List[str],
    target_chain: str,
    output_file: Path,
    force: bool,
) -> List[List[Tuple[str, str]]]:

    frames = entry.get_saveframes_by_category("nef_chemical_shift_list")
    frames = select_frames_by_name(frames, shift_frame_selectors)

    _exit_if_no_frames_selected(frames)

    assigned_shifts, unassigned_shifts = frames_to_assigned_and_unassigned_shift_lists(
        frames
    )

    shift_chains = shifts_to_chains([*assigned_shifts, *unassigned_shifts])

    target_chain = _select_target_chain_from_sequence_if_not_defined(
        target_chain, shift_chains
    )

    table = _build_assigned_shifts(assigned_shifts, target_chain)

    exit_if_file_has_bytes_and_no_force(output_file, force)

    file_h = sys.stdout if output_file == STDOUT else open(output_file, "w")

    print(tabulate(table, tablefmt="plain"), file=file_h)

    if output_file != STDOUT:
        file_h.close()

    result = None
    if output_file != STDOUT:
        result = entry

    return result


def _build_assigned_shifts(assigned_shifts, target_chain):
    result = []
    assigned_shifts = _filter_shifts_by_chain(assigned_shifts, target_chain)
    assigned_residues = {shift.atom.residue for shift in assigned_shifts}
    for assigned_residue in sorted(assigned_residues):
        residue_name = assigned_residue.residue_name
        sequence_code = assigned_residue.sequence_code
        assigned_residue_name = f"AR_{sequence_code}_{residue_name}"
        result.append([assigned_residue_name, str(sequence_code)])

    return result
