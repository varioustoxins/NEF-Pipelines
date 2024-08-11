from pathlib import Path

import typer

from nef_pipelines.lib.nef_lib import (
    molecular_system_from_entry_or_exit,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import chains_from_frames
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.transcoders.fasta.exporters.sequence import pipe as fasta_pipe
from nef_pipelines.transcoders.mars import export_app


@export_app.command()
def sequence(
    chain_code: str = typer.Option(
        None,
        "-c",
        "--chain_code",
        help=" single chain to export  [default: 'A']",
        metavar="<CHAIN-CODE>",
    ),
    input_file: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    output_file: Path = typer.Argument(
        None,
        help="file name to output to [default <ENTRY-ID.fasta>] for stdout use -",
        metavar="<FASTA-SEQUENCE-FILE>",
    ),
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="force overwrite of output file if it exists and isn't empty",
    ),
):
    """- write a mars sequence file [fasta]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input_file)

    output_file = output_file if output_file else f"{entry.entry_id}.fasta"

    molecular_system = molecular_system_from_entry_or_exit(entry)

    chain_code = _get_single_chain_code_or_exit(
        chain_code, molecular_system, input_file
    )

    entry = fasta_pipe(entry, chain_code, Path(output_file), force)

    if entry:
        print(entry)


def _get_single_chain_code_or_exit(chain_code_selector, molecular_system, input_file):

    chain_codes = chains_from_frames(molecular_system)

    _exit_if_no_chain_codes(chain_codes, input)

    chain_code = None
    if not chain_code_selector:
        chain_code = _get_default_chain_code_or_exit(chain_codes, input_file)

    if not chain_code:
        chain_code = _select_single_chain_code_or_exit(chain_code_selector, chain_codes)

    return chain_code


def _exit_if_no_chain_codes(chain_codes, input):
    if len(chain_codes) != 1:
        msg = f"""\
            A  chain code is required and I didn't fina any in
            {input}
        """
        exit_error(msg)


def _select_single_chain_code_or_exit(chain_code, chain_codes):

    if chain_code not in chain_codes:
        chain_code_list = ", ".join(chain_codes)
        msg = f"""\
                the selected chain code is {chain_code} but this wasn't found in the input
                {input}
                this contained the following chain codes
                {chain_code_list}
            """
        exit_error(msg)

    return chain_code


def _get_default_chain_code_or_exit(chain_codes, input_file):

    if len(chain_codes) != 1:
        num_chains = len(chain_codes)
        chains_list = ", ".join(chain_codes)
        msg = f"""\
            You didn't select a chain code and single chain is required...
            I found {num_chains} chains in {input_file}
            the chains were:
            {chains_list}
        """
        exit_error(msg)

    return chain_codes[0]
