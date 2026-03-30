import re
import sys
from itertools import zip_longest
from pathlib import Path
from typing import List

import typer
from fyeah import f
from pynmrstar import Entry

from nef_pipelines import nef_app
from nef_pipelines.lib.util import (
    STDIN,
    STDOUT,
    exit_error,
    parse_comma_separated_options,
    read_from_file_or_exit,
)

FILE_PATHS_HELP = """write the entries to files named, these maybe comma separated
                    or multiple calls to the option maybe made. If a single directory is provided,
                    the entries will be saved in the directory with the entry name from the template
                    if stdout [-] is provided, the entries will be printed to stdout with delimiter
                    the default is write entries to the current directory again with the entry name
                    from the template"""

if nef_app:
    # noinspection PyUnusedLocal
    @nef_app.app.command(rich_help_panel="NEF manipulation")
    def save(
        input: Path = typer.Option(
            STDIN,
            "-i",
            "--in",
            metavar="NEF-FILE-STREAM",
            help="read NEF data stream from a file instead of stdin",
        ),
        template: str = typer.Option(
            "{entry_id}.nef",
            help="the new name for the entry",
        ),
        force: bool = typer.Option(
            False, "-f", "--force", help="overwrite existing files"
        ),
        single_file: bool = typer.Option(
            False, help="write all entries to a single file"
        ),
        no_globals_cleanup: bool = typer.Option(
            False, "--no-globals-cleanup", help="do not remove the globals frame"
        ),
        no_header: bool = typer.Option(False, help="do not write a header"),
        file_paths: List[str] = typer.Argument(None, help=FILE_PATHS_HELP),
    ):
        """- save the entries in the stream to a file / files or stdout with delimiters"""

        # this is a gratuitous hack Typer doesn't seem to allow an argument to be - so we have to check
        # TODO: report this!
        if not file_paths:
            if sys.argv[-1] == "-":
                file_paths = ["-"]
            else:
                file_paths = [
                    Path.cwd(),
                ]

        file_paths = parse_comma_separated_options(file_paths)

        if file_paths == [
            str(STDIN),
        ]:
            file_paths = [
                STDIN,
            ]
        else:
            file_paths = [Path(file_path).resolve() for file_path in file_paths]

        entries = list(_entry_list_from_stdin_or_exit_error_if_none(input))

        if not no_globals_cleanup:
            for entry in entries:
                for save_frame in entry.get_saveframes_by_category("nefpls_globals"):
                    entry.remove_saveframe(save_frame)

        entries = pipe(entries, file_paths, template, no_header, single_file, force)

        if entries:
            for entry in entries:
                print(entry)


def pipe(
    entries: List[Entry],
    file_paths: List[Path],
    template: str,
    no_header: bool,
    single_file: bool,
    force: bool,
):

    _exit_if_no_file_paths(file_paths)

    _exit_if_no_entries(entries)

    _exit_if_single_file_and_out_is_directory(file_paths, single_file)

    _exit_if_single_file_and_out_is_multiple_files(file_paths, single_file)

    # are we writing to STDOUT?
    write_stdout = file_paths == [
        STDOUT,
    ]

    DELIMITER = "-" * 50  # noqa: F841
    HEADER = "{DELIMITER} {entry_id} {DELIMITER}"

    # do we need to write a header?
    write_header = False
    write_header = not no_header and (
        file_paths
        == [
            STDOUT,
        ]
        or single_file
    )

    # every file is written to stdout if we write to STDOUT
    if write_stdout:
        single_file = True

    # make file paths from directory and entry_id id we are writing to a directory
    if len(file_paths) == 1 and file_paths[0].is_dir():
        directory = file_paths[0]
        file_paths = []
        for entry in entries:
            entry_id = entry.entry_id
            file_name = f(template)
            file_paths.append(directory / file_name)

    # deal with what append mode to use
    if single_file:
        append_modes = [
            True,
        ] * len(entries)
        append_modes[0] = False
    else:
        append_modes = [
            False,
        ] * len(entries)

    if single_file:
        file_paths = file_paths * len(entries)

    for i, (entry, file_path, append_mode) in enumerate(
        zip_longest(entries, file_paths, append_modes, fillvalue=None)
    ):

        _exit_if_we_ran_out_of_entries(entry, file_path)

        _exit_if_we_ran_out_of_file_paths(entry, file_path)

        _exit_if_file_exists_and_no_append_or_force(file_path, append_mode, force)

        file_h = (
            sys.stdout
            if file_path == STDOUT
            else open(file_path, "a" if append_mode else "w")
        )

        if len(entries) > 1 and write_header:
            entry_id = entry.entry_id  # noqa: F841
            header_text = f(HEADER)
            print(header_text, file=file_h)
        else:
            header_text = None

        print(entry, file=file_h)

        if not file_h == sys.stdout:
            file_h.close()

    if write_header and header_text:
        file_h = (
            sys.stdout
            if file_path == STDOUT
            else open(file_path, "a" if append_mode else "w")
        )
        if len(entries) > 1:
            print("-" * len(header_text), file=file_h)

        if not write_stdout:
            file_h.close()

    return None if write_stdout else entries


