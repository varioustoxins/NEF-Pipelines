# original implementation by esther
import sys
from dataclasses import dataclass
from pathlib import Path
from string import digits
from typing import Iterable, Iterator, List, Tuple, Union

import typer
from ordered_set import OrderedSet
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.transcoders.mars import export_app

STDOUT_PATH = "-"

app = typer.Typer()

# TODO: name translations
# TODO: correct weights
# TODO: move utuilities to lib
# TODO: support multiple chains

REMOVE_DIGITS = str.maketrans("", "", digits)


def has_numbers(input: str) -> bool:
    return any(char.isdigit() for char in input)


# noinspection PyUnusedLocal
@export_app.command()
def fragments(
    shift_frames: List[str] = typer.Option(
        [],
        "-f",
        "--frame",
        help="selector for the shift restraint frames to use, can be called multiple times and include wild cards",
    ),
    input: Path = typer.Option(
        STDIN,
        "--input",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
    chain: str = typer.Option(
        [],
        "-c",
        "--chain",
        help="chains to export, to add multiple chains use repeated calls  [default: 'A']",
        metavar="<CHAIN-CODE>",
    ),
    output_file: str = typer.Argument(
        None,
        help="file name to output to [default <entry_id>_fix_con.tab] for stdout use -",
        metavar="<MARS_SHIFT_FILE>",
    ),
):
    """- convert nef chemical shifts to mars"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    if len(shift_frames) == 0:
        shift_frames = ["*"]

    # print(entry)

    output_file = (
        f"{entry.entry_id}_fix_ass.tab" if output_file is None else output_file
    )

    frames = entry.get_saveframes_by_category("nef_chemical_shift_list")

    frames = select_frames_by_name(frames, shift_frames)

    if len(frames) == 0:
        exit_error("no shift frames selected")

    shifts = nef_frames_to_shifts(frames)

    @dataclass(frozen=True, order=True)
    class PseudoAtom:
        sequence_code: Union[int, str]
        residue_name: str
        negative_offset: int
        atom_name: str

    by_chain = {}
    for shift in shifts:

        # first deal with completely unassigned residues chain_code @- and sequence_code @xxxx where xxx
        # is the pseudo residue
        chain_code = shift.atom.residue.chain_code
        sequence_code = shift.atom.residue.sequence_code

        if chain_code.startswith("#"):
            chain_code = chain_code.lstrip("#")
            sequence_code = sequence_code.lstrip("@")

            sequence_code_fields = sequence_code.split("-")

            if len(sequence_code_fields) > 2:
                continue

            sequence_code = sequence_code_fields[0]

            by_chain.setdefault(chain_code, OrderedSet()).add(sequence_code)

    table = []
    ends = []
    for chain_code, residue_codes in by_chain.items():

        row = [
            f"PR_{first} PR_{second}"
            for first, second in overlapped_pairs(residue_codes)
        ]
        ends.append(f"#{chain_code}")
        table.append(row)

    max_overall_elem_length = 0
    for row in table:

        max_elem_length = max([len(elem) for elem in row])
        max_overall_elem_length = (
            max_elem_length
            if max_elem_length > max_overall_elem_length
            else max_overall_elem_length
        )

    for row in table:
        for i, elem in enumerate(row):
            prs = elem.split()
            pr_length = len(prs[0]) + len(prs[1])
            pad = " " * (max_overall_elem_length - pr_length)
            pr_pair = f"{prs[0]}{pad}{prs[1]}"
            row[i] = pr_pair

    file_h = sys.stdout if output_file == "-" else open(output_file, "w")

    print(tabulate(table, tablefmt="plain"), file=file_h)

    # if output_file != STDOUT_PATH:
    #     file_h.close()

    # if output_file != STDOUT_PATH:
    #     # if not sys.stdout.isatty():
    print(entry)


# https://stackoverflow.com/questions/480214/how-do-i-remove-duplicates-from-a-list-while-preserving-order
def remove_duplicates_stable(seq: Iterable) -> List:

    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


# https://stackoverflow.com/questions/21303224/iterate-over-all-pairs-of-consecutive-items-in-a-list
def overlapped_pairs(seq: Iterator) -> Iterator[Tuple]:
    for first, second in zip(seq, seq[1:]):
        yield first, second


def _filter_headings_by_pseudoatoms(base_headers, pseudo_residues):
    atom_names = set()
    for pseudo_residue in pseudo_residues.values():
        for pseudo_atom in pseudo_residue.values():
            offset = (
                f"-{pseudo_atom.negative_offset}"
                if pseudo_atom.negative_offset == 1
                else ""
            )
            atom_names.add(f"{pseudo_atom.atom_name.upper()}{offset}")
    headers = []
    for header in base_headers:
        if header == "" or header in atom_names:
            headers.append(header)
    return headers
