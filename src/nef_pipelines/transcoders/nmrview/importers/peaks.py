# TODO: xplor names -> iupac and deal with %% and ## properly
# TODO: add common experiment types
# TODO: add a chemical shift list reference
# TODO: _nef_nmr_spectrum: value_first_point, folding, absolute_peak_positions, is_acquisition
# TODO: cleanup
# TODO: multiple assignments per peak... howto in nef
# TODO: add libs pipeline

import itertools
import string
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple

import typer
from fyeah import f
from pynmrstar import Entry, Loop, Saveframe

from nef_pipelines.lib import constants
from nef_pipelines.lib.constants import NEF_UNKNOWN
from nef_pipelines.lib.isotope_lib import GAMMA_RATIOS
from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    get_residue_name_from_lookup,
    sequence_from_entry_or_exit,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    PeakAxis,
    PeakList,
    PeakListData,
    PeakValues,
    Residue,
    SequenceResidue,
)
from nef_pipelines.lib.util import (
    NEWLINE,
    STDIN,
    exit_error,
    is_float,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.nmrview import import_app

from ..nmrview_lib import parse_float_list, parse_tcl

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
    in_file: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    chain_codes: List[str] = typer.Option(
        None, "--chain", help="chain code", metavar="<chain-code>"
    ),
    # TODO: add don't filter deleted?
    # TODO: add a flag to remove checking residue types
    file_names: List[Path] = typer.Argument(
        ..., help="input peak files", metavar="<peak-file.xpk>"
    ),
):
    """convert nmrview peak file <nmrview>.xpk files to NEF"""

    if not chain_codes:
        chain_codes = ["A"] * len(file_names)

    if len(chain_codes) == 1:
        chain_codes = chain_codes * len(file_names)

    chain_codes = parse_comma_separated_options(chain_codes)

    entry = read_entry_from_file_or_stdin_or_exit_error(in_file)

    sequence = sequence_from_entry_or_exit(entry)

    _exit_if_num_chains_and_files_dont_match(chain_codes, file_names)

    entry = pipe(entry, file_names, chain_codes, sequence)

    print(entry)


def pipe(
    entry: Entry, file_names: List[str], chain_codes: List[str], sequence: List[Residue]
) -> Entry:

    frames = []
    sequence_lookup = _sequence_to_residue_type_lookup(sequence)

    frame_names_and_peak_lists = []
    for file_name, chain_code in zip(file_names, chain_codes):
        with open(file_name, "r") as lines:
            peaks_list = read_raw_peaks(lines, chain_code, sequence_lookup)

        frame_name = _make_peak_list_frame_name(peaks_list)

        frame_names_and_peak_lists.append((frame_name, peaks_list))

    frame_names_and_peak_lists = _disambiguate_frame_names(frame_names_and_peak_lists)

    for (frame_name, peaks_list), chain_code in zip(
        frame_names_and_peak_lists, chain_codes
    ):
        frames.append(create_spectrum_frame(frame_name, peaks_list, chain_code))

    return add_frames_to_entry(entry, frames)


def _disambiguate_frame_names(peak_lists_and_entry_names):
    seen_frames = Counter()
    for i, (frame_name, peaks_list) in enumerate(peak_lists_and_entry_names):
        if frame_name in seen_frames:
            seen_frames[frame_name] += 1
            frame_name = f"{frame_name}`{seen_frames[frame_name]}`"
            peak_lists_and_entry_names[i] = (frame_name, peaks_list)
        else:
            seen_frames[frame_name] = 1
    return peak_lists_and_entry_names


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
            file_name = "".join(
                [
                    letter if letter in numbers_and_letters else "_"
                    for letter in file_name
                ]
            )
            file_name = f"_{file_name}"
            new_entry_names.append(f(entry_name_template))
    return new_entry_names


def read_raw_peaks(lines, chain_code, sequence_lookup):

    header = get_header_or_exit(lines)

    header_data = read_header_data(lines, header)

    column_indices = read_peak_columns(lines, header_data)

    raw_peaks = read_peak_data(
        lines, header_data, column_indices, chain_code, sequence_lookup
    )

    return PeakList(header_data, raw_peaks)


