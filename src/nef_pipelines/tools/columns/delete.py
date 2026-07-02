from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry, Loop

from nef_pipelines.lib.cli_lib import (
    BadFrameLoopTagSyntaxException,
    _merge_tag_lists,
    parse_frame_loop_and_tags,
)
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.structures import FrameLoopsAndTags
from nef_pipelines.lib.util import STDIN, exit_error, warn
from nef_pipelines.tools.columns import columns_app
from nef_pipelines.tools.columns.columns_cli_lib import (
    _build_frame_loop_and_tag_selector_error_message,
    parse_selected_loop_tags_or_raise,
)
from nef_pipelines.tools.columns.columns_lib import _filter_tags


@columns_app.command()
def delete(
    input: Path = typer.Option(
        STDIN,
        "--in",
        metavar="|PIPE|",
        help="read NEF data from a file or stdin",
    ),
    selectors: List[str] = typer.Argument(
        ...,
        help="frame.loop:col selectors — columns to delete",
    ),
) -> None:
    """- delete columns from loops; selectors: frame.loop:col_1,col_2,..."""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frames_loops_and_tags = _parse_frame_loop_and_tag_selectors_or_exit_error(
        entry, selectors
    )
    frames_loops_and_tags = _process_selections_into_frame_loops_and_tags(
        frames_loops_and_tags
    )

    entry = pipe(entry, frames_loops_and_tags)
    print(entry)


def pipe(entry: Entry, frames_loops_and_tags: List[FrameLoopsAndTags]) -> Entry:
    """Delete columns from loops."""

    for item in frames_loops_and_tags:
        for loop in item.loops:
            loop_tags = item.loop_tags.get(loop.category, [])
            to_delete = set(_filter_tags(loop.tags, loop_tags, loop.category))
            if not to_delete:
                _warn_no_matching_column(loop, loop_tags)
                continue
            for tag in to_delete:
                loop.remove_tag(tag)

    return entry


def _warn_no_matching_column(loop: Loop, loop_tags):
    if loop_tags:
        msg = f" no columns matching {loop_tags!r} found in loop {loop.category.lstrip('_')}"
        warn(msg)


def _process_selections_into_frame_loops_and_tags(selections):
    """Process parsed selections into FrameLoopsAndTags, grouping by frame and merging tags."""
    result = []
    for selector_index, frame, loop, tags in selections:
        existing = next((it for it in result if it.frame is frame), None)
        if existing is None:
            existing = FrameLoopsAndTags(frame=frame)
            result.append(existing)
        if not any(lp is loop for lp in existing.loops):
            existing.loops.append(loop)
        category = loop.category
        current = existing.loop_tags.get(category, [])
        existing.loop_tags[category] = _merge_tag_lists(current, tags)
    return result


def _parse_frame_loop_and_tag_selectors_or_exit_error(
    entry: Entry, selectors: list[str]
) -> list[FrameLoopsAndTags]:
    """Parse selectors and group by frame/loop. Exits on invalid syntax."""
    try:
        frames_loops_and_tags = parse_selected_loop_tags_or_raise(entry, selectors)
    except BadFrameLoopTagSyntaxException as e:
        for index, selector_str in enumerate(selectors):
            try:
                parse_frame_loop_and_tags(selector_str)
            except BadFrameLoopTagSyntaxException:
                exit_error(
                    _build_frame_loop_and_tag_selector_error_message(
                        selector_str, index, e
                    )
                )
        raise

    return frames_loops_and_tags