def _exit_if_file_exists_and_no_append_or_force(file_path, append_mode, force):

    if file_path != STDOUT and file_path.exists() and not (force or append_mode):
        msg = f"""
            when trying to write the file {file_path} it already exists,
            if you want to overwrite it use the force option
        """

        exit_error(msg)


def _exit_if_we_ran_out_of_file_paths(entry, file_path):
    if not file_path:
        msg = f"""
            Number of entries does not match number of file paths, at entry
            {entry.entry_id} i ran out of file paths to write to
        """

        exit_error(msg)


def _exit_if_we_ran_out_of_entries(entry, file_path):
    if not entry:
        msg = f"""
            Number of entries does not match number of file paths, at file name
            {file_path} i ran out of entries to write
        """

        exit_error(msg)


# TODO: when we start using ustar we can replace much of this!
def _entry_list_from_stdin_or_exit_error_if_none(file_name):

    file_path = Path(file_name)

    try:
        text = read_from_file_or_exit(file_path)
    except Exception as e:
        msg = f"""
            Failed to read input file {file_path} because: {e}
        """
        exit_error(msg, e)

    # Split entries by finding data_ blocks, preserving original text format
    # This avoids the tokenization/reconstruction issue that corrupts multi-line strings
    entry_strings = []

    # Find all data_ block starts
    # Match data_ at the beginning of a line with optional leading whitespace
    data_pattern = re.compile(r"^\s*data_", re.MULTILINE)

    # Find all positions where data_ blocks start
    matches = list(data_pattern.finditer(text))

    if not matches:
        # No data blocks found, try to parse as single entry
        if text.strip():
            msg = f"""
                No data_ blocks found in input from {file_path}.
                Input length: {len(text)} bytes
                Input preview: {text[:500]}...
            """
            exit_error(msg)
        else:
            msg = f"""
                Input from {file_path} is empty or contains only whitespace.
                Cannot save empty NEF data.
            """
            exit_error(msg)

    # Extract each entry as original text
    for i, match in enumerate(matches):
        start = match.start()
        # End is the start of the next data_ block, or end of file
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        entry_string = text[start:end].strip()
        if entry_string:
            entry_strings.append(entry_string)

    # Parse entries with better error handling
    entries = []
    for i, entry_string in enumerate(entry_strings, 1):
        try:
            entries.append(Entry.from_string(entry_string))
        except Exception as e:
            msg = f"""
                Failed to parse entry {i} from {file_path} because: {e}
                Entry preview: {entry_string[:500]}...
            """
            exit_error(msg, e)

    return entries


def _exit_if_single_file_and_out_is_multiple_files(file_paths, single_file):
    if single_file and len(file_paths) > 1:
        file_paths_string = "\n".join([str(file_path) for file_path in file_paths])
        msg = f"""
            the single file option is incompatible with multiple file paths, there were {len(file_paths)} file paths
            the paths were
            {file_paths_string}
        """
        exit_error(msg)


def _exit_if_single_file_and_out_is_directory(file_paths, single_file):
    if single_file and file_paths[0].is_dir():
        msg = f"""
            ouput to a single file option is incompatible with specifiying a directory as the file path
            the file path you provided was {file_paths[0]}
        """
        exit_error(msg)


def _exit_if_no_file_paths(file_paths):
    if not file_paths:
        msg = "you must provide at least one file_path to write to"
        exit_error(msg)


def _exit_if_no_entries(entries):
    if not entries:
        msg = "you must provide at least one entry to write, did you input a NEF file stream?"
        exit_error(msg)
