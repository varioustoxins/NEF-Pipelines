# original implementation by esther
import sys
from pathlib import Path
from string import digits
from typing import Iterable, Iterator, List, Tuple

import typer
from pynmrstar import Entry, Saveframe
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    loop_row_namespace_iter,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.structures import LineInfo
from nef_pipelines.lib.util import STDIN, end_with_ordinal, exit_error
from nef_pipelines.transcoders.mars import export_app

NMR_RESIDUE = "nmr_residue"

NMR_CHAIN = "nmr_chain"

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
    input: Path = typer.Option(
        STDIN,
        "--input",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
    output_file: str = typer.Argument(
        None,
        help="file name to output to [default <entry_id>_fix_con.tab] for stdout use -",
        metavar="<MARS_SHIFT_FILE>",
    ),
):
    """- convert nef chemical shifts to mars"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    output_file = (
        f"{entry.entry_id}_fix_ass.tab" if output_file is None else output_file
    )

    table = pipe(entry)

    table = _format_table(table)
    file_h = sys.stdout if output_file == "-" else open(output_file, "w")

    print(tabulate(table, tablefmt="plain"), file=file_h)

    if output_file != STDOUT_PATH:
        file_h.close()

    if output_file != STDOUT_PATH:
        if not sys.stdout.isatty():
            print(entry)


def _format_table(table: List[List[Tuple[str, str]]]) -> List[List[str]]:
    max_overall_elem_length = 0
    for chain in table:
        max_elem_length = max([len(" ".join(prs)) for prs in chain])
        max_overall_elem_length = (
            max_elem_length
            if max_elem_length > max_overall_elem_length
            else max_overall_elem_length
        )
    for chain in table:
        for i, prs in enumerate(chain):
            pr_length = len(prs[0]) + len(prs[1])
            pad = " " * (max_overall_elem_length - pr_length)
            pr_pair = f"{prs[0]}{pad}{prs[1]}"
            chain[i] = pr_pair
    return table


def pipe(entry: Entry) -> List[List[Tuple[str, str]]]:
    frame = _get_assignment_frame_or_exit(entry)
    connected_residues = _get_connected_residues_and_chains(frame, entry)
    return _build_connected_pseudo_residues(connected_residues)


def _build_connected_pseudo_residues(connected_residues):
    table = []
    ends = []
    for chain_code, residue_codes in connected_residues.items():
        chain = [
            (f"PR_{first}", f"PR_{second}")
            for first, second in overlapped_pairs(residue_codes)
        ]
        ends.append(f"#{chain_code}")
        table.append(chain)

    return table


def _get_connected_residues_and_chains(frame: Saveframe, entry: Entry):
    connected_chains = set()
    for chain in loop_row_namespace_iter(frame.get_loop(NMR_CHAIN)):
        if chain.is_connected:
            connected_chains.add(chain.short_name)
    connected_residues = {}
    nmr_residue_loop = frame.get_loop(NMR_RESIDUE)
    for line_no, residue in enumerate(
        loop_row_namespace_iter(nmr_residue_loop), start=1
    ):
        chain_code = residue.chain_code

        if chain_code in connected_chains:
            line = nmr_residue_loop[line_no - 1]
            line_info = LineInfo(entry.entry_id, line_no, line)
            sequence_code = _get_connected_residue_or_exit_error(residue, line_info)

            connected_residues.setdefault(chain_code, []).append(sequence_code)
    for connected_chain, connected_residue_list in connected_residues.items():
        connected_residues[connected_chain] = remove_duplicates_stable(
            connected_residue_list
        )
    return connected_residues


def _get_assignment_frame_or_exit(entry):
    frames = entry.get_saveframes_by_category("ccpn_assignment")
    if len(frames) == 0:
        exit_error(f"no assignment frame found in entry {entry.name}")
    if len(frames) > 1:
        msg = f"""\
                    there should only be one assignment frame i found {len(frames)} in entry {entry.name}
                    there names were {' '.join([frame.name for frame in frames])}
            """
        exit_error(msg)
    frame = frames[0]
    return frame


def _get_connected_residue_or_exit_error(residue, line_info: LineInfo):
    sequence_code = residue.sequence_code
    if sequence_code.startswith("@"):
        sequence_code = sequence_code.lstrip("@")
        sequence_code_fields = sequence_code.split("-")
        if len(sequence_code_fields) == 0 or len(sequence_code_fields) > 2:
            msg = f"""\
                for the {end_with_ordinal(line_info.line_no)} line in the frame '_save_nmr_residue in frame
                save_ccpn_assignment in entity {line_info.file_name} the sequence code {sequence_code} had an unexpected
                format it should be @i or @i-1 where i is a number, the line was
                {line_info.line}
            """
            exit_error(msg)
        sequence_code = sequence_code_fields[0]
    return sequence_code


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