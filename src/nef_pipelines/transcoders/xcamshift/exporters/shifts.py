import sys
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry, Saveframe
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    read_entry_from_stdin_or_exit,
    select_frames_by_name,
)
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.util import STDOUT, exit_error, is_int
from nef_pipelines.transcoders.xcamshift import export_app

XCAMSHIFT_ATOMS = "HN N CA CB C HA HA1 HA2".split()


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
        help="file name to output to,  for stdout use -",
        metavar="<XPLOR-SHIFT-FILE>",
    ),
):
    """- convert nef chemical shifts to xplor (xcamshift)"""

    if len(shift_frames) == 0:
        shift_frames = ["*"]

    entry = read_entry_from_stdin_or_exit()

    output_file = (
        f"{entry.entry_id}_shifts.tab" if output_file is None else Path(output_file)
    )

    entry = pipe(entry, shift_frames, output_file)

    if not (sys.stdout.isatty() or output_file == STDOUT):
        print(entry)


def pipe(entry: Entry, shift_frames: List[Saveframe], output_file: Path) -> Entry:

    frames = entry.get_saveframes_by_category("nef_chemical_shift_list")

    frames = select_frames_by_name(frames, shift_frames)

    if len(frames) == 0:
        exit_error("no shift frames selected")

    shifts = nef_frames_to_shifts(frames)

    lines = []

    no_uncertainties = True
    for shift in shifts:
        if shift.value_uncertainty != UNUSED:
            no_uncertainties = False

    for shift in shifts:

        chain_code = shift.atom.residue.chain_code
        sequence_code = shift.atom.residue.sequence_code
        atom_name = shift.atom.atom_name
        residue_name = shift.atom.residue.residue_name

        if _is_pseudo_residue(chain_code, sequence_code):
            continue

        if atom_name not in XCAMSHIFT_ATOMS:
            continue

        value = shift.value
        value_uncertainty = shift.value_uncertainty
        chain_segid = f"segid {chain_code} and"
        assign = f"assign ( {chain_segid}  resid {sequence_code} and resn {residue_name} and name {atom_name} )"

        if no_uncertainties:
            value_uncertainty = ""
        lines.append(f"{assign} {value} {value_uncertainty}".split())

    file_h = sys.stdout if output_file == STDOUT else open(output_file, "w")

    print(tabulate(lines, tablefmt="plain", floatfmt="7.3f"), file=file_h)

    if output_file != STDOUT:
        file_h.close()

    return entry


def _is_pseudo_residue(chain_code, sequence_code):
    return (
        chain_code.startswith("@-")
        or not is_int(sequence_code)
        and sequence_code.startswith("@")
    )


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
