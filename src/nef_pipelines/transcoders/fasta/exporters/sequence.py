import re
import sys
from pathlib import Path
from typing import Dict, List

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    molecular_system_from_entry_or_exit,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    make_chunked_sequence_1let,
    sequence_to_chains,
    sequences_from_frames,
    translate_3_to_1,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import (
    STDIN,
    STDOUT,
    exit_error,
    exit_if_file_has_bytes_and_no_force,
)
from nef_pipelines.transcoders.fasta import export_app

# TODO: we should be able to output *s on the ends of sequences and comments
# TODO: we should be able to select chains by fnmatch

CHAIN_CODES_HELP = """
    chains to export, to add multiple chains use repeated calls, to select all chains use * [default: 'A']
"""


# noinspection PyUnusedLocal
@export_app.command()
def sequence(
    chain_codes: List[str] = typer.Option(
        [],
        "-c",
        "--chain_code",
        help=CHAIN_CODES_HELP,
        metavar="<CHAIN-CODE>",
    ),
    in_file: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    output_file: str = typer.Argument(
        None,
        help="file name to output to [default <entry_id>.fasta] for stdout use -",
        metavar="<FASTA-SEQUENCE-FILE>",
    ),
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="force overwrite of output file if it exists and isn't empty",
    ),
):
    """- convert nef sequence to fasta"""

    chain_codes = ["*"] if len(chain_codes) == 0 else chain_codes

    entry = read_entry_from_file_or_stdin_or_exit_error(in_file)

    output_file = f"{entry.entry_id}.fasta" if output_file is None else output_file
    output_file = STDOUT if output_file == "-" else output_file

    entry = pipe(entry, chain_codes, Path(output_file), force)

    if entry:
        print(entry)


def pipe(entry: Entry, chain_codes: List[str], output_file: Path, force: bool):

    fasta_records = fasta_records_from_entry(entry, chain_codes)

    exit_if_file_has_bytes_and_no_force(output_file, force)

    # TODO: move to utility function and use in all outputs
    try:
        file_h = sys.stdout if output_file == STDOUT else open(output_file, "w")
    except Exception as e:
        msg = (
            f"Error opening output file {output_file} for writing fasa file because {e}"
        )
        exit_error(msg, e)

    # TODO we ought to be able to output to multiple files with a filename template
    records = []
    for record in fasta_records.values():
        records.append("\n".join(record))
    print("\n\n".join(records), file=file_h)

    if output_file != STDOUT:
        file_h.close()

    return entry if output_file != STDOUT else None


def fasta_records_from_entry(entry, chain_codes):

    molecular_system = molecular_system_from_entry_or_exit(entry)

    residues = sequences_from_frames(molecular_system)

    fasta_records = nef_to_fasta_records(residues, chain_codes, entry.entry_id)

    return fasta_records


def nef_to_fasta_records(
    residues: List[SequenceResidue], target_chain_codes: List[str], entry_id: str
) -> Dict[str, List[str]]:

    all_chain_codes = sequence_to_chains(residues)

    chain_codes = []
    for target_chain_code in target_chain_codes:
        for chain_code in all_chain_codes:
            if target_chain_code == chain_code:
                chain_codes.append(chain_code)
                continue
            if target_chain_code == "*":
                chain_codes.append(chain_code)
                continue

    residues_by_chain = {}
    for chain_code in chain_codes:
        residues_by_chain[chain_code] = [
            residue for residue in residues if residue.chain_code == chain_code
        ]

    chain_starts = {}
    for chain_code, residues in residues_by_chain.items():
        chain_starts[chain_code] = residues[0].sequence_code

    residue_sequences = {}
    for chain_code in chain_codes:
        residue_sequences[chain_code] = [
            residue.residue_name for residue in residues_by_chain[chain_code]
        ]

    residue_sequences = {
        chain: translate_3_to_1(residue_sequence)
        for chain, residue_sequence in residue_sequences.items()
    }
    residue_sequences = {
        chain: make_chunked_sequence_1let(residue_sequence)
        for chain, residue_sequence in residue_sequences.items()
    }

    result = {}
    for chain_code, residue_sequence in residue_sequences.items():
        entry_id = re.sub(r"\s+", "", entry_id)
        result[chain_code] = [
            f">{entry_id} NEFPLS | CHAIN: {chain_code} | START: {chain_starts[chain_code]}",
            "\n".join(residue_sequence),
        ]

    return result
