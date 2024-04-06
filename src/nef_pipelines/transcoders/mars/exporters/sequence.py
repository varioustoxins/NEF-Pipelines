from pathlib import Path

import typer

from nef_pipelines.transcoders.fasta.exporters.sequence import (
    sequence as fasta_sequence,
)
from nef_pipelines.transcoders.mars import export_app


@export_app.command()
def sequence(
    chain_code: str = typer.Option(
        "A",
        "-c",
        "--chain_code",
        help=" single chain to export  [default: 'A']",
        metavar="<CHAIN-CODE>",
    ),
    in_file: Path = typer.Option(
        None, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    output_file: Path = typer.Argument(
        None,
        help="file name to output to [default <ENTRY-ID.fasta>] for stdout use -",
        metavar="<FASTA-SEQUENCE-FILE>",
    ),
):
    """- write a mars sequence file [fasta]"""
    fasta_sequence(chain_code, in_file, output_file)
