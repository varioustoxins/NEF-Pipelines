from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List

import typer
from fyeah import f
from pynmrstar import Saveframe

from nef_pipelines.lib.nef_frames_lib import CCPN_MERIT, SPECTRUM_FRAME_CATEGORY
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    extract_column,
    read_or_create_entry_exit_error_on_bad_file,
    set_column,
    set_column_to_value,
)
from nef_pipelines.lib.sequence_lib import MoleculeTypes, sequence_from_entry
from nef_pipelines.lib.util import (  # STDIN,; exit_error,; parse_comma_separated_options,
    STDIN,
    is_float,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.echidna import import_app
from nef_pipelines.transcoders.sparky.importers.peaks import (
    pipe as sparky_peak_import_pipe,
)

DEFAULT_MERIT_FUNTION = "round(x**(1.0/6.0),5)"

# TODO: rationalise these into lib
CCPN_COMMENT = "ccpn_comment"
HEIGHT = "height"
NEF_PEAK = "nef_peak"

app = typer.Typer()

DEFAULT_NUCLEI_HELP = (
    "nuclei to use for each dimension, if not defined they are guessed from the assignments"
    "or an error is reported"
)


# noinspection PyUnusedLocal
class BadEchidnaFileException(Exception):
    pass


@dataclass
class TensorFrame:
    amplitude: float
    rhombicity: float

    theta: float
    psi: float
    phi: float


@dataclass
class Position:
    x: float
    y: float
    z: float


TENSOR_HEADERS = set("Xax Xrh theta psi phi".split())
ATOM_POSITION_HEADERS = set("-x -y -z".split())
TENSOR_AND_ATOM_HEADERS = [*TENSOR_HEADERS, *ATOM_POSITION_HEADERS]


def _parse_echidna(input: Iterator[str], file_name: str):

    lines = []
    number_column_counts = OrderedDict()

    in_data = False
    tensor_header_indices = {}
    for line_no, line in enumerate(input):
        line = line.strip()
        fields = line.split()

        if line_no == 0:
            _check_for_echidna_header_and_raise_if_bad(fields, file_name, line)
            continue

        if line_no == 1:

            fields = [field.replace("metal", "") for field in fields]

            _check_for_echidna_tensor_and_raise_if_bad(fields, file_name, line)

            _check_for_correct_number_tensor_fields_and_raise_if_bad(
                fields, file_name, line
            )

            tensor_headers = fields[2:]

            _check_tensor_headings_and_raise_if_bad(tensor_headers, line, file_name)

            tensor_header_indices = {
                tensor_header: index
                for index, tensor_header in enumerate(tensor_headers)
            }

            continue

        if line_no == 2:

            _check_tensor_values_in_comment_or_raise(fields, line, file_name)

            tensor_and_atom_position = fields[1:]

            NUM_TENSOR_FIELDS = len(TENSOR_AND_ATOM_HEADERS)
            _check_number_tensor_fields_or_raise(
                len(tensor_and_atom_position), NUM_TENSOR_FIELDS, line, file_name
            )

            tensor = _parse_tensor_values_and_raise_if_bad(
                fields, tensor_header_indices, file_name, line
            )
            atom_position = _parse_atom_position_and_raise_if_bad(
                fields, tensor_header_indices, file_name, line
            )
            continue

        if len(fields) == 0:
            continue

        if line_no > 2 and fields[0] == "Assignment":
            in_data = True
            continue

        if line_no > 2 and in_data:
            number_count = 0
            for field in fields[1:]:
                if is_float(field):
                    number_count += 1

            number_column_counts[(line, line_no)] = number_count
            lines.append(line)

    column_count = set(number_column_counts.values())
    if len(column_count) > 1:

        raise BadEchidnaFileException()

    else:
        num_dimension_columns = list(number_column_counts.values())[0] - 1
        dimensions = " ".join([f"w{i+1}" for i in range(num_dimension_columns)])
        header = f"Assignment {dimensions} Data Height"
        lines.insert(0, "")
        lines.insert(0, header)

    return lines, tensor, atom_position


def _parse_tensor_values_and_raise_if_bad(
    fields, tensor_header_indices, file_name, line
):
    FIELD_TRANSLAIONS = {"Xax": "amplitude", "Xrh": "rhombicity"}

    fields = fields[1:]  # to remove the #

    values = {}
    for field_name in TENSOR_HEADERS:
        value = fields[tensor_header_indices[field_name]]

        if not is_float(value):
            msg = f"""
                The tensor field {field_name} in the file {file_name} is not a floating point number
                the value was {value}

                the line was

                {line}
            """
            raise BadEchidnaFileException(msg)
        else:
            field_name = (
                FIELD_TRANSLAIONS[field_name]
                if field_name in FIELD_TRANSLAIONS
                else field_name
            )
            values[field_name] = float(value)

    return TensorFrame(**values)


def _parse_atom_position_and_raise_if_bad(
    fields, tensor_header_indices, file_name, line
):

    FIELD_TRANSLAIONS = {"-x": "x", "-y": "y", "-z": "z"}

    values = {}
    for field_name in ATOM_POSITION_HEADERS:
        value = fields[tensor_header_indices[field_name]]
        if not is_float(value):
            msg = f"""
                The the atom position field {field_name} in the file {file_name} is not a floating point number
                the value was {value}

                the line was

                {line}
            """
            raise BadEchidnaFileException(msg)
        else:

            values[FIELD_TRANSLAIONS[field_name]] = float(value)

    return Position(**values)


def _check_number_tensor_fields_or_raise(
    number_fields, NUM_TENSOR_FIELDS, line, file_name
):
    if number_fields != NUM_TENSOR_FIELDS:
        msg = f"""
            in the file {file_name} at line 2 for an echidna file I expected there to be
            {NUM_TENSOR_FIELDS} fields I got {number_fields}

            the line was

            {line}
        """
        raise BadEchidnaFileException(msg)


def _check_tensor_values_in_comment_or_raise(fields, line, file_name):
    if len(fields) == 0 or fields[0] != "#":
        msg = f"""
                    An echidna tensor headers values must be in a comment, file {file_name} line 2 did not start
                    with a comment I got

                    {line}
                """
        raise BadEchidnaFileException(msg)


def _check_tensor_headings_and_raise_if_bad(tensor_headers, line, file_name):

    if set(tensor_headers) != set(TENSOR_AND_ATOM_HEADERS):
        msg = f"""
                    in the file {file_name} at line 2 for an echidna file I expected the tensor headers
                    to include: {' '.join(TENSOR_AND_ATOM_HEADERS)}
                    i got:  {' '.join(tensor_headers)}

                    the line was:  {line}

                    please note the text 'metal' in the line is ignored
                """
        raise BadEchidnaFileException(msg)


def _check_for_correct_number_tensor_fields_and_raise_if_bad(fields, file_name, line):

    if len(fields) != 10:
        msg = f"""
                In an echidna file I expected to have 10 tensor values in the tensor header [line 2 of the file]:

                    # Tensor: Xax, Xrh, theta, psi, phi, -x, -y, -z

                in the file {file_name} I got {len(fields) - 2}  after the comment character [#]

                the line was:

                {line}

                please note the text 'metal' has been filtered out from the input line if it was present
            """
        raise BadEchidnaFileException(msg)


def _check_for_echidna_tensor_and_raise_if_bad(fields, file_name, line):
    if fields[0] != "#" and fields[1] != "Tensor":
        msg = f"""
                        in the file {file_name} at line 1 for an echidna file I expected '# Tensor' i got
                        {line}
                    """
        raise BadEchidnaFileException(msg)


def _check_for_echidna_header_and_raise_if_bad(fields, file_name, line):
    if fields[0] != "#" and fields[1] != "Echidna":
        msg = f"""
                    in the file {file_name} at line 0 for an echidna file I expected '# Echidna' i got
                    {line}
                """
        raise BadEchidnaFileException(msg)


HELP_MERIT_FUNCTION = """
    function to calculate a merit value from an echidna error value, the error value is provided as the parameter x
"""


@import_app.command(no_args_is_help=True)
def peaks(
    frame_name: str = typer.Option(
        "{file_name}",
        "-f",
        "--frame-name",
        help="a templated name for the frame {file_name} will be replaced by input filename without its extension",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    nuclei: List[str] = typer.Option([], help=DEFAULT_NUCLEI_HELP),
    molecule_type: MoleculeTypes = typer.Option(
        MoleculeTypes.PROTEIN, help="the type of molecule"
    ),
    default_chain_code: str = typer.Option(
        "A",
        "-c",
        "--chain-code",
        help="default chain code to use if none is provided in the file",
    ),
    no_validate: bool = typer.Option(
        False,
        help="if set don't validate the peaks agains the inpuy sequence if provided",
    ),
    spectrometer_frequency: float = typer.Option(
        600.123456789, help="spectrometer frequency in MHz"
    ),
    merit_function: str = typer.Option(DEFAULT_MERIT_FUNTION, help=HELP_MERIT_FUNCTION),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type peaks.txt", metavar="<ECHIDNA-peaks>.txt"
    ),
):
    """convert echidna peak assignment file <ECHIDNA-PEAKS>.txt to NEF"""

    file_data = {}
    for file_name in file_names:
        with open(file_name) as fh:

            file_data[file_name] = fh.read().split("\n")

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    sequence = sequence_from_entry(entry) if not no_validate else None

    nuclei = parse_comma_separated_options(nuclei)

    for file_name, lines in file_data.items():
        entry = pipe(
            entry,
            frame_name,
            {file_name: lines},
            default_chain_code,
            sequence,
            input_dimensions=nuclei,
            spectrometer_frequency=spectrometer_frequency,
            molecule_type=molecule_type,
            merit_function=merit_function,
        )

    print(entry)


def is_iterable(target):
    result = True
    try:
        iter(target)
    except TypeError:
        result = False

    return result


#
def pipe(
    entry,
    frame_name_template,
    file_names_and_lines,
    chain_code,
    sequence,
    input_dimensions,
    spectrometer_frequency,
    molecule_type=MoleculeTypes.PROTEIN,
    merit_function=DEFAULT_MERIT_FUNTION,
):

    for file_name, lines in file_names_and_lines.items():

        lines, tensor, atom_position = _parse_echidna(lines, file_name)

        entry = sparky_peak_import_pipe(
            entry,
            frame_name_template,
            {file_name: lines},
            chain_code,
            sequence,
            input_dimensions,
            spectrometer_frequency,
            molecule_type=molecule_type,
        )

        file_name = file_name.stem  # used by f()

        frame_code = f"{SPECTRUM_FRAME_CATEGORY}_{f(frame_name_template)}"

        frame = entry.get_saveframe_by_name(frame_code)

        frame_name = file_name

        loop = frame.get_loop(NEF_PEAK)

        loop.add_tag(CCPN_MERIT, update_data=True)

        comment_values = _remove_and_store_comments(loop)

        height_index = loop.tag_index(HEIGHT)
        merit_index = loop.tag_index(CCPN_MERIT)

        _convert_heights_to_figure_of_merit(
            loop, height_index, merit_index, merit_function
        )

        comment_index = _append_stored_comments(loop, comment_values)

        _add_frame_comment_for_large_violation_limit(
            frame, loop, comment_index, merit_index
        )

        _add_tensor_frame_saveframe(entry, frame, tensor, frame_name)

        _add_atom_position_saveframe(entry, frame, atom_position, frame_name)

    return entry


def _add_atom_position_saveframe(entry, frame, atom_position, frame_name):
    atom_position_category = "np_atom_position"
    atom_position_name = f"{atom_position_category}_{frame_name}"
    frame.add_tag("np_atom_position_name", atom_position_name)
    tag_values = {"x": atom_position.x, "y": atom_position.y, "z": atom_position.z}
    atom_position_save_frame = create_simple_frame(
        atom_position_category, atom_position_name, tag_values
    )
    entry.add_saveframe(atom_position_save_frame)


def _add_tensor_frame_saveframe(entry, frame, tensor, frame_name):
    tensor_frame_category = "np_tensor_frame"
    tensor_frame_name = f"{tensor_frame_category}_{frame_name}"
    frame.add_tag("np_tensor_frame_name", tensor_frame_name)
    tag_values = {
        "restraint_origin": "measured",
        "ccpn_format": "angles_euler",
        "restraint_magnitude": tensor.amplitude,
        "restraint_rhomicity": tensor.rhombicity,
        "ccpn_phi": tensor.phi,
        "ccpn_psi": tensor.psi,
        "ccpn_theta": tensor.theta,
    }
    tensor_save_frame = create_simple_frame(
        tensor_frame_category, tensor_frame_name, tag_values
    )
    entry.add_saveframe(tensor_save_frame)


def _add_frame_comment_for_large_violation_limit(
    frame, loop, comment_index, merit_index
):
    merits_for_large_violations = []
    for row in loop:
        if "large violation!" in row[comment_index]:
            merits_for_large_violations.append(float(row[merit_index]))
    lowest_large_violation_merit = min(merits_for_large_violations)
    note = f"NOTE: merits with values > {lowest_large_violation_merit} are flagged as large violations"
    frame.add_tag(CCPN_COMMENT, note)


def _append_stored_comments(loop, comment_values):
    loop.add_tag(CCPN_COMMENT, update_data=True)
    comment_index = loop.tag_index(CCPN_COMMENT)
    set_column(loop, comment_index, comment_values)
    return comment_index


def _convert_heights_to_figure_of_merit(
    loop, height_index, merit_index, merit_function
):
    heights = extract_column(loop, height_index)
    heights = [float(height) for height in heights]
    set_column_to_value(loop, height_index, UNUSED)
    merits = [eval(merit_function) for x in heights]
    set_column(loop, merit_index, merits)


def _remove_and_store_comments(loop):
    comment_index = loop.tag_index(CCPN_COMMENT)
    comment_values = extract_column(loop, comment_index)
    comment_values = [
        comment.lstrip().lstrip(";").lstrip() for comment in comment_values
    ]
    loop.remove_tag(CCPN_COMMENT)
    return comment_values


def create_simple_frame(atom_position_category, atom_position_name, tag_values):
    save_frame = Saveframe.from_scratch(atom_position_name, atom_position_category)

    save_frame.add_tag("sf_category", atom_position_category)
    save_frame.add_tag("sf_framecode", atom_position_name)
    for tag, value in tag_values.items():
        save_frame.add_tag(tag, value)

    return save_frame
