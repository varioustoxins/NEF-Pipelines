import sys
from fnmatch import fnmatch
from typing import List

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry
from typer import Argument, Option

from nef_pipelines.lib.util import chunks, get_pipe_file
from nef_pipelines.tools.chains import chains_app

app = typer.Typer()

# TODO: it would be nice to put the chains with the first molecular system frame


# noinspection PyUnusedLocal
@chains_app.command()
def rename(
    old: str = Argument(..., help="old chain code"),
    new: str = Argument(..., help="new chain code"),
    comment: bool = Option(False, "--comment", help="prepend comment to chains"),
    verbose: bool = Option(False, "-v", "--verbose", help="print verbose info"),
    use_category: bool = Option(
        False,
        "-c",
        "--category",
        help="select frames to rename chains in by category rather than name",
    ),
    frames: List[str] = Option(
        [],
        "-f",
        "--frame",
        help="limit changes to a a particular frame by name [or category if --category is set], note: wildcards are "
        "allowed, repeated uses add more frames",
    ),
):
    """- change the name of chains across one or multuiple frames"""

    lines = "".join(get_pipe_file([]).readlines())
    entry = Entry.from_string(lines)

    changes = 0
    changed_frames = OrderedSet()
    for save_frame in entry:
        process_frame = True
        for frame_selector in frames:

            if use_category:
                if not fnmatch(save_frame.category, f"*{frame_selector}*"):

                    process_frame = False
            else:
                if not fnmatch(save_frame.name, f"*{frame_selector}*"):
                    process_frame = False

        if process_frame:
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

    if verbose:
        comment = "# " if comment else ""
        out = sys.stderr if not comment else sys.stdout
        if changes >= 1:
            print(
                f"{comment}rename chain: {changes} changes made in the following frames",
                file=out,
            )
            for chunk in chunks(changed_frames, 5):
                print(f'{comment}  {", ".join(chunk)}', file=out)

        else:
            print(f"{comment}rename chain: no changes made", file=out)
        print(file=out)

    print(entry)
