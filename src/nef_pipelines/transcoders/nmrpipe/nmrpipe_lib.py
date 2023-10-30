import functools
import operator
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import IntEnum
from textwrap import dedent
from typing import Callable, List, Optional, TextIO, Tuple, Union

from tabulate import tabulate

from nef_pipelines.lib.sequence_lib import (
    MoleculeTypes,
    make_chunked_sequence_1let,
    offset_chain_residues,
    sequence_3let_to_sequence_residues,
    translate_1_to_3,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    LineInfo,
    PeakAxis,
    PeakList,
    PeakListData,
    PeakValues,
    SequenceResidue,
    ShiftData,
    ShiftList,
)
from nef_pipelines.lib.util import exit_error, is_int


class PEAK_TYPES(IntEnum):
    PEAK = 1
    NOISE = 2
    SINC_WIGGLE = 3


# known field types
DATA = "DATA"
REMARK = "REMARK"
VALUES = "__VALUES__"
SEQUENCE = "SEQUENCE"
FORMAT = "FORMAT"
VARS = "VARS"
COMMENT = "#"
NULLSTRING = "NULLSTRING"
NULLVALUE = "NULLVALUE"

NMRPIPE_PEAK_EXPECTED_FIELDS = "INDEX X_AXIS XW XW_HZ ASS CLUSTID MEMCNT".split()
NMRPIPE_SHIFTS_EXPECTED_FIELDS = "RESID RESNAME ATOMNAME SHIFT".split()


@dataclass(frozen=True)
class DbRecord:
    index: int
    type: str
    values: Tuple[Union[int, str, float]]
    line_info: LineInfo = None


@dataclass
class DbFile:
    name: str = "unknown"
    records: List[DbRecord] = field(default_factory=list)


def _raise_data_before_format(line_info):
    msg = f"""\
            bad nmrpipe db file, data seen before VAR and FORMAT
            file: {line_info.file_name}'
            line no: {line_info.line_no}
            line: {line_info.line}
            """
    msg = dedent(msg)
    raise DataBeforeFormat(msg)


def read_db_file_records(file_h: TextIO, file_name: str = "unknown") -> DbFile:

    """
    Read from NmrPipe (NIH) tab/gdb-file
    Args:
        file_h (TextIO): a file like object
        file_name (str): the name of the file being read (for debugging)

    Returns DbFile:
        a list of all the records in the fiule
    """

    records: List[DbRecord] = []
    column_names = None
    column_formats = None
    record_count = Counter()
    in_header = True

    for line_index, line in enumerate(file_h):

        line_info = LineInfo(file_name, line_index + 1, line)
        line = line.strip()

        raw_fields = line.strip().split()

        if len(line) == 0:
            continue

        record_type = raw_fields[0]
        record_count[record_type] += 1

        fields = raw_fields

        handled = False

        if in_header:
            if record_type == "VARS":

                column_names = fields[1:]
                records.append(
                    DbRecord(
                        record_count[record_type], record_type, column_names, line_info
                    )
                )
                handled = True

                if record_count[record_type] != 1:
                    _raise_multiple(record_type, line_info)

            if record_type == "FORMAT":
                column_formats = _formats_to_constructors(fields, line_info)

                _check_var_and_format_count_raise_if_bad(
                    column_names, column_formats, line_info
                )

                records.append(
                    DbRecord(
                        record_count[record_type], record_type, fields[1:], line_info
                    )
                )
                in_header = False
                continue

            if record_type in ("REMARK", "#"):
                records.append(
                    DbRecord(record_count[record_type], record_type, line, line_info)
                )
                handled = True

            if record_type == DATA:
                records.append(
                    DbRecord(
                        record_count[record_type], record_type, fields[1:], line_info
                    )
                )
                handled = True

            if not handled:
                _raise_data_before_format(line_info)

        if not in_header:

            if record_type in (VARS, FORMAT):
                _raise_multiple(record_type, line_info)

            if column_names and column_formats:
                record_count["__VALUES__"] += 1

                del record_count[record_type]

                values = _build_values_or_raise(
                    column_formats, column_names, fields, line_info
                )

                record = DbRecord(
                    record_count["__VALUES__"], "__VALUES__", values, line_info
                )
                records.append(record)

                handled = True

        if not handled:
            records.append(
                DbRecord(record_count[record_type], record_type, fields[1:], line_info)
            )

    return DbFile(file_name, records)


