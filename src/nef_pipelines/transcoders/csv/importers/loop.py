from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import Any, List, Tuple

import typer
from pynmrstar import Entry, Loop, Saveframe
from strenum import KebabCaseStrEnum, LowercaseStrEnum

from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.structures import PipeOutput
from nef_pipelines.lib.tabular_data_lib import (
    ENCODING,
    HELP_FOR_FORMATS,
    CsvLikeFormats,
    CsvParseError,
    _apply_skip_and_comment,
    _parse_csv_rows_from_text,
    parse_csv_text,
)
from nef_pipelines.lib.util import STDIN, chunks, exit_error, warn
from nef_pipelines.transcoders.csv import import_app


@dataclass(frozen=True)
class FrameLoopPath:
    """Associates a saveframe with a loop category and CSV file path for loading.

    Used to pass pre-looked-up frames to pipe() that loads CSV data into loops.
    The CLI looks up frames by name, and pipe() receives the actual frame objects.

    Attributes:
        frame: Saveframe object to add the loop to
        loop_category: NEF loop category name (loop doesn't exist yet)
        path: Path to CSV file to load
    """

    frame: Saveframe
    loop_category: str
    path: Path


HELP_FILE_ARGS = """\
    for COMMAND_LINE policy: triplets of framecode loop_category path
    for FILE_NAME policy: paths to CSV files with names like <framecode>__<loop_category>.csv
    for HEADER policy: paths to CSV files where the first line contains framecode,loop_category
    for COMMENT policy: paths to CSV files with structured comment like # framename: <name> loop: <category>
"""

HELP_FRAME_POLICY = """\
    defines how to determine the  frame and loop:
    whn using the  command-line [the default] : arguments are triplets of framecode loop name and a path to a file
    FILE_NAME: filename encodes frame as <framecode>__<loop_category>.csv
    HEADER: first line of file (may be #-prefixed): framecode,loop_category
    COMMENT: comment line in file with format: # framename: <framecode> loop: <loop_category>
"""


class FrameNamePolicy(LowercaseStrEnum, KebabCaseStrEnum):
    """Policy for specifying the target frame and loop category."""

    COMMAND_LINE = auto()
    FILE_NAME = auto()
    HEADER = auto()
    COMMENT = auto()


@import_app.command(no_args_is_help=True)
def loop(
    input: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read input from [- is stdin]"
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
    frame_policy: FrameNamePolicy = typer.Option(
        FrameNamePolicy.COMMAND_LINE, "--frame-policy", help=HELP_FRAME_POLICY
    ),
    file_args: List[str] = typer.Argument(None, help=HELP_FILE_ARGS),
) -> None:
    """- import one or more CSV files as loops into existing NEF saveframes"""

    csv_format = CsvLikeFormats(csv_format.upper())

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    # COMMENT policy requires --comment to be specified
    if frame_policy == FrameNamePolicy.COMMENT and not comment:
        msg = """\
            the comment frame policy requires --comment to be specified
            (the comment character may not be # in all files)
        """
        exit_error(msg)

    framecode_loop_category_paths = _load_frames_loops_and_paths_or_exit_error(
        file_args, csv_format, frame_policy, comment, skip
    )

    # HEADER policy: skip is already applied when parsing framecode/loop_category,
    # and we need to skip 1 more row (the framecode line itself) before reading column headers
    if frame_policy == FrameNamePolicy.HEADER:
        header_skip = 1 + skip  # Skip initial rows + framecode line
        data_skip = 0  # Don't skip again when reading data
    else:
        header_skip = 0  # No rows to skip before headers
        data_skip = skip  # Skip rows after headers

    # Look up frames and build FrameLoopPath objects
    frame_loop_paths = []
    _build_frames_loops_and_paths_or_exit_error(
        entry, frame_loop_paths, framecode_loop_category_paths
    )

    try:
        result = pipe(
            entry, frame_loop_paths, csv_format, data_skip, comment, header_skip
        )
    except CsvParseError as e:
        exit_error(str(e))

    for warning in result.warnings:
        warn(warning)

    print(result.entry)


def pipe(
    entry: Entry,
    frame_loop_paths: List[FrameLoopPath],
    csv_format: CsvLikeFormats,
    skip: int = 0,
    comment: str = "",
    header_skip: int = 0,
) -> PipeOutput:
    """Add loops read from CSV files to existing saveframes in entry.

    Args:
        entry: NEF entry containing the target saveframes
        frame_loop_paths: List of pre-looked-up frames with loop categories and CSV paths
        csv_format: Format of CSV files (CSV, TSV, SSV, or AUTO)
        skip: Number of extra header rows to skip after column headers
        comment: Prefix for comment lines to ignore
        header_skip: Number of rows to skip before reading column headers

    Returns:
        PipeOutput with modified entry and warnings about normalized headers
    """

    all_warnings = []

    for frame_loop_path in frame_loop_paths:
        # Read file once, parse as text
        try:
            text = frame_loop_path.path.read_text(encoding=ENCODING)
        except (OSError, PermissionError, UnicodeDecodeError) as e:
            exit_error(f"failed to read {frame_loop_path.path}: {e}")

        tags, data_rows, warnings = parse_csv_text(
            text, csv_format, skip, comment, header_skip, frame_loop_path.path
        )
        all_warnings.extend(warnings)

        nef_loop = Loop.from_scratch()
        nef_loop.set_category(frame_loop_path.loop_category)
        nef_loop.add_tag(tags)

        row_dicts = [dict(zip(tags, row)) for row in data_rows]
        nef_loop.add_data(row_dicts)

        frame_loop_path.frame.add_loop(nef_loop)

    return PipeOutput(entry=entry, warnings=all_warnings)


