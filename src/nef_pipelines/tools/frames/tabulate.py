# TODO: tests on output to multiple files
#       better default formatting of headings for table formats that can support spaces
#       headers/dividers if mutiple frames are to be output into the same file / stream

import csv
import re
import sys
from collections import Counter
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List

import typer
import wcmatch.fnmatch as fnmatch
from fyeah import f
from ordered_set import OrderedSet
from tabulate import tabulate as tabulate_formatter

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.typer_utils import get_args
from nef_pipelines.lib.util import (
    STDOUT,
    exit_error,
    is_int,
    parse_comma_separated_options,
)
from nef_pipelines.tools.frames import frames_app

NO_FLAGS = 0x0000
ALL_LOOPS = "*"

UNDERSCORE = "_"

parser = None

EXIT_ERROR = 1

FORMAT_TO_EXTENSION = {
    "csv": "csv",
    "fancy_grid": "txt",
    "fancy_outline": "txt",
    "github": "md",
    "grid": "txt",
    "html": "html",
    "latex": "tex",
    "latex_booktabs": "tex",
    "latex_longtable": "tex",
    "latex_raw": "tex",
    "mediawiki": "txt",
    "moinmoin": "txt",
    "orgtbl": "org",
    "pipe": "txt",
    "plain": "txt",
    "presto": "presto",
    "pretty": "txt",
    "psql": "mkd",
    "rst": "rst",
    "simple": "txt",
    "textile": "textile",
    "tsv": "tsv",
    "unsafehtml": "html",
}

formats = list(FORMAT_TO_EXTENSION)
FORMAT_HELP = f"""
    format for the table, [possible formats are: {", ".join(formats)}: most of those provided by tabulate, if you
    require other formats provided by tabulate contact the authors]
"""
FRAME_AND_LOOP_SELECTOR_HELP = """
Selectors for frames and loops to tabulate. Multiple frames and loops can be selected. Frame names and loop categories /
indices are separated by a dot [e.g. frame-name.loop-category or frame-name.loop-index]. Wild cards are allowed and are
attached to the start and end of the frame-names and loop-categories by default when searching. Specific loops can be
chosen by index or loop category. Exact matching of frame names and loop categories can be made using the --exact
option. Details of frames in a file loops can be listed using 'nef frame list -vvv'
"""

# meaningful matches
# 1. nothing == * all frames and loops                         *
# 2. an exact frame name: all loops within that frame          bens_data
# 3. a frame category: all loops within that frame             nef_nmr_spectrum
# 4. a loop category                                           nmr_peaks
# 5. a loop name and index                                     bens_data.1
# 6. a frame name and a loop category                          bens_data.nmr_peaks
# 7. a frame category and a loop category                      nef_nmr_spectrum.nmr_peaks]
# 8. a frame category and a loop index                         for all frames of the category the nth loop - meaningful
#                                                              loops can appear in any order
# 9. a frame name and a loop index
#
# Loop category	Loop index	Loop category and index	No loop id
# save frame name	6	9	X	2
# save frame category	7	8	X	3
# No save frame id	4	X	5	1

