import sys
from pathlib import Path
from typing import Dict, List

import typer

from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.sequence_lib import (
    make_chunked_sequence_1let,
    sequence_from_frame,
    translate_3_to_1,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import exit_error
from nef_pipelines.transcoders.fasta import export_app

# TODO: move to lib
STDOUT = "-"


# noinspection PyUnusedLocal
@export_app.command()
def sequence(
    chain_codes: str = typer.Option(
        [],
        "-c",
        "--chain_code",
        help="chains to export, to add multiple chains use repeated calls  [default: 'A']",
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

    # frame_selectors = parse_comma_separated_options(chain_codes)

    chain_codes = ["A"] if not chain_codes else chain_codes

    entry = read_entry_from_file_or_stdin_or_exit_error(in_file)

    output_file = f"{entry.entry_id}.fasta" if output_file is None else output_file

    fasta_records = fasta_records_from_entry(entry, chain_codes)

    # TODO: move to utility function and use in all outputs
    file_h = sys.stdout if output_file == STDOUT else open(output_file, "w")

    for record in fasta_records.values():
        print("\n".join(record), file=file_h)

    if output_file != STDOUT:
        file_h.close()

        if not sys.stdout.isatty():
            print(entry)


def fasta_records_from_entry(entry, chain_codes):

    molecular_system = molecular_system_from_entry_or_exit(entry)

    residues = sequence_from_frame(molecular_system)

    fasta_records = nef_to_fasta_records(residues, chain_codes)

    return fasta_records


def molecular_system_from_entry_or_exit(entry):

    # noinspection PyUnboundLocalVariable
    molecular_systems = entry.get_saveframes_by_category("nef_molecular_system")
    if not molecular_systems:
        exit_error(
            "Couldn't find a molecular system frame it should be labelled 'save_nef_molecular_system'"
        )

    if len(molecular_systems) > 1:
        exit_error("There can only be one molecular system in a NEF file")

    return molecular_systems[0]


def nef_to_fasta_records(
    residues: List[SequenceResidue], chain_codes: List[str]
) -> Dict[str, List[str]]:

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
            f">CHAIN: A | START RESIDUE: {chain_starts[chain_code]}",
            "\n".join(residue_sequence),
        ]

    return result