from pathlib import Path
from typing import List

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    NEF_MOLECULAR_SYSTEM,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import sequence_from_entry, sequence_to_nef_frame
from nef_pipelines.lib.util import (
    exit_error,
    get_text_from_file_or_exit,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.xplor import import_app
from nef_pipelines.transcoders.xplor.psf_lib import parse_xplor_PSF

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
    no_chain_starts: List[str] = typer.Option(
        [], "--no-chain-start", help=NO_CHAIN_START_HELP
    ),
    no_chain_ends: List[str] = typer.Option(
        [], "--no-chain-end", help=NO_CHAIN_END_HELP
    ),
    entry_name: str = typer.Option("xplor", help="a name for the entry if required"),
    input_path: Path = typer.Option(
        None,
        metavar="|PIPE|",
        help="file to read NEF data from default is stdin '-'",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="if set don't output the nef stream"
    ),
    file_paths: List[Path] = typer.Argument(
        None, help="the file to read", metavar="<XPLOR-PSF-FILES>"
    ),
):
    """- convert xplor psf to nef sequence"""

    # NOTEs
    # 1. we read in the residues and add them to the current sequence frame if there is one
    # 2. this means if you have a sequence frame already you may want to delete it if it clashes...

    if len(file_paths) == 0:
        exit_error("no psf files provided to read sequences from")

    if input_path:
        entry = read_entry_from_file_or_stdin_or_exit_error(input_path)
    else:
        entry = Entry.from_scratch(entry_id=entry_name)

    sequence_residues = OrderedSet(sequence_from_entry(entry))

    no_chain_starts = parse_comma_separated_options(no_chain_starts)
    no_chain_ends = parse_comma_separated_options(no_chain_ends)

    xplor_psf_residues = []
    for file_path in file_paths:
        text = get_text_from_file_or_exit(file_path)
        xplor_psf_residues = parse_xplor_PSF(text)

    if len(xplor_psf_residues) == 0:
        exit_error(f"no residues read from {input_path}")

    sequence_residues.update(xplor_psf_residues)

    sequence_frame = sequence_to_nef_frame(
        sequence_residues, no_chain_starts, no_chain_ends
    )

    if NEF_MOLECULAR_SYSTEM in entry:
        entry.remove_saveframe(NEF_MOLECULAR_SYSTEM)
    entry.add_saveframe(sequence_frame)

    if not quiet:
        print(entry)