def _find_nth(haystack, needle, n):
    # https://stackoverflow.com/questions/1883980/find-the-nth-occurrence-of-substring-in-a-string/41626399#41626399
    start = haystack.find(needle)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start + len(needle))
        n -= 1
    return start


def _build_values_or_raise(column_formats, column_names, fields, line_info):
    columns_formats = _check_column_count_raise_if_bad(
        column_formats, column_names, line_info
    )
    result = []
    field_count = Counter()
    for column_no, (raw_field, constructor) in enumerate(zip(fields, columns_formats)):
        try:
            field_count[raw_field] += 1
            value = constructor(raw_field)

        except Exception:
            absolute_column = _find_nth(
                line_info.line, raw_field, field_count[raw_field]
            )
            msg = f"""
                    Couldn't convert {raw_field} to type {_constructor_to_name(constructor)}
                    file: {line_info.file_name}
                    line no: {line_info.line_no}
                    column: {column_no + 1}
                    line: {line_info.line.rstrip()}
                          {' ' * absolute_column + '^'}
                """
            msg = dedent(msg)
            raise BadFieldFormat(msg)
        result.append(value)
    return result


def _raise_multiple(format_str, line_info):
    msg = f"""\
                bad NMRPipe db file, multiple {format_str} statements found
                file: {line_info.file_name}
                line no: {line_info.line_no}
                line: {line_info.line}
                """
    msg = dedent(msg)

    if format_str == "VARS":
        raise MultipleVars(msg)
    elif format_str == "FORMAT":
        raise MultipleFormat(msg)


def _check_var_and_format_count_raise_if_bad(column_names, column_formats, line_info):
    if column_names is None:
        msg = f"""\
               no column names defined by a VARS line when FORMAT line read
               file: {line_info.file_name}
               line no: {line_info.line_no}
               line: {line_info.line}"""
        msg = dedent(msg)
        raise NoVarsLine(msg)

    num_formats = len(column_names)
    num_column_names = len(column_formats)
    if num_formats != num_column_names:
        msg = f"""\
                  number of column names and formats must agree
                  got {num_column_names} column names and {num_formats} formats
                  file: {line_info.file_name}
                  line no: {line_info.line_no}
                  line: {line_info.line}
               """
        msg = dedent(msg)

        raise WrongColumnCount(msg)


def _check_column_count_raise_if_bad(column_formats, column_names, line_info):
    raw_fields = line_info.line.split()
    num_fields = len(raw_fields)
    num_columns = len(column_formats)

    missing_fields = ["*"] * abs(num_fields - num_columns)
    raw_fields = [*raw_fields, *missing_fields]

    if num_fields != num_columns:
        column_formats = _constructor_names(column_formats)
        tab = [
            column_names,
            column_formats,
            raw_fields,
        ]
        tabulated = tabulate(tab, tablefmt="plain")
        msg = f"""\
                number fields ({num_fields + 1}) doesn't not match number of columns ({num_columns + 1})

                expected
                %s

                missing fields marked with *

                file: {line_info.file_name}
                line no: {line_info.line_no}
                line: {line_info.line}

            """
        msg = dedent(msg)
        msg = msg % tabulated
        raise WrongColumnCount(msg)
    return column_formats


def _formats_to_constructors(formats, line_info):
    result = []

    field_counter = Counter()
    for column_index, field_format in enumerate(formats[1:]):
        field_counter[field_format] += 1
        field_format = field_format.strip()
        field_format = field_format[-1]

        if field_format == "d":
            result.append(int)
        elif field_format == "f":
            result.append(float)
        elif field_format == "s":
            result.append(str)
        elif field_format == "e":
            result.append(float)
        else:
            format_column = _find_nth(
                line_info.line, field_format, field_counter[field_format]
            )
            msg = f"""
                unexpected format {field_format} at index {column_index+1}, expected formats are:
                s, d, e, f (string, integer, scientific(float), float)

                file: {line_info.file_name}
                line no: {line_info.line_no}
                line: {line_info.line}
                      {' ' * format_column + '^'}

            """
            raise BadFieldFormat(msg)
    return result


OptionDbRecordPredicate = Optional[Callable[[DbRecord], bool]]


