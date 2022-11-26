# original implementation by esther
from dataclasses import dataclass
from string import digits
from typing import List

import typer
from tabulate import tabulate

from lib.nef_lib import create_entry_from_stdin_or_exit, select_frames_by_name
from lib.shift_lib import nef_frames_to_shifts
from lib.util import exit_error, is_float, is_int
from transcoders.mars import export_app

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
    chains: str = typer.Option(
        [],
        "-c",
        "--chain",
        help="chains to export, to add mutiple chains use repeated calls  [default: 'A']",
        metavar="<CHAIN-CODE>",
    ),
):
    """- convert nef chemical shifts to mars"""

    if len(shift_frames) == 0:
        shift_frames = ["*"]

    entry = create_entry_from_stdin_or_exit()

    frames = entry.get_saveframes_by_category("nef_chemical_shift_list")

    frames = select_frames_by_name(frames, shift_frames)

    if len(frames) == 0:
        exit_error("no shift frames selected")

    shifts = nef_frames_to_shifts(frames)

    @dataclass(frozen=True, order=True)
    class PseudoAtom:
        sequence_code: int
        residue_name: str
        negative_offset: int
        atom_name: str

    pseudo_atom_shifts = {}
    for shift in shifts:

        # first deal with completely unassigned residues chain_code @- and sequence_code @xxxx where xxx
        # is the pseudo residue
        chain_code = shift.atom.chain_code
        sequence_code = shift.atom.sequence_code
        atom_name = shift.atom.atom_name
        if chain_code.startswith("@-") and sequence_code.startswith("@"):
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
                shift.atom.residue_name,
                negative_offset,
                atom_name=atom_name,
            )

            if not is_float(shift.shift):
                continue

                # TODO: should be value
            value = float(shift.shift)

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
    headers = (" ", "H", "N", "CA", "CA-1", "CB", "CB-1", "CO", "CO-1", "HA", "HA-1")

    pseudo_residues = {}
    for pseudo_atom in pseudo_atom_shifts:
        key = (pseudo_atom.atom_name, pseudo_atom.negative_offset)
        pseudo_residues.setdefault(pseudo_atom.sequence_code, {})[key] = pseudo_atom

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
            else:
                line.append("-         ")

    print(tabulate(lines, headers=headers, tablefmt="plain"))