from copy import copy
from itertools import tee
from pathlib import Path
from textwrap import dedent
from typing import Dict, List, Union

import typer
from pynmrstar import Entry
from tabulate import tabulate
from typer import Argument, Option

from nef_pipelines.lib.nef_lib import (
    NEF_MOLECULAR_SYSTEM,
    SELECTORS_LOWER,
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.sequence_lib import (
    chains_from_frames,
    get_chain_starts,
    select_best_residues_by_info_content,
    sequences_from_frames,
)
from nef_pipelines.lib.util import (
    chunks,
    end_with_ordinal,
    exit_error,
    is_int,
    strings_to_tabulated_terminal_sensitive,
)
from nef_pipelines.tools.chains import chains_app

REFERENCE_FRAMES_HELP = """
frames to find the starting residue of a chain for renumbering when using starts  you can have multiple reference
frames and the lowest residue number found amongst them is used. The option can be repeated  or you can use comma
separated lists of frame names [default: the molecular system frame if present otherwise all frames].
"""

app = typer.Typer()

CHAIN_CODE = "chain_code"

SEQUENCE_CODE = "sequence_code"


# noinspection PyUnusedLocal
@chains_app.command()
def renumber(
    chain_offsets_or_starts: List[str] = Argument(
        None,
        metavar="<CHAIN-CODE> <OFFSET/START>",
        help="chain-codes and offsets/starts for renumbering residue numbers, offsets are used by default and chain "
        "starts are available using the --starts option [default: no selections, no offets; do nothing...]",
        show_default=False,
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
    reference_frame_selectors: List[str] = Option(
        None, "--references", help=REFERENCE_FRAMES_HELP, show_default=False
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
        "note: the option -t /--selector-type allows you to choose which selection type to use. "
        "[default: all frames]",
        show_default=False,
    ),
):
    """- renumber chains in a nef file"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    if not reference_frame_selectors:
        reference_frames = []

    chain_offsets_or_starts = _get_chain_offset_pairs_or_exit_error(
        chain_offsets_or_starts
    )

    reference_frames = _select_reference_frames(entry, reference_frame_selectors)

    _exit_error_if_no_reference_frames(
        entry, reference_frame_selectors, reference_frames
    )

    if starts:
        reference_chains_residues = sequences_from_frames(reference_frames)
        reference_chain_starts = get_chain_starts(reference_chains_residues)
        chain_offsets = _chain_starts_to_offsets(
            reference_chain_starts, chain_offsets_or_starts
        )
    else:
        chain_offsets = chain_offsets_or_starts

    _exit_if_selected_chain_not_in_frames(
        "reference_chain", reference_frames, input, chain_offsets.keys()
    )
    _exit_error_if_no_chain_offsets(chain_offsets_or_starts, reference_frames, input)

    entry = pipe(entry, frame_selectors, selector_type, chain_offsets)

    print(entry)


def pipe(
    entry: Entry,
    frame_selectors: Union[str, List[str]],
    frame_selector_type: SelectionType,
    offsets: Dict[str, int],
) -> Entry:

    frames = select_frames(entry, frame_selectors, frame_selector_type)

    _exit_if_selected_chain_not_in_frames(
        "chain to renumber", frames, input, offsets.keys()
    )

    offset_chains_in_frames(frames, offsets)

    return entry


def _exit_if_selected_chain_not_in_frames(chain_type, frames, input, chains):
    frame_chains = set()
    for frame in frames:
        frame_chains.update(chains_from_frames(frame))
    frame_chain_names = strings_to_tabulated_terminal_sensitive(frame_chains)

    for chain in chains:

        selected_frames = strings_to_tabulated_terminal_sensitive(
            [frame.name for frame in frames]
        )
        if chain not in frame_chains:
            msg = """
                using the input {input}
                the {chain_type} '{chain}' is not in the frames selected for renumbering

                the selected frames are:

                {selected_frames}

                which have the chains

                {frame_chain_names}
                """
            msg = msg.format(
                chain_type=chain_type,
                input=input,
                chain=chain,
                selected_frames=selected_frames,
                frame_chain_names=frame_chain_names,
            )
            exit_error(msg)


def _exit_error_if_no_chain_offsets(chain_offsets, reference_frames, input):
    if not chain_offsets:
        sequences = [sequences_from_frames(frame) for frame in reference_frames]

        all_residues = set()
        for sequence in sequences:
            all_residues.update(sequence)

        all_residues = select_best_residues_by_info_content(all_residues)

        chain_starts = [
            [chain, start] for chain, start in get_chain_starts(all_residues).items()
        ]

        reference_frame_names = strings_to_tabulated_terminal_sensitive(
            [frame.name for frame in reference_frames]
        )

        if chain_starts:
            headings = "chain start".split()
            table = tabulate(chain_starts, headings)
            table_msg = (
                "here are the starts for the chains in the selected reference frames"
            )
        else:
            table = ""
            table_msg = (
                "also no chain starts were found in the selected reference frames"
            )

        msg = """
                in the file {input}
                you didn't provide any chains and offsets/starts
                {table_msg}

                {table}

                the reference frames for sequences and chain starts were

                {reference_frame_names}
            """
        msg = dedent(msg)
        msg = msg.format(
            input=input,
            table=table,
            table_msg=table_msg,
            reference_frame_names=reference_frame_names,
        )

        exit_error(msg)


def _exit_error_if_no_reference_frames(
    entry, reference_frame_selectors, reference_frames
):
    if not reference_frames:
        msg = """
            no reference frames found using the selection:

            {reference_frame_selectors}

            possible frame names are

            {frame_names}
            """
        msg = dedent(msg)
        reference_frame_selectors = ", ".join(reference_frame_selectors)
        reference_frame_selectors = strings_to_tabulated_terminal_sensitive(
            reference_frame_selectors
        )

        frame_names = strings_to_tabulated_terminal_sensitive(
            [frame.name for frame in entry.frame_list]
        )
        msg = msg.format(
            reference_frame_selectors=reference_frame_selectors, frame_names=frame_names
        )

        exit_error(msg)


def _select_reference_frames(entry, reference_frame_selectors):

    if not reference_frame_selectors:
        reference_frames = select_frames(
            entry, NEF_MOLECULAR_SYSTEM, SelectionType.CATEGORY
        )

        if not reference_frames:
            reference_frames = copy(entry.frame_list)
    else:
        reference_frames = []
        for frame_selector in reference_frame_selectors:
            reference_frames += select_frames(entry, frame_selector, SelectionType.ANY)

    return reference_frames


def _chain_starts_to_offsets(current_chains_starts, new_chain_starts):
    result = {}

    for chain, new_start in new_chain_starts.items():
        old_start = current_chains_starts[chain]

        offset = new_start - old_start
        result[chain] = offset

    return result


def exit_if_molecular_system_isnt_a_singleton(molecular_system_frames):
    number_of_molecular_system_frames = len(molecular_system_frames)
    if number_of_molecular_system_frames == 0:
        exit_error("there must be a molecular system defined to use the starts option")
    elif number_of_molecular_system_frames > 1:
        # could go ahead and combine but warn of inconsistent results
        exit_error(
            "there can only be one  molecular system frame defined in a NEF file"
        )


def offset_chains_in_frames(frames, chain_offsets):
    for frame in frames:
        for chain, offset in chain_offsets.items():
            _offset_residue_numbers(frame, chain, offset)


def _exit_multiple_offsets_for_chain(chain, first_offset, second_offset):
    msg = """
        the chain {chain} has more than one offset/start to use for renumbering

        the first offset/start is {first_offset}
        the second offset/start is {second_offset}
        """
    msg = msg.format(
        input=input, chain=chain, first_offset=first_offset, second_offset=second_offset
    )

    exit_error(msg)


def _get_chain_offset_pairs_or_exit_error(chain_offsets):

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

    result = {}
    seen_chains = set()
    for i, (chain, offset) in enumerate(chain_offsets, start=1):

        _exit_if_offset_isnt_int(chain, offset, i)

        offset = int(offset)

        if chain in seen_chains:
            _exit_multiple_offsets_for_chain(
                chain=chain, first_offset=result[chain], second_offset=offset
            )

        seen_chains.add(chain)
        result[chain] = offset

    return result


def _exit_if_offset_isnt_int(chain, offset, i):
    if not is_int(offset):
        msg = f"""\
                the offset/start {offset} in the {end_with_ordinal(i)} chain offset/start pair: {chain} {offset}
                can't be converted to an int
            """
        exit_error(msg)


def _exit_if_chains_and_offsets_dont_match(chains, offsets):
    num_chains = len(chains)
    num_offsets = len(offsets)
    if num_chains != num_offsets:
        msg = f"""\
            chains and offsets must have the same length i got {num_chains} chains and {num_offsets}
            chains: {','.join(chains)}
            offsets: {','.join([str(offset) for offset in offsets])}
        """
        exit_error(msg)


def _offset_residue_numbers(frame, chain, offset):

    for loop_data in frame.loop_dict.values():
        for tag in loop_data.tags:
            if _tag_is_based_on(tag, SEQUENCE_CODE):
                sequence_index = loop_data.tag_index(tag)

                chain_code_tag = _tag_based_on(tag, SEQUENCE_CODE, CHAIN_CODE)
                chain_code_index = loop_data.tag_index(chain_code_tag)
                for line in loop_data:
                    if chain_code_index is not None and line[chain_code_index] == chain:
                        sequence = line[sequence_index]
                        if is_int(sequence):
                            sequence = int(sequence)
                            sequence = sequence + offset
                            line[sequence_index] = str(sequence)


def _tag_based_on(tag, base, substitute):
    column_code = tag[len(base) :]
    new_tag = f"{substitute}{column_code}"
    return new_tag


def _tag_is_based_on(tag, base):
    return tag.startswith(base)