# form the point of grammar
# 1            2                3         a               b            c
# <frame-name>|<frame-category>|<nothing>.<loop-category>|<loop-index>|<nothing>
# 9 possibilities
# x 1a. <frame-name>.<loop-category>       - can contain dots? -> higher priority
# x 1b. <frame-name>.<loop-index>          - frame name can contain dots look for the name with dots first
# x 1c. <frame-name>                       - can coontain dots! -> higher priotity
# x 2a. <frame-category>.<loop-category>   - either can contain dots so higher priority but lower than a names()
# x 2b. <frame-category>.<loop-index>      - not sure its menaingful, unless loops are ordered in all frames in a file
# x 2c. <frame-category>                   - all loops in a particular frame type
# x 3a. <loop-category>                    - every case of that loop
# 3b. <loop-index>                          - not useful it would be the nth loop of all frames!
# x 3c. <nothing>.<nothing>                - all frames all loops
# ** plus one more loop-category + index
#
# nothing == wildcard
# priority
# frame-names | loop-categories >  frame-categories > fame-nothing > loop-index > loop-nothing
#
# so search order would be
# 3c nothing-nothing                           - everything
# 1a frame-name.loop-category                  - can contain dots and numbers so high priority, add wild cards to all
#                                                all components
# 2a frame-category.loop-category              - can contain dots and numbers so high priority, add wild cards to all
#                                                components
# 1c frame-name                                - can contain dots and numbers so high priority, all loops in the frame
# 3a loop-category                             - can contain dots and numbers so high priority, all loops of the
#                                                category
# 2c frame-category                            - can contain dots and numbers so high priority, all loops for frames of
#                                                the category
# 1b frame-name.loop-index                     - the nth loops in the frame with the name
# 2b frame-category.loop-index                 - the nth loop for all frames with the category                       -
# loop-category.index                          - the nth loop with the category


ABBREVIATED_HEADINGS = {
    "index": "ind",
    "chain_code": "chain",
    "sequence_code": "seq",
    "residue_name": "resn",
    "linking": "link",
    "cis_peptide": "cis",
    "ccpn_compound_name": "ccpn_name",
    "ccpn_chain_role": "ccpn_role",
    "ccpn_comment": "comment",
    "ccpn_dataset_serial": "data_serial",
    "program_name": "name",
    "program_version": "version",
    "script_name": "script",
    "peak_id": "id",
    "volume": "vol",
    "volume_uncertainty": "vol-err",
    "height_uncertainty": "height-err",
    "position": "pos",
    "position_uncertainty": "pos-err",
    "ccpn_figure_of_merit": "merit",
    "ccpn_annotation": "ann",
    "ccpn_peak_list_serial": "ccpn-serial",
    "atom_name": "atom",
    "isotope_number": "iso",
    "value_uncertainty": "err",
    "element": "elem",
}
SELECT_HELP = """
    a list of columns to select for output, to specify multiple columns specify the option multiple times or use a comma
    separated list. Prepend columns to exclude with - and columns to include with a +. If neither a + or - is prepended
    to a column a + is assumed, a -- at the start of a column name is treated as an escape for a - at the start of a
    columns name. Wildcards are applied before and after the selections if the --exact option is not specified.
"""

OUT_HELP = """
    file or files to write to including templates, the place holders {entry} {frame} and {loop} will get replaced the
    current entry id frame name and loop category, if multiple frame names and loop names apply multiple files maybe
    output
"""

ABBREVIATE_HELP = """
    abbreviate column headings. Also convert _ to - in  formats wich require single word headings such as csv and tsv
"""


class ColumnSelectionType(Enum):
    INCLUDE = auto()
    EXCLUDE = auto()


# noinspection PyUnusedLocal
@frames_app.command(no_args_is_help=True)
def tabulate(
    input_file: Path = typer.Option(
        None,
        "--in",
        metavar="|PIPE|",
        help="pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]",
    ),
    out_format: str = typer.Option(
        "plain", "-f", "--format", help=FORMAT_HELP, metavar="format"
    ),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="include frame names etc in output"
    ),
    full: bool = typer.Option(
        False, "--full", help="don't suppress empty columns [default: False]"
    ),
    exact: bool = typer.Option(
        False,
        "--exact",
        help="when matching frames and categories do it exactly",
    ),
    no_title: bool = typer.Option(
        False, "--no-title", help="don't display the frame name as a title"
    ),
    select_columns: List[str] = typer.Option(["+*"], help=SELECT_HELP),
    out: str = typer.Option(str(STDOUT), help=OUT_HELP),
    abbreviate: bool = typer.Option(False, "--abbreviate", help=ABBREVIATE_HELP),
    frame_loop_selectors: List[str] = typer.Argument(
        None, help=FRAME_AND_LOOP_SELECTOR_HELP, metavar="<frame-and-loop-selectors>..."
    ),
):
    """
    - tabulate loops from frames in a NEF file. notes: 1. using the name of a frame as a selector will tabulate all
      in the frame while using frame.loop_index [e.g. molecular_system.1] or frame.loop_name [e.g. shift_frame_HN.peaks]
      will tabulate a specific loop. 2. wild cards can be used for frame names e.g. mol*tem would select
      molecular_system and any other frame whose name contains mol followed by sys and is case-insensitive 3. all loop
      and frame selector components are surrounded by *'s before use unless the --exact option is used 3. by default
      empty columns are ignored unless the option --full is used"""

    args = get_args()

    if not args.frame_loop_selectors:
        args.frame_loop_selectors = [
            ALL_LOOPS,
        ]

    args.select_columns = _build_column_selections(args.select_columns, args.exact)

    args.frame_loop_selectors = parse_comma_separated_options(args.frame_loop_selectors)

    entry = read_or_create_entry_exit_error_on_bad_file(args.input_file)

    tabulate_frames(entry, args)


