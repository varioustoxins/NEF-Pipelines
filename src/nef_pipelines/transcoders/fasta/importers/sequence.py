from itertools import chain, cycle, islice, zip_longest
from pathlib import Path
from typing import Iterable, List

import typer
from fastaparser import Reader
from ordered_set import OrderedSet

from nef_pipelines.lib.sequence_lib import (
    BadResidue,
    MoleculeType,
    MoleculeTypes,
    chain_code_iter,
    offset_chain_residues,
    sequence_3let_to_res,
    sequence_to_nef_frame,
    translate_1_to_3,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.typer_utils import get_args
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    parse_comma_separated_options,
    process_stream_and_add_frames,
)
from nef_pipelines.transcoders.fasta import import_app

app = typer.Typer()

NO_CHAIN_START_HELP = """don't include the start chain link type on a chain for the first residue [linkage will be
                         middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                         option multiple times to set chain starts for multiple chains"""
NO_CHAIN_END_HELP = """don't include the end chain link type on a chain for the last residue [linkage will be
                       middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                       option multiple times to set chain ends for multiple chains"""


# todo add comment to other sequences etc
@import_app.command()
def sequence(
    chain_codes: List[str] = typer.Option(
        [],
        "--chains",
        help="chain codes to use for the imported chains, can be a a comma separated list or can be called "
        "multiple times",
        metavar="<CHAIN-CODES>",
    ),
    starts: List[str] = typer.Option(
        [],
        "--starts",
        help="first residue number of sequences can be a comma separated list or ",
        metavar="<START>",
    ),
    no_chain_starts: List[str] = typer.Option(
        [], "--no-chain-start", help=NO_CHAIN_START_HELP
    ),
    no_chain_ends: List[str] = typer.Option(
        [], "--no-chain-end", help=NO_CHAIN_END_HELP
    ),
    # TODO: unused inputs!
    entry_name: str = typer.Option("fasta", help="a name for the entry if required"),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]",
    ),
    molecule_types: List[MoleculeType] = typer.Option(
        [
            MoleculeType.PROTEIN,
        ],
        "--molecule-type",
        help="molecule type",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="the file to read", metavar="<FASTA-FILE>"
    ),
):
    """- convert fasta sequence to nef"""

    chain_codes = parse_comma_separated_options(chain_codes)
    if not chain_codes:
        chain_codes = ["A"]

    no_chain_starts = parse_comma_separated_options(no_chain_starts)
    if not no_chain_starts:
        no_chain_starts = [False]

    no_chain_ends = parse_comma_separated_options(no_chain_ends)
    if no_chain_ends:
        no_chain_ends = [False]

    starts = [int(elem) for elem in parse_comma_separated_options(starts)]
    if not starts:
        starts = [1]

    molecule_types = parse_comma_separated_options(molecule_types)
    if not molecule_types:
        molecule_types = [
            MoleculeType.PROTEIN,
        ]

    args = get_args()

    args.chain_codes = chain_codes
    args.no_chain_starts = no_chain_starts
    args.no_chain_ends = no_chain_ends
    args.starts = starts
    args.molecule_types = molecule_types

    # TODO: doesn't provide a pipe command
    process_sequences(args)


def process_sequences(args):
    fasta_frames = []

    chain_code_iterator = chain_code_iter(args.chain_codes)
    fasta_sequences = OrderedSet()
    for file_path in args.file_names:
        fasta_sequences.update(
            read_sequences(file_path, chain_code_iterator, args.molecule_types)
        )

    read_chain_codes = residues_to_chain_codes(fasta_sequences)

    offsets = _get_sequence_offsets(read_chain_codes, args.starts)

    fasta_sequences = offset_chain_residues(fasta_sequences, offsets)

    fasta_sequences = sorted(fasta_sequences)

    fasta_frames.append(sequence_to_nef_frame(fasta_sequences))

    entry = process_stream_and_add_frames(fasta_frames, args)

    print(entry)


def _get_sequence_offsets(chain_codes: List[str], starts: List[int]):

    offsets = [start - 1 for start in starts]
    cycle_starts = chain(
        offsets,
        cycle(
            [
                0,
            ]
        ),
    )
    offsets = list(islice(cycle_starts, len(chain_codes)))

    return {chain_code: offset for chain_code, offset in zip(chain_codes, offsets)}


def residues_to_chain_codes(residues: List[SequenceResidue]) -> List[str]:
    return list(OrderedSet([residue.chain_code for residue in residues]))


# could do with taking a list of offsets
# noinspection PyUnusedLocal
def read_sequences(
    path: Path, chain_codes: Iterable[str], molecule_types: List[MoleculeType]
) -> List[SequenceResidue]:

    residues = OrderedSet()
    try:
        with open(path) as handle:
            try:
                reader = Reader(handle)
                sequences = [sequence for sequence in reader]
            except Exception as e:
                # check if relative to os.getcwd
                exit_error(f"Error reading fasta file {str(path)}", e)

            number_sequences = len(sequences)

            # read as many chain codes as there are sequences
            # https://stackoverflow.com/questions/16188270/get-a-fixed-number-of-items-from-a-generator

            chain_codes = list(islice(chain_codes, number_sequences))

            for sequence, chain_code, molecule_type in zip_longest(
                sequences, chain_codes, molecule_types, fillvalue=None
            ):
                if molecule_type is None:
                    molecule_type = MoleculeTypes.PROTEIN

                sequence = [letter_code.letter_code for letter_code in sequence]
                try:
                    sequence_3_let = translate_1_to_3(
                        sequence, molecule_type=molecule_type
                    )
                except BadResidue as e:
                    exit_error(
                        f"Error translating sequence {sequence} to 3 letter code {e}",
                        e,
                    )
                chain_residues = sequence_3let_to_res(sequence_3_let, chain_code)

                residues.update(chain_residues)

    except IOError as e:
        exit_error(f"couldn't open {path} because:\n{e}", e)

    return residues
