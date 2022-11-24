from pathlib import Path
from typing import List, Dict

from pynmrstar import Entry

from lib.nef_lib import create_entry_from_stdin_or_exit
from lib.sequence_lib import sequence_from_frame, translate_3_to_1, make_chunked_sequence_1let
from lib.structures import SequenceResidue
from lib.util import parse_comma_separated_options, exit_error
from transcoders.fasta import export_app
import typer

app = typer.Typer()

# noinspection PyUnusedLocal
@export_app.command()
def sequence(
    chain_codes: str = typer.Option([], '-c', '--chain_code', help="chains to export, to add multiple chains use repeated calls  [default: 'A']", metavar='<CHAIN-CODE>'),
    pipe: Path = typer.Option(None, '-i', '--in', help='file to read nef data from', metavar='<NEF-FILE>')
):
    """- convert nef sequence to fasta"""

    frame_selectors = parse_comma_separated_options(chain_codes)

    chain_codes = ['A'] if not chain_codes else chain_codes

    if pipe is None:
        entry = create_entry_from_stdin_or_exit()
    else:
        try:
            with open(pipe) as fh:
                entry = Entry.from_file(fh)

        except IOError as e:
            exit_error(f"couldn't read from the file {pipe}", e)

    # noinspection PyUnboundLocalVariable
    molecular_systems = entry.get_saveframes_by_category('nef_molecular_system')
    if not molecular_systems:
        exit_error("Couldn't find a molecular system frame it should be labelled 'save_nef_molecular_system'")

    if len(molecular_systems) > 1:
        exit_error('There can only be one molecular system in a NEF file')

    residues = sequence_from_frame(molecular_systems[0])

    fasta_records = nef_to_fasta_records(residues, chain_codes)
    for record in fasta_records.values():
        print("\n".join(record))



def nef_to_fasta_records(residues: List[SequenceResidue], chain_codes: List[str]) -> Dict[str, List[str]]:

    residues_by_chain = {}
    for chain_code in chain_codes:
        residues_by_chain[chain_code] = [residue for residue in residues if residue.chain_code == chain_code]

    chain_starts = {}
    for chain_code, residues in residues_by_chain.items():
        chain_starts[chain_code] = residues[0].sequence_code

    residue_sequences = {}
    for chain_code in chain_codes:
        residue_sequences[chain_code] = [residue.residue_name for residue in residues_by_chain[chain_code]]

    residue_sequences = {chain: translate_3_to_1(residue_sequence) for chain, residue_sequence in residue_sequences.items()}
    residue_sequences = {chain: make_chunked_sequence_1let(residue_sequence) for chain, residue_sequence in residue_sequences.items()}

    result = {}
    for chain_code, residue_sequence in residue_sequences.items():
        result[chain_code] = [
            f'>CHAIN: A | START RESIDUE: {chain_starts[chain_code]}',
            '\n'.join(residue_sequence)
        ]

    return result