def select_records(
    gdb: DbFile, record_type: str, predicate: OptionDbRecordPredicate = None
) -> List[DbRecord]:
    """
    Select records from a gdb file by type and predicate
    Args:
        gdb (DbFile): gdb/tab file
        type (str): the type of the record #, REMARK, __VALUE__ etc
        predicate (OptionDbRecordPredicate): an optional test to apply to the record

    Returns List[DbRecord]:
        in the selected gdb/tab records
    """
    result = [record for record in gdb.records if record.type == record_type]
    if predicate:
        result = [record for record in result if predicate(record)]
    return result


def select_data_records(gdb: DbFile, type: str) -> List[DbRecord]:
    """
    Select data records from the db file that have the specific type

    :param gdb:  a parsed GBD files
    :param type: the type of data record to select
    :return: a list of matching DbRecords
    """
    return select_records(gdb, "DATA", predicate=lambda rec: rec.values[0] == type)


def gdb_to_3let_sequence(
    gdb: DbFile, molecule_type: MoleculeTypes = MoleculeTypes.PROTEIN
) -> List[SequenceResidue]:
    """
    read sequence records from a gdb file and convert them to a list of sequence residues
    it is assumed that residues start from 1 and are in chain A
    Args:
        gdb (DbFile): the source db/tab file records
        molecule_type (MoleculeTypes): the type of the molecule to translate

    Returns List[SequenceResidue]:
        a list of sequence residues
    """
    sequence_records = select_data_records(gdb, "SEQUENCE")

    sequence = [record.values[1:] for record in sequence_records]

    flattened_sequence = functools.reduce(operator.iconcat, sequence, [])
    sequence_string = "".join(flattened_sequence)

    return translate_1_to_3(sequence_string, molecule_type=molecule_type)


def gdb_to_chain_start(gdb_file: DbFile) -> int:
    """
    Find a first resid record in a GbdFile and return it or return 1
    :param gdb_file: a GBD file
    :return: a chain start
    """

    chain_start_records = select_data_records(gdb_file, "FIRST_RESID")

    if len(chain_start_records) == 0:
        chain_start = 1
    else:
        chain_start = int(chain_start_records[-1].values[1])

    return chain_start


def gdb_to_sequence(gdb_file: DbFile, chain_code: str) -> List[SequenceResidue]:

    """
    Read the sequence from a GDB file, note if a FIRST_RESID record is found the sequence
    is offset correctly...
    :param gdb_file:  a GDB file
    :param chain_code: the chain code to give the sequence
    :return: a List of sequence residues
    """
    chain_start = gdb_to_chain_start(gdb_file)

    sequence_3let = gdb_to_3let_sequence(gdb_file)

    sequence_residues = sequence_3let_to_sequence_residues(
        sequence_3let, chain_code=chain_code
    )

    sequence_residues = offset_chain_residues(
        sequence_residues, {chain_code: chain_start - 1}
    )

    return sequence_residues


def _assignments_to_atom_labels(assignments, dimensions, chain_code="A"):
    result = []

    for assignment in assignments:
        chain_code = chain_code

        residue_name = None
        len_assignment = len(assignment)
        if len_assignment > 0:
            residue_name = translate_1_to_3(assignment[0], unknown=".")[0]

        sequence_code = None
        if len_assignment > 1:
            raw_sequence_code = assignment[1]
            if is_int(raw_sequence_code):
                sequence_code = int(raw_sequence_code)

        atom_name = None
        if len_assignment > 2:
            atom_name = assignment[2]

        result.append(
            AtomLabel(
                SequenceResidue(chain_code, sequence_code, residue_name), atom_name
            )
        )

    len_result = len(result)
    if len_result < dimensions:
        for i in len_result - dimensions:
            result.append(AtomLabel(SequenceResidue(None, None, None), None))
    return result


