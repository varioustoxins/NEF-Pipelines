from itertools import chain, cycle, islice
from pathlib import Path
from typing import Iterable, List

import typer
from fastaparser import Reader
from ordered_set import OrderedSet
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    BadResidue,
    MoleculeType,
    chain_code_iter,
    offset_chain_residues,
    sequence_3let_to_res,
    sequence_to_nef_frame,
    translate_1_to_3,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import STDIN, exit_error, parse_comma_separated_options
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
    in_file: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [- is stdin]",
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

    file_names = parse_comma_separated_options(file_names)

    chain_codes = parse_comma_separated_options(chain_codes)
    if not chain_codes:
        chain_codes = [
            "A",
        ]

    no_chain_starts = parse_comma_separated_options(no_chain_starts)
    if not no_chain_starts:
        no_chain_starts = [
            False,
        ]

    no_chain_ends = parse_comma_separated_options(no_chain_ends)
    if no_chain_ends:
        no_chain_ends = [
            False,
        ]

    starts = [int(elem) for elem in parse_comma_separated_options(starts)]
    if not starts:
        starts = [
            1,
        ]

    molecule_types = parse_comma_separated_options(molecule_types)
    if not molecule_types:
        molecule_types = [
            MoleculeType.PROTEIN,
        ]

    entry = read_or_create_entry_exit_error_on_bad_file(in_file)

    entry = pipe(
        entry,
        chain_codes,
        starts,
        no_chain_starts,
        no_chain_ends,
        molecule_types,
        file_names,
        in_file,
    )

    print(entry)


def pipe(
    entry: Entry,
    chain_codes: List[str],
    starts: List[int],
    no_chain_starts: List[bool],
    no_chain_ends: List[bool],
    molecule_types: List[MoleculeType],
    file_names,
    input: Path,
):
    fasta_frames = []

    chain_code_iterator = chain_code_iter(chain_codes)
    fasta_sequences = OrderedSet()

    fasta_sequences.update(
        _read_sequences(file_names, chain_code_iterator, molecule_types)
    )

    read_chain_codes = residues_to_chain_codes(fasta_sequences)

    offsets = _get_sequence_offsets(read_chain_codes, starts)

    fasta_sequences = offset_chain_residues(fasta_sequences, offsets)

    fasta_sequences = sorted(fasta_sequences)

    fasta_frames.append(sequence_to_nef_frame(fasta_sequences))

    entry = add_frames_to_entry(entry, fasta_frames)

    return entry


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
def _read_sequences(
    file_paths: List[Path],
    chain_codes: Iterable[str],
    molecule_types: List[MoleculeType],
) -> List[SequenceResidue]:

    sequences = []
    headers = []
    for file_path in file_paths:
        try:
            with open(file_path) as handle:
                try:
                    reader = Reader(handle)
                    sequences.extend([sequence for sequence in reader])
                    headers.extend([header for header in reader])
                except Exception as e:
                    # check if relative to os.getcwd
                    exit_error(f"Error reading fasta file {str(file_path)}", e)
        except IOError as e:
            exit_error(f"couldn't open {file_path} because:\n{e}", e)

    number_sequences = len(sequences)
    number_molecule_types = len(molecule_types)

    if number_molecule_types == 1:
        molecule_types = molecule_types * number_sequences
    elif number_molecule_types == 0 or number_molecule_types < number_sequences:
        msg = f"""
            number molecule types [{number_molecule_types}] is different from number of chains {number_sequences}
        """
        exit_error(msg)

    residues = OrderedSet()
    # read as many chain codes as there are sequences
    # https://stackoverflow.com/questions/16188270/get-a-fixed-number-of-items-from-a-generator
    for sequence, chain_code, molecule_type in zip(
        sequences, chain_code_iter(chain_codes), molecule_types
    ):

        sequence = [letter_code.letter_code for letter_code in sequence]

        try:
            sequence_3_let = translate_1_to_3(sequence, molecule_type=molecule_type)
        except BadResidue as e:
            exit_error(
                f"Error translating sequence {sequence} to 3 letter code {e}",
                e,
            )
        chain_residues = sequence_3let_to_res(sequence_3_let, chain_code)

        residues.update(chain_residues)

    return residues
