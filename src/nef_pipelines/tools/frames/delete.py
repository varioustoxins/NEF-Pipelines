import inspect
import sys
from fnmatch import fnmatch
from typing import List

import typer
from pynmrstar import Entry

from nef_pipelines.lib.util import exit_error, running_in_pycharm
from nef_pipelines.tools.frames import frames_app

UNDERSCORE = "_"

parser = None


# noinspection PyUnusedLocal
@frames_app.command()
def delete(
    use_categories: bool = typer.Option(
        False,
        "-c",
        "--category",
        help="if selected use the category of the frame to select it for deletion rather than it name",
    ),
    exact: bool = typer.Option(
        False, "-e", "--exact", help="don't treat name as a wild card"
    ),
    selectors: List[str] = typer.Argument(
        ...,
        help="a list of frames to delete by type or name,  names can be wildcards, names have lead _'s removed and "
        "surrounding back quotes `  removed",
    ),
):
    """- delete frames in the current input by type or name"""

    entry = _create_entry_from_stdin_or_exit(current_function())

    to_delete = []
    for name in selectors:
        for frame in entry:
            frame_full_name = frame.name
            frame_category = frame.category
            frame_name = frame_full_name[len(frame_category) :].lstrip("_").strip("`")

            for selector in selectors:
                if not exact:
                    selector = f"*{selector}*"

                if use_categories:
                    if fnmatch(frame_category, selector):
                        to_delete.append(frame)
                else:
                    if fnmatch(frame_name, selector):
                        to_delete.append(frame)

    entry.remove_saveframe(to_delete)

    print(entry)


def current_function():

    return inspect.stack()[1][3]


def calling_function():

    return inspect.stack()[2][3]


# TODO: This should be a library function
def _create_entry_from_stdin_or_exit(command_name: str):

    try:

        if sys.stdin.isatty():
            exit_error(
                f"the command {command_name} reads from stdin and there is no stream..."
            )

        if running_in_pycharm():
            exit_error("you can't build read fron stdin in pycharm...")

        lines = list(iter(sys.stdin))

        if len(lines) == 0:
            exit_error(
                f"the command {command_name} reads from stdin and the stream is empty..."
            )

        entry = Entry.from_string("".join(lines))

    except Exception as e:
        exit_error(f"failed to read nef entry from stdin because {e}", e)

    return entry
