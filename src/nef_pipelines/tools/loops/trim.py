import string
from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry
from strenum import LowercaseStrEnum
from typer import Argument, Option

from nef_pipelines.lib.nef_lib import (
    NEF_MOLECULAR_SYSTEM,
    SELECTORS_LOWER,
    SelectionType,
    loop_row_dict_iter,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.sequence_lib import (
    chains_from_frames,
    get_chain_ends,
    get_chain_starts,
    sequences_from_frames,
)
from nef_pipelines.lib.util import (
    chunks,
    exit_error,
    is_int,
    parse_comma_separated_options,
    strings_to_tabulated_terminal_sensitive,
    strip_characters_right,
)
from nef_pipelines.tools.loops import loops_app


class TrimAction(LowercaseStrEnum):
    DELETE = auto()
    DEASSIGN = auto()


@dataclass
class ChainBound:
    chain: str
    start: int
    end: int


# noinspection PyUnusedLocal
@loops_app.command()
def trim(
    chain_bounds: List[str] = Argument(
        None,
        metavar="<CHAIN-CODE> <START> <END> | <FRAME_SELECTOR>",
        help="""chain-codes and inclusive chain starts and ends to trim the chain to
                or a list of reference frames to find chain bounds from
                [default: use the molecular system.]""",
        show_default=False,
    ),
    reference_selector_type: SelectionType = typer.Option(
        SelectionType.ANY,
        "-t",
        "--reference-selector-type",
        help=f"control how to select reference frames to find chain bounds, can be one of: {SELECTORS_LOWER}. ",
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
        help=f"control how to select frames to trim, can be one of: {SELECTORS_LOWER}. "
        "Any will match on names first and then if there is no match attempt to match on category",
    ),
    # invert: bool = Option(False,  "--invert", help="invert the selection"),
    # action: TrimAction = Option(
    #     TrimAction.DELETE,
    #     "--action",
    #     metavar="<ACTION>",
    #     help="the action to take on the selected chains [default: renumber]",
    # ),
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
    """- trim the lengths of assigned chains in a nef file [alpha]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    chain_bounds = parse_comma_separated_options(chain_bounds)

    if not chain_bounds:
        chain_bounds = [
            NEF_MOLECULAR_SYSTEM,
        ]

    chains = chains_from_frames(entry.frame_list)

    reference_frames = _find_reference_frames(
        entry, chain_bounds, reference_selector_type
    )

    if reference_frames:
        chain_bounds = _chain_bounds_from_frames(reference_frames)
    else:
        chain_bounds = _parse_chain_bounds_exit_if_bad(chain_bounds, chains)

    entry = pipe(entry, frame_selectors, selector_type, chain_bounds)

    print(entry)


def pipe(
    entry: Entry,
    frame_selectors: List[str],
    frame_selector_type: SelectionType,
    chain_bounds: List[ChainBound],
) -> Entry:

    frames = select_frames(entry, frame_selectors, frame_selector_type)

    target_chains = chain_bounds.keys()

    _exit_if_selected_chain_not_in_frames("chain to trim", frames, input, target_chains)

    _trim_chains_in_frames(frames, chain_bounds)

    return entry


def _find_reference_frames(entry, chain_bounds, reference_selector_type):
    return select_frames(entry, chain_bounds, reference_selector_type)


def _chain_bounds_from_frames(reference_frames):
    sequences = sequences_from_frames(reference_frames)
    chain_starts = get_chain_starts(sequences)
    chain_ends = get_chain_ends(sequences)

    result = {}
    for chain in chain_starts:
        result[chain] = [
            ChainBound(chain, chain_starts[chain], chain_ends[chain]),
        ]

    return result


def _trim_chains_in_frames(frames, chain_bounds):

    for frame in frames:
        rows_to_remove = set()

        for loop in frame:
            for i, row in enumerate(loop_row_dict_iter(loop)):
                for name, value in row.items():
                    if name.startswith("chain_code"):
                        _, index = strip_characters_right(name, string.digits + "_")
                        chain_code = value
                        if chain_code not in chain_bounds:
                            continue

                        sequence_code_tag = f"sequence_code{index}"
                        sequence_code = row[sequence_code_tag]
                        if is_int(sequence_code):
                            sequence_code = int(sequence_code)
                        else:
                            continue

                        for chain_bound in chain_bounds[chain_code]:
                            if (
                                sequence_code < chain_bound.start
                                or sequence_code > chain_bound.end
                            ):
                                rows_to_remove.add(i)

        rows_to_keep = []
        for i, row in enumerate(loop_row_dict_iter(loop)):
            if i not in rows_to_remove:
                rows_to_keep.append(dict(row))

        loop.clear_data()

        loop.add_data(rows_to_keep)

        if "index" in loop.tags:
            loop.renumber_rows("index")


def _exit_error_if_no_chain_bounds(chain_bounds):
    if not chain_bounds:
        msg = """
            you didn't provide any chain bounds to trim the chains
            """
        exit_error(msg)


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


def _parse_chain_bounds_exit_if_bad(chain_bounds, chains):

    if len(chain_bounds) % 3:
        msg = """
            the chain bounds must be a triplet of values
            each chain bound being of the form <chain-code> <start> <end>
            you gave {chain_bounds}
            """
        msg = msg.format(chain_bounds=chain_bounds)
        exit_error(msg)

    result = {}
    for chain, start, end in chunks(chain_bounds, 3):
        if chain not in chains:
            msg = f"""
                the chain {chain} is not in the chains in the read frames
                the chains in the stream are {', '.join(chains)}
                """
            msg = msg.format(chain=chain, chains=chains)
            exit_error(msg)

        if not is_int(start):
            msg = f"""
                the start value {start} for chain {chain} is not an integer
                """
            exit_error(msg)

        if not is_int(end):
            msg = f"""
                the end value {end} for chain {chain} is not an integer
                """
            exit_error(msg)

        result.setdefault(chain, []).append(ChainBound(chain, int(start), int(end)))

        if end <= start:
            msg = f"""
                the end value {end} for chain {chain} is not greater than the start value {start}
                """
            exit_error(msg)

    return result
