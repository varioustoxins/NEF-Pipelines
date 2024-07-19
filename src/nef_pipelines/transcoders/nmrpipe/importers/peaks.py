import itertools
import re
import string
from collections import Counter
from pathlib import Path
from textwrap import dedent
from typing import List

import typer
from fyeah import f
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.util import (
    NEWLINE,
    STDIN,
    exit_error,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.nmrpipe import import_app

from ...nmrview.importers.peaks import _create_spectrum_frame
from ..nmrpipe_lib import (
    NMRPIPE_PEAK_EXPECTED_FIELDS,
    check_is_peak_file,
    get_gdb_columns,
    read_db_file_records,
    read_peak_file,
)

app = typer.Typer()

# TODO should check peaks against sequence


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
    chain_codes: str = typer.Option(
        "A", "--chain", help="chain code", metavar="<chain-code>"
    ),
    filter_noise: bool = typer.Option(True, help="remove peaks labelled as noise"),
    in_file: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    entry_name: str = typer.Option(
        "nmrpipe", "-e", "--entry", help="entry name", metavar="<entry-name>"
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input peak files", metavar="<peak-file.xpk>"
    ),
):
    """convert nmrpipe peak file <NMRPIPE>.tab files to NEF"""

    if not chain_codes:
        chain_codes = ["A"] * len(file_names)

    if len(chain_codes) == 1:
        chain_codes = chain_codes * len(file_names)

    chain_codes = parse_comma_separated_options(chain_codes)

    _exit_if_num_chains_and_files_dont_match(chain_codes, file_names)

    entry = read_or_create_entry_exit_error_on_bad_file(in_file, entry_name=entry_name)

    entry = pipe(entry, file_names, chain_codes, filter_noise)

    print(entry)


def pipe(
    entry: Entry, file_names: List[Path], chain_codes: List[str], filter_noise: bool
) -> Entry:

    peak_lists = _read_nmrpipe_peaks(file_names, chain_codes, filter_noise=filter_noise)

    frame_name_template = "{file_name}"

    frame_names = _create_entry_names_from_template_if_required(
        frame_name_template, [], file_names
    )

    frames = []
    for i, (peak_list, frame_name, chain_code) in enumerate(
        zip(peak_lists, frame_names, chain_codes), start=1
    ):

        frames.append(_create_spectrum_frame(frame_name, peak_list, chain_code))

    # TODO when adding frames they need to be disambiguated if there are name clashes
    return add_frames_to_entry(entry, frames)


# TODO move much of this to utilities
def _exit_if_num_chains_and_files_dont_match(chain_codes, file_names):
    if len(chain_codes) != len(file_names):
        msg = f"""
            the number of chain codes {len(chain_codes)} does not match number of files {len(file_names)}
            the chain codes are {', '.join(chain_codes)}
            the files are
            {NEWLINE.join(file_names)}
        """
        exit_error(msg)


def _disambiguate_names(names):
    name_count = Counter()
    result = []
    for name in names:
        if name in name_count:
            result.append(f"{name}_{name_count[name]}")
        else:
            result.append(name)
        name_count[name] += 1
    return result


def _remove_repeated_underscores(s):
    return re.sub("_+", "_", s)


def _create_entry_names_from_template_if_required(
    entry_name_template, entry_names, file_names
):
    new_entry_names = []
    for file_name, entry_name in itertools.zip_longest(file_names, entry_names):
        if entry_name:
            new_entry_names.append(entry_name)
        else:
            file_name = str(Path(file_name).stem)
            numbers_and_letters = string.ascii_lowercase + string.digits
            file_name = "".join(  # noqa: F841
                [
                    letter if letter in numbers_and_letters else "_"
                    for letter in file_name
                ]
            )

            new_name = f(entry_name_template)

            new_name = _remove_repeated_underscores(new_name)

            new_entry_names.append(new_name)

    return _disambiguate_names(new_entry_names)


def _read_nmrpipe_peaks(file_names, chain_codes, filter_noise):
    results = []
    for file_name, chain_code in zip(file_names, chain_codes):
        with open(file_name) as file_h:
            gdb_file = read_db_file_records(file_h, file_name=file_name)

        _check_is_peak_file_or_exit(gdb_file)

        results.append(read_peak_file(gdb_file, chain_code, filter_noise=filter_noise))

    return results


def _check_is_peak_file_or_exit(gdb_file):
    columns = set(get_gdb_columns(gdb_file))

    if not check_is_peak_file(gdb_file):
        msg = f"""\
                this gdb file doesn't appear to contain all the columns expected for a peak file
                expected: {','.join(NMRPIPE_PEAK_EXPECTED_FIELDS)}
                got {','.join(columns & NMRPIPE_PEAK_EXPECTED_FIELDS)}
                file: {gdb_file.file_name}
                """
        msg = dedent(msg)
        exit_error(msg)
