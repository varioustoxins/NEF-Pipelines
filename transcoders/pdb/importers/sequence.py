import warnings
from argparse import Namespace
from typing import Iterable, List

from lib.sequence_lib import sequence_to_nef_frame, chain_code_iter
from lib.typer_utils import get_args

from pathlib import Path

from lib.structures import SequenceResidue
from lib.util import exit_error, process_stream_and_add_frames


from transcoders.pdb import import_app
import typer

from lib.util import parse_comma_separated_options

app = typer.Typer()

CHAINS_HELP = """chains [or segid] to read', metavar='<CHAIN-CODE>, multiple chains can be added as a comma joined list 
                [eg A.B.C] ] or by calling this option mutiple times"""
NO_CHAIN_START_HELP = """don't include the start chain link type on a chain for the first residue [linkage will be 
                         middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                         option multiple times to set chain starts for multiple chains"""
NO_CHAIN_END_HELP = """don't include the end chain link type on a chain for the last residue [linkage will be 
                       middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                       option multiple times to set chain ends for multiple chains"""

# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def sequence(
    chain_codes: List[str] = typer.Option(None, '-c', '--chains', help=CHAINS_HELP),
    use_segids: bool = typer.Option(False, '-s', '--segid', help='use segid instead of chain'),
    no_chain_starts: List[str] = typer.Option([], '--no-chain-start', help=NO_CHAIN_START_HELP),
    no_chain_ends: List[str] = typer.Option([], '--no-chain-end', help=NO_CHAIN_END_HELP),
    entry_name: str = typer.Option('pdb', help='a name for the nef entry if not updating an existing entry'),
    file_name: Path = typer.Argument(..., help='input pdb file', metavar='<PDB-FILE>')
):
    """extracts a sequence from a pdb file"""

    chain_codes = parse_comma_separated_options(chain_codes)
    no_chain_starts = parse_comma_separated_options(no_chain_starts)
    no_chain_ends =  parse_comma_separated_options(no_chain_ends)

    try:
        args = get_args()

        process_sequence(args)

    except Exception as e:
        exit_error(f"reading sequence failed because {e}", e)




def process_sequence(args: Namespace):



    pdb_sequences = read_sequences(args.file_name, args.chain_codes, use_segids=args.use_segids)

    pdb_frame = sequence_to_nef_frame(pdb_sequences, set(args.no_chain_starts), set(args.no_chain_ends))

    #TODO: need a a warning if the sequence already exists in a molecular system and ability to merge
    entry = process_stream_and_add_frames([pdb_frame,], args)

    print(entry)


def read_sequences(path, target_chain_codes, use_segids=False):

    from Bio.PDB.PDBExceptions import  PDBConstructionWarning

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', PDBConstructionWarning)


        from Bio.PDB.PDBParser import PDBParser
        parser = PDBParser(PERMISSIVE=1)
        structure = parser.get_structure('pdb', path)
        model = structure[0]

        sequences = []

        if not use_segids:
            for chain in model:
                id = chain.id.strip()
                if len(id) == 0:
                    use_segids=True

        all_chains = len(target_chain_codes) == 0


        for chain in model:
            for residue in chain:
                chain_code = residue.segid if use_segids else chain.id
                chain_code = chain_code.strip()

                if not all_chains and chain_code not in target_chain_codes:
                    continue

                hetero_atom_flag, sequence_code, _= residue.get_id()

                if len(hetero_atom_flag.strip()) != 0:
                    continue

                residue = SequenceResidue(chain_code=chain_code, sequence_code=sequence_code,
                                          residue_name=residue.get_resname())
                sequences.append(residue)

    return sequences
