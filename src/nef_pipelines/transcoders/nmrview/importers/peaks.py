# TODO: add reading of sequence from input stream
# TODO: xplor names -> iupac and deal with %% and ## properly
# TODO: add common experiment types
# TODO: guess axis codes
# TODO: add a chemical shift list reference
# TODO: _nef_nmr_spectrum: value_first_point, folding, absolute_peak_positions, is_acquisition
# TODO: cleanup
# TODO: add function
# TODO: remove ics
# TODO: multiple assignments per peak... howto in nef
# TODO: add libs pipeline
# TODO axis codes need to be guessed
# TODO doesn't check if peaks are deleted (should have an option to read all peaks?)

import itertools
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple

import typer
from ordered_set import OrderedSet
from pynmrstar import Loop, Saveframe

from nef_pipelines.lib import constants
from nef_pipelines.lib.constants import NEF_UNKNOWN
from nef_pipelines.lib.sequence_lib import (
    get_residue_name_from_lookup,
    get_sequence_or_exit,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    PeakAxis,
    PeakList,
    PeakListData,
    PeakValues,
    SequenceResidue,
)
from nef_pipelines.lib.typer_utils import get_args
from nef_pipelines.lib.util import STDIN, exit_error, process_stream_and_add_frames
from nef_pipelines.transcoders.nmrview import import_app

from ..nmrview_lib import parse_float_list, parse_tcl

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
    entry_name: str = typer.Option(
        "nmrview",
        "-n",
        "--name",
        help="a name for a shift frame, additional calls add more names",
    ),
    chain_code: str = typer.Option(
        "A", "--chain", help="chain code", metavar="<chain-code>"
    ),
    sequence: Path = typer.Option(
        STDIN,
        "-s",
        "--sequence",
        metavar="<nmrview>.seq)",
        help="seq file for the chain <seq-file>.seq",
    ),
    axis_codes: str = typer.Option(
        "1H.15N",
        "-a",
        "--axis",
        metavar="<axis-codes>",
        help="a list of axis codes joined by dots",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input peak files", metavar="<peak-file.xpk>"
    ),
):
    """convert nmrview peak file <nmrview>.xpk files to NEF"""
    args = get_args()

    raw_sequence = get_sequence_or_exit(sequence)

    sequence_lookup = _sequence_to_residue_type_lookup(raw_sequence)

    frames = [
        read_xpk_file(args, sequence_lookup),
    ]

    entry = process_stream_and_add_frames(frames, args)
    print(entry)


def read_xpk_file(args, sequence_lookup, entry_name=None):

    with open(args.file_names[0], "r") as lines:
        peaks_list = read_raw_peaks(lines, args.chain_code, sequence_lookup)

    if not entry_name:
        entry_name = make_peak_list_entry_name(peaks_list)

    return create_spectrum_frame(args, entry_name, peaks_list)


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
                f"failed to parse file a line {line_no} with input: '{raw_line.strip()}' field: {field}  axis: "
                f"  {axis_index + 1} exception: {e}"
            )
            exit_error(msg)
    return raw_peaks


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
                residue_number, atom_name = label.split(".")
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


def sequence_from_frames(frames: Saveframe):

    residues = OrderedSet()
    for frame in frames:
        for loop in frame:
            chain_code_index = loop.tag_index("chain_code")
            sequence_code_index = loop.tag_index("sequence_code")
            residue_name_index = loop.tag_index("residue_name")

            for line in loop:
                chain_code = line[chain_code_index]
                sequence_code = line[sequence_code_index]
                residue_name = line[residue_name_index]
                residue = SequenceResidue(chain_code, sequence_code, residue_name)
                residues.append(residue)

    return list(residues)


