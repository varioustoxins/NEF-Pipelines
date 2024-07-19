import itertools
import re
import string
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import List

import typer
from fyeah import f
from pynmrstar import Entry

from nef_pipelines.lib.isotope_lib import CODE_TO_ISOTOPE, GAMMA_RATIOS
from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.util import (
    NEWLINE,
    STDIN,
    exit_error,
    is_float,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.deep import import_app
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import (
    get_gdb_columns,
    read_db_file_records,
    read_peak_file,
    select_data_records,
)
from nef_pipelines.transcoders.nmrview.importers.peaks import _create_spectrum_frame

DEEP_PEAK_EXPECTED_FIELDS = (
    "INDEX X_AXIS X_PPM  XW X1 X3  HEIGHT ASS CONFIDENCE POINTER".split()
)

app = typer.Typer()

# TODO should check peaks against sequence


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
    chain_codes: str = typer.Option(
        "A", "--chain", help="chain code", metavar="<chain-code>"
    ),
    # filter_noise: bool = typer.Option(True, help="remove peaks labelled as noise"),
    in_file: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    spectrometer_frequencies: List[float] = typer.Option(
        ..., "--spectrometer-frequency", help="the 1H frequencies of the spectrometers"
    ),
    entry_name: str = typer.Option(
        "nmrpipe", "-e", "--entry", help="entry name", metavar="<entry-name>"
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input peak files", metavar="<peak-file.xpk>"
    ),
):
    """convert deep peak file <DEEP>.tab files to NEF [alpha]"""

    number_files = len(file_names)
    if not chain_codes:
        chain_codes = ["A"] * number_files

    if len(chain_codes) == 1:
        chain_codes = chain_codes * number_files

    spectrometer_frequencies = parse_comma_separated_options(spectrometer_frequencies)

    number_spectrometer_frequencies = len(spectrometer_frequencies)
    if (
        number_spectrometer_frequencies > 1
        and number_files != number_spectrometer_frequencies
    ):
        _exit_lenghts_spectrometer_frequencies_and_files_dont_match(
            file_names, spectrometer_frequencies
        )
    elif number_spectrometer_frequencies == 1 and number_files > 1:
        spectrometer_frequencies = spectrometer_frequencies * number_files

    chain_codes = parse_comma_separated_options(chain_codes)

    _exit_if_num_chains_and_files_dont_match(chain_codes, file_names)

    entry = read_or_create_entry_exit_error_on_bad_file(in_file, entry_name=entry_name)

    entry = pipe(entry, file_names, chain_codes, spectrometer_frequencies)

    print(entry)