# NMRPIPE VARS https://spin.niddk.nih.gov/NMRPipe/doc2new/
#
# INDEX = 'INDEX'  # REQUIRED      - The unique peak ID number.
# X_AXIS = 'X_AXIS'  # REQUIRED      - Peak position: in points in 1st dimension, from left of spectrum limit
# Y_AXIS = 'Y_AXIS'  # REQUIRED      - Peak position: in points in 2nd dimension, from bottom of spectrum limit
# DX = 'DX'  # NOT REQUIRED  - Estimate of the error in peak position due to random noise, in points.
# DY = 'DY'  # NOT REQUIRED  - Estimate of the error in peak position due to random noise, in points.
# X_PPM = 'X_PPM'  # NOT REQUIRED  - Peak position: in ppm in 1st dimension
# Y_PPM = 'Y_PPM'  # NOT REQUIRED  - Peak position: in ppm in 2nd dimension
# X_HZ = 'X_HZ'  # NOT REQUIRED  - Peak position: in Hz in 1st dimension
# Y_HZ = 'Y_HZ'  # NOT REQUIRED  - Peak position: in Hz in 2nd dimension
# XW = 'XW'  # REQUIRED      - Peak width: in points in 1st dimension
# YW = 'YW'  # REQUIRED      - Peak width: in points in 2nd dimension
# XW_HZ = 'XW_HZ'  # REQUIRED      - Peak width: in points in 1st dimension
# YW_HZ = 'YW_HZ'  # REQUIRED      - Peak width: in points in 2nd dimension
# X1 = 'X1'  # NOT REQUIRED  - Left border of peak in 1st dim, in points
# X3 = 'X3'  # NOT REQUIRED  - Right border of peak in 1st dim, in points
# Y1 = 'Y1'  # NOT REQUIRED  - Left border of peak in 2nd dim, in points
# Y3 = 'Y3'  # NOT REQUIRED  - Right border of peak in 2nd, in points
# HEIGHT = 'HEIGHT'  # NOT REQUIRED  - Peak height
# DHEIGHT = 'DHEIGHT'  # NOT REQUIRED  - Peak height error
# VOL = 'VOL'  # NOT REQUIRED  - Peak volume
# PCHI2 = 'PCHI2'  # NOT REQUIRED  - the Chi-square probability for the peak (i.e. probability due to the noise)
# TYPE = 'TYPE'  # NOT REQUIRED  - the peak classification; 1=Peak, 2=Random Noise, 3=Truncation artifact.
# ASS = 'ASS'  # REQUIRED      - Peak assignment
# CLUSTID = 'CLUSTID'  # REQUIRED      - Peak cluster id. Peaks with the same CLUSTID value are the overlapped.
# MEMCNT = 'MEMCNT'  # REQUIRED      - the total number of peaks which are in a given peak's cluster
# (i.e. peaks which have the same CLUSTID value)


def get_column_indices(gdb_file):
    return {column: index for index, column in enumerate(get_gdb_columns(gdb_file))}


def _mean(values):
    return sum(values) / len(values)


def _get_peak_list_dimension(gdb_file):

    return len(_get_axis_labels(gdb_file))


def _get_axis_labels(gdb_file):
    columns = get_gdb_columns(gdb_file)

    result = []
    for var in columns:
        if var.endswith("_AXIS"):
            result.append(var.split("_")[0])
    return result


def get_gdb_columns(gdb_file: DbFile) -> List[str]:
    return select_records(gdb_file, VARS)[0].values


def check_is_peak_file(gdb_file):
    columns = set(get_gdb_columns(gdb_file))
    expected_fields = set(NMRPIPE_PEAK_EXPECTED_FIELDS)

    return expected_fields.issubset(columns)


def check_is_shifts_file(gdb_file):
    columns = set(get_gdb_columns(gdb_file))
    expected_fields = set(NMRPIPE_SHIFTS_EXPECTED_FIELDS)

    return expected_fields.issubset(columns)


def read_peak_file(gdb_file, args):
    data = select_records(gdb_file, VALUES)

    dimensions = _get_peak_list_dimension(gdb_file)

    column_indices = get_column_indices(gdb_file)

    axis_labels = _get_axis_labels(gdb_file)

    spectrometer_frequencies = [[] for _ in range(dimensions)]

    raw_peaks = []
    for index, line in enumerate(data, start=1):

        peak = {}
        raw_peaks.append(peak)
        peak_type = line.values[column_indices["TYPE"]]
        if args.filter_noise and peak_type != PEAK_TYPES.PEAK:
            continue

        assignment = line.values[column_indices["ASS"]]
        assignments = assignment.split("-")
        assignments = _propagate_assignments(assignments)
        assignments = _assignments_to_atom_labels(assignments, dimensions)

        height = line.values[column_indices["HEIGHT"]]
        # height_error = line.values[column_indices["DHEIGHT"]]
        # height_percentage_error = height_error / height
        volume = line.values[column_indices["VOL"]]
        # volume_error = volume * height_percentage_error

        peak_values = PeakValues(
            serial=index, volume=volume, height=height, deleted=False, comment=""
        )
        peak["values"] = peak_values

        for i, dimension in enumerate("X Y Z A".split()[:dimensions]):

            shift = line.values[column_indices["%s_PPM" % dimension]]

            # point_error = line.values[column_indices["D%s" % dimension]]

            # point = line.values[column_indices["%s_AXIS" % dimension]]
            # shift_error = point_error / point * shift

            pos_hz = line.values[column_indices["%s_HZ" % dimension]]

            axis = PeakAxis(atom_labels=assignments[i], ppm=shift, merit=1)

            peak[i] = axis

            sf = pos_hz / shift

            spectrometer_frequencies[i].append(sf)

    spectrometer_frequencies = [
        _mean(frequencies) for frequencies in spectrometer_frequencies
    ]
    header_data = PeakListData(
        num_axis=dimensions,
        axis_labels=axis_labels,
        data_set=None,
        sweep_widths=None,
        spectrometer_frequencies=spectrometer_frequencies,
    )

    peak_list = PeakList(header_data, raw_peaks)

    return peak_list


