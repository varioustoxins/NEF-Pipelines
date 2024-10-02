# original implementation by esther
import sys
from dataclasses import dataclass
from pathlib import Path
from string import digits
from textwrap import dedent
from typing import List, Union

import typer
from pynmrstar import Entry
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.sequence_lib import (
    exit_if_chain_not_in_entrys_sequence,
    get_residue_name_from_lookup,
    sequence_from_entry_or_exit,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.shift_lib import (
    frames_to_assigned_and_unassigned_shift_lists,
    shifts_to_chains,
)
from nef_pipelines.lib.util import (
    STDIN,
    STDOUT,
    exit_error,
    exit_if_file_has_bytes_and_no_force,
    is_float,
    is_int,
)
from nef_pipelines.transcoders.mars import export_app
from nef_pipelines.transcoders.mars.util import (
    _exit_if_no_frames_selected,
    _select_target_chain_from_sequence_if_not_defined,
)

STDOUT_PATH = "-"

app = typer.Typer()

# TODO: name translations
# TODO: correct weights
# TODO: move utilities to lib

REMOVE_DIGITS = str.maketrans("", "", digits)

HEADINGS = (
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

OUPUT_TABLE_HEADERS = (
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


# TODO: replace with equivalent in structures
@dataclass(frozen=True, order=True)
class MarsAtom:
    atom_name: str
    sequence_code: Union[int, str]
    residue_name: str
    negative_offset: int = 0


# noinspection PyUnusedLocal
@export_app.command()
def shifts(
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
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
        help="file name to output to [default <entry_id>_shifts.tab] for stdout use -",
        metavar="<MARS_SHIFT_FILE>",
    ),
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="force overwrite of output file if it exists and isn't empty",
    ),
    shift_frame_selectors: List[str] = typer.Argument(
        None,
        help="selector for the shift restraint frames to use, can be called multiple times and include wild cards",
    ),
):
    """- write a mars chemical shift file"""

    if not shift_frame_selectors:
        shift_frame_selectors = ["*"]

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    output_file = f"{entry.entry_id}_shifts.tab" if output_file is None else output_file

    entry = pipe(entry, shift_frame_selectors, target_chain, Path(output_file), force)

    if entry:
        print(entry)


def _assigned_shifts_filter_non_numeric_sequence_codes(assigned_shifts):
    new_assigned_shifts = set()

    for assigned_shift in assigned_shifts:
        if not is_int(assigned_shift.atom.residue.sequence_code):
            continue
        else:
            new_assigned_shifts.add(assigned_shift)

    return new_assigned_shifts


def pipe(
    entry: Entry,
    shift_frame_selectors: List[str],
    target_chain: str,
    output_file: Path,
    force: bool,
) -> Entry:

    frames = entry.get_saveframes_by_category("nef_chemical_shift_list")
    frames = select_frames_by_name(frames, shift_frame_selectors)

    _exit_if_no_frames_selected(frames)

    assigned_shifts, unassigned_shifts = frames_to_assigned_and_unassigned_shift_lists(
        frames
    )

    # TODO: filter shifts which have odd assignments
    # TODO: issue a warning if there are shifts which are not defined
    assigned_shifts = _assigned_shifts_filter_non_numeric_sequence_codes(
        assigned_shifts
    )

    shift_chains = shifts_to_chains([*assigned_shifts, *unassigned_shifts])

    target_chain = _select_target_chain_from_sequence_if_not_defined(
        target_chain, shift_chains
    )

    exit_if_chain_not_in_entrys_sequence(target_chain, entry)

    sequence = sequence_from_entry_or_exit(entry)
    residue_name_lookup = sequence_to_residue_name_lookup(sequence)

    _exit_on_sequence_and_shift_residue_name_mismatch(
        assigned_shifts, residue_name_lookup
    )

    # TODO: filter assigned shifts which are not in the target_chain

    pseudo_atom_shifts = _build_pseudo_atom_shifts(unassigned_shifts)
    assigned_atom_shifts = _build_assigned_atom_shifts(assigned_shifts)

    lines, headers = _build_output_table(assigned_atom_shifts, pseudo_atom_shifts)

    exit_if_file_has_bytes_and_no_force(output_file, force)

    file_h = sys.stdout if output_file == STDOUT else open(output_file, "w")

    print(
        tabulate(lines, headers=headers, tablefmt="plain", floatfmt="7.3f"), file=file_h
    )

    if output_file != STDOUT:
        file_h.close()

    return None if output_file == STDOUT else entry


def _has_numbers(input: str) -> bool:
    return any(char.isdigit() for char in input)


def _build_output_table(assigned_atom_shifts, pseudo_atom_shifts):
    lines = []
    assigned_residues = _build_residues(assigned_atom_shifts)
    pseudo_residues = _build_residues(pseudo_atom_shifts)
    headers = _filter_headings_by_pseudoatoms(
        OUPUT_TABLE_HEADERS, {**pseudo_residues, **assigned_residues}
    )
    lines.extend(_build_residue_rows(assigned_atom_shifts, headers, assigned=True))
    lines.extend(_build_residue_rows(pseudo_atom_shifts, headers, assigned=False))

    return lines, headers


def _build_assigned_atom_shifts(assigned_shifts):
    assigned_atom_shifts = {}
    for shift in assigned_shifts:
        pseudo_atom = MarsAtom(
            atom_name=shift.atom.atom_name,
            sequence_code=shift.atom.residue.sequence_code,
            residue_name=shift.atom.residue.residue_name,
        )
        assigned_atom_shifts[pseudo_atom] = shift.value

    _add_m1_shifts(assigned_atom_shifts)

    return assigned_atom_shifts


def _build_residue_rows(atom_shifts, headers, assigned=False):

    residues = _build_residues(atom_shifts)
    residue_names = {
        atom_shift.sequence_code: atom_shift.residue_name for atom_shift in atom_shifts
    }
    lines = []
    for residue_num in sorted(residues):
        pseudo_atoms = residues[residue_num]

        line = []
        lines.append(line)

        if assigned:
            line.append(f"AR_{residue_num}_{residue_names[residue_num]}")
        else:
            line.append(f"PR_{residue_num}")

        for heading, heading_key in HEADINGS:

            if heading_key in pseudo_atoms:

                pseudo_atom = pseudo_atoms[heading_key]
                shift = atom_shifts[pseudo_atom]

                line.append("%-7.3f    " % shift)
            elif heading.upper() in headers:
                line.append("-         ")

    return lines


def _build_residues(assigned_atom_shifts):
    result = {}
    for assigned_atom in assigned_atom_shifts:
        key = (assigned_atom.atom_name, assigned_atom.negative_offset)
        result.setdefault(assigned_atom.sequence_code, {})[key] = assigned_atom
    return result


def _exit_on_sequence_and_shift_residue_name_mismatch(shifts, residue_name_lookup):
    for shift in shifts:
        chain_code = str(shift.atom.residue.chain_code)
        sequence_code = shift.atom.residue.sequence_code
        sequence_residue_name = get_residue_name_from_lookup(
            chain_code, sequence_code, residue_name_lookup
        )
        if sequence_residue_name != shift.atom.residue.residue_name:
            frame_line = shift.frame_line.split("\n")
            frame_headers = frame_line[0].split(",")
            frame_row = frame_line[1].split(",")
            frame_headers[0] = f"#{frame_headers[0]}"
            line_info = tabulate([frame_headers, frame_row], tablefmt="plain")
            msg = f"""
                    error for atom {shift.atom.atom_name} in chain {shift.atom.residue.chain_code}
                    the residue type in the sequence doesn't match residue type in shifts

                    sequence residue name {sequence_residue_name}
                    shifts residue name {shift.atom.residue.residue_name}

                    the shift came from
                    frame name {shift.frame_name}
                    row number {shift.frame_row}
                    data in the row

                """
            msg = dedent(msg)
            msg += line_info
            exit_error(msg)


def _build_pseudo_atom_shifts(unassigned_shifts):
    pseudo_atom_shifts = {}
    for shift in unassigned_shifts:
        # first deal with completely unassigned residues chain_code @- and sequence_code @xxxx where xxx
        # is the pseudo residue
        sequence_code = str(shift.atom.residue.sequence_code)
        atom_name = shift.atom.atom_name

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
        if _has_numbers(atom_name):
            continue

        pseudo_atom = MarsAtom(
            atom_name=atom_name,
            sequence_code=sequence_code,
            residue_name=shift.atom.residue.residue_name,
            negative_offset=negative_offset,
        )

        if not is_float(shift.value):
            continue

            # TODO: should be value
        value = float(shift.value)

        pseudo_atom_shifts[pseudo_atom] = value

    return pseudo_atom_shifts


def _filter_headings_by_pseudoatoms(base_headers, pseudo_residues):
    atom_names = set()
    for pseudo_residue in pseudo_residues.values():
        for pseudo_atom in pseudo_residue.values():
            offset = (
                f"-{pseudo_atom.negative_offset}"
                if pseudo_atom.negative_offset == 1
                else ""
            )
            atom_name = pseudo_atom.atom_name.upper()
            atom_name = "CO" if atom_name == "C" else atom_name
            atom_names.add(f"{atom_name}{offset}")
    headers = []
    for header in base_headers:
        if header == "" or header in atom_names:
            headers.append(header)
    return headers


def _add_m1_shifts(assigned_shifts):

    new_shifts = {}

    shifts_by_residue_and_atom = {}
    sequence_code_to_residue_name = {}
    for mars_atom in assigned_shifts:
        shifts_by_residue_and_atom.setdefault(mars_atom.sequence_code, {})[
            mars_atom.atom_name
        ] = mars_atom
        sequence_code_to_residue_name[mars_atom.sequence_code] = mars_atom.residue_name

    for sequence_code, atoms_and_shifts in shifts_by_residue_and_atom.items():
        residue_name = sequence_code_to_residue_name[sequence_code]
        sequence_code_m1 = sequence_code - 1
        m1_shifts = (
            shifts_by_residue_and_atom[sequence_code_m1]
            if sequence_code_m1 in shifts_by_residue_and_atom
            else {}
        )
        for atom_name in "HA CA CB C".split():
            if atom_name in m1_shifts:
                mars_atom = m1_shifts[atom_name]
                new_atom = MarsAtom(
                    atom_name=atom_name,
                    sequence_code=sequence_code,
                    residue_name=residue_name,
                    negative_offset=1,
                )
                new_shifts[new_atom] = assigned_shifts[mars_atom]

    assigned_shifts.update(new_shifts)

    return assigned_shifts
