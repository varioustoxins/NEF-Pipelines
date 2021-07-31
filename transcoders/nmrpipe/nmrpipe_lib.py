from collections import Counter
from dataclasses import dataclass, field
from textwrap import dedent
from typing import List, Union, TextIO

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


def raise_data_before_format(line_info):
    msg = f"""\
            bad nmrpipe db file, data seen before VAR and FORMAT 
            file: {line_info.file_name}' 
            line no: {line_info.line_no}
            line: {line_info.line}
            """
    msg = dedent(msg)
    raise DataBeforeFormat(msg)


def read_db_file_records(file_h: TextIO, file_name: str = 'unknown') -> DbFile:

    """Read from NmrPipe (NIH) tab-file string; Return self
    """

    records: List[DbRecord] = []
    column_names = None
    column_formats = None
    record_count = Counter()

    for line_index, line in enumerate(file_h):
        line_info = LineInfo(file_name, line_index+1, line)
        line = line.strip()

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
                raise_multiple('VARS', line_info)

            column_names = fields
            records.append(DbRecord(record_count[record_type], record_type, column_names))
            handled = True

        if record_type == 'FORMAT':
            column_formats = formats_to_constructors(fields, line_info)

            if record_count[record_type] != 1:
                raise_multiple('FORMAT', line_info)

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
                raise_data_before_format(line_info)

        if not handled:
            records.append(DbRecord(record_count[record_type], record_type, fields))


    return DbFile(file_name, records)


def find_nth(haystack, needle, n):
    start = haystack.find(needle)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start+len(needle))
        n -= 1
    return start

def build_values_or_raise(column_formats, column_names, fields, line_info):
    non_index_column_formats = check_column_count_raise_if_bad(column_formats, column_names, line_info)
    result = []
    field_count = Counter()
    for column_no, (raw_field, constructor) in enumerate(zip(fields, non_index_column_formats)):
        try:
            field_count[raw_field] += 1
            value = constructor(raw_field)

        except Exception:
            absolute_column = find_nth(line_info.line, raw_field, field_count[raw_field])
            msg = f"""
                    Couldn't convert {raw_field} to type {constructor_to_name(constructor)}
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


def raise_multiple(format_str, line_info):
    msg = f"""\
                bad NMRPipe db file, multiple {format_str} statements found
                file: {line_info.file_name}
                line no: {line_info.line_no}
                line: {line_info.line}
                """
    msg = dedent(msg)

    if format_str == 'VARS':
        raise MultipleVars(msg)
    elif format_str == 'FORMAT':
        raise MultipleFormat(msg)



def check_var_and_format_count_raise_if_bad(column_names, column_formats, line_info):
    if column_names is None:
        msg = f'''\
               no column names defined by a VARS line when FORMAT line read
               file: {line_info.file_name}
               line no: {line_info.line_no}
               line: {line_info.line}'''
        msg = dedent(msg)
        raise NoVarsLine(msg)

    num_formats = len(column_names)
    num_column_names = len(column_formats)
    if num_formats != num_column_names:
        msg = f'''\
                  number of column names and formats must agree
                  got {num_column_names} column names and {num_formats} formats
                  file: {line_info.file_name}
                  line no: {line_info.line_no}
                  line: {line_info.line}
               '''
        msg = dedent(msg)

        raise WrongColumnCount(msg)


def check_column_count_raise_if_bad(column_formats, column_names, line_info):
    non_index_column_formats = column_formats[1:]
    raw_fields = line_info.line.split()
    num_fields = len(raw_fields)
    num_columns = len(non_index_column_formats) + 1

    missing_fields = ['*'] * abs(num_fields - num_columns)
    raw_fields = [*raw_fields, *missing_fields]

    if num_fields != num_columns:
        column_formats = constructor_names(column_formats)
        tab = [
            column_names,
            column_formats,
            raw_fields,

        ]
        tabulated = tabulate(tab, tablefmt='plain')
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
    return non_index_column_formats



@dataclass
class LineInfo:
    file_name: str
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


def formats_to_constructors(formats, line_info):
    result = []

    field_counter = Counter()
    for column_index, field_format in enumerate(formats):
        field_counter[field_format] += 1
        field_format = field_format.strip()
        field_format = field_format[-1]

        if field_format == 'd':
            result.append(int)
        elif field_format == 'f':
            result.append(float)
        elif field_format == 's':
            result.append(str)
        else:
            format_column = find_nth(line_info.line, field_format, field_counter[field_format])
            msg = f'''
                unexpected format {field_format} at index {column_index+1}, expected formats are s, d, f (string, integer, float)
                file: {line_info.file_name}
                line no: {line_info.line_no}
                line: {line_info.line}
                      {' ' * format_column + '^'}
                
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


class NoVarsLine(BadNmrPipeFile):
    pass


class NoFormatLine(BadNmrPipeFile):
    pass


class MultipleVars(BadNmrPipeFile):
    pass


class MultipleFormat(BadNmrPipeFile):
    pass


class DataBeforeFormat(BadNmrPipeFile):
    pass
