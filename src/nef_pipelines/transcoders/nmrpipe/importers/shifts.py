from dataclasses import replace
from pathlib import Path
from typing import Iterable, List

import typer

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_file_or_exit,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import chain_code_iter, translate_1_to_3
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import ShiftList
from nef_pipelines.lib.util import STDIN, parse_comma_separated_options
from nef_pipelines.transcoders.nmrpipe import import_app
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import (
    read_db_file_records,
    read_shift_file,
)

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command()
def shifts(
    chain_codes: List[str] = typer.Option(
        None,
        "--chains",
        help="chain codes, can be called multiple times and or be a comma separated list [no spaces!]",
        metavar="<CHAIN-CODES>",
    ),
    entry_name: str = typer.Option("nmrpipe", help="a name for the entry"),
    frame_name: str = typer.Option("nmrpipe", help="a name for the frame"),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type nmrpipe.tab", metavar="<TAB-FILE>"
    ),
):
    """convert nmrpipe shift file <nmrpipe>.tab files to NEF"""

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name)

    chain_codes = parse_comma_separated_options(chain_codes)

    if not chain_codes:
        chain_codes = ["A"]

    pipe(entry, chain_codes, file_names, frame_name)


def pipe(entry, chain_codes, file_names, frame_name):
    nmrpipe_frames = []

    for file_name, chain_code in zip(file_names, chain_code_iter(chain_codes)):

        lines = read_file_or_exit(file_name)

        nmrpipe_shifts = read_shifts(lines, chain_code=chain_code)

        nmrpipe_shifts = _convert_1let_3let_if_needed(nmrpipe_shifts)

        frame = shifts_to_nef_frame(nmrpipe_shifts, frame_name)

        nmrpipe_frames.append(frame)

    entry = add_frames_to_entry(entry, nmrpipe_frames)

    print(entry)


def _convert_1let_3let_if_needed(shifts: ShiftList) -> ShiftList:

    new_shifts = []
    for shift in shifts.shifts:
        residue_name = [
            shift.atom.residue.residue_name,
        ]

        if len(residue_name[0]) == 1:
            residue_name = translate_1_to_3(residue_name)

        new_residue = replace(shift.atom.residue, residue_name=residue_name[0])
        new_atom = replace(shift.atom, residue=new_residue)
        new_shift = replace(shift, atom=new_atom)

        new_shifts.append(new_shift)

    new_shift_list = ShiftList(new_shifts)

    return new_shift_list


def read_shifts(
    shift_lines: Iterable[str],
    chain_code: str = "A",
    sequence_file_name: str = "unknown",
) -> ShiftList:

    gdb_file = read_db_file_records(shift_lines, sequence_file_name)

    return read_shift_file(gdb_file, chain_code)
