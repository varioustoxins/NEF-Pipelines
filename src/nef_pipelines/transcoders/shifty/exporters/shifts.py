import sys
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry, Saveframe
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    read_entry_from_stdin_or_exit,
    select_frames_by_name,
)
from nef_pipelines.lib.sequence_lib import TRANSLATIONS_3_1_PROTEIN
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.structures import ShiftData
from nef_pipelines.lib.util import STDOUT, exit_error, flatten, is_int
from nef_pipelines.transcoders.shifty import export_app

OUTPUT_FILE_SHORTCUTS = """\
    for stdout use -, ! will use the name of the nef entry in the
    form <NEF-ENTRY-NAME>_shifts.shifty
"""

OUTPUT_FILE_HELP = f"""\
    file name to output to [{OUTPUT_FILE_SHORTCUTS}]
"""

SHIFTY_HEADINGS_LOOKUP = (
    ("HA", ("HA1", "HA")),
    ("HN", ("H", "HN")),  # TODO: this is a hack awaiting the translations module
    ("N15", ("N",)),
    ("CA", ("CA",)),
    ("CB", ("CB",)),
    ("CO", ("C",)),
)
SHIFTY_ATOMS = [shifty_atom for shifty_atom, _ in SHIFTY_HEADINGS_LOOKUP]
SHIFTY_LOOKUP_ATOMS = flatten(
    [lookup_atom for _, lookup_atom in SHIFTY_HEADINGS_LOOKUP]
)
SHIFTY_EXTRA_HEADINGS = "#NUM AA".split()
SHIFTY_HEADINGS = [*SHIFTY_EXTRA_HEADINGS, *SHIFTY_ATOMS]


# noinspection PyUnusedLocal
@export_app.command()
def shifts(
    shift_frames: List[str] = typer.Option(
        [],
        "-f",
        "--frame",
        help="selector for the shift restraint frames to use, can be called multiple times and include wild cards",
    ),
    chain_code: str = typer.Option(
        None,
        "-c",
        "--chain",
        help="chain to export [defaults to the first chain if only one present]",
        metavar="<CHAIN-CODE>",
    ),
    output_file: str = typer.Argument(
        None,
        help=OUTPUT_FILE_HELP,
        metavar="<SHIFTY-SHIFT-FILE-NAME>",
    ),
):
    """- convert nef chemical shifts to shifty"""

    if len(shift_frames) == 0:
        shift_frames = ["*"]

    entry = read_entry_from_stdin_or_exit()

    if output_file is None:
        msg = f"you need to specify an output file name, [{OUTPUT_FILE_SHORTCUTS}]"

        exit_error(msg)
    output_file = (
        f"{entry.entry_id}_shifts.shifty" if output_file == "!" else Path(output_file)
    )

    entry = pipe(entry, shift_frames, chain_code, output_file)

    if not (sys.stdout.isatty() or output_file == STDOUT):
        print(entry)


def pipe(
    entry: Entry,
    shift_frames: List[Saveframe],
    selected_chain_code: str,
    output_file: Path,
) -> Entry:

    frames = entry.get_saveframes_by_category("nef_chemical_shift_list")

    frames = select_frames_by_name(frames, shift_frames)

    if len(frames) == 0:
        exit_error("no shift frames selected")

    shifts = nef_frames_to_shifts(frames)

    selected_chain_code = _get_chain_code_or_exit(shifts, selected_chain_code, entry)

    lines = {}

    for shift in shifts:

        chain_code = shift.atom.residue.chain_code
        sequence_code = shift.atom.residue.sequence_code
        atom_name = shift.atom.atom_name
        residue_name = shift.atom.residue.residue_name

        if _is_pseudo_residue(chain_code, sequence_code):
            continue

        if residue_name.upper() not in TRANSLATIONS_3_1_PROTEIN:
            continue

        if atom_name not in SHIFTY_LOOKUP_ATOMS:
            continue

        if chain_code != selected_chain_code:
            continue

        if not is_int(sequence_code):
            continue

        sequence_code = int(sequence_code)
        residue_name_1let = TRANSLATIONS_3_1_PROTEIN[residue_name]
        value = shift.value

        key = sequence_code, residue_name_1let
        lines.setdefault(key, {})[atom_name] = value

    table = [[*SHIFTY_EXTRA_HEADINGS, *SHIFTY_ATOMS]]

    for (residue_number, residue_type), shifts in lines.items():

        row = [residue_number, residue_type]
        table.append(row)

        shift_values = []
        for shift_name, lookup_atom_names in SHIFTY_HEADINGS_LOOKUP:
            shift_value = 0.0
            for lookup_atom_name in lookup_atom_names:
                if lookup_atom_name in shifts:
                    shift_value = shifts[lookup_atom_name]

            # if we use floats the trailing zeros get removed
            # shift_values.append(shift_value)
            shift_values.append(format(shift_value, "7.3f"))
        row.extend(shift_values)

    file_h = sys.stdout if output_file == STDOUT else open(output_file, "w")

    COL_ALIGN = [
        "right",
    ] * len(SHIFTY_HEADINGS)
    COL_ALIGN[0] = "left"
    COL_ALIGN[1] = "left"

    print(tabulate(table, tablefmt="plain", colalign=COL_ALIGN), file=file_h)

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


def _get_chain_code_or_exit(
    read_shifts: ShiftData, selected_chain_code: str, entry: Entry
):

    chain_codes = set([shift.atom.residue.chain_code for shift in read_shifts])

    if selected_chain_code is None:

        if len(chain_codes) > 1:
            msg = f"""\
                no chain code selected and ambiguous chain codes available [{' '.join(chain_codes)}]
            """
            exit_error(msg)
        else:
            selected_chain_code = list(chain_codes)[0]

    if selected_chain_code not in chain_codes:
        msg = f"""\
            the chain code you selected [{selected_chain_code}] isn't in the chain codes [{' '.join(chain_codes)}]
            in the entry {entry.name}
        """
        exit_error(msg)

    return selected_chain_code
