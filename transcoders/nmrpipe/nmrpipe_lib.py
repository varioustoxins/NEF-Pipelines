from collections import Counter
from dataclasses import dataclass, field
from typing import List, Union, TextIO

from icecream import ic
from tabulate import tabulate


@dataclass
class DbRecord:
    index: int
    type: str
    values: List[Union[int, str, float]]


@dataclass
class DbFile:
    name: str = 'unknown'
    records: List[DbRecord] = field(default_factory=list)


def read_db_file_records(file_h: TextIO, file_name: str = 'unknown') -> DbFile:

    """Read from NmrPipe (NIH) tab-file string; Return self
    """

    records: List[DbRecord] = []
    column_names = None
    column_formats = None
    record_count = Counter()

    for line_no, line in enumerate(file_h):
        line_info = LineInfo(line_no, line)
        line = line.strip()
        if len(line) > 0:
            raw_fields = line.strip().split()

            if len(line) == 0:
                continue

            record_type = raw_fields[0]
            record_count[record_type] += 1

            if len(raw_fields) > 1:
                fields = raw_fields[1:]
            else:
                fields = raw_fields

            handled = False

            if record_type == 'VARS':

                if record_count[record_type] != 1:
                    raise_multiple('VARS', file_name, line)


                column_names = fields
                records.append(DbRecord(record_count[record_type], record_type, column_names))
                handled = True

            if record_type == 'FORMAT':
                column_formats = formats_to_constructors(fields)

                if record_count[record_type] != 1:
                    raise_multiple('FORMAT', file_name, line)

                check_var_and_format_count_raise_if_bad(column_names, column_formats, line_info)


                records.append(DbRecord(record_count[record_type], record_type, fields))
                handled = True

            if record_type in ('REMARK', '#'):
                records.append(DbRecord(record_count[record_type], record_type, line))
                handled = True

            if is_int(record_type):
                if column_names and column_formats:
                    record_count['__VALUES__'] += 1

                    del record_count[record_type]

                    values = build_values_or_raise(column_formats, column_names, fields, line_info)

                    record = DbRecord(record_count['__VALUES__'], '__VALUES__', values)
                    records.append(record)

                    handled = True



                else:
                    msg = f"""
                          bad nmrpipe db file, data seen before VAR and FORMAT in file '{file_name}' at line {line_no+1}
                          line data: {line}
                    """
                    raise BadNmrPipeFile(msg)

            if not handled:
                records.append(DbRecord(record_count[record_type], record_type, fields))



    return DbFile(file_name, records)


def build_values_or_raise(column_formats, column_names, fields, line_info):
    non_index_column_formats = check_column_count_raise_if_bad(column_formats, column_names, line_info)
    result = []
    for column_no, (raw_field, constructor) in enumerate(zip(fields, non_index_column_formats)):
        try:
            value = constructor(raw_field)
        except Exception:
            msg = f"""
                    Couldn't convert {raw_field} to type {constructor_to_name(constructor)}
                    at line: {line_info.line_no}
                    column: {column_no}
                    line data: {line_info.line}
                """
            raise BadFieldFormat(msg)
        result.append(value)
    return result


def raise_multiple(format_str, file_name, line):
    msg = f"""\
                    bad NMRPipe db file, multiple {format_str} statements found at line {line} in file {file_name}
                    line: {line}
                    """
    raise BadNmrPipeFile(msg)


def check_var_and_format_count_raise_if_bad(column_names, column_formats, line_info):
    num_formats = len(column_names)
    num_column_names = len(column_formats)
    if num_formats != num_column_names:
        msg = f'''number of column names and formats must agree 
                  got {num_column_names} column names and f{num_formats}' formats
                  at line {line_info.line_no}
                  with value {line_info.line}'''
        raise WrongColumnCount(msg)


def check_column_count_raise_if_bad(column_formats, column_names, line_info):
    non_index_column_formats = column_formats[1:]
    raw_fields = line_info.line.split()
    num_fields = len(raw_fields)
    num_columns = len(non_index_column_formats) + 1
    if num_fields != num_columns:
        tab = [
            column_names,
            column_formats,
            raw_fields
        ]
        tabulated = tabulate(tab, tablefmt='plain')
        msg = \
            f"""
                number fields ({num_fields + 1}) doesn't not match number of columns ({num_columns + 1}
                expected 
                {tabulated}
                at line: {line_info.line_no}
                line data : {' '.join(raw_fields)}
            """
        raise WrongColumnCount(msg)
    return non_index_column_formats



@dataclass
class LineInfo:
    line_no: int
    line: str


def is_int(value: str):
    result = False
    try:
        int(value)
        result = True
    except ValueError:
        pass

    return result


def formats_to_constructors(formats):
    result = []

    for i, field_format in enumerate(formats):
        field_format = field_format.strip()
        field_format = field_format[-1]

        if field_format == 'd':
            result.append(int)
        elif field_format == 'f':
            result.append(float)
        elif field_format == 's':
            result.append(str)
        else:
            msg = f'''
                Unexpected format {field_format} at index {i+1}, expected formats are s,d,f (string, decimal, float)
                formats: {' '.join(formats)}
            '''
            raise BadFieldFormat(msg)
    return result


def constructor_to_name(constructor):
    constructors_to_type_name = {
        int: 'int',
        float: 'float',
        str: 'str'
    }

    return constructors_to_type_name[constructor]


def constructor_names(constructors):

    result = []
    for constructor in constructors:
        result.append(constructor_to_name(constructor))

    return result


class BadNmrPipeFile(Exception):
    pass


class BadFieldFormat(BadNmrPipeFile):
    pass


class WrongColumnCount(BadNmrPipeFile):
    pass