def pipe(
    entry: Entry,
    file_names: List[Path],
    chain_codes: List[str],
    spectrometer_frequencies: List[float],
) -> Entry:

    gdb_files = _read_gdb_files(file_names)
    peak_list_map = _read_deep_peaks(gdb_files, chain_codes)

    deep_sweep_widths_map, deep_isotopes_map = _read_deep_sweep_widths_and_isotopes(
        gdb_files
    )

    frame_name_template = "{file_name}"

    for i, (path, peak_list) in enumerate(peak_list_map.items()):

        if peak_list.peak_list_data.sweep_widths is None:
            new_peak_list_data = replace(peak_list.peak_list_data, sweep_widths=[])
            peak_list = replace(peak_list, peak_list_data=new_peak_list_data)
            peak_list_map[path] = peak_list

        deep_sweep_widths = deep_sweep_widths_map[path]
        for axis_label in peak_list.peak_list_data.axis_labels:
            peak_list.peak_list_data.sweep_widths.append(deep_sweep_widths[axis_label])

        deep_isotopes = deep_isotopes_map[path]
        for axis_label in peak_list.peak_list_data.axis_labels:
            axis_isotope = deep_isotopes[axis_label]
            isotope = CODE_TO_ISOTOPE[axis_isotope]
            gamma_ratio = GAMMA_RATIOS[isotope]
            peak_list_map[path].peak_list_data.spectrometer_frequencies.append(
                spectrometer_frequencies[i] * gamma_ratio
            )

    frame_names = _create_entry_names_from_template_if_required(
        frame_name_template, [], file_names
    )

    frames = []
    for i, (peak_list, frame_name, chain_code) in enumerate(
        zip(peak_list_map.values(), frame_names, chain_codes), start=1
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


def _read_gdb_files(file_names):
    results = []
    for file_name in file_names:
        with open(file_name) as file_h:
            gdb_file = read_db_file_records(file_h, file_name=file_name)

        _check_is_peak_file_or_exit(gdb_file)

        results.append(gdb_file)

    return results


def _read_deep_peaks(gdb_files, chain_codes):
    results = {}
    for gdb_file, chain_code in zip(gdb_files, chain_codes):

        results[gdb_file.name] = read_peak_file(gdb_file, chain_code)

    return results


def _check_is_peak_file_or_exit(gdb_file):
    columns = set(get_gdb_columns(gdb_file))
    data_records = select_data_records(gdb_file, "*_AXIS")
    data_record_names = [data_record.values[0] for data_record in data_records]

    if not _check_is_deep_file(gdb_file):
        if set(DEEP_PEAK_EXPECTED_FIELDS) != set(columns):
            msg = f"""\
                    this gdb file doesn't appear to contain all the columns expected for an deep peak file
                    expected: {','.join(DEEP_PEAK_EXPECTED_FIELDS)}
                    got {','.join(columns & set(DEEP_PEAK_EXPECTED_FIELDS))}
                    file name: {gdb_file.name}
                    """
            exit_error(msg)
        else:
            msg = f"""\
                    this gdb file doesn't appear to contain all the columns expected for an deep peak file
                    I expected DATA records begining X_AXIS, Y_AXIS etc
                    got {', '.join(data_record_names)}
                    file_name {gdb_file.name}
                   """
            exit_error(msg)


def _check_is_deep_file(gdb_file):

    columns = set(get_gdb_columns(gdb_file))
    expected_fields = set(DEEP_PEAK_EXPECTED_FIELDS)

    data_records = select_data_records(gdb_file, "*_AXIS")
    return expected_fields.issubset(columns) and data_records


def _report_bad_sweep_width_line(data_record, message):
    line_info = data_record.line_info
    msg = f"""
                        Couldn't read axis DATA records of the form
                        DATA *_AXIS  <isotope> <left-point> <right-point> <left-ppm> <right-ppm> such as

                        DATA  X_AXIS 1H           1   779   11.303ppm    5.149ppm

                        because {message}
                        at line {line_info.line_no} in {line_info.file_name}

                        the line was

                        {line_info.line}
                    """
    exit_error(msg)


def _position_to_ppm(position):
    result = None
    if position.endswith("ppm"):
        position = position[: -len("ppm")]
        if is_float(position):
            result = float(position)

    return result


def _parse_axis(axis):

    result = None

    axis = axis.split("_")
    if len(axis) == 2:
        result = axis[0]

    return result


def _read_deep_sweep_widths_and_isotopes(gdb_files):
    sweep_widths_result = {}
    isotopes_result = {}

    for gdb_file in gdb_files:
        data_records = select_data_records(gdb_file, "*_AXIS")
        for data_record in data_records:
            try:
                values = data_record.values
                axis, isotope, _, _, raw_right_ppm, raw_left_ppm = values
            except Exception:
                msg = f"wrong number of records (got {len(values)} expected 6)"
                _report_bad_sweep_width_line(data_record, msg)

            axis = _parse_axis(axis)

            if not axis:
                msg = f"can't parse axis field ({axis}) should be of the form *_AXIS where * is one of X,Y,Z,A"
                _report_bad_sweep_width_line(data_record, msg)

            left_ppm = _position_to_ppm(raw_left_ppm)
            right_ppm = _position_to_ppm(raw_right_ppm)

            if not left_ppm:
                _report_bad_sweep_width_line(
                    data_record, f" left ppm position ({raw_left_ppm}) is bad"
                )
            if not right_ppm:
                _report_bad_sweep_width_line(
                    data_record, f" right ppm position ({raw_right_ppm}) is bad"
                )

            sweep_width = right_ppm - left_ppm
            sweep_widths_result.setdefault(gdb_file.name, {})[axis] = sweep_width

            isotopes_result.setdefault(gdb_file.name, {})[axis] = isotope

    return sweep_widths_result, isotopes_result


def _exit_lenghts_spectrometer_frequencies_and_files_dont_match(
    file_names, spectrometer_frequencies
):
    pass
