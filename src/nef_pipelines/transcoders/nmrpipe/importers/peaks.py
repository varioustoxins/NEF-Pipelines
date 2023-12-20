from pathlib import Path
from textwrap import dedent
from typing import List

import typer

from nef_pipelines.lib.typer_utils import get_args
from nef_pipelines.lib.util import exit_error, process_stream_and_add_frames
from nef_pipelines.transcoders.nmrpipe import import_app

from ...nmrview.importers.peaks import create_spectrum_frame
from ..nmrpipe_lib import (
    NMRPIPE_PEAK_EXPECTED_FIELDS,
    check_is_peak_file,
    get_gdb_columns,
    read_db_file_records,
    read_peak_file,
)

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
    entry_name: str = typer.Option("nmrpipe", help="a name for the entry"),
    chain_code: str = typer.Option(
        "A", "--chain", help="chain code", metavar="<chain-code>"
    ),
    axis_codes: str = typer.Option(
        "1H.15N", metavar="<axis-codes>", help="a list of axis codes joined by dots"
    ),
    filter_noise: bool = typer.Option(True, help="remove peaks labelled as noise"),
    file_names: List[Path] = typer.Argument(
        ..., help="input peak files", metavar="<peak-file.xpk>"
    ),
):
    """convert nmrpipe peak file <nmrview>.xpk files to NEF"""

    args = get_args()

    peak_lists = _read_nmrpipe_peaks(args)

    frames = []
    for i, peak_list in enumerate(peak_lists, start=1):

        frame_name = entry_name if len(peak_lists) == 1 else f"{entry_name}_{i}"

        frames.append(create_spectrum_frame(args, frame_name, peak_list))

    entry = process_stream_and_add_frames(frames, args)

    print(entry)


def _read_nmrpipe_peaks(args):
    results = []
    for file_name in args.file_names:
        with open(file_name) as file_h:
            gdb_file = read_db_file_records(file_h, file_name=file_name)

        _check_is_peak_file_or_exit(gdb_file)

        results.append(read_peak_file(gdb_file, args))

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
