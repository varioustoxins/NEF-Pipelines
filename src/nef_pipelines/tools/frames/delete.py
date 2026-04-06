from fnmatch import fnmatchcase
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry, Saveframe

from nef_pipelines.lib.nef_lib import (
    parse_frame_name,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.tools.frames import frames_app


@frames_app.command()
def delete(
    input_path: Path = typer.Option(
        None,
        "--in",
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

    saveframes_to_delete = _find_saveframes(
        entry, selectors, use_categories=use_categories, exact=exact
    )

    result = pipe(entry, saveframes_to_delete)

    print(result)


# TODO: should be in a library
def _find_saveframes(
    entry: Entry,
    selectors: List[str],
    use_categories: bool = False,
    exact: bool = False,
) -> List[Saveframe]:
    """\
    Find saveframes matching the given selectors.

    Args:
        entry: NEF entry to search
        selectors: List of selector patterns (wildcards supported unless exact=True)
        use_categories: If True, match against category instead of name/identity
        exact: If True, don't add wildcards to selectors

    Returns:
        List of matching saveframes
    """
    to_delete = []

    for frame in entry:
        parsed = parse_frame_name(frame)

        for selector in selectors:
            if not exact:
                selector = f"*{selector}*"

            if use_categories:
                if fnmatchcase(parsed.category, selector):
                    to_delete.append(frame)
                    break
            else:
                identity_match = parsed.identity is not None and fnmatchcase(
                    parsed.identity, selector
                )
                full_name_match = fnmatchcase(parsed.full_name, selector)

                if identity_match or full_name_match:
                    to_delete.append(frame)
                    break

    return to_delete


def pipe(entry: Entry, saveframes_to_delete: List[Saveframe]) -> Entry:
    """\
    Remove specified saveframes from entry.

    Args:
        entry: NEF entry to modify
        saveframes_to_delete: List of saveframes to remove

    Returns:
        Modified entry with saveframes removed
    """
    entry.remove_saveframe(saveframes_to_delete)
    return entry
