import fnmatch
import os
import sys

from tools.frames import frames_app
from lib.util import get_pipe_file, chunks
from lib.sequence_lib import frame_to_chains, count_residues
from math import floor
from pathlib import Path
from pynmrstar import Entry
import argparse
from tabulate import tabulate
from lib.typer_utils import get_args

UNDERSCORE = "_"

parser = None

import typer

# noinspection PyUnusedLocal
@frames_app.command(no_args_is_help=True)
def list(
    pipe: Path = typer.Option(None, metavar='|PIPE|',
                              help='pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]'),
    number: bool = typer.Option(False, '-n', '--number', help='number entries'),
    filter: str = typer.Option(None, '-f', '--filter', help='filter string for entries and categories to show'),
    verbose: int = typer.Option(False, '-v', '--verbose', count=True, help='print verbose information more verbose options give more information')
):
    """- list the frames in the current input"""

    args = get_args()

    pipe_file = get_pipe_file(args)

    if pipe_file:
        raw_lines = pipe_file.readlines()
        lines = ''.join(raw_lines)

        entry = Entry.from_string(lines)

        print(f'entry {entry.entry_id}')
        if verbose:
            import hashlib
            md5=hashlib.md5(lines.encode('ascii')).hexdigest()
            print(f'    lines: {len(raw_lines)} frames: {len(entry)} checksum: {md5} [md5]')
        print()

        frame_names  = [frame_data.name for frame_data in entry.frame_dict.values()]

        if verbose == 0:
            if number:
                frame_names = [f'{i}. {frame_name}' for i, frame_name in enumerate(frame_names, start=1)]

            frame_list = string_list_to_tabulation(frame_names)
            print(tabulate(frame_list, tablefmt='plain'))

        else:
            for i, frame_name in enumerate(frame_names, start=1):
                frame_info = entry.frame_dict[frame_name]
                category = frame_info.category

                extended_filter = f'*{filter}*'
                if filter:
                    if not (fnmatch.fnmatch(frame_name, extended_filter) or  fnmatch.fnmatch(category, extended_filter)):
                        continue

                print(f'    category: {category}')
                if len(frame_name) != len(category):
                    print(f'    name: {frame_name[len(category):].lstrip(UNDERSCORE)}')

                loop_lengths = []
                for loop in frame_info.loop_dict:
                    loop_lengths.append(str(len(loop)))

                loops = ''
                if len(loops) == 1:
                    loops = ' [length: 1]'
                else:
                    loops = f' [lengths: {", ".join(loop_lengths)}]'

                print(f'    loops: {len(frame_info.loop_dict)}{loops}')

                frame_standard = frame_name[:len("nef")]
                is_standard_frame = frame_standard == "nef"
                print(f'    is nef frame: {is_standard_frame}')

                #ccpn_compound_name
                if verbose == 2 and category == 'nef_molecular_system':
                    chains = frame_to_chains(frame_info)

                    print(f'    chains: {len(chains)} [{", ".join(chains)}]')

                    residue_counts  = {}
                    for chain in chains:
                        residue_counts[chain] = count_residues(frame_info, chain)

                    residue_count_per_chain = {}
                    for chain in chains:
                        residue_count_per_chain[chain] = sum(residue_counts[chain].values())

                    output = [f'{chain} {num_residues}' for chain, num_residues in residue_count_per_chain.items()]
                    print(f'    residues: {", ".join(output)}')

                    for chain in chains:
                        counts_and_percentages = []

                        for residue, count in residue_counts[chain].items():
                            percentage  = f"{count/ residue_count_per_chain[chain]*100:5.2f}"
                            counts_and_percentages.append(f"{residue}: {count} [{percentage}%]")

                        pre_string = f"              {chain}. "
                        pre_string_width = len(pre_string)

                        tabulation = string_list_to_tabulation(counts_and_percentages, pre_string_width)
                        table = tabulate(tabulation, tablefmt='plain')

                        print(indent_with_prestring(table, pre_string))

                print()

def indent_with_prestring(text_block, pre_string):
    raw_result = []
    empty_prestring = " "* len(pre_string)
    for i, string in enumerate(text_block.split('\n')):
        if i == 0:
            raw_result.append(f"{pre_string}{string}")
        else:
            raw_result.append(f"{empty_prestring}{string}")

    return "\n".join(raw_result)


def string_list_to_tabulation(string_list, used_columns = 0):
    try:
        width, _ = os.get_terminal_size()
    except:
        width = 100

    width -= used_columns

    # apply a sensible minimum width
    if width < 20:
        width = 20

    frame_name_widths = [len(frame_name) for frame_name in string_list]
    max_frame_name_width = max(frame_name_widths)

    columns = int(floor(width / (max_frame_name_width + 1)))
    column_width = int(floor(width / columns))

    columns = 1 if columns == 0 else columns

    string_list = [frame_name.rjust(column_width) for frame_name in string_list]
    frame_list = chunks(string_list, columns)

    return frame_list