def read_peak_data(lines, header_data, column_indices, chain_code, sequence_lookup):
    raw_peaks = []
    field = None
    axis_index = None
    for line_no, raw_line in enumerate(lines):
        if not len(raw_line.strip()):
            continue
        try:
            peak = {}
            line = parse_tcl(raw_line)
            # TODO validate and report errors
            peak_index = int(line[0])

            for axis_index, axis in enumerate(header_data.axis_labels):
                axis_values = read_axis_for_peak(
                    line, axis, column_indices, chain_code, sequence_lookup
                )

                peak[axis_index] = PeakAxis(*axis_values)

            raw_values = read_values_for_peak(line, column_indices)
            peak["values"] = PeakValues(peak_index, **raw_values)

            raw_peaks.append(peak)

        except Exception as e:
            field = str(field) if field else "unknown"
            msg = (
                f"failed to parse the line {line_no} with input: '{raw_line.strip()}' field: {field}  axis: "
                f"  {axis_index + 1} exception: {e}"
            )
            exit_error(msg)
    return raw_peaks


def _exit_if_num_chains_and_files_dont_match(chain_codes, file_names):
    if len(chain_codes) != len(file_names):
        msg = f"""
            the number of chain codes {len(chain_codes)} does not match number of files {len(file_names)}
            the chain codes are {', '.join(chain_codes)}
            the files are
            {NEWLINE.join(file_names)}
        """
        exit_error(msg)


def read_peak_columns(lines, header_data):
    line = next(lines)
    raw_headings = line.split()
    heading_indices = OrderedDict({"index": 0})
    for axis_index, axis in enumerate(header_data.axis_labels):
        for axis_field in list("LPWBEJU"):
            header = f"{axis}.{axis_field}"
            if header in raw_headings:
                heading_indices[header] = raw_headings.index(header) + 1
    for peak_item in ["vol", "int", "stat", "comment", "flag0"]:
        if peak_item in raw_headings:
            heading_indices[peak_item] = raw_headings.index(peak_item) + 1
    return heading_indices


def read_header_data(lines, headers):
    data_set = None
    sweep_widths = []
    spectrometer_frequencies = []
    num_axis = None
    axis_labels = None
    for header_no, header_type in enumerate(headers):
        line = next(lines)
        if header_type == "label":
            axis_labels = line.strip().split()
            num_axis = len(axis_labels)
        elif header_type == "dataset":
            data_set = line.strip()
        elif header_type == "sw":
            line_no = header_no + 2
            sweep_widths = parse_float_list(line, line_no)
            check_num_fields(sweep_widths, num_axis, "sweep widths", line, line_no)
        elif header_type == "sf":
            line_no = header_no + 2
            spectrometer_frequencies = parse_float_list(line, line_no)
            check_num_fields(
                spectrometer_frequencies,
                num_axis,
                "spectrometer frequencies",
                line,
                line_no,
            )

    # sweep widths are in ppm for nef!
    sweep_widths = [float(sweep_width) for sweep_width in sweep_widths]
    spectrometer_frequencies = [
        float(spectrometer_frequency)
        for spectrometer_frequency in spectrometer_frequencies
    ]

    for i, (sweep_width, spectrometer_frequency) in enumerate(
        zip(sweep_widths, spectrometer_frequencies)
    ):
        sweep_widths[i] = f"{sweep_width / spectrometer_frequency:.4f}"

    # TODO: peaks shifts, spectrometer frequencies how many decimal points
    spectrometer_frequencies = [
        f"{spectrometer_frequency:4}"
        for spectrometer_frequency in spectrometer_frequencies
    ]

    peak_list_data = PeakListData(
        num_axis, axis_labels, data_set, sweep_widths, spectrometer_frequencies
    )
    return peak_list_data


def get_header_or_exit(lines):
    header_items = ["label", "dataset", "sw", "sf"]

    line = next(lines)

    headers = []
    if line:
        headers = line.strip().split()

    if len(headers) != 4:
        msg = f"""this doesn't look like an nmrview xpk file,
                  i expected a header containing 4 items on the first line: {','.join(header_items)}
                  i got {line} at line 1"""
        exit_error(msg)

    for name in header_items:
        if name not in headers:
            msg = f"""this doesn't look like an nmrview xpk file,
                       i expected a header containing the values: {', '.join(header_items)}
                       i got '{line}' at line 1"""
            exit_error(msg)

    return headers


