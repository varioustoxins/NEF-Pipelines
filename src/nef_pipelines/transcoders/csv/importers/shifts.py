from itertools import cycle
from pathlib import Path
from typing import List, Tuple

import typer
from pynmrstar import Entry, Loop

from nef_pipelines.lib.nef_lib import (
    is_save_frame_name_in_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.tabular_data_lib import HELP_FOR_FORMATS, CsvLikeFormats
from nef_pipelines.lib.tabular_data_lib import read_csv as _read_csv
from nef_pipelines.lib.util import STDIN, chunks, exit_error, warn
from nef_pipelines.tools.frames.create import pipe as frames_create_pipe
from nef_pipelines.transcoders.csv import import_app

FRAME_CATEGORY = "nef_chemical_shift_list"
LOOP_CATEGORY = "nef_chemical_shift"

REQUIRED_COLUMN = "value"

HELP_NAME_FILE = """\
    alternating name and file pairs, e.g. myshifts shifts.csv or
    myshifts_A shifts_A.csv myshifts_B shifts_B.csv
"""


@import_app.command(no_args_is_help=True)
def shifts(
    input: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read input from [- is stdin]"
    ),
    chain_codes: List[str] = typer.Option(
        ["A"],
        "-c",
        "--chains",
        help="default chain code(s) to use if chain_code column is absent in the CSV",
    ),
    csv_format: CsvLikeFormats = typer.Option(
        CsvLikeFormats.AUTO, "-f", "--format", help=HELP_FOR_FORMATS
    ),
    skip: int = typer.Option(
        0, "--skip", help="extra header rows to skip after the column header row"
    ),
    comment: str = typer.Option(
        "", "--comment", help="ignore lines that start with this prefix before parsing"
    ),
    quiet: bool = typer.Option(
        False, "-q", "--quiet", help="suppress warnings about replacing existing frames"
    ),
    name_file: List[str] = typer.Argument(
        ...,
        help=HELP_NAME_FILE,
    ),
) -> None:
    """- import chemical shifts from one or more CSV files into NEF shift list frames"""

    csv_format = CsvLikeFormats(csv_format.upper())

    _check_names_and_file_are_pairs_or_exit_errors(name_file)

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    name_file_pairs = [(name, Path(path)) for name, path in chunks(name_file, 2)]

    # Check which frames exist before import (to warn after)
    existing_frames = _check_existing_frames(entry, name_file_pairs)

    result = pipe(entry, name_file_pairs, chain_codes, csv_format, skip, comment)

    _warn_about_replaced_frames(existing_frames, quiet)

    print(result)


def pipe(
    entry: Entry,
    name_file_pairs: List[Tuple[str, Path]],
    chain_codes: List[str],
    csv_format: CsvLikeFormats,
    skip: int = 0,
    comment: str = "",
) -> Entry:
    """Import chemical shifts from CSV files into new shift list frames in entry."""

    chain_code_iter = cycle(chain_codes)

    category_name_pairs = [(FRAME_CATEGORY, name) for name, _ in name_file_pairs]
    entry = frames_create_pipe(entry, category_name_pairs)

    for name, csv_file in name_file_pairs:
        default_chain_code = next(chain_code_iter)
        tags, data_rows, _ = _read_csv(csv_file, csv_format, skip, comment)

        _validate_shift_tags_or_exit(tags, csv_file)

        if "chain_code" not in tags:
            tags = ["chain_code"] + tags
            data_rows = [[default_chain_code] + row for row in data_rows]

        framecode = f"{FRAME_CATEGORY}_{name}"
        frame = entry.get_saveframe_by_name(framecode)

        nef_loop = Loop.from_scratch()
        nef_loop.set_category(LOOP_CATEGORY)
        nef_loop.add_tag(tags)
        for row in data_rows:
            nef_loop.add_data([dict(zip(tags, row))])
        frame.add_loop(nef_loop)

    return entry


def _check_existing_frames(
    entry: Entry, name_file_pairs: List[Tuple[str, Path]]
) -> List[str]:
    """Check which frames will be replaced and return their names."""
    existing = []
    for name, _ in name_file_pairs:
        framecode = f"{FRAME_CATEGORY}_{name}"
        if is_save_frame_name_in_entry(entry, framecode):
            existing.append(framecode)
    return existing


def _warn_about_replaced_frames(existing_frames: List[str], quiet: bool) -> None:
    """Warn about frames that were replaced (unless --quiet)."""
    if not quiet:
        for framecode in existing_frames:
            warn(f"frame {framecode} already exists, replacing it")


def _check_names_and_file_are_pairs_or_exit_errors(name_file: list[str]):
    if len(name_file) % 2 != 0:
        msg = f"""\
            name and file must be provided in pairs, i got {len(name_file)} argument(s)
            the last unpaired argument was: {name_file[-1]}
        """
        exit_error(msg)


def _validate_shift_tags_or_exit(tags: List[str], csv_file: Path) -> None:
    """Exit with an error if the required 'value' column is absent."""
    if REQUIRED_COLUMN not in tags:
        msg = f"""\
            the CSV file {csv_file} is missing the required column '{REQUIRED_COLUMN}'
            columns found: {', '.join(tags)}
        """
        exit_error(msg)
