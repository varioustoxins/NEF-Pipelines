import os
from math import floor
from pathlib import Path
from textwrap import dedent
from typing import List, Optional

import typer
from pynmrstar import Entry
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import SelectionType, select_frames
from nef_pipelines.lib.sequence_lib import count_residues, frame_to_chains
from nef_pipelines.lib.typer_utils import get_args
from nef_pipelines.lib.util import chunks, exit_error, get_pipe_file
from nef_pipelines.tools.frames import frames_app

UNDERSCORE = "_"

parser = None


def _if_is_nef_file_load_as_entry(file_path):
    entry = None
    try:
        entry = Entry.from_file(file_path)
    except Exception:
        pass

    return entry


# noinspection PyUnusedLocal
@frames_app.command()
def list(
    pipe: Path = typer.Option(
        None,
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="read NEF data from a file instead of stdin",
    ),
    selector_type: SelectionType = typer.Option(
        SelectionType.ANY,
        "-t",
        "--selector-type",
        help=f"force how to select frames can be one of {', '.join(SelectionType.__members__)}",
    ),
    number: bool = typer.Option(False, "-n", "--number", help="number entries"),
    verbose: int = typer.Option(
        False,
        "-v",
        "--verbose",
        count=True,
        help="print verbose information more verbose options give more information",
    ),
    filters: Optional[List[str]] = typer.Argument(
        None, help="filters string for entry names and categories to list"
    ),
):
    """- list the frames in the current input"""

    entry = None
    if len(filters) > 0:
        entry = _if_is_nef_file_load_as_entry(filters[0])
        if entry is not None:
            if pipe:
                msg = f"""\
                   two nef file paths supplied...
                       path 1: {pipe} [from --in]
                       path 2: {filters[0]} [from args]"""
                msg = dedent(msg)
                exit_error(msg)
            else:
                pipe = filters[0]
                filters = filters[1:]
    if not filters:
        filters = [
            "*",
        ]

    args = get_args()

    if entry is None:
        pipe_file = get_pipe_file(args)
        raw_lines = pipe_file.readlines()
        lines = "".join(raw_lines)

        try:
            entry = Entry.from_string(lines)
        except Exception as e:
            exit_error(f"failed to read nef file {args.pipe} because", e)

    if entry is None:
        if args.pipe is not None:
            exit_error(f"couldn't read a nef stream from the file: {args.pipe}")
        elif len(filters) > 0:
            exit_error(f"couldn't read a nef stream from either {filters[0]} or stdin")
        else:
            exit_error("couldn't read a nef stream from stdin")

    print(f"entry {entry.entry_id}")
    if verbose:

        import hashlib

        md5 = hashlib.md5(lines.encode("ascii")).hexdigest()
        print(f"    lines: {len(raw_lines)} frames: {len(entry)} checksum: {md5} [md5]")
    print()

    frames = select_frames(entry, selector_type, filters)

    if verbose == 0:
        frame_names = [frame.name for frame in frames]
        if number:
            frame_names = [
                f"{i}. {frame_name}"
                for i, frame_name in enumerate(frame_names, start=1)
            ]

        frame_list = _string_list_to_tabulation(frame_names)
        print(tabulate(frame_list, tablefmt="plain"))

    else:

        for frame in enumerate(frames, start=1):

            filters = [f"*{filter}*" for filter in filters]

            if verbose == 0:
                frame_names = [
                    f"{i}. {frame.name}" for i, frame_name in enumerate(frames, start=1)
                ]

                frame_list = _string_list_to_tabulation(frame_names)
                print(tabulate(frame_list, tablefmt="plain"))

                print(f"    category: {frame.category}")
                if len(frame.name) != len(frame.category):
                    print(
                        f"    name: {frame.name[len(frame.category):].lstrip(UNDERSCORE)}"
                    )

                loop_lengths = []
                for loop in frame.loop_dict:
                    loop_lengths.append(str(len(loop)))

                loops = ""
                if len(loops) == 1:
                    loops = " [length: 1]"
                else:
                    loops = f' [lengths: {", ".join(loop_lengths)}]'

                print(f"    loops: {len(frame.loop_dict)}{loops}")

                frame_standard = frame.name[: len("nef")]
                is_standard_frame = frame_standard == "nef"
                print(f"    is nef frame: {is_standard_frame}")

                # ccpn_compound_name
                if verbose == 2 and frame.category == "nef_molecular_system":
                    chains = frame_to_chains(frame)

                    print(f'    chains: {len(chains)} [{", ".join(chains)}]')

                    residue_counts = {}
                    for chain in chains:
                        residue_counts[chain] = count_residues(frame, chain)

                    residue_count_per_chain = {}
                    for chain in chains:
                        residue_count_per_chain[chain] = sum(
                            residue_counts[chain].values()
                        )

                    output = [
                        f"{chain} {num_residues}"
                        for chain, num_residues in residue_count_per_chain.items()
                    ]
                    print(f'    residues: {", ".join(output)}')

                    for chain in chains:
                        counts_and_percentages = []

                        for residue, count in residue_counts[chain].items():
                            percentage = (
                                f"{count/ residue_count_per_chain[chain]*100:5.2f}"
                            )
                            counts_and_percentages.append(
                                f"{residue}: {count} [{percentage}%]"
                            )

                        pre_string = f"              {chain}. "
                        pre_string_width = len(pre_string)

                        tabulation = _string_list_to_tabulation(
                            counts_and_percentages, pre_string_width
                        )
                        table = tabulate(tabulation, tablefmt="plain")

                        print(_indent_with_prestring(table, pre_string))

    print()


def _indent_with_prestring(text_block, pre_string):
    raw_result = []
    empty_prestring = " " * len(pre_string)
    for i, string in enumerate(text_block.split("\n")):
        if i == 0:
            raw_result.append(f"{pre_string}{string}")
        else:
            raw_result.append(f"{empty_prestring}{string}")

    return "\n".join(raw_result)


def _string_list_to_tabulation(frame_names, used_columns=0):
    try:
        width, _ = os.get_terminal_size()
    except Exception:
        width = 100

    width -= used_columns

    # apply a sensible minimum width
    if width < 20:
        width = 20

    if len(frame_names) > 0:
        frame_name_widths = [len(frame_name) for frame_name in frame_names]
        max_frame_name_width = max(frame_name_widths)

        columns = int(floor(width / (max_frame_name_width + 1)))
        column_width = int(floor(width / columns))

        columns = 1 if columns == 0 else columns

        frame_names = [frame_name.rjust(column_width) for frame_name in frame_names]
        frame_name_list = chunks(frame_names, columns)
    else:
        frame_name_list = [[]]

    return frame_name_list