def _build_column_selections(column_selections, exact):
    column_selections = parse_comma_separated_options(column_selections)

    curated_column_selections = []

    SIMPLE_SELECTIONS = {
        "": (ColumnSelectionType.INCLUDE, "*"),
        "*": (ColumnSelectionType.INCLUDE, "*"),
        "-": (ColumnSelectionType.EXCLUDE, "*"),
        "+": (ColumnSelectionType.INCLUDE, "*"),
        "-*": (ColumnSelectionType.EXCLUDE, "*"),
        "+*": (ColumnSelectionType.INCLUDE, "*"),
    }
    for column_selection in column_selections:
        if column_selection in SIMPLE_SELECTIONS:
            curated_column_selections.append(SIMPLE_SELECTIONS[column_selection])
            continue
        if column_selection.startswith("--"):
            curated_column_selections.append(
                (ColumnSelectionType.INCLUDE, column_selection)
            )
            continue
        if column_selection.startswith("+"):
            curated_column_selections.append(
                (ColumnSelectionType.INCLUDE, column_selection[1:])
            )
            continue
        if column_selection.startswith("-"):
            curated_column_selections.append(
                (ColumnSelectionType.EXCLUDE, column_selection[1:])
            )
            continue
        if not column_selection[0] in ("-", "+"):
            curated_column_selections.append(
                (ColumnSelectionType.INCLUDE, column_selection)
            )
            continue

    expanded_curated_selections = []
    if not exact:
        for action, selection in curated_column_selections:
            if len(selection) > 1 and not selection.endswith("*"):
                selection = f"{selection}*"
            if len(selection) > 1 and not selection.startswith("*"):
                selection = f"*{selection}"
            expanded_curated_selections.append((action, selection))
        curated_column_selections = expanded_curated_selections

    return curated_column_selections


def tabulate_frames(entry, args):
    frames_and_loops_to_tabulate = _select_chosen_frames_and_loops(
        entry, args.frame_loop_selectors, args.exact
    )

    seen_files = set()
    for frame_name, loop_category in frames_and_loops_to_tabulate:

        frame = [frame for frame in entry.frame_list if frame.name == frame_name][0]
        loop = frame.get_loop(loop_category)
        frame_category = frame.category
        category_length = len(frame_category)
        frame_id = frame.name[category_length:].lstrip("_")
        frame_id = frame_id.strip()
        frame_id = frame_id if len(frame_id) > 0 else ""

        _output_loop(loop, frame_id, frame.category, entry.entry_id, args, seen_files)


def _remove_empty_columns(tabulation, headers):

    counter = Counter()
    for row in tabulation:
        for i, header in enumerate(headers):
            if row[i] != UNUSED:
                counter[i] += 1

    empty_columns = []
    for column_index, heading in enumerate(headers):
        if not counter[column_index]:
            empty_columns.append(column_index)

    empty_columns = list(reversed(empty_columns))

    for row in tabulation:
        for column_index in empty_columns:
            del row[column_index]

    for column_index in empty_columns:
        del headers[column_index]

    return tabulation, headers