def read_axis_for_peak(line, axis, heading_indices, chain_code, sequence_lookup):
    axis_values = []
    for axis_field in list("LPWBEJU"):
        header = f"{axis}.{axis_field}"
        field_index = heading_indices[header]
        value = line[field_index]

        if axis_field == "L":
            label = value[0] if value else "?"
            if label == "?":
                residue_number = None
                atom_name = ""
            else:
                residue_name_residue_number, atom_name = label.split(".")
                residue_number = residue_name_residue_number.lstrip(
                    string.ascii_letters
                )
                if residue_number == "?":
                    residue_number = None
                residue_number = int(residue_number)

            if residue_number:
                residue_type = get_residue_name_from_lookup(
                    chain_code, residue_number, sequence_lookup
                )
            else:
                residue_type = NEF_UNKNOWN

            if residue_type is None:
                exit_error(
                    f"residue type not defined for chain: {chain_code} and residue number: {residue_number}"
                )

            if residue_number:
                atom = AtomLabel(
                    SequenceResidue(chain_code, residue_number, residue_type),
                    atom_name.upper(),
                )
            else:
                atom = AtomLabel(SequenceResidue("", None, ""), atom_name.upper())
            axis_values.append(atom)

        elif axis_field == "P":
            if not is_float(value):
                msg = f"""
                    in file
                    expected a float for the peak position got {value} i
                """
                exit_error(msg)
            shift = float(value)
            axis_values.append(shift)
        elif axis_field in "WJU":
            pass
        elif axis_field == "E":
            merit = value
            axis_values.append(merit)
    return axis_values


def read_values_for_peak(line, heading_indices):
    peak_values = {}
    for value_field in ["vol", "int", "stat", "comment", "flag0"]:
        field_index = heading_indices[value_field]
        value = line[field_index]

        if value_field == "vol":
            peak_values["volume"] = float(value)
        elif value_field == "int":
            peak_values["height"] = float(value)
        elif value_field == "stat":
            peak_values["deleted"] = int(value) < 0
        elif value_field == "comment":
            comment = value[0].strip("'") if value else ""
            peak_values["comment"] = comment
        elif value_field == "flag0":
            pass

    return peak_values


def check_num_fields(fields, number, field_type, line, line_no):
    if len(fields) != number:
        msg = f"Expected {number} {field_type} got {len(fields)} for line: {line} at line {line_no}"
        exit_error(msg)


def _sequence_to_residue_type_lookup(
    sequence: List[SequenceResidue],
) -> Dict[Tuple[str, int], str]:
    result: Dict[Tuple[str, int], str] = {}
    for residue in sequence:
        result[residue.chain_code, residue.sequence_code] = residue.residue_name
    return result


def _get_isotope_code_or_exit(axis, axis_codes):
    if axis >= len(axis_codes):
        msg = f"can't find isotope code for axis {axis + 1} got axis codes {','.join(axis_codes)}"
        exit_error(msg)
    axis_code = axis_codes[axis]
    return axis_code


def round_to_nearest_and_distance(number, nearest):
    rounded = round(number / nearest) * nearest
    return rounded, abs(rounded - number)


def _guess_spectrometer_frequency(peak_list):
    frequencies = [
        float(frequency)
        for frequency in peak_list.peak_list_data.spectrometer_frequencies
    ]
    max_frequency = max(frequencies)

    divisor = 10 if max_frequency < 240 else 50

    distance_and_frequency = {}
    for spectrometer_frequency in frequencies:
        rounded_spectrometer_frequency, distance = round_to_nearest_and_distance(
            spectrometer_frequency, divisor
        )
        distance_and_frequency[distance] = spectrometer_frequency

    min_distance = min(distance_and_frequency.keys())
    return distance_and_frequency[min_distance]


def _spectrometer_frequencies_to_axis_codes(spectrometer_frequency, peak_list):
    isotopes = []
    for frequency in peak_list.peak_list_data.spectrometer_frequencies:
        frequency = float(frequency)
        ratio = frequency / spectrometer_frequency
        ratio_distances = {
            isotope: abs(ratio - gamma_ratio)
            for isotope, gamma_ratio in GAMMA_RATIOS.items()
        }
        closest_isotope = min(ratio_distances, key=ratio_distances.get)
        isotopes.append(closest_isotope)

    return isotopes


