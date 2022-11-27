from argparse import Namespace
from pathlib import Path

import typer
from pynmrstar import Entry
from typer import Option

from nef_pipelines.lib.sequence_lib import frame_to_chains
from nef_pipelines.lib.util import get_pipe_file
from nef_pipelines.tools.chains import chains_app

app = typer.Typer()

# TODO: it would be nice to put the chains with the first molecular system frame


# noinspection PyUnusedLocal
@chains_app.command()
def list(
    pipe: Path = typer.Option(
        None,
        metavar="|PIPE|",
        help="pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]",
    ),
    comment: bool = Option(False, "-c", "--comment", help="prepend comment to chains"),
    verbose: bool = Option(False, "-v", "--verbose", help="print verbose info"),
    stream: bool = Option(False, "-s", "--stream", help="stream file after comment"),
):
    """- list the chains in the molecular systems"""
    lines = "".join(get_pipe_file(Namespace(pipe=pipe)).readlines())
    entry = Entry.from_string(lines)
    sequence_frames = entry.get_saveframes_by_category("nef_molecular_system")

    chains = []
    if len(sequence_frames) > 0:
        chains = frame_to_chains(sequence_frames[0])

    result = " ".join(chains)
    chains = "chain" if len(chains) == 1 else "chains"

    verbose = f"{len(result)} {chains}: " if verbose else ""

    comment = "# " if comment else ""

    print(f"{comment}{verbose}{result}")

    if stream:
        print(lines)
