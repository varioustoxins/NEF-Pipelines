# original implementation by esther
import sys
from dataclasses import dataclass
from string import digits
from typing import List, Union

import typer
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    read_entry_from_stdin_or_exit,
    select_frames_by_name,
)
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.util import exit_error, is_float, is_int
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
def shifts(
    shift_frames: List[str] = typer.Option(
        [],
        "-f",
        "--frame",
        help="selector for the shift restraint frames to use, can be called multiple times and include wild cards",
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
        help="file name to output to [default <entry_id>_shifts.tab] for stdout use -",
        metavar="<MARS_SHIFT_FILE>",
    ),
):
    """- write a mars chemical shift file"""

    if len(shift_frames) == 0:
        shift_frames = ["*"]

    entry = read_entry_from_stdin_or_exit()

    output_file = f"{entry.entry_id}_shifts.tab" if output_file is None else output_file

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

    pseudo_atom_shifts = {}
    for shift in shifts:

        # first deal with completely unassigned residues chain_code @- and sequence_code @xxxx where xxx
        # is the pseudo residue
        chain_code = str(shift.atom.residue.chain_code)
        sequence_code = str(shift.atom.residue.sequence_code)
        atom_name = shift.atom.atom_name
        if (
            chain_code.startswith("@") or chain_code.startswith("#")
        ) and sequence_code.startswith("@"):
            sequence_code = sequence_code.lstrip("@")
            sequence_code_fields = sequence_code.split("-")

            if len(sequence_code_fields) > 2:
                continue

            sequence_code = sequence_code_fields[0]
            if not is_int(sequence_code):
                continue
            sequence_code = int(sequence_code)

            negative_offset = (
                sequence_code_fields[1] if len(sequence_code_fields) == 2 else 0
            )

            if not is_int(negative_offset):
                continue
            else:
                negative_offset = int(negative_offset)

            if negative_offset not in (0, 1):
                continue

            atom_name = atom_name.replace("@", "")
            if has_numbers(atom_name):
                continue

            pseudo_atom = PseudoAtom(
                sequence_code,
                shift.atom.residue.residue_name,
                negative_offset,
                atom_name=atom_name,
            )

            if not is_float(shift.value):
                continue

                # TODO: should be value
            value = float(shift.value)

            pseudo_atom_shifts[pseudo_atom] = value

    headings = (
        ("H", ("H", 0)),
        ("N", ("N", 0)),
        ("Ca", ("CA", 0)),
        ("Ca-1", ("CA", 1)),
        ("Cb", ("CB", 0)),
        ("Cb-1", ("CB", 1)),
        ("CO", ("C", 0)),
        ("CO-1", ("C", 1)),
        ("HA", ("HA", 0)),
        ("HA-1", ("HA", 1)),
    )
    base_headers = (
        "",
        "H",
        "N",
        "CA",
        "CA-1",
        "CB",
        "CB-1",
        "CO",
        "CO-1",
        "HA",
        "HA-1",
    )

    pseudo_residues = {}
    for pseudo_atom in pseudo_atom_shifts:
        key = (pseudo_atom.atom_name, pseudo_atom.negative_offset)
        pseudo_residues.setdefault(pseudo_atom.sequence_code, {})[key] = pseudo_atom

    headers = _filter_headings_by_pseudoatoms(base_headers, pseudo_residues)

    lines = []
    for pseudo_residue_num in sorted(pseudo_residues):
        pseudo_atoms = pseudo_residues[pseudo_residue_num]

        line = []
        lines.append(line)

        line.append("PR_" + str(pseudo_residue_num))

        for heading, heading_key in headings:

            if heading_key in pseudo_atoms:

                pseudo_atom = pseudo_atoms[heading_key]
                shift = pseudo_atom_shifts[pseudo_atom]

                line.append("%-7.3f    " % shift)
            elif heading.upper() in headers:
                line.append("-         ")

    file_h = sys.stdout if output_file == "-" else open(output_file, "w")

    print(tabulate(lines, headers=headers, tablefmt="plain"), file=file_h)

    if output_file != STDOUT_PATH:
        file_h.close()

        if not sys.stdout.isatty():
            print(entry)


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