def create_spectrum_frame(entry_name, peak_list, chain_code):

    spectrometer_frequency = _guess_spectrometer_frequency(peak_list)
    axis_isotopes = _spectrometer_frequencies_to_axis_codes(
        spectrometer_frequency, peak_list
    )

    category = "nef_nmr_spectrum"
    frame_code = f"{category}_{entry_name}"
    frame = Saveframe.from_scratch(frame_code, category)

    frame.add_tag("sf_category", category)
    frame.add_tag("sf_framecode", frame_code)
    frame.add_tag("num_dimensions", peak_list.peak_list_data.num_axis)
    frame.add_tag("chemical_shift_list", constants.NEF_UNKNOWN)
    loop = Loop.from_scratch("nef_spectrum_dimension")
    frame.add_loop(loop)
    list_tags = (
        "dimension_id",
        "axis_unit",
        "axis_code",
        "spectrometer_frequency",
        "spectral_width",
        "value_first_point",
        "folding",
        "absolute_peak_positions",
        "is_acquisition",
    )
    loop.add_tag(list_tags)
    list_data = peak_list.peak_list_data
    for i in range(list_data.num_axis):
        row = {
            "dimension_id": i + 1,
            "axis_unit": "ppm",
            "axis_code": axis_isotopes[i],
            "spectrometer_frequency": list_data.spectrometer_frequencies[i],
            "spectral_width": (
                list_data.sweep_widths[i] if list_data.sweep_widths else NEF_UNKNOWN
            ),
            "value_first_point": NEF_UNKNOWN,
            "folding": "circular",
            "absolute_peak_positions": "true",
            "is_acquisition": NEF_UNKNOWN,
        }
        loop.add_data(
            [
                row,
            ]
        )

    loop = Loop.from_scratch("nef_spectrum_dimension_transfer")
    frame.add_loop(loop)
    transfer_dim_tags = ("dimension_1", "dimension_2", "transfer_type")
    loop.add_tag(transfer_dim_tags)
    loop = Loop.from_scratch("nef_peak")
    frame.add_loop(loop)

    # TODO: put this in a sane order!
    peak_tags = [
        "index",
        "peak_id",
        "volume",
        "volume_uncertainty",
        "height",
        "height_uncertainty",
    ]
    position_tags = [
        (f"position_{i + 1}", f"position_uncertainty_{i + 1}")
        for i in range(list_data.num_axis)
    ]
    position_tags = itertools.chain(*position_tags)
    atom_name_tags = [
        (
            f"chain_code_{i + 1}",
            f"sequence_code_{i + 1}",
            f"residue_name_{i + 1}",
            f"atom_name_{i + 1}",
        )
        for i in range(list_data.num_axis)
    ]
    atom_name_tags = itertools.chain(*atom_name_tags)
    tags = [*peak_tags, *position_tags, *atom_name_tags]

    loop.add_tag(tags)
    for i, peak in enumerate(peak_list.peaks):
        peak_values = peak["values"]
        if peak_values.deleted:
            continue

        positions = {}
        for tag in tags:
            if tag.split("_")[0] == "position" and len(tag.split("_")) == 2:
                index = int(tag.split("_")[-1]) - 1
                positions[tag] = peak[index].ppm

        chain_codes = {}
        for tag in tags:
            if tag.split("_")[:2] == ["chain", "code"]:
                index = int(tag.split("_")[-1]) - 1
                chain_code = peak[index].atom_labels.residue.chain_code
                chain_code = chain_code if chain_code is not None else chain_code
                chain_code = chain_code if chain_code else "."
                chain_codes[tag] = chain_code

        sequence_codes = {}
        for tag in tags:
            if tag.split("_")[:2] == ["sequence", "code"]:
                index = int(tag.split("_")[-1]) - 1
                sequence_code = peak[index].atom_labels.residue.sequence_code
                sequence_code = sequence_code if sequence_code else "."
                sequence_codes[tag] = sequence_code

        residue_names = {}
        for tag in tags:
            if tag.split("_")[:2] == ["residue", "name"]:
                index = int(tag.split("_")[-1]) - 1

                # TODO: there could be more than 1 atom label here and this should be a list...
                residue_name = peak[index].atom_labels.residue.residue_name
                residue_name = residue_name if residue_name else "."
                residue_names[tag] = residue_name

        atom_names = {}
        for tag in tags:
            if tag.split("_")[:2] == ["atom", "name"]:
                index = int(tag.split("_")[-1]) - 1

                atom_name = peak[index].atom_labels.atom_name
                atom_name = atom_name if atom_name else "."
                atom_names[tag] = atom_name

        row_dict = {
            "index": i + 1,
            "peak_id": peak_values.serial,
            **chain_codes,
            **sequence_codes,
            **residue_names,
            **atom_names,
            **positions,
            "volume": peak_values.volume,
            "volume_uncertainty": NEF_UNKNOWN,
            "height": peak_values.height,
            "height_uncertainty": NEF_UNKNOWN,
        }
        loop.add_data(
            [
                row_dict,
            ]
        )
    return frame


# TODO: can be replaced by str.removesuffix when min python version >= 3.9
def _remove_suffix(string: str, suffix: str) -> str:

    result = string
    if string.endswith(suffix):
        result = string[: -len(suffix)]

    return result


def _make_peak_list_frame_name(peaks_list):
    entry_name = peaks_list.peak_list_data.data_set.replace(" ", "_")
    entry_name = _remove_suffix(entry_name, ".nv")
    entry_name = entry_name.replace(".", "_")
    return entry_name
