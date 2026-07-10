from pathlib import Path
from typing import List, Optional

import typer

from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.util import STDIN
from nef_pipelines.tools.columns import columns_app
from nef_pipelines.tools.columns.columns_structures import ExtractFormat
from nef_pipelines.tools.columns.insert import pipe

#
# TODO: Support full insert syntax:
#      - Combined format: frame.loop:col=@file:col (currently requires paired args)
#      - All value specs: frame.loop:col=1..10, frame.loop:col=A*, etc. (currently only @file)
#      - Note: Imbalanced argument sets are not allowed - must be even pairs


@columns_app.command()
def replace(
    input: Path = typer.Option(
        STDIN,
        "--in",
        metavar="|PIPE|",
        help="read NEF data from a file or stdin",
    ),
    # TODO remove simple format?
    #   ⏺ Agree - SIMPLE format is problematic:
    #
    # Why remove it:
    # 1. Ambiguous - No way to verify you're reading the right data
    # 2. Not self-documenting - What does line 1 represent? No idea.
    # 3. Error-prone - Easy to use wrong file or wrong column
    # 4. Trivial to add header - echo "value" > temp.csv && cat data.txt >> temp.csv
    # 5. CSV is standard - Every tool expects headers
    # 6. Less code to maintain - Remove format parameter, simplify FileValueSpecification
    #
    # If you remove it:
    # - Take out format parameter from replace, columns_cli_lib, columns_lib
    # - Remove ExtractFormat.SIMPLE handling
    # - Remove format field from FileValueSpecification
    # - Update tests to only use CSV
    # - Add migration note: "Use CSV with headers - add a header line to headerless files"
    #
    # The test that uses it (test_replace_from_simple_file) gets removed.
    format: ExtractFormat = typer.Option(
        ExtractFormat.CSV,
        "--format",
        help="csv: first line is header, reads named column; simple: no header, reads all lines as values",
    ),
    selector: Optional[str] = typer.Option(
        None,
        "--selector",
        "-s",
        help="frame.loop selector for the loops to modify",
    ),
    args: List[str] = typer.Argument(
        ...,
        help="alternating selector @file pairs: frame.loop:col @file.csv:col ...",
    ),
) -> None:
    """Replace column values using dat from a file.

    works with pairs of arguments

    `frame.loop:col @file.csv:col [frame.loop:col @file.csv:col...]`

    File Formats:
      --format csv (default): First line is header, reads by column name
        Example file test.csv:
        `
            value uncertainty
            9.99  0.01
            8.88  0.50
        `
        @test.csv:value → reads column "value"

      --format simple: No header, all lines are values
        Example file test.txt:
        `
            9.99
            8.88
        `
        @test.txt reads 9.99 and 8.88

    Missing data Handling:
      - if the target loop has fewer rows than the input, add extra rows with '.' and issue a warning
      - if the input columns has fewer rows than the target loop, extends the input  with '.' and issue a warning

    """

    from nef_pipelines.tools.columns.columns_cli_lib import (
        _parse_replace_arguments_or_exit_error,
    )

    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    column_instructions = _parse_replace_arguments_or_exit_error(
        selector, args, entry, input, format
    )
    entry = pipe(entry, column_instructions)
    print(entry)
