import sys
from pathlib import Path
from typing import Any, List

import typer

from nef_pipelines.lib.cli_lib import BadFrameLoopTagSyntaxException
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.tools.columns.columns_cli_lib import (
    _build_column_instructions,
    _group_column_specifications_by_loop_or_raise,
    _parse_ordered_col_instructions,
    _resolve_frame_loop_strings_to_loops_or_raise,
)
from nef_pipelines.tools.columns.columns_structures import (
    ColumnPlacement,
    InsertPlacement,
    NEFColumnsException,
    NEFInsertCLILoopNotDefinedException,
)
from nef_pipelines.tools.columns.insert import pipe as insert_pipe
from nef_pipelines.tools.loops import loops_app

PLACEHOLDER_COLUMN = "place_holder"


@loops_app.command()
def create(
    input: Path = typer.Option(
        STDIN, "--in", metavar="|PIPE|", help="read NEF data from a file or stdin"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="overwrite an existing loop instead of erroring",
    ),
    skip: int = typer.Option(
        0,
        "--skip",
        help="pre-header rows to skip before the column header row (for @file value specs)",
    ),
    comment: str = typer.Option(
        "",
        "--comment",
        help="ignore lines starting with this prefix before parsing (for @file value specs)",
    ),
    specs: List[str] = typer.Argument(
        ...,
        help=(
            "frame.loop:col1,col2=val,col3=v*N,col4=M..N,col5=@path:csv_col; "
            "bare @file refs auto-name from CSV header: @path (all cols), "
            "@path:col, @path:col1,col2, @path1:c1,@path2 (multi-file, comma-@ splits)"
        ),
    ),
) -> None:
    """- create a loop inside an existing frame with either a placeholder column or columns read
    from a TSV/CSV file or from the command line. Comments and header lines in files maybe skipped.

    Supports the same value specifications and file name and column references as columns insert:

       * col=v1,v2 (literals),
       * col=v*N (N copies)
       * col=M..N (integer range, inclusive),
       * col=M.. (integer range starting from M)
       * col=@path:csv_col (import column csv_col froma file as column col).
       * @file all columns from a file the files column headings become the NEF column headings
       * @path:col one column from a file the file's heading names the NEF column
       * @path:col1,col2 several columns from a file the file's heading names the NEF columns


    Use --skip to skip leading header rows after lines whichwhich contain --comment have
    the comment text removed upto and including the complete line.
    Errors if the loop already exists. The placeholder column is called place_holder.
    When importing columns from TSV/CSV files spaces in column headings are replaced with _.
    Multiple value and file specifications can be separated by ,s.
    """
    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # Parse and group column specs
    # TODO: loop definitions us an extended Frame.Loop:Tags syntax which needs to be merged into the
    #       syntax already defined as an extension for consistency
    column_specifications_grouped_by_frame_loop = (
        _parse_colum_specifications_or_exit_error(specs)
    )

    # Filter out empty column specs (from frame.loop: specs with no columns)
    column_specifications_grouped_by_frame_loop = {
        frame_loop: [spec for spec in specs if spec.col_spec]
        for frame_loop, specs in column_specifications_grouped_by_frame_loop.items()
    }

    # Add placeholder columns for loops with no column specifications
    column_specifications_grouped_by_frame_loop = _add_placeholder_to_empty_loops(
        column_specifications_grouped_by_frame_loop
    )

    # Resolve frame.loop strings to actual loops - syntax validation happens here
    resolved_loop_column_specification_pairs = (
        _resolve_loop_speification_pairs_or_exit_error(
            entry, specs, column_specifications_grouped_by_frame_loop
        )
    )

    column_instructions = _build_column_instructions(
        resolved_loop_column_specification_pairs, skip=skip, comment=comment
    )

    # Check for existing loops and handle based on --force
    _exit_error_on_existing_loops_if_no_force(column_instructions, force)
    _check_for_existing_loops_and_warn_if_force(column_instructions, force)

    # If --force, clear existing loop tags to replace (not add to) the loop
    if force:
        _clear_existing_loop_tags(column_instructions)

    try:
        entry = insert_pipe(entry, column_instructions)
    except NEFColumnsException as e:
        exit_error(str(e))

    print(entry)


