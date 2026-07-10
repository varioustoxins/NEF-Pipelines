import csv
import io
from enum import auto

import clevercsv
from strenum import StrEnum

from nef_pipelines.tools.columns.columns_lib import (
    TabularFormatResult,
    detect_tabular_format,
)


class CsvLikeFormats(StrEnum):
    """CSV-like formats supported for reading."""

    CSV = auto()
    TSV = auto()
    SSV = auto()
    AUTO = auto()
    csv = auto()
    tsv = auto()
    ssv = auto()
    auto = auto()


HELP_FOR_FORMATS = """\
    CSV like formats that can be read [CSV: comma separated variables, TSV tab separated variables,
    SSV space separated variables, AUTO read file and guess format from contents]
"""

COLUMN_SEPARATORS_MAY_HAVE_CHANGED = (
    "note: column separators shown here may different to those in the original file..."
)


def _get_csv_reader_for_format(csv_format, csv_fp, encoding):
    """Return a csv.reader configured for the given format."""
    if csv_format == CsvLikeFormats.AUTO:
        content = csv_fp.read()
        lines = content.splitlines()

        if not lines:
            return iter([])

        format_result = detect_tabular_format(lines)

        if format_result == TabularFormatResult.RAGGED_WHITESPACE:
            normalized_lines = []
            for line in lines:
                fields = line.split()
                normalized_lines.append("\t".join(fields))
            normalized = "\n".join(normalized_lines)
            reader = csv.reader(io.StringIO(normalized), delimiter="\t")
        elif format_result == TabularFormatResult.CLEVERCSV_AUTO:
            reader = clevercsv.reader(io.StringIO(content))
        elif format_result == TabularFormatResult.UNKNOWN_OR_MESSY:
            reader = csv.reader(io.StringIO(content))
        else:
            reader = clevercsv.reader(io.StringIO(content), dialect=format_result)
    elif csv_format == CsvLikeFormats.TSV:
        reader = csv.reader(csv_fp, delimiter="\t")
    elif csv_format == CsvLikeFormats.CSV:
        reader = csv.reader(csv_fp)
    elif csv_format == CsvLikeFormats.SSV:
        reader = csv.reader(csv_fp, delimiter=" ", skipinitialspace=True)
    else:
        reader = csv.reader(csv_fp, delimiter=" ", skipinitialspace=True)
    return reader
