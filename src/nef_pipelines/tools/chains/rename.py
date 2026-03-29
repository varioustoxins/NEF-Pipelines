from pathlib import Path
from typing import List, Sequence

import typer
from pynmrstar import Saveframe
from typer import Argument, Option

from nef_pipelines.lib.nef_lib import (
    SELECTORS_LOWER,
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.util import STDIN, exit_error, parse_comma_separated_options
from nef_pipelines.tools.chains import chains_app

# TODO: it would be nice to put the chains with the first molecular system frame

# because wee need the chaincodes twice on =ce inside the pipe ond once outside
_chain_code_tags_cache = {}


# noinspection PyUnusedLocal
@chains_app.command()
def rename(
    new_old: List[str] = Argument(
        ...,
        help="""\
            old chain-code followed by new chain-code, multiple pairs of old and new chain-codes can be provided.
            Values can be provided as separate arguments (A B C D), as comma-separated values (A,B C,D),
            or as a mixture of both (A,B C D). If chain codes contain commas, use --use-escapes and escape commas as
            ,, (e.g. "A,,1,B" defines two chain A,1 and B if --use-escapes is used).
        """,
    ),
    # TODO: just use --category instead to make life simpler???
    selector_type: SelectionType = typer.Option(
        SelectionType.ANY,
        "-t",
        "--selector-type",
        help=f"how to select frames to renumber, can be one of: {SELECTORS_LOWER}."
        "Any will match on names first and then if there is no match attempt to match on category",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    frame_selectors: List[str] = Option(
        None,
        "-f",
        "--frame",
        help="limit changes to a a particular frame by a selector which can be a frame name or category, "
        "note: wildcards [*] are allowed. Frames are selected by name and subsequently by category if the name "
        "doesn't match [-t /--selector-type allows you to force which selection type to use]. If no frame"
        "names or categories are provided chain-codes are renamed in all frames.",
    ),
    use_escapes: bool = typer.Option(
        False,
        "--use-escapes",
        help="enable escape sequences for chain codes containing commas (use ,, for a literal comma escape)",
    ),
):
    """- change the name of chains across one or multiple frames"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frames_to_process = select_frames(entry, frame_selectors, selector_type)

    frames_loops_and_chain_code_tags = _collect_frames_and_loops_by_chain_code_tags(
        frames_to_process
    )

    _check_frames_for_commas_in_chain_codes_exit_if_bad(
        frames_loops_and_chain_code_tags, frames_to_process, use_escapes
    )

    chain_codes = _parse_comma_separated_options_with_escapes(new_old, use_escapes)

    _exit_error_if_chaincodes_arent_pairs(chain_codes)

    old_new_chain_id_pairs = _get_list_as_pairs(chain_codes)

    entry = pipe(entry, frames_to_process, old_new_chain_id_pairs)

    print(entry)


def pipe(
    entry,
    frames_to_process: List[Saveframe],
    old_new_chain_id_pairs: list[tuple[str, str]],
):
    chain_code_tags = _collect_frames_and_loops_by_chain_code_tags(
        tuple(frames_to_process)
    )

    _rename_chains(chain_code_tags, frames_to_process, old_new_chain_id_pairs)

    return entry


def _check_frames_for_commas_in_chain_codes_exit_if_bad(
    frames_loops_and_chain_code_tags: list[tuple[str, str, str]],
    frames_to_process: list[Saveframe],
    use_escapes: bool,
):
    """\
    Check if chain codes in frames contain commas when --use-escapes is not set.

    Args:
        frames_loops_and_chain_code_tags: List of (frame_name, loop_category, tag_name) tuples
        frames_to_process: List of saveframes to look up frames/loops
        use_escapes: If True, commas in chain codes are allowed

    Raises:
        SystemExit: If commas found in chain codes without --use-escapes
    """

    if not use_escapes:
        # Create a lookup dict for frames by name
        frames_by_name = {frame.name: frame for frame in frames_to_process}

        problematic_chains = set()
        for frame_name, loop_category, tag in frames_loops_and_chain_code_tags:
            save_frame = frames_by_name[frame_name]
            loop = save_frame.get_loop(loop_category)
            tag_values = loop[tag]
            for value in tag_values:
                if "," in value:
                    problematic_chains.add(value)

        if problematic_chains:
            chain_list = ", ".join(sorted(problematic_chains))
            msg = f"""\
                The following chain codes contain commas: {chain_list}. Use --use-escapes to enable escape sequences
                for commas in chain codes and use double commas ',,' to escape commas.
            """
            exit_error(msg)


def _parse_comma_separated_options_with_escapes(
    chain_codes_raw: List[str], use_escapes: bool
) -> List[str]:
    """\
    Parse chain codes with optional escape sequence handling.

    Args:
        chain_codes_raw: Raw chain code arguments
        use_escapes: If True, process ,, as literal comma

    Returns:
        List of parsed chain codes
    """

    if use_escapes:
        # Use placeholder for escaped commas
        placeholder = "\x00COMMA\x00"
        unescaped = []
        for code in chain_codes_raw:
            # Replace escaped commas with placeholder
            code = code.replace(",,", placeholder)
            unescaped.append(code)

        # Parse comma-separated options
        parsed = parse_comma_separated_options(unescaped)

    else:
        result = parse_comma_separated_options(chain_codes_raw)

    # Restore escaped commas
    if use_escapes:
        result = [code.replace(placeholder, ",") for code in parsed]

    return result


def _get_list_as_pairs(chain_codes: list[str]) -> list[tuple[str, str]]:
    return [(chain_codes[i], chain_codes[i + 1]) for i in range(0, len(chain_codes), 2)]


def _rename_chains(
    chain_code_tags: list[tuple[str, str, str]],
    frames_to_process: list[Saveframe],
    pairs: list[tuple[str, str]],
):
    # Create a lookup dict for frames by name
    frames_by_name = {frame.name: frame for frame in frames_to_process}

    for old, new in pairs:
        for frame_name, loop_category, tag in chain_code_tags:
            save_frame = frames_by_name[frame_name]
            loop = save_frame.get_loop(loop_category)
            tag_values = loop[tag]
            modified = False
            for i, value in enumerate(tag_values):
                if value == old:
                    tag_values[i] = new
                    modified = True
            if modified:
                loop[tag] = tag_values


def _clear_chain_code_tags_cache():
    _chain_code_tags_cache.clear()


def _collect_frames_and_loops_by_chain_code_tags(
    frames_to_process: Sequence[Saveframe],
) -> list[tuple[str, str, str]]:
    """\
    Collect chain code tag information from frames.

    Returns (frame_name, loop_category, tag_name) tuples instead of actual objects.
    This allows caching since strings are hashable.
    """
    # Create cache key from frame names
    cache_key = tuple(frame.name for frame in frames_to_process)

    if cache_key in _chain_code_tags_cache:
        return _chain_code_tags_cache[cache_key]

    chain_code_tags = [
        (save_frame.name, loop.category, tag)
        for save_frame in frames_to_process
        for loop in save_frame.loop_iterator()
        for tag in loop.get_tag_names()
        if tag.split(".")[-1].startswith("chain_code")
    ]

    _chain_code_tags_cache[cache_key] = chain_code_tags
    return chain_code_tags


def _exit_error_if_chaincodes_arent_pairs(chain_codes: list[str]):
    # Validate we have pairs (even number of elements)
    if len(chain_codes) % 2 != 0:
        raise typer.BadParameter(
            f"Chain code pairs must come in pairs (old, new). Got {len(chain_codes)} values: {chain_codes}"
        )
