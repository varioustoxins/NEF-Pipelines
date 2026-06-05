from pathlib import Path
from textwrap import dedent
from typing import List

import typer
from pynmrstar import Entry

from nef_pipelines.lib.cli_lib import (
    parse_frame_loop_selectors_and_get_errors,
    validate_loop_selection_only_or_raise,
)
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.structures import (
    BadFrameLoopTagSyntaxException,
    FrameLoopsAndTags,
)
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.tools.loops import loops_app


@loops_app.command()
def delete(
    input: Path = typer.Option(
        STDIN,
        "--in",
        metavar="|PIPE|",
        help="read NEF data from a file or stdin",
    ),
    selectors: List[str] = typer.Argument(
        ...,
        help="frame.loop selectors — loops to delete (slash-separated or multiple args)",
    ),
) -> None:
    """- delete loops from frames; selectors: frame.loop or frame1.loop1/frame2.loop2"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frames_loops_and_tags = _parse_selectors_to_loops_or_exit(entry, selectors)

    try:
        entry = pipe(entry, frames_loops_and_tags)
    except BadFrameLoopTagSyntaxException as e:
        msg = f" There was a problem parsing the selectors because:\n{e}"
        exit_error(msg)

    print(entry)


def pipe(entry: Entry, frames_loops_and_tags: List[FrameLoopsAndTags]) -> Entry:
    """Delete loops from frames.

    Args:
        entry: NEF entry to modify
        frames_loops_and_tags: Selections with only frame and loop defined (no tags)

    Raises:
        ValueError: If selections contain frame_tags or loop_tags
    """

    for item in frames_loops_and_tags:
        validate_loop_selection_only_or_raise(item)

        for loop in item.loops:
            if loop in item.frame.loops:
                item.frame.loops.remove(loop)

    return entry


def _parse_selectors_to_loops_or_exit(
    entry: Entry, selectors: list[str]
) -> List[FrameLoopsAndTags]:

    loops, errors = parse_frame_loop_selectors_and_get_errors(entry, selectors)
    if errors:
        errors = "\n".join(error for error in errors)

        msg = f"""
            There was a problem parsing the following selectors to loop selections:

            {errors}
        """
        exit_error(dedent(msg))

    return loops
