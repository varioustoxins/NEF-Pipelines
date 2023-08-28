# TODO: support NMRPipe his and cis variants
# TODO: what do unassigned nmrpipe shifts look like?
# TODO: support general nmrpipe shift input
# TODO: support the HA2|HA3 syntax
# TODO: support unassigned
# TODO: support multiple chains & files
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import List

import tabulate
import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_frames_lib import SHIFT_LIST_FRAME_CATEGORY
from nef_pipelines.lib.nef_lib import (
    get_frame_id,
    get_frame_ids,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.sequence_lib import (
    TRANSLATIONS_3_1,
    MoleculeTypes,
    get_chain_starts,
    make_chunked_sequence_1let,
    sequence_from_entry,
    sequence_residues_to_sequence_3let,
    sequence_to_chains,
    translate_3_to_1,
)
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.util import STDIN, exit_error, is_float, is_int
from nef_pipelines.transcoders.talos import export_app

app = typer.Typer()


# noinspection PyUnusedLocal
@export_app.command()
def shifts(
    context: typer.Context,
    user_chain: str = typer.Option(
        None,
        "-c",
        "--chain",
        help="chain to export",
        metavar="<CHAIN-CODE>",
    ),
    output_to_stdout: bool = typer.Option(
        False, "-o", "--out", help="write the files to stdout for debugging"
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        help="input to read NEF data from [- is stdin]",
    ),
    frame_selector: str = typer.Option(
        None,
        "-f",
        "--frame",
        help="selector for the chemical shift list frame to use",
    ),
):
    """- convert nef shifts and sequence to talos input [alpha]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    user_chain = _select_chain_or_exit(entry, user_chain)

    output = pipe(entry, user_chain, frame_selector)

    print("\n".join(output))


def pipe(entry: Entry, target_chain_code: str, frame_selector: str) -> List[str]:

    target_shift_frame = _select_shift_frame_or_exit(entry, frame_selector)

    sequence = sequence_from_entry(entry)

    target_sequence = [
        residue for residue in sequence if residue.chain_code == target_chain_code
    ]

    start_residue = get_chain_starts(target_sequence)[target_chain_code]

    sequence_1let = translate_3_to_1(
        sequence_residues_to_sequence_3let(target_sequence)
    )

    chunked_sequence = make_chunked_sequence_1let(sequence_1let, line_length=50)

    shifts = nef_frames_to_shifts(
        [target_shift_frame],
    )

    shifts = [
        shift for shift in shifts if shift.atom.residue.chain_code == target_chain_code
    ]

    TALOS_ATOMS = set("H N CA CB C HA HA2 HA3".split())
    shifts = [shift for shift in shifts if shift.atom.atom_name in TALOS_ATOMS]

    shifts = [shift for shift in shifts if is_int(shift.atom.residue.sequence_code)]

    shifts = [shift for shift in shifts if is_float(shift.value)]

    shifts = [
        shift
        for shift in shifts
        if shift.atom.residue.residue_name in TRANSLATIONS_3_1[MoleculeTypes.PROTEIN]
    ]

    with redirect_stdout(StringIO()) as capture:
        print(f"REMARK Chemical shift table for {entry.entry_id}")
        print()
        print(f"DATA CHAIN {target_chain_code}")
        print(f"DATA FIRST_RESID {start_residue}")
        print()
        for sub_sequence in chunked_sequence:
            print(f"DATA SEQUENCE {sub_sequence}")
        print()

        headers = [
            "VARS   RESID\nFORMAT %4d",
            "RESNAME\n%1s",
            "ATOMNAME\n%4s",
            "SHIFT\n%8.3f",
        ]

        table = []

        for shift in shifts:
            table.append(
                [
                    int(shift.atom.residue.sequence_code),
                    translate_3_to_1(
                        [
                            shift.atom.residue.residue_name,
                        ]
                    )[0],
                    shift.atom.atom_name,
                    float(shift.value),
                ]
            )

        print(
            tabulate.tabulate(
                table,
                tablefmt="plain",
                headers=headers,
                colalign=["left", "left", "left", "decimal"],
            )
        )

    return str(capture.getvalue()).split("\n")


def _select_shift_frame_or_exit(entry, frame_selector):

    shift_frames = entry.get_saveframes_by_category(SHIFT_LIST_FRAME_CATEGORY)

    if len(shift_frames) == 0:
        print(typer.context.get_help())
        exit_error("no shift frames in input stream")

    if len(shift_frames) == 1:
        target_shift_frame = shift_frames[0]
        if frame_selector is not None:
            target_id = get_frame_id(target_shift_frame)
            if target_id != frame_selector:
                msg = f"""
                        the selected frame [{frame_selector}] is different from the frame found [{target_id}]
                        as only one shift frame is present you don't need a frame selector [--frame]!
                    """
                exit(msg)

    if len(shift_frames) > 1:
        if frame_selector is None:
            frame_ids = ",".join(get_frame_ids(shift_frames))
            msg = f"""
                    multiple shift frames in the stream but no frame selection option [use --frame to select one]
                    the frame ids are {frame_ids}
                """
            exit_error(msg)
        else:
            selected_frames = select_frames_by_name(shift_frames, frame_selector)
            if len(selected_frames) == 0:
                frame_ids = ", ".join(get_frame_ids(shift_frames))
                msg = f"""
                    the selector {frame_selector} didn't selected a frame FROM the available frames
                    the ids of the available shift frames are {frame_ids}
                    """
                exit_error(msg)

    return target_shift_frame


def _select_chain_or_exit(entry, user_chain):

    sequence = sequence_from_entry(entry)

    sequence_chains = sequence_to_chains(sequence)

    if len(sequence_chains) == 0:
        msg = """
            there are no chains in the molecular sequence!
        """
        exit_error(msg)

    if len(sequence_chains) == 1:
        target_sequence_chain = sequence_chains[0]
        if user_chain is not None and target_sequence_chain != user_chain:
            msg = f"""
                    the selected chain_code [{user_chain}] is not in the available chain_codes [{target_sequence_chain}]
                    as only one chain is present you don't need a chain selector [--chain]!
                """
            exit_error(msg)

    if len(sequence_chains) > 1:
        if user_chain is not None and user_chain not in sequence_chains:
            chain_codes = ", ".join(sequence_chains)
            msg = f"""
                    the selected chain_code {user_chain} is not one of the available chain_codes {chain_codes}
                """
            exit_error(msg)
        if user_chain is None:
            msg = f"""
                    multiple chains found [{chain_codes}] but no chain selector [--chain] given
                """
            exit_error(msg)
        target_sequence_chain = user_chain

    return target_sequence_chain