def _build_frames_loops_and_paths_or_exit_error(
    entry: Entry,
    frame_loop_paths: list[Any],
    framecode_loop_category_paths: list[tuple[Any, Any, Path]],
):
    for framecode, loop_category, csv_file in framecode_loop_category_paths:
        try:
            frame = entry.get_saveframe_by_name(framecode)
        except KeyError:
            msg = f"""\
                the frame {framecode} was not found in the entry {entry.entry_id}
                you may need to create it first using: nef frames create
            """
            exit_error(msg)
        frame_loop_paths.append(FrameLoopPath(frame, loop_category, csv_file))


def _load_frames_loops_and_paths_or_exit_error(
    file_args: list[str],
    csv_format: CsvLikeFormats,
    frame_policy: FrameNamePolicy,
    comment: str,
    skip: int,
) -> list[tuple[Any, Any, Path]]:
    if frame_policy == FrameNamePolicy.COMMAND_LINE:
        if len(file_args) % 3 != 0:
            msg = f"""\
                for the command-line frame policy arguments must be triplets of framecode loop-category and path
                i got {len(file_args)} argument(s), the last unpaired argument was: {file_args[-1]}
            """
            exit_error(msg)
        framecode_loop_category_paths = [
            (framecode, loop_category, Path(path))
            for framecode, loop_category, path in chunks(file_args, 3)
        ]
    elif frame_policy == FrameNamePolicy.FILE_NAME:
        framecode_loop_category_paths = _parse_file_name_policy(file_args)
    elif frame_policy == FrameNamePolicy.HEADER:
        framecode_loop_category_paths = _parse_frame_and_loop_from_file_header(
            file_args, csv_format, skip, comment
        )
    elif frame_policy == FrameNamePolicy.COMMENT:
        framecode_loop_category_paths = _parse_frame_and_loop_from_comment(
            file_args, comment
        )
    else:
        exit_error(f"unknown frame policy: {frame_policy}")
    return framecode_loop_category_paths


def _parse_file_name_policy(file_args: List[str]) -> List[Tuple[str, str, Path]]:
    """Parse FILE_NAME policy: filename is <framecode>__<loop_category>.csv."""
    result = []
    for path_str in file_args:
        path = Path(path_str)
        stem = path.stem
        if "__" not in stem:
            msg = f"""\
                for the file_name frame policy the filename must encode the frame as
                <framecode>__<loop_category>.csv but {path.name} does not contain '__'
            """
            exit_error(msg)
        framecode, loop_category = stem.split("__", 1)
        result.append((framecode, loop_category, path))
    return result


def _parse_frame_and_loop_from_file_header(
    file_args: List[str], csv_format: CsvLikeFormats, skip: int, comment: str = ""
) -> List[Tuple[str, str, Path]]:
    """Parse HEADER policy: first line after comments and skip rows contains framecode,loop_category."""
    result = []
    for path_str in file_args:
        path = Path(path_str)
        raw_text = path.read_text(encoding=ENCODING)
        filtered_text = _apply_skip_and_comment(raw_text, skip=skip, comment=comment)

        # Parse CSV rows from text (no file pointer needed)
        rows = _parse_csv_rows_from_text(filtered_text, csv_format)
        first_row = rows[0] if rows else None

        if first_row is None:
            exit_error(f"the CSV file {path} is empty")

        header_line = [cell.strip().lstrip("#").strip() for cell in first_row]
        if len(header_line) < 2:
            msg = f"""\
                for the header frame policy the first line of {path.name} must contain
                framecode and loop_category separated by the file's delimiter
            """
            exit_error(msg)
        framecode = header_line[0]
        loop_category = header_line[1]
        result.append((framecode, loop_category, path))
    return result


def _parse_frame_and_loop_from_comment(
    file_args: List[str], comment: str = ""
) -> List[Tuple[str, str, Path]]:
    """Parse COMMENT policy: find framename: and loop: in comment lines (can be separate lines)."""
    result = []

    for path_str in file_args:
        path = Path(path_str)
        raw_text = path.read_text(encoding=ENCODING)

        framecode = None
        loop_category = None
        comment_prefix = comment if comment else "#"

        for line in raw_text.splitlines():
            stripped = line.strip()
            # Skip if not a comment line
            if not stripped.startswith(comment_prefix):
                continue

            # Remove comment prefix
            content = stripped.lstrip(comment_prefix).strip().lower()

            # Look for framename: <value>
            if framecode is None and "framename:" in content:
                parts = content.split("framename:", 1)
                if len(parts) == 2:
                    value = parts[1].strip().split()[0] if parts[1].strip() else None
                    if value:
                        framecode = value

            # Look for loop: <value>
            if loop_category is None and "loop:" in content:
                parts = content.split("loop:", 1)
                if len(parts) == 2:
                    value = parts[1].strip().split()[0] if parts[1].strip() else None
                    if value:
                        loop_category = value

            # Stop searching once we have both
            if framecode and loop_category:
                break

        if framecode is None or loop_category is None:
            missing = []
            if framecode is None:
                missing.append("framename: <framecode>")
            if loop_category is None:
                missing.append("loop: <loop_category>")
            msg = f"""\
                for the comment frame policy {path.name} must contain comment lines with:
                {', '.join(missing)}
                but they were not found
            """
            exit_error(msg)

        result.append((framecode, loop_category, path))
    return result
