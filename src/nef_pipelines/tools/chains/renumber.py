from itertools import tee
from pathlib import Path
from typing import List

import typer
from typer import Argument, Option

from nef_pipelines.lib.nef_lib import (
    NEF_MOLECULAR_SYSTEM,
    SELECTORS_LOWER,
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.sequence_lib import sequence_from_frame
from nef_pipelines.lib.util import chunks, end_with_ordinal, exit_error, is_int
from nef_pipelines.tools.chains import chains_app

app = typer.Typer()

CHAIN_CODE = "chain_code"

SEQUENCE_CODE = "sequence_code"


# noinspection PyUnusedLocal
@chains_app.command()
def renumber(
    chain_offsets: List[str] = Argument(
        None,
        metavar="<CHAIN-CODE> <OFFSET/START>",
        help="chain-codes and offsets/starts for renumbering residue numbers, offsets are used by default and chain "
        "starts are available using the --starts option",
    ),
    input: Path = typer.Option(
        Path("-"),
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="where to read NEF data from either a file or stdin '-'",
    ),
    selector_type: SelectionType = typer.Option(
        SelectionType.ANY,
        "-s",
        "--selector",
        help=f"control how to select frames to renumber, can be one of: {SELECTORS_LOWER}. "
        "Any will match on names first and then if there is no match attempt to match on category",
    ),
    starts: bool = Option(
        False,
        "-s",
        "--starts",
        help="renumber residues using a starting value for the chain "
        "rather than an offset",
    ),
    frame_selectors: List[str] = Option(
        None,
        "-f",
        "--frames",
        metavar="<FRAME-SELECTOR>",
        help="Limit changes to a particular frame by name or category [the selector], note: wildcards are "
        "allowed. Frames are selected by name and then category if the name doesn't match"
        " [the option -t /--selector-type allows you to choose which selection type to use]. If no frame"
        "selectors are provided all frames are renumbered",
    ),
):
    """- renumber chains in a nef file"""

    chain_offsets = get_chain_offset_pairs_or_exit(chain_offsets)

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    if starts:
        molecular_system_frames = entry.get_saveframes_by_category(NEF_MOLECULAR_SYSTEM)

        exit_if_molecular_system_isnt_a_singleton(molecular_system_frames)

        molecular_system = molecular_system_frames[0]

        chain_offsets = chain_starts_to_offsets(molecular_system, chain_offsets)

    frames = select_frames(entry, selector_type, frame_selectors)

    offset_chains_in_frames(frames, chain_offsets, starts)

    print(entry)

    # # get_help()
    #
    # # typer_click_object = typer.main.get_command(chains_app)
    # # print(chains_app.typer_instance)
    # print(typer_click_object.command()())


def chain_starts_to_offsets(molecular_system, chain_offsets):
    result = []
    for chain, start in chain_offsets:
        sorted_residues = sorted(sequence_from_frame(molecular_system, chain))

        for residue in sorted_residues:

            if is_int(residue.sequence_code):
                start_sequence_code = int(sorted_residues[0].sequence_code)
                break

        result.append([chain, start - start_sequence_code])

    return result


# def chain_starts_to_offsets(molecular_system, chain_offsets):
#     result = []
#     for chain, start in chain_offsets:
#         sorted_residues = sorted(sequence_from_frame(molecular_system, chain))
#
#         if len(sorted_residues) > 0:
#             start_sequence_code = int(sorted_residues[0].sequence_code)
#
#             result.append([chain, start - start_sequence_code])
#
#     return result


def exit_if_molecular_system_isnt_a_singleton(molecular_system_frames):
    number_of_molecular_system_frames = len(molecular_system_frames)
    if number_of_molecular_system_frames == 0:
        exit_error("there must be a molecular system defined to use the starts option")
    elif number_of_molecular_system_frames > 1:
        # could go ahead and combine but warn of inconsistent results
        exit_error(
            "there can only be one  molecular system frame defined in a NEF file"
        )


def offset_chains_in_frames(frames, chain_offsets, starts):
    for frame in frames:
        for chain, offset in chain_offsets:
            offset_residue_numbers(frame, chain, offset)


def get_chain_offset_pairs_or_exit(chain_offsets):

    if not chain_offsets:
        exit_error("you didn't provide any chains and offsets/starts")

    # tee here as we use the chain_offsets generator twice
    chain_offsets_check, chain_offsets = tee(chunks(chain_offsets, 2))

    for chain_offset in chain_offsets_check:
        if len(chain_offset) % 2:
            chain_offset_pairs = []

            for chain_offset in chain_offsets:
                chain_offset_pairs.append(":".join(chain_offset))

            msg = f"""\
                there must be an offset/start for each chain
                i got the following pairs of chain:offset/start: {', '.join(chain_offset_pairs)}
                the last one is missing an offset.
            """
            exit_error(msg)

    result = []
    for i, (chain, offset) in enumerate(chain_offsets, start=1):

        exit_if_offset_isnt_int(chain, offset, i)

        offset = int(offset)

        result.append((chain, offset))

    return result


def exit_if_offset_isnt_int(chain, offset, i):
    if not is_int(offset):
        msg = f"""\
                the offset/start {offset} in the {end_with_ordinal(i)} chain offset/start pair: {chain} {offset}
                can't be converted to an int
            """
        exit_error(msg)


def exit_if_chains_and_offsets_dont_match(chains, offsets):
    num_chains = len(chains)
    num_offsets = len(offsets)
    if num_chains != num_offsets:
        msg = f"""\
            chains and offsets must have the same length i got {num_chains} chains and {num_offsets}
            chains: {','.join(chains)}
            offsets: {','.join([str(offset) for offset in offsets])}
        """
        exit_error(msg)


def offset_residue_numbers(frame, chain, offset, starts=False):

    for loop_data in frame.loop_dict.values():
        for tag in loop_data.tags:
            if tag_is_based_on(tag, SEQUENCE_CODE):
                sequence_index = loop_data.tag_index(tag)

                chain_code_tag = tag_based_on(tag, SEQUENCE_CODE, CHAIN_CODE)
                chain_code_index = loop_data.tag_index(chain_code_tag)
                for line in loop_data:
                    if chain_code_index is not None and line[chain_code_index] == chain:
                        sequence = line[sequence_index]
                        if is_int(sequence):
                            sequence = int(sequence)
                            sequence = sequence + offset
                            line[sequence_index] = str(sequence)


def tag_based_on(tag, base, substitute):
    column_code = tag[len(base) :]
    new_tag = f"{substitute}{column_code}"
    return new_tag


def tag_is_based_on(tag, base):
    return tag.startswith(base)


#
#
# def read_args():
#     global parser
#     parser = argparse.ArgumentParser(
#         description="Add chemical shift errors to a NEF file"
#     )
#     parser.add_argument(
#         "-c",
#         "--chain",
#         metavar="CHAIN",
#         type=str,
#         default="A",
#         dest="chain",
#         help="chain in which to offset residue numbers",
#     )
#     parser.add_argument(
#         "-o",
#         "--offset",
#         metavar="OFFSET",
#         type=int,
#         default=0,
#         dest="offset",
#         help="offset to add to residue numbers",
#     )
#     parser.add_argument(metavar="FILES", nargs=argparse.REMAINDER, dest="files")
#
#     return parser.parse_args()
#
#
# def check_stream():
#     # make stdin a non-blocking file
#     fd = sys.stdin.fileno()
#     fl = fcntl.fcntl(fd, fcntl.F_GETFL)
#     fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
#
#     try:
#         result = sys.stdin.read()
#     except Exception:
#         result = ""
#
#     return result
#
#
# if __name__ == "__main__":
#
#     args = read_args()
#
#     is_tty = sys.stdin.isatty()
#
#     if is_tty and len(args.files) == 0:
#         parser.print_help()
#         print()
#         msg = """I require at least 1 argument or input stream with a chemical_shift_list frame"""
#
#         exit_error(msg)
#
#     entries = []
#     try:
#         if len(args.files) == 0:
#             lines = check_stream()
#             if len(lines) != 0:
#                 entries.append(Entry.from_string(lines))
#             else:
#                 exit_error("Error: input appears to be empty")
#         else:
#             for file in args.files:
#                 entries.append(Entry.from_file(file))
#     except OSError as e:
#         msg = f"couldn't open target nef file because {e}"
#         exit_error(msg)
#
#     for entry in entries:
#         offset_residue_numbers(entry, args.chain, args.offset)
#
#         # print(entry)