class OutputFormat(Enum):
    PER_ENTRY = auto()
    PER_FRAME = auto()
    PER_LOOP = auto()
    STDOUT = auto()


# from bing chatgpt
def _replace_quoted_string(string):
    return re.sub(r"`([^`]+)`", r"::\1", string)


def _output_loop(loop_data, frame_id, frame_category, entry_id, args, seen_files):

    out_type = _get_out_type_or_exit_error(args.out)

    entry = entry_id  # noqa F841
    frame = f"{frame_category}_{frame_id}"  # noqa F841
    loop = loop_data.category.lstrip("_")  # noqa F841
    file_extension = FORMAT_TO_EXTENSION[args.out_format]
    expanded_file_name = f(args.out)
    out_name = f"{expanded_file_name}.{file_extension}"
    out_name = _replace_quoted_string(out_name)

    if out_type == OutputFormat.STDOUT:
        out_file = sys.stdout
    else:
        append = out_name in seen_files
        if not append:
            out_file = open(out_name, "wt")
            seen_files.add(out_name)
        else:
            out_file = open(out_name, "at")

    if args.verbose:
        print()
        if frame_id:
            print(f"{frame_id}: {frame_category}/{loop_data.category[1:]}")
        else:
            print(f"{frame_category}/{loop_data.category[1:]}")
        print()
    table = []

    headers = loop_data.tags
    used_headers = _get_selected_columns(headers, args.select_columns, args.exact)

    if used_headers and loop_data.data:
        for line in loop_data.data:
            row = list(line)
            out_row = []
            for column_index, (column, header) in enumerate(zip(row, headers)):
                if header in used_headers:
                    out_row.append(column)
            table.append(out_row)

        if not args.full:
            table, used_headers = _remove_empty_columns(table, used_headers)

        frame_category = loop_data.category.lstrip("_")
        if args.abbreviate:
            used_headers = _abbreviate_headers(used_headers, ABBREVIATED_HEADINGS)

        if not args.no_title:
            if len(frame_id.strip()) == 0:
                title = f"{frame_category}"
            else:
                title = f"{frame_id} [{frame_category}]"
            print(title)
            print("-" * len(title))
            print()

        if args.out_format in ["csv", ""]:
            writer = csv.writer(out_file, lineterminator="\n")
            used_headers = [header.strip() for header in used_headers]
            writer.writerow(used_headers)
            for row in table:
                writer.writerow(row)
        else:
            print(
                tabulate_formatter(
                    table, headers=used_headers, tablefmt=args.out_format
                ),
                file=out_file,
            )

        if out_type == OutputFormat.STDOUT:
            print()
        else:
            out_file.close()


def _get_selected_columns(headers, columns_selections, exact):

    selected_columns = set(headers)
    match_flags = fnmatch.IGNORECASE if not exact else NO_FLAGS

    for selection_type, selection_string in columns_selections:
        current_selections = set(
            [
                header
                for header in headers
                if fnmatch.fnmatch(header, selection_string, flags=match_flags)
            ]
        )

        if selection_type == ColumnSelectionType.INCLUDE:
            selected_columns.update(current_selections)
        else:
            selected_columns.difference_update(current_selections)

    # this ensures the columns are in the order in the file
    result = []
    for header in headers:
        if header in selected_columns:
            result.append(header)

    return result


def _get_out_type_or_exit_error(out_string):

    out_string = str(out_string)
    have_entry = "{entry}" in out_string
    have_frame = "{frame}" in out_string
    have_frame_id = "{frame_id}" in out_string
    have_frame_category = "{frame_category}" in out_string
    if have_frame_id and have_frame_id:
        have_frame = True
    have_loop = "{loop}" in out_string

    if have_loop and not have_frame:
        msg = f"""
            if template contains {{loop}} it must also contain either {{frame}}...
            the output template was {out_string}
        """
        exit_error(msg)

    if (have_frame_id and not have_frame_category) or (
        have_frame_category and not have_frame_id
    ):
        msg = f"""
            if you have frame_id you must have frame_category and vice versa
            the output template was {out_string}
        """
        exit_error(msg)

    output_type = OutputFormat.PER_ENTRY

    if have_frame:
        output_type = OutputFormat.PER_FRAME
    if have_loop:
        output_type = OutputFormat.PER_LOOP
    if have_entry:
        output_type = OutputFormat.PER_ENTRY

    if out_string == "-":
        output_type = OutputFormat.STDOUT

    return output_type


