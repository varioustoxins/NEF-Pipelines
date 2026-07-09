from pathlib import Path
from typing import Dict, List, Tuple

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    SelectionType,
    loop_row_dict_iter,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
    select_loops_by_category,
)
from nef_pipelines.lib.structures import FrameLoopAndTagSelectors
from nef_pipelines.lib.util import STDIN, exit_error, warn
from nef_pipelines.tools.columns import columns_app
from nef_pipelines.tools.columns.columns_cli_lib import (
    _build_rename_parse_error_message,
    _parse_rename_arguments_or_raise,
)
from nef_pipelines.tools.columns.columns_lib import _rebuild_loop, _resolve_tag
from nef_pipelines.tools.columns.columns_structures import (
    NEFColumnsRenameParseException,
)


@columns_app.command()
def rename(
    arguments: List[str] = typer.Argument(
        ...,
        help="rename specifications: <saveframe>.<loop>:<tag>=<new-name> or <tag> <new-name>",
    ),
    input: Path = typer.Option(
        STDIN,
        "--in",
        metavar="|PIPE|",
        help="read NEF data from a file or stdin",
    ),
    selector: str = typer.Option(
        None,
        "--selector",
        "-s",
        help="frame.loop selector (optional if full selectors provided)",
    ),
) -> None:
    """- rename columns: frame.loop:tag=new or tag=new (with --selector)"""
    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    rename_pairs = _parse_rename_arguments_or_exit_error(
        arguments, selector, entry, input
    )

    _warn_if_duplicate_targets(rename_pairs)
    _validate_columns_exist(entry, rename_pairs)

    entry = pipe(entry, rename_pairs)
    print(entry)


def _parse_rename_arguments_or_exit_error(
    arguments: list[str], selector: str, entry: Entry, input_file: Path
) -> list[tuple[FrameLoopAndTagSelectors, str]]:
    """Parse rename arguments or exit with formatted error message.

    Wrapper around _parse_rename_arguments_or_raise that catches exceptions,
    formats them with context (entry ID, file path), and calls exit_error.
    """
    try:
        return _parse_rename_arguments_or_raise(arguments, selector)
    except NEFColumnsRenameParseException as e:
        msg = _build_rename_parse_error_message(e, entry, input_file)
        exit_error(msg)


def pipe(
    entry: Entry, rename_pairs: List[Tuple[FrameLoopAndTagSelectors, str]]
) -> Entry:
    """Rename columns using FrameLoopAndTagSelectors.

    Args:
        entry: NEF entry to modify
        rename_pairs: List of (FrameLoopAndTagSelectors, new_name) where each selector
                      must specify exactly one tag

    Raises:
        ValueError: if selector doesn't specify exactly one tag

    Note: Assumes columns exist (CLI should validate before calling).
    """
    _raise_if_selectors_dont_have_single_tag(rename_pairs)
    renames_by_loop = _group_renames_by_loop(rename_pairs)
    _apply_renames_to_entry(entry, renames_by_loop)
    return entry


def _raise_if_selectors_dont_have_single_tag(
    rename_pairs: List[Tuple[FrameLoopAndTagSelectors, str]]
) -> None:
    """Validate that all selectors specify exactly one tag."""
    for sel, _ in rename_pairs:
        if not sel.loop_tags or len(sel.loop_tags) != 1:
            # TODO this should be a structure exception in the nefpiplines hierearchy
            raise ValueError(
                "Selector must specify exactly one tag, "
                + f"got {len(sel.loop_tags) if sel.loop_tags else 0} tags"
            )


def _group_renames_by_loop(
    rename_pairs: List[Tuple[FrameLoopAndTagSelectors, str]]
) -> Dict[Tuple[str, str], List[Tuple[str, str]]]:
    """Group renames by (frame_pattern, loop_pattern) key."""
    renames_by_loop = {}
    for sel, new_name in rename_pairs:
        old_tag = sel.loop_tags[0]
        loop_key = (sel.frame_name, sel.loop_name)

        if loop_key not in renames_by_loop:
            renames_by_loop[loop_key] = []
        renames_by_loop[loop_key].append((old_tag, new_name))

    return renames_by_loop


def _apply_renames_to_entry(
    entry: Entry, renames_by_loop: Dict[Tuple[str, str], List[Tuple[str, str]]]
) -> None:
    """Apply grouped renames to all matching frames and loops in entry."""
    for (frame_pattern, loop_pattern), tag_pairs in renames_by_loop.items():
        frames = select_frames(entry, [frame_pattern], SelectionType.ANY)

        for frame in frames:
            loops = select_loops_by_category(
                frame.loops, [loop_pattern] if loop_pattern else []
            )
            for loop in loops:
                _rename_loop_columns(frame, loop, tag_pairs)


def _rename_loop_columns(frame, loop, pairs: List[Tuple[str, str]]) -> None:
    """Rename columns in a single loop using (old_tag, new_tag) pairs."""
    loop_rename_map = _build_loop_rename_map(loop, pairs)
    new_tags = [loop_rename_map.get(t, t) for t in loop.tags]
    rows = list(loop_row_dict_iter(loop, convert=False))
    new_rows = [{loop_rename_map.get(k, k): v for k, v in row.items()} for row in rows]
    _rebuild_loop(frame, loop, new_tags, new_rows)


def _build_loop_rename_map(loop, pairs: List[Tuple[str, str]]) -> Dict[str, str]:
    """Build {old_tag: new_tag} map for a single loop.

    Note: Assumes all columns exist (validated by CLI preflight).
    """
    loop_rename_map = {}
    for old_name, new_name in pairs:
        old_name = _resolve_tag(old_name, loop.tags)
        loop_rename_map[old_name] = new_name

    return loop_rename_map


def _warn_if_duplicate_targets(
    rename_pairs: List[Tuple[FrameLoopAndTagSelectors, str]]
) -> None:
    """Warn if multiple tags are being renamed to the same target name."""
    targets = [new_name for _, new_name in rename_pairs]
    seen = set()
    duplicates = [t for t in targets if t in seen or seen.add(t)]

    if duplicates:
        warn(f"multiple tags being renamed to same target: {list(set(duplicates))}")


def _validate_columns_exist(
    entry: Entry, rename_pairs: List[Tuple[FrameLoopAndTagSelectors, str]]
) -> None:
    """Validate that all source columns exist in their respective loops.

    Exits with error if any column is not found.
    """
    renames_by_loop = _group_renames_by_loop(rename_pairs)

    for (frame_pattern, loop_pattern), tag_pairs in renames_by_loop.items():
        frames = select_frames(entry, [frame_pattern], SelectionType.ANY)

        for frame in frames:
            loops = select_loops_by_category(
                frame.loops, [loop_pattern] if loop_pattern else []
            )
            for loop in loops:
                for old_name, _ in tag_pairs:
                    old_name = _resolve_tag(old_name, loop.tags)
                    if old_name not in loop.tags:
                        exit_error(
                            f"column '{old_name}' not found in loop {loop.category.lstrip('_')}"
                        )
