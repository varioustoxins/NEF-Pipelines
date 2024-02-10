from pathlib import Path

import typer
from typer import Option

from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.sequence_lib import frame_to_chains
from nef_pipelines.lib.util import STDIN
from nef_pipelines.tools.chains import chains_app

app = typer.Typer()

# TODO: it would be nice to put the chains with the first molecular system frame


# noinspection PyUnusedLocal
@chains_app.command()
def list(
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from, for testing [overrides stdin !use stdin instead!]",
    ),
    comment: bool = Option(False, "-c", "--comment", help="prepend comment to chains"),
    verbose: bool = Option(False, "-v", "--verbose", help="print verbose info"),
    stream: bool = Option(False, "-s", "--stream", help="stream file after comment"),
):
    """- list the chains in the molecular systems"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

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
        print(entry)
