import functools
import io
from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import Any, List, Tuple

import typer
from pynmrstar import Entry, Loop, Saveframe
from strenum import KebabCaseStrEnum, LowercaseStrEnum

from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.structures import PipeOutput
from nef_pipelines.lib.util import (
    STDIN,
    chunks,
    escape_spaces_with_underscore,
    exit_error,
    warn,
)
from nef_pipelines.tools.columns.columns_lib import _apply_skip_and_comment
from nef_pipelines.transcoders.csv import import_app
from nef_pipelines.transcoders.csv.importers.csv_lib import (
    HELP_FOR_FORMATS,
    CsvLikeFormats,
    CsvParseError,
    _get_csv_reader_for_format,
)

ENCODING = "utf-8-sig"


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

    # HEADER policy consumes first line for framecode/loop_category, so skip it when reading CSV data
    if frame_policy == FrameNamePolicy.HEADER:
        skip += 1

    # Look up frames and build FrameLoopPath objects
    frame_loop_paths = []
    _build_frames_loops_and_paths_or_exit_error(
        entry, frame_loop_paths, framecode_loop_category_paths
    )

    try:
        result = pipe(entry, frame_loop_paths, csv_format, skip, comment)
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
) -> PipeOutput:
    """Add loops read from CSV files to existing saveframes in entry.

    Args:
        entry: NEF entry containing the target saveframes
        frame_loop_paths: List of pre-looked-up frames with loop categories and CSV paths
        csv_format: Format of CSV files (CSV, TSV, SSV, or AUTO)
        skip: Number of extra header rows to skip after column headers
        comment: Prefix for comment lines to ignore

    Returns:
        PipeOutput with modified entry and warnings about normalized headers
    """

    all_warnings = []

    for frame_loop_path in frame_loop_paths:
        tags, data_rows, warnings = _read_csv(
            frame_loop_path.path, csv_format, skip, comment
        )
        all_warnings.extend(warnings)

        nef_loop = Loop.from_scratch()
        nef_loop.set_category(frame_loop_path.loop_category)
        nef_loop.add_tag(tags)

        row_dicts = [dict(zip(tags, row)) for row in data_rows]
        nef_loop.add_data(row_dicts)

        frame_loop_path.frame.add_loop(nef_loop)

    return PipeOutput(entry=entry, warnings=all_warnings)


@functools.lru_cache(maxsize=128)
def _read_raw_csv_file(path: Path) -> str:
    """Read a CSV file from disk; result is cached for the process lifetime."""
    return path.read_text(encoding=ENCODING)


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


def _read_csv(
    csv_file: Path, csv_format: CsvLikeFormats, skip: int = 0, comment: str = ""
) -> Tuple[List[str], List[List[str]], List[str]]:
    """Read a CSV file and return (tags, data_rows, warnings).

    The file is cached after the first read so repeated calls for the same path
    within one pipeline step incur only one disk read.

    Returns:
        Tuple of (tags, data_rows, warnings) where warnings is a list of warning strings

    Raises:
        CsvParseError: If CSV file is empty
    """
    encoding_kwargs = {"encoding": ENCODING}
    raw_text = _read_raw_csv_file(csv_file.resolve())
    filtered_text = _apply_skip_and_comment(raw_text, skip=skip, comment=comment)

    csv_fp = io.StringIO(filtered_text)
    reader = _get_csv_reader_for_format(csv_format, csv_fp, encoding_kwargs)
    rows = list(reader)

    if not rows:
        raise CsvParseError(f"the CSV file {csv_file} is empty")

    header_row = rows[0]
    data_start = 1

    # Track headers that get normalized (spaces replaced with underscores)
    warnings = []
    tags = []
    normalized_headers = []
    for header in header_row:
        stripped = header.strip()
        normalized = escape_spaces_with_underscore(stripped)
        tags.append(normalized)
        if stripped != normalized:
            normalized_headers.append(f"{stripped!r} -> {normalized!r}")

    if normalized_headers:
        msg = f"normalized headers with spaces in {csv_file}:\n  " + "\n  ".join(
            normalized_headers
        )
        warnings.append(msg)

    data_rows = [[cell.strip() for cell in row] for row in rows[data_start:]]

    return tags, data_rows, warnings


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
    """Parse HEADER policy: first line of each CSV which isn't skipped or commented contains framecode,loop_category."""
    result = []
    for path_str in file_args:
        path = Path(path_str)
        encoding_kwargs = {"encoding": ENCODING}
        raw_text = path.read_text(encoding=ENCODING)
        filtered_text = _apply_skip_and_comment(raw_text, skip=0, comment=comment)

        csv_fp = io.StringIO(filtered_text)
        with csv_fp:
            reader = _get_csv_reader_for_format(csv_format, csv_fp, encoding_kwargs)
            first_row = next(reader, None)

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