def create_spectrum_frame(args, entry_name, peaks_list):

    category = "nef_nmr_spectrum"
    frame_code = f"{category}_{entry_name}"
    frame = Saveframe.from_scratch(frame_code, category)

    frame.add_tag("sf_category", category)
    frame.add_tag("sf_framecode", frame_code)
    frame.add_tag("num_dimensions", peaks_list.peak_list_data.num_axis)
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
    list_data = peaks_list.peak_list_data
    for i in range(list_data.num_axis):
        for tag in list_tags:
            if tag == "dimension_id":
                loop.add_data_by_tag(tag, i + 1)
            elif tag == "axis_unit":
                loop.add_data_by_tag(tag, "ppm")
            elif tag == "axis_code":
                axis_codes = args.axis_codes.split(".")
                loop.add_data_by_tag(tag, _get_isotope_code_or_exit(i, axis_codes))
            elif tag == "spectrometer_frequency":
                loop.add_data_by_tag(tag, list_data.spectrometer_frequencies[i])
            elif tag == "spectral_width":
                if list_data.sweep_widths:
                    loop.add_data_by_tag(tag, list_data.sweep_widths[i])
                else:
                    loop.add_data_by_tag(tag, NEF_UNKNOWN)
            elif tag == "folding":
                loop.add_data_by_tag(tag, "circular")
            elif tag == "absolute_peak_positions":
                loop.add_data_by_tag(tag, "true")
            else:
                loop.add_data_by_tag(tag, NEF_UNKNOWN)
    loop = Loop.from_scratch("nef_spectrum_dimension_transfer")
    frame.add_loop(loop)
    transfer_dim_tags = ("dimension_1", "dimension_2", "transfer_type")
    loop.add_tag(transfer_dim_tags)
    loop = Loop.from_scratch("nef_peak")
    frame.add_loop(loop)
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
    for i, peak in enumerate(peaks_list.peaks):
        peak_values = peak["values"]
        if peak_values.deleted:
            continue

        for tag in tags:

            if tag == "index":
                loop.add_data_by_tag(tag, i + 1)
            elif tag == "peak_id":
                loop.add_data_by_tag(tag, peak_values.serial)
            elif tag == "volume":
                loop.add_data_by_tag(tag, peak_values.volume)
            elif tag == "height":
                loop.add_data_by_tag(tag, peak_values.height)
            elif tag.split("_")[0] == "position" and len(tag.split("_")) == 2:
                index = int(tag.split("_")[-1]) - 1
                loop.add_data_by_tag(tag, peak[index].ppm)
            elif tag.split("_")[:2] == ["chain", "code"]:
                index = int(tag.split("_")[-1]) - 1
                chain_code = peak[index].atom_labels.residue.chain_code
                chain_code = chain_code if chain_code is not None else args.chain_code
                chain_code = chain_code if chain_code else "."
                loop.add_data_by_tag(tag, chain_code)
            elif tag.split("_")[:2] == ["sequence", "code"]:
                index = int(tag.split("_")[-1]) - 1
                sequence_code = peak[index].atom_labels.residue.sequence_code
                sequence_code = sequence_code if sequence_code else "."
                loop.add_data_by_tag(tag, sequence_code)
            elif tag.split("_")[:2] == ["residue", "name"]:
                index = int(tag.split("_")[-1]) - 1

                # TODO: there could be more than 1 atom label here and this should be a list...
                residue_name = peak[index].atom_labels.residue.residue_name
                residue_name = residue_name if residue_name else "."
                loop.add_data_by_tag(tag, residue_name)
            elif tag.split("_")[:2] == ["atom", "name"]:
                index = int(tag.split("_")[-1]) - 1

                atom_name = peak[index].atom_labels.atom_name
                atom_name = atom_name if atom_name else "."
                loop.add_data_by_tag(tag, atom_name)
            else:
                loop.add_data_by_tag(tag, constants.NEF_UNKNOWN)
    return frame


# TODO: can be replaced by str.removesuffix when min python version >= 3.9
def _remove_suffix(string: str, suffix: str) -> str:

    result = string
    if string.endswith(suffix):
        result = string[: -len(suffix)]

    return result


def make_peak_list_entry_name(peaks_list):
    entry_name = peaks_list.peak_list_data.data_set.replace(" ", "_")
    entry_name = _remove_suffix(entry_name, ".nv")
    entry_name = entry_name.replace(".", "_")
    return entry_name
