from pathlib import Path

import typer

from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.sequence_lib import MoleculeType
from nef_pipelines.lib.util import STDIN
from nef_pipelines.transcoders.fasta.importers.sequence import pipe
from nef_pipelines.transcoders.mars import import_app


@import_app.command(no_args_is_help=True)
def sequence(
    chain_code: str = typer.Option(
        None,
        "--chain",
        help="chain code to use for the imported chains [only one mars only supports one]",
        metavar="<CHAIN-CODE>",
    ),
    start: int = typer.Option(
        1,
        "--start",
        help="first residue number of the sequence",
        metavar="<START>",
    ),
    no_chain_start: bool = typer.Option(None, "--no-chain-start", help=""),
    no_chain_end: bool = typer.Option(None, "--no-chain-end", help=""),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_name: Path = typer.Argument(
        ..., help="input files of type sequence.fasta", metavar="<MARS-SEQUENCE>.fasta"
    ),
):
    """- import mars sequence from fasta file"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    chain_codes = (
        [
            chain_code,
        ]
        if chain_code
        else []
    )
    starts = [
        start,
    ]
    no_chain_starts = (
        [
            no_chain_start,
        ]
        if no_chain_start
        else []
    )
    no_chain_ends = (
        [
            no_chain_end,
        ]
        if no_chain_end
        else []
    )
    molecule_types = [
        MoleculeType.PROTEIN,
    ]
    file_names = [
        file_name,
    ]

    entry = pipe(
        entry,
        chain_codes,
        starts,
        no_chain_starts,
        no_chain_ends,
        molecule_types,
        False,
        file_names,
        file_name.root,
    )

    print(entry)