def read_shift_file(gdb_file, chain_code="A"):
    data = select_records(gdb_file, VALUES)

    column_indices = get_column_indices(gdb_file)

    raw_shifts = []
    for index, line in enumerate(data, start=1):

        atom_name = line.values[column_indices["ATOMNAME"]]
        residue_number = line.values[column_indices["RESID"]]
        residue_type = line.values[column_indices["RESNAME"]]
        shift = line.values[column_indices["SHIFT"]]

        atom = AtomLabel(
            SequenceResidue(chain_code, residue_number, residue_type), atom_name
        )

        shift = ShiftData(atom, shift)

        raw_shifts.append(shift)

    return ShiftList(raw_shifts)


def _propagate_assignments(assignments):

    current = []
    result = []
    for assignment in assignments:
        fields = re.split(r"(\d+)", assignment)
        if len(fields) == 3:
            current = fields[:2]
        elif len(fields) == 1:
            fields = [*current, *fields]

        result.append(fields)

    return result


def _constructor_to_name(constructor):
    constructors_to_type_name = {int: "int", float: "float", str: "str"}

    return constructors_to_type_name[constructor]


def _constructor_names(constructors):

    result = []
    for constructor in constructors:
        result.append(_constructor_to_name(constructor))

    return result


class BadNmrPipeFile(Exception):
    """
    Base exception for bad nmr pipe files, this is the one to catch!
    """

    pass


class BadFieldFormat(BadNmrPipeFile):
    """
    One of the fields int he file has a bad format
    """

    pass


class WrongColumnCount(BadNmrPipeFile):
    """
    The number of columns in the VARS FORMAT or data lines disagree in their count
    """

    pass


class NoVarsLine(BadNmrPipeFile):
    """
    Tried to read data without a VARS line
    """

    pass


class NoFormatLine(BadNmrPipeFile):
    """
    Tried to read data without a FORMAT line
    """

    pass


class MultipleVars(BadNmrPipeFile):
    """
    Multiple VARS lines detected
    """

    pass


class MultipleFormat(BadNmrPipeFile):
    """
    Multiple FORMAT lines detected
    """

    pass


class DataBeforeFormat(BadNmrPipeFile):
    """
    Data seen before VARS and FORMAT lines detected
    """

    pass


def format_pipe_sequence(sequence_1_let: List[str]) -> str:

    """
    convert a set of 1 letter amino acid codes to an nmr pipe DATA SEQUENCE record
    :param sequence_1_let:  1 letter amino acid codes as a list of strings
    :return: nmrpipe data sequence string nicely formatted as a list of data record strings
    """

    row_strings = make_chunked_sequence_1let(sequence_1_let)

    result = []
    for row_string in row_strings:
        result.append(f"DATA SEQUENCE {row_string}")

    return result


def exit_if_required_columns_missing(
    gdb_records: DbFile, required_columns: List[str], file_name: str
):
    gdb_columns = get_gdb_columns(gdb_records)
    column_set = set(gdb_columns)

    required_column_set = set(required_columns)

    if not required_column_set.issubset(column_set):
        msg = f"""
            the required column in the file {file_name} are:

            {', '.join(required_columns)}

            found columns are

            {', '.join(gdb_columns)}

            missing columns are

            {', '.join(required_column_set - column_set)}
        """

        exit_error(msg)


def dbfile_to_first_residue_number(gdb_records: DbFile) -> int:
    first_residue_records = select_data_records(gdb_records, "FIRST_RESID")
    first_residue = 1
    if len(first_residue_records) == 1:
        first_residue = int(first_residue_records[0].values[1])
    return first_residue
