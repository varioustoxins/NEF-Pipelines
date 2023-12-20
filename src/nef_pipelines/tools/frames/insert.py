import inspect
import sys
from enum import auto
from fnmatch import fnmatch
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry
from strenum import LowercaseStrEnum

from nef_pipelines.lib.util import (
    exit_error,
    parse_comma_separated_options,
    running_in_pycharm,
)
from nef_pipelines.tools.frames import frames_app

UNDERSCORE = "_"

parser = None


class PRIORITY(LowercaseStrEnum):
    STDIN = auto()
    FILE = auto()


SELECT_HELP = """a list of frames by full name or categeory to merge from the the inserted file, can use lists for frame
               names joined with , or be called mutiple times [default is all frames] if --category is set use
               categories rather than names, if --exact isn'r fefined you can use wild cards"""


# noinspection PyUnusedLocal
@frames_app.command()
def insert(
    exact: bool = typer.Option(
        False, "-e", "--exact", help="don't treat name as a wild card"
    ),
    use_categories: bool = typer.Option(
        False,
        "-c",
        "--category",
    ),
    select: List[str] = typer.Option(None, "-s", "--select", help=SELECT_HELP),
    priority: PRIORITY = typer.Option(
        PRIORITY.FILE,
        "-p",
        "--priority",
        help=f"source of frames to prioritise, one of {PRIORITY.STDIN} and {PRIORITY.FILE}",
    ),
    nef_file_paths: List[Path] = typer.Argument(
        ..., help="nef files from which to insert frames into the current stream"
    ),
):
    """- insert frames from another nef file into the current stream"""

    select = parse_comma_separated_options(select)
    select_all = len(select) == 0

    stream_entry = _create_entry_from_stdin_or_exit(current_function())

    for nef_file_path in nef_file_paths:
        external_entry = Entry.from_file(nef_file_path.open())
        for external_frame in external_entry:

            ok_external_frame = False

            if select_all:
                ok_external_frame = True
            if use_categories and exact and external_frame.category in select:
                ok_external_frame = True
            if not use_categories and exact and external_frame.name in select:
                ok_external_frame = True
            if use_categories and not exact:
                for category in select:
                    if fnmatch(external_frame.category, f"*{category}*"):
                        ok_external_frame = True
            if not use_categories and not exact:
                for name in select:
                    if fnmatch(external_frame.name, f"*{name}*"):
                        ok_external_frame = True

            if ok_external_frame:
                if external_frame in stream_entry:
                    if priority == PRIORITY.STDIN:
                        continue
                    elif priority == PRIORITY.FILE:
                        del stream_entry[external_frame.name]
                        stream_entry.add_saveframe(external_frame)
                else:
                    stream_entry.add_saveframe(external_frame)

    print(stream_entry)


def current_function():

    return inspect.stack()[1][3]


def calling_function():

    return inspect.stack()[2][3]


def _create_entry_from_stdin_or_exit(command_name: str):

    try:

        if sys.stdin.isatty():
            exit_error(
                f"the command {command_name} reads from stdin and there is no stream..."
            )

        if running_in_pycharm():
            exit_error("you can't build read fron stdin in pycharm...")

        result = sys.stdin.readlines()

        # result is an iterable as well as an iter, but may have been read already making the iter empty?
        # hence the need to call iter?
        lines = list(iter(result))

        if len(lines) == 0:
            exit_error(
                f"the command {command_name} reads from stdin and the stream is empty..."
            )

        entry = Entry.from_string("".join(lines))

    except Exception as e:
        exit_error(f"failed to read nef entry from stdin because {e}", e)

    return entry
