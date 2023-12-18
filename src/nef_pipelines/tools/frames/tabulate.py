import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

import typer
import wcmatch.fnmatch as fnmatch
from pynmrstar import Saveframe
from tabulate import tabulate as tabulate_formatter
from tabulate import tabulate_formats

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.typer_utils import get_args
from nef_pipelines.lib.util import exit_error, is_int, parse_comma_separated_options
from nef_pipelines.tools.frames import frames_app

NO_FLAGS = 0x0000
ALL_LOOPS = "*"


FORMAT_HELP = f'format for the table, [possible formats are: {", ".join(tabulate_formats)}: those provided by tabulate]'
FRAME_AND_LOOP_SELECTOR_HELP = """
Selectors for frames and loops to tabulate. Multiple frames and loops can be selected. Frame names and loop categories /
indices are separated by a dot [e.g. frame-name.loop-category or frame-name.loop-index]. Wild cards are allowed and are
attached to the start and end of the frame-names and loop-categories by defualt when searching. Specific loops can be
chosen by index or loop category. Exact matching of frame names and loop categories can be made using the --exact
option. Details of frames in a file loops can be listed using 'nef frame list -vvv'
"""

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
    "atom-name": "atom",
}
EXCLUDE_HELP = """
    a list of columns to exclude from the output, to specify multiple columns specify
    the option multiple times or use a comma separated list. Wildcards are uses if the --exact
    option is not specified. Exclusions are made before inclusions.
"""

INCLUDE_HELP = """
    a list of columns to include in the output, to specify multiple columns specify
    the option multiple times or use a comma separated list. Wildcards are uses if the --exact
    option is not specified. Exclusions are made before inclusions.
"""

OUT_HELP = """
    file or files to write to including templates, the place holders {entry} {frame} and {loop} will get replaced the
    current entry id frame name and loop category, if multiple frame names and loop names apply multiple files maybe
    output
"""


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
    exclude: List[str] = typer.Option([], help=EXCLUDE_HELP),
    include: List[str] = typer.Option([], help=INCLUDE_HELP),
    no_abbreviations: bool = typer.Option(
        False, "--no-abbreviations", help="dont' abbreviate column headings"
    ),
    frame_loop_selectors: List[str] = typer.Argument(
        None, help=FRAME_AND_LOOP_SELECTOR_HELP, metavar="<frame-and-loop-selectors>..."
    ),
):
    """
    - tabulate loops from frames in a NEF file. notes: 1. using the name of a frame as a selector will tabulate all
    in the frame while using frame.loop_index [e.g. molecular_system.1] or frame.loop_name [e.g. shift_frame_HN.peaks]
    will tabulate a specific loop. 2. wild cards can be used for frame names e.g. mol*tem would select molecular_system
    and any other frame whose name contains mol followed by sys and is case-insensitive 3. all loop and frame selector
    components are surrounded by *'s before use unless the --exact option is used 3. by default empty columns are
    ignored unless the option --full is used"""

    args = get_args()

    if not args.frame_loop_selectors:
        args.frame_loop_selectors = [
            ALL_LOOPS,
        ]

    args.exclude = parse_comma_separated_options(args.exclude)
    args.include = parse_comma_separated_options(args.include)

    if len(args.exclude) == 0 and len(args.include) == 0:
        args.include = [
            "*",
        ]

    entry = read_or_create_entry_exit_error_on_bad_file(args.input_file)

    tabulate_frames(entry, args)


def tabulate_frames(entry, args):
    frames_to_tabulate = _get_frames_to_tabulate(
        entry, args.frame_loop_selectors, args.exact
    )
    frame_indices = _select_loop_indices(args.frame_loop_selectors)

    for frame_name, frame_data in frames_to_tabulate.items():

        frame_category = frame_data.category

        category_length = len(frame_category)

        frame_id = frame_data.name[category_length:].lstrip("_")
        frame_id = frame_id.strip()
        frame_id = frame_id if len(frame_id) > 0 else ""

        for i, loop in enumerate(frame_data.loops, start=1):
            if _should_output_loop(
                i, frame_name, frame_indices, loop.category, args.exact
            ):
                _output_loop(loop, frame_id, loop.category, args)


def _select_loop_indices(frames):
    frame_indices = {}
    for frame_selector in frames:
        frame_selector_index = frame_selector.split(".")
        if len(frame_selector_index) == 1:
            frame_name_selector = frame_selector_index[0]
            frame_indices.setdefault(frame_name_selector, set()).add(ALL_LOOPS)
        elif len(frame_selector_index) == 2:
            frame_name_selector = frame_selector_index[0]
            index = frame_selector_index[1]
            index = int(index) if is_int(index) else index
            frame_indices.setdefault(frame_name_selector, set()).add(index)
        else:
            exit_error(
                f'[frames tabulate] too many fields int the frame selector {".".join(frame_selector)}'
            )
    for frame_selector, indices in frame_indices.items():
        if ALL_LOOPS in indices and len(indices) > 1:
            indices.remove(ALL_LOOPS)
            index_strings = ", ".join([str(index) for index in indices])
            message = f"""
                [frames tabulate] incompatible selections, you selected all loops and a specific index for
                frame: {frame_selector} indices were: {index_strings}
                """

            exit_error(message)

    return frame_indices


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


