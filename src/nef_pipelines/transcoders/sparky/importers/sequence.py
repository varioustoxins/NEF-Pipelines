from itertools import chain, cycle, islice, zip_longest
from pathlib import Path
from typing import List

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.sequence_lib import (
    MoleculeType,
    chain_code_iter,
    offset_chain_residues,
    sequence_3let_to_res,
    sequence_to_nef_frame,
    translate_1_to_3,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import STDIN, exit_error, parse_comma_separated_options
from nef_pipelines.transcoders.sparky import import_app

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
        help="chain codes to use for the imported chains, can be a a comma sepatared list or can be called "
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
    entry_name: str = typer.Option("sparky", help="a name for the entry if required"),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
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
        ..., help="the file to read", metavar="<SPARKY-SEQUENCE-FILE>"
    ),
):
    """- convert sparky sequences to nef"""

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

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name)

    entry = pipe(
        entry,
        file_names,
        chain_codes,
        starts,
        no_chain_starts,
        no_chain_ends,
        molecule_types,
    )

    print(entry)


def pipe(
    entry: Entry,
    file_names: List[Path],
    chain_codes: List[str],
    starts: List[int],
    no_chain_starts: List[bool],
    no_chain_ends: List[bool],
    molecule_types: List[MoleculeType],
):

    chain_code_iterator = chain_code_iter(chain_codes)

    chain_offsets = {}
    chains_with_no_start = set()
    chains_with_no_end = set()

    sparky_sequences = set()

    for (
        file_name,
        chain_code,
        molecule_type,
        start,
        no_chain_start,
        no_chain_end,
    ) in zip_longest(
        file_names,
        chain_code_iterator,
        molecule_types,
        starts,
        no_chain_starts,
        no_chain_ends,
    ):

        if file_name is None:
            break

        if molecule_type is None:
            molecule_type = MoleculeType.PROTEIN

        if start is None:
            start = 1

        if no_chain_start is None:
            no_chain_start = False

        if no_chain_end is None:
            no_chain_start = False

        if no_chain_start:
            chains_with_no_start.add(chain)

        if no_chain_end:
            chains_with_no_end.add(chain)

        chain_offsets[chain_code] = start

        sparky_sequences.update(read_sequence(file_name, chain_code, molecule_type))

    sparky_sequences = sorted(sparky_sequences)

    sparky_sequences = offset_chain_residues(sparky_sequences, chain_offsets)

    sparky_frame = sequence_to_nef_frame(
        sparky_sequences, no_chain_starts, no_chain_ends
    )

    entry.add_saveframe(sparky_frame)

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
def read_sequence(
    file_name: Path, chain_code: str, molecule_type: MoleculeType
) -> List[SequenceResidue]:

    try:
        with open(file_name) as handle:
            try:
                sequence = "".join(handle.readlines())
                sequence = "".join(sequence.split())
            except Exception as e:
                exit_error(f"Error reading sparky sequence file {str(file_name)}", e)

            sequence_3_let = translate_1_to_3(sequence, molecule_type=molecule_type)
            chain_residues = sequence_3let_to_res(sequence_3_let, chain_code)

    except IOError as e:
        exit_error(f"couldn't open {file_name} because:\n{e}", e)

    return chain_residues