def _resolve_loop_speification_pairs_or_exit_error(
    entry,
    specs: list[str] | list[ColumnPlacement],
    column_specifications_grouped_by_frame_loop: dict[Any, Any],
) -> list[tuple[Any, list[ColumnPlacement]]]:
    try:
        resolved_loop_column_specification_pairs = (
            _resolve_frame_loop_strings_to_loops_or_raise(
                entry, column_specifications_grouped_by_frame_loop
            )
        )
    except BadFrameLoopTagSyntaxException as e:
        exit_error(f"invalid selector syntax in '{e.original_spec}'")

    if not resolved_loop_column_specification_pairs:
        selector_list = ", ".join(specs)
        exit_error(f"no frames matched by {selector_list}")
    return resolved_loop_column_specification_pairs


def _parse_colum_specifications_or_exit_error(
    specs: list[str],
) -> dict[str, list[ColumnPlacement]]:
    column_placements = _parse_ordered_col_instructions(None, specs)

    try:
        column_specifications_grouped_by_frame_loop = (
            _group_column_specifications_by_loop_or_raise(
                column_placements,
                selector=None,
            )
        )
    except NEFInsertCLILoopNotDefinedException as e:
        exit_error(f"frame and loop name must be separated by '.' in '{e.col_spec}'")
    except BadFrameLoopTagSyntaxException as e:
        exit_error(f"invalid selector syntax in '{e.original_spec}'")
    return column_specifications_grouped_by_frame_loop


def _add_placeholder_to_empty_loops(grouped_specifications):
    """Add placeholder column spec to loops that have no column specifications."""
    result = {}
    for frame_loop, col_specs in grouped_specifications.items():
        if not col_specs:
            print(
                f"WARNING: no columns specified for '{frame_loop}'; "
                f"adding placeholder column '{PLACEHOLDER_COLUMN}'",
                file=sys.stderr,
            )
            # Create a placeholder column specification (no frame.loop prefix - already grouped)
            result[frame_loop] = [
                ColumnPlacement(PLACEHOLDER_COLUMN, InsertPlacement.APPEND, None)
            ]
        else:
            result[frame_loop] = col_specs
    return result


def _check_for_existing_loops_and_warn_if_force(column_instructions, force: bool):
    """Warn about existing loops being replaced when --force is used."""
    if not force:
        return

    loops_to_replace = set()
    for instr in column_instructions:
        loop_id = f"{instr.loop.category.lstrip('_')}"
        if loop_id not in loops_to_replace and instr.loop.tags:
            loops_to_replace.add(loop_id)
            existing_columns = ", ".join(instr.loop.tags)
            print(
                f"WARNING: replacing existing loop '{loop_id}' "
                f"with columns: {existing_columns}",
                file=sys.stderr,
            )


def _exit_error_on_existing_loops_if_no_force(column_instructions, force: bool):
    """Exit with error if loops already exist and --force not specified."""
    if force:
        return

    clashes = []
    for instr in column_instructions:
        if instr.loop.tags:
            existing_columns = ", ".join(instr.loop.tags)
            clashes.append(
                f"loop '{instr.loop.category.lstrip('_')}' already exists "
                f"with columns: {existing_columns}"
            )
    if clashes:
        count = len(clashes)
        plural = "loops" if count > 1 else "loop"
        header = f"{count} {plural} already exist:\n"
        exit_error(header + "\n".join(clashes))


def _clear_existing_loop_tags(column_instructions):
    """Clear all tags and data from existing loops to enable full replacement with --force."""
    for instr in column_instructions:
        if instr.loop.tags:
            # Clear all data rows first
            instr.loop.data = []
            # Then clear all existing tags from the loop
            for tag in list(instr.loop.tags):
                instr.loop.remove_tag(tag)
