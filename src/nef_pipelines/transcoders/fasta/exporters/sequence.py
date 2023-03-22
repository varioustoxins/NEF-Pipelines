import sys
from pathlib import Path
from typing import Dict, List

import typer

from nef_pipelines.lib.nef_lib import (
    molecular_system_from_entry_or_exit,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    make_chunked_sequence_1let,
    sequence_from_frame,
    sequence_to_chains,
    translate_3_to_1,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import STDOUT
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
        None, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    output_file: str = typer.Argument(
        None,
        help="file name to output to [default <entry_id>.fasta] for stdout use -",
        metavar="<FASTA-SEQUENCE-FILE>",
    ),
):
    """- convert nef sequence to fasta"""

    chain_codes = ["*"] if len(chain_codes) == 0 else chain_codes

    entry = read_entry_from_file_or_stdin_or_exit_error(in_file)

    output_file = f"{entry.entry_id}.fasta" if output_file is None else output_file

    fasta_records = fasta_records_from_entry(entry, chain_codes)

    # TODO: move to utility function and use in all outputs
    file_h = sys.stdout if output_file == str(STDOUT) else open(output_file, "w")

    # TODO we ought to output to multiple files witha template
    for record in fasta_records.values():
        print("\n\n".join(record), file=file_h)

    if output_file != STDOUT:
        file_h.close()

        if not sys.stdout.isatty():
            print(entry)


def fasta_records_from_entry(entry, chain_codes):

    molecular_system = molecular_system_from_entry_or_exit(entry)

    residues = sequence_from_frame(molecular_system)

    fasta_records = nef_to_fasta_records(residues, chain_codes)

    return fasta_records


def nef_to_fasta_records(
    residues: List[SequenceResidue], target_chain_codes: List[str]
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
        result[chain_code] = [
            f">CHAIN: {chain_code} | START RESIDUE: {chain_starts[chain_code]}",
            "\n".join(residue_sequence),
        ]

    return result