def _output_loop(loop_data, frame_id, category, args):

    if args.verbose:
        print()
        if frame_id:
            print(f"{frame_id}: {category}/{loop_data.category[1:]}")
        else:
            print(f"{category}/{loop_data.category[1:]}")
        print()
    table = []
    headers = loop_data.tags
    used_headers = []

    match_flags = fnmatch.IGNORECASE if not args.exact else NO_FLAGS
    for header in headers:
        include_column = True
        if args.exact:
            if header in args.exclude:
                include_column = False
        else:
            column_exclusions = [
                fnmatch.fnmatch(header, f"*{exclusion}*", flags=match_flags)
                for exclusion in args.exclude
            ]
            include_column = not any(column_exclusions)

        if args.exact:
            if header in args.include:
                include_column = True
        else:
            column_exclusions = [
                fnmatch.fnmatch(header, f"*{inclusion}*", flags=match_flags)
                for inclusion in args.include
            ]
            include_column = any(column_exclusions)

        if include_column:
            used_headers.append(header)

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
    if not args.no_abbreviations:
        used_headers = _abbreviate_headers(used_headers, ABBREVIATED_HEADINGS)

    if not args.no_title:
        print(frame_category)
        print("-" * len(frame_category))
        print()

    print(tabulate_formatter(table, headers=used_headers, tablefmt=args.out_format))


def _abbreviate_headers(headers: List[str], abbreviations: Dict[str, str]) -> List[str]:

    result = []

    for header in headers:
        for stem in abbreviations:

            if header.startswith(stem):

                header = f"{abbreviations[stem]}{header[len(stem):]} "

        result.append(header.replace("_", "-"))

    return result


def _should_output_loop(index, frame_name, frame_indices, loop_category, exact):

    do_output = False
    match_flags = fnmatch.IGNORECASE if not exact else NO_FLAGS
    for frame_selector in frame_indices:
        if exact:
            matched = frame_name == frame_selector
        else:
            matched = fnmatch.fnmatch(
                frame_name.lstrip("_"), f"*{frame_selector}*", flags=match_flags
            )

        if matched:
            indices = frame_indices[frame_selector]

            if index in indices:
                do_output = True

            if ALL_LOOPS in indices:
                do_output = True

            if exact:
                output_tests = [
                    loop_category.lstrip("_") == target_index
                    for target_index in indices
                ]
            else:
                output_tests = [
                    fnmatch.fnmatch(
                        loop_category, f"*{target_index}*", flags=match_flags
                    )
                    for target_index in indices
                ]

            if any(output_tests):
                do_output = True

            if do_output:
                break

    return do_output


def _count_loop_rows(save_frame: Saveframe) -> int:
    count = 0
    for loop in save_frame.loops:
        count += len(loop)

    return count


def _get_frames_to_tabulate(entry, frame_selectors, exact):

    frames_with_empty_loops = _get_loops_with_empty_frames_and_errors(entry)

    frames_to_tabulate = _select_chosen_frames(entry, frame_selectors, exact)

    _remove_empty_frames_and_warn(frames_to_tabulate, frames_with_empty_loops)

    return frames_to_tabulate


def _remove_empty_frames_and_warn(frames_to_tabulate, frames_with_empty_loops):
    for frame_name in frames_to_tabulate:
        if frame_name in frames_with_empty_loops:
            print(frames_with_empty_loops[frame_name], file=sys.stderr)
    for frame_name in frames_with_empty_loops:
        if frame_name in frames_to_tabulate:
            del frames_to_tabulate[frame_name]


def _select_chosen_frames(entry, frame_selectors, exact):
    frames_to_tabulate = {}
    match_flags = fnmatch.IGNORECASE if not exact else NO_FLAGS
    for frame_name, data in entry.frame_dict.items():
        if len(frame_selectors) > 0:
            for frame_selector in frame_selectors:
                frame_selector = frame_selector.split(".")[0]

                if fnmatch.fnmatch(
                    frame_name, f"*{frame_selector}*", flags=match_flags
                ):
                    frames_to_tabulate[frame_name] = data
        else:

            frames_to_tabulate[frame_name] = data
    return frames_to_tabulate


def _get_loops_with_empty_frames_and_errors(entry):
    frames_with_empty_loops = {}
    for frame_name, data in entry.frame_dict.items():
        if len(data.loops) == 0:
            msg = f"WARNING: frame {frame_name} has no loops and the frame will be ignored"
            frames_with_empty_loops[frame_name] = msg

        if frame_name not in frames_with_empty_loops and _count_loop_rows(data) == 0:
            msg = f"WARNING: frame {frame_name} has loops but they contain no data and the frame will be ignored"
            frames_with_empty_loops[frame_name] = msg
    return frames_with_empty_loops
