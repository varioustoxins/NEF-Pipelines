from pathlib import Path
from typing import List

import typer
from ordered_set import OrderedSet
from typer import Argument, Option

from nef_pipelines.lib.nef_lib import (
    SELECTORS_LOWER,
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.util import STDIN
from nef_pipelines.tools.chains import chains_app

app = typer.Typer()

# TODO: it would be nice to put the chains with the first molecular system frame


# noinspection PyUnusedLocal
@chains_app.command()
def rename(
    new_old: List[str] = Argument(
        ...,
        help="old chain-code followed by new chain-code, multiple pairs of old and new "
        "chain-codes can be provided",
    ),
    # TODO: just use --category instead to make life simpler???
    selector_type: SelectionType = typer.Option(
        SelectionType.ANY,
        "-t",
        "--selector-type",
        help=f"how to select frames to renumber, can be one of: {SELECTORS_LOWER}."
        "Any will match on names first and then if there is no match attempt to match on category",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    frame_selectors: List[str] = Option(
        None,
        "-f",
        "--frame",
        help="limit changes to a a particular frame by a selector which can be a frame name or category, "
        "note: wildcards [*] are allowed. Frames are selected by name and subsequently by category if the name "
        "doesn't match [-t /--selector-type allows you to force which selection type to use]. If no frame"
        "names or categories are provided chain-codes are renamed in all frames.",
    ),
):
    """- change the name of chains across one or multiple frames"""
    old = new_old[0]
    new = new_old[1]

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    changes = 0
    changed_frames = OrderedSet()

    frames_to_process = select_frames(entry, frame_selectors, selector_type)

    for save_frame in frames_to_process:
        for loop in save_frame.loop_iterator():
            for tag in loop.get_tag_names():
                tag_parts = tag.split(".")
                if tag_parts[-1].startswith("chain_code"):
                    tag_values = loop[tag]
                    for i, row in enumerate(tag_values):
                        if row == old:
                            tag_values[i] = new
                            changes += 1
                            changed_frames.add(save_frame.name)

                    loop[tag] = tag_values

    print(entry)