def _abbreviate_headers(headers: List[str], abbreviations: Dict[str, str]) -> List[str]:

    result = []

    for header in headers:
        for stem in abbreviations:

            if header.startswith(stem):

                header = f"{abbreviations[stem]}{header[len(stem):]} "

        result.append(header.replace("_", "-"))

    return result


def _select_chosen_frames_and_loops(entry, frame_selectors, exact):
    loops_to_tabulate = OrderedSet()

    # match on everything most probably we ough to use a sentinal instead such as *
    if len(frame_selectors) == 0:
        for frame in entry.frame_dict.values():
            for loop in frame.loops:
                loops_to_tabulate.add((frame.name, loop.category))

    else:
        match_flags = fnmatch.IGNORECASE if not exact else NO_FLAGS
        for frame_selector in frame_selectors:

            matched = False
            for frame_name, frame_data in entry.frame_dict.items():

                # check if we can match on the whole thing against a frame name
                if fnmatch.fnmatch(
                    frame_name, f"*{frame_selector}*", flags=match_flags
                ):
                    for loop in frame_data:
                        loops_to_tabulate.add((frame_data.name, loop.category))
                    matched = True
                    break

                # check for match on exact frame and loop category
                if not matched:
                    for loop in frame_data.loops:
                        if fnmatch.fnmatch(
                            f"{frame_name}.{loop.category}",
                            f"*{frame_selector}*",
                            flags=match_flags,
                        ):

                            loops_to_tabulate.add((frame_data.name, loop.category))
                            matched = True
                            break

                # match on inexact frame names and  loop categories
                if not matched:
                    frame_selector_parts = frame_selector.split(".")
                    wildcard_frame_selector = "*".join(frame_selector_parts)
                    for loop in frame_data.loops:
                        if fnmatch.fnmatch(
                            f"{frame_name}.{loop.category}",
                            f"*{wildcard_frame_selector}*",
                            flags=match_flags,
                        ):
                            loops_to_tabulate.add((frame_data.name, loop.category))
                            matched = True
                            break

                # match on frame_name with an index for the loop
                if not matched:
                    frame_selector_parts = frame_selector.split(".")

                    if is_int(frame_selector_parts[-1]):
                        stub_frame_selector = ".".join(frame_selector_parts[:-1])
                        loop_index = int(frame_selector_parts[-1])

                        if fnmatch.fnmatch(
                            frame_name, f"*{stub_frame_selector}*", flags=match_flags
                        ):
                            if loop_index > 0 and loop_index <= len(frame_data.loops):
                                loops_to_tabulate.add(
                                    (
                                        frame_data.name,
                                        frame_data.loops[loop_index - 1].category,
                                    )
                                )
                            matched = True
                            break

            # match on loop category and index
            if not matched:
                matched_count = 0
                selector_parts = frame_selector.split(".")
                if is_int(selector_parts[-1]):
                    category_part = ".".join(selector_parts[:-1])
                    category_index = int(selector_parts[:-1]) + 1
                    for frame_name, frame_data in entry.frame_dict.items():
                        for loop in frame_data.loops:
                            if fnmatch.fnmatch(
                                loop.category, f"*{category_part}*", flags=match_flags
                            ):
                                matched_count += 1
                                if matched_count == category_index:
                                    loops_to_tabulate.add(
                                        (frame_data.name, loop.category)
                                    )
                                    matched = True
                                    break

    return loops_to_tabulate
