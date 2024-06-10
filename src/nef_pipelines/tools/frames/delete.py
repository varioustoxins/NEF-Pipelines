from fnmatch import fnmatch
from pathlib import Path
from typing import List

import typer

from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.tools.frames import frames_app

UNDERSCORE = "_"

parser = None


# noinspection PyUnusedLocal
@frames_app.command()
def delete(
    input_path: Path = typer.Option(
        None,
        metavar="|PIPE|",
        help="file to read NEF data from default is stdin '-'",
    ),
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

    entry = read_entry_from_file_or_stdin_or_exit_error(input_path)

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
