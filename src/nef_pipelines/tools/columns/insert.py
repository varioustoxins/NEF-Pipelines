import textwrap
from pathlib import Path
from typing import List, Optional

import typer
from click import Context
from pynmrstar import Entry

from nef_pipelines.lib.cli_lib import BadFrameLoopTagSyntaxException
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.structures import NEFPipelinesException
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.tools.columns import columns_app
from nef_pipelines.tools.columns.columns_cli_lib import (
    _build_column_instructions,
    _build_missing_loop_error_message,
    _FrameLoopGroups,
    _group_column_specifications_by_loop_or_raise,
    _parse_ordered_col_instructions,
    _resolve_frame_loop_strings_to_loops_or_raise,
    _ResolvedLoopColumnSpecificationPairs,
    track_order,
)
from nef_pipelines.tools.columns.columns_lib import (
    _resolve_tag,
    apply_column_instructions,
)
from nef_pipelines.tools.columns.columns_structures import (
    ColumnPlacement,
    InsertInstruction,
    InsertPlacement,
    NEFColumnsColumnNotFoundInFileException,
    NEFColumnsColumnNotFoundInLoopException,
    NEFColumnsDuplicateLoopException,
    NEFColumnsException,
    NEFColumnsFileIOException,
    NEFColumnsFileNotFoundException,
    NEFColumnsTagCategoryMismatchException,
    NEFInsertCLILoopNotDefinedException,
)


@columns_app.command()
def insert(
    ctx: Context,
    specs: Optional[List[str]] = typer.Argument(
        None,
        help="column specifications (col=value, @file, frame.loop:col=val, etc.)",
    ),
    nef_input: Path = typer.Option(
        STDIN,
        "--in",
        metavar="|PIPE|",
        help="read NEF data from a file or stdin",
    ),
    before: Optional[str] = typer.Option(
        None,
        "--before",
        "-b",
        callback=track_order,
        metavar="ANCHOR",
        help="insert the preceding column(s) before the ANCHOR column (name or 1-based index)",
    ),
    after: Optional[str] = typer.Option(
        None,
        "--after",
        "-a",
        callback=track_order,
        metavar="ANCHOR",
        help="insert the preceding column(s) after the ANCHOR column (name or 1-based index)",
    ),
    at: Optional[str] = typer.Option(
        None,
        "--at",
        "-@",
        callback=track_order,
        metavar="ANCHOR",
        help="replace the ANCHOR column (name or 1-based index)",
    ),
    selector: Optional[str] = typer.Option(
        None,
        "--selector",
        "-s",
        help="""\
            a single frame, or frame.loop selector setting the default target for col specs that do not
            carry their own frame or frame.loop prefix; not needed when col specs are fully qualified""",
    ),
    exact: bool = typer.Option(
        False,
        "--exact",
        help="match the selector exactly rather than as a substring",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="overwrite an existing column instead of erroring",
    ),
    skip: int = typer.Option(
        0,
        "--skip",
        help="number of rows to skip after stripping comment lines, before the header row (for @file value specs)",
    ),
    comment: str = typer.Option(
        "",
        "--comment",
        help="strip lines starting with this prefix before parsing @file value specs (applied before --skip)",
    ),
) -> None:
    """Insert columns into a loop using values from the command line or columns from a file.

    In the general form each imported or created column is specified by a column specification of the form:

    `<frame>.<loop>:<column-specification>,[<column-specification>...]`

    a `<column-specification>` has the form `<column-name>=<column-definition>`.
    The `<column-definition>` defines how to fill the column with values, as described in the Column Definitions
    section below.

    Notes & Special cases:

    * unfilled cells are filled with the NEF unused value `'.'`
    * when a new columns name matches an existing column name this produces an error unless --force is passed
    * new loops are created as needed
    * frame and loop identifiers may be omitted when `--selector` supplies them
    * a `<column-specification>` starting with `@` reads values from a file (see Column Definitions)
    * a bare `@path` token (no `col=` prefix) expands to multiple columns with names from CSV headers
    * there is special handling for when a complete file of columns should be read into a loop
      `frame.loop=@file` or `loop:=@file` (with `--selector frame`) bulk-imports all CSV columns into the loop
    * `col_1,...,col_N=<column-specification>` applies the same column specification to all listed columns


    ### Position Flags

    These flags apply **only** to the column specification(s) that **precede** them, placing them relative to an
    `anchor` column. The <anchor> defines a column by name or a 1-based index. There are 3 relative positions that
    can be added `--before / -b <anchor>`, `--after /  -a <anchor>` & `--at  / -@ <anchor>`. Several groups may be
    combined in one command, e.g. `colA --before atom_name colB --after value`.

    `--force` is needed only when the new column's name already exists elsewhere in the loop
    (not required with `--at`, which removes the column at `<anchor>` regardless of name).

    ### Column Specifications

    | Spec              | Example             | Meaning                                        |
    |-------------------|---------------------|------------------------------------------------|
    | `v1,v2,...`       | `ok,.,ok`           | comma-separated literal values                 |
    | `v*N`             | `A*19`              | N copies of literal v                          |
    | `v*`              | `A*`                | one copy of v per existing row                 |
    | `M..N`            | `1..10`             | integers M to N inclusive (reverse if M > N)   |
    | `M..`             | `1..`               | integers from M, one per existing row          |
    | `col=@path`       | `weight=@data.csv`  | CSV column named `col` (inferred from left)    |
    | `col=@path:name`  | `w=@data.csv:weight`| named CSV column (NEF column name is `col`)    |
    | `col=@path:N`     | `w=@data.csv:2`     | CSV column by 1-based index (NEF name: `col`)  |
    | `@path`           | `@shifts.csv`       | all columns (names from CSV headers)           |
    | `@path:name`      | `@f.csv:value`      | one named column (NEF name from CSV header)    |
    | `@path:N`         | `@f.csv:2`          | one column by 1-based index                    |
    | `@path:c1,c2`     | `@f.csv:a,b`        | multiple named columns                         |
    | `@path:N1,N2`     | `@f.csv:1,3`        | multiple columns by 1-based index              |

    """

    entry = read_entry_from_file_or_stdin_or_exit_error(nef_input)

    _exit_error_if_no_column_specifications(specs)

    raw_loops_and_column_specifications = _parse_ordered_col_instructions(ctx, specs)

    column_specifications_grouped_by_frame_loop = (
        _group_column_specifications_by_loop_or_exit_error(
            raw_loops_and_column_specifications,
            selector,
        )
    )

    resolved_loop_column_specification_pairs = (
        _resolve_frame_loop_strings_to_loops_or_exit_error(
            entry, column_specifications_grouped_by_frame_loop, specs, exact=exact
        )
    )

    column_instructions = _build_column_instructions(
        resolved_loop_column_specification_pairs, skip=skip, comment=comment
    )

    _exit_error_on_column_clashes_if_no_force(column_instructions, force)
    _validate_anchors_or_exit_error(column_instructions, ctx, specs)

    try:
        entry = pipe(entry, column_instructions)
    except NEFPipelinesException as e:
        _exit_error_on_pipe_exception(e, specs)

    print(entry)


def _exit_error_if_no_column_specifications(specs: Optional[List[str]]):
    if not specs:
        exit_error("no column specifications provided")


def _exit_error_on_pipe_exception(e, specs):
    # Format specs list with each on its own line for readability
    def format_specs(relevant_spec=None):
        lines = ["column specifications:"]
        if relevant_spec:
            lines.append(f"  (referenced by: {relevant_spec})")
        for s in specs:
            lines.append(f"  {s}")
        return "\n".join(lines)

    if isinstance(e, NEFColumnsFileNotFoundException):
        relevant_spec = next((s for s in specs if e.path in s), None)
        msg = f"""
                file not found: {e.path}
                {format_specs(relevant_spec)}
            """
        msg = textwrap.dedent(msg).strip()
    elif isinstance(e, NEFColumnsFileIOException):
        relevant_spec = next((s for s in specs if e.path in s), None)
        msg = f"""
                failed to {e.operation} file {e.path} because {e.cause}
                {format_specs(relevant_spec)}
            """
        msg = textwrap.dedent(msg).strip()
    elif isinstance(e, NEFColumnsColumnNotFoundInLoopException):
        if isinstance(e.ref, int):
            detail = f"column index {e.ref} out of range (loop has {e.n_columns} columns, indices are 1-based)"
        else:
            detail = f"column '{e.ref}' not found in loop {e.loop_category}"
        msg = f"""
                {detail}
                {format_specs()}
            """
        msg = textwrap.dedent(msg).strip()
    elif isinstance(e, NEFColumnsColumnNotFoundInFileException):
        available_str = ", ".join(e.available) if e.available else "(no columns)"
        if isinstance(e.ref, int):
            detail = f"""
                    column index {e.ref} out of range in {e.path} (file has {len(e.available)}
                    columns, indices are 1-based)
                """
        else:
            detail = f"column '{e.ref}' not found in {e.path}; available columns are: {available_str}"
        relevant_spec = next((s for s in specs if e.path in s), None)
        msg = f"""
                {detail}
                {format_specs(relevant_spec)}
            """
        msg = textwrap.dedent(msg).strip()
    elif isinstance(e, NEFColumnsDuplicateLoopException):
        msg = f"""
                cannot create loop '{e.loop_category}' in frame '{e.frame_name}'
                a loop with that category already exists:

                {format_specs()}
            """
        msg = textwrap.dedent(msg).strip()
    elif isinstance(e, NEFColumnsTagCategoryMismatchException):
        msg = f"""
                column '{e.tag_name}' has category '{e.tag_category}' but the loop has category '{e.loop_category}'
                {format_specs()}
            """
        msg = textwrap.dedent(msg).strip()
    else:
        msg = str(e)

    exit_error(msg)


def _resolve_frame_loop_strings_to_loops_or_exit_error(
    entry: Entry,
    column_specifications_grouped_by_frame_loop: _FrameLoopGroups,
    specs: List[str],
    exact: bool = False,
) -> _ResolvedLoopColumnSpecificationPairs:
    try:
        return _resolve_frame_loop_strings_to_loops_or_raise(
            entry,
            column_specifications_grouped_by_frame_loop,
            exact,
        )
    except BadFrameLoopTagSyntaxException as e:
        msg = f"""
                the frame.loop selector '{e.original_spec}' is not valid: {e.reason}
                column specifications: {' '.join(specs)}
            """
        msg = textwrap.dedent(msg).strip()
        exit_error(msg)


def _group_column_specifications_by_loop_or_exit_error(
    raw_loops_and_column_specifications: List[ColumnPlacement], selector: Optional[str]
) -> _FrameLoopGroups:
    try:
        return _group_column_specifications_by_loop_or_raise(
            raw_loops_and_column_specifications, selector
        )
    except NEFInsertCLILoopNotDefinedException as e:
        msg = _build_missing_loop_error_message(e)
        exit_error(msg)


def _validate_anchors_or_exit_error(
    column_instructions: List[InsertInstruction], ctx: Context, specs: List[str]
) -> None:
    """Validate that every placement anchor exists in its target loop before any data is written."""
    error_msg = None
    for instr in column_instructions:
        if instr.keyword in (
            InsertPlacement.BEFORE,
            InsertPlacement.AFTER,
            InsertPlacement.AT,
        ):
            try:
                resolved = _resolve_tag(instr.position_anchor, instr.loop.tags)
            except NEFColumnsException as e:
                error_msg = f"{e}\ncolumn specifications: {' '.join(specs)}"
                break
            if resolved not in instr.loop.tags:
                category = instr.loop.category.lstrip("_")
                error_msg = f"""
                        anchor column '{instr.position_anchor}' not found in loop {category}
                        column specifications: {' '.join(specs)}
                    """
                error_msg = textwrap.dedent(error_msg).strip()
                break

    if error_msg is not None:
        exit_error(error_msg)


def _exit_error_on_column_clashes_if_no_force(
    column_instructions: List[InsertInstruction], force: bool
):
    if not force:
        clashes = [
            f"column '{instr.column_spec.col_name}' already exists in loop {instr.loop.category.lstrip('_')}"
            for instr in column_instructions
            if instr.column_spec.col_name in instr.loop.tags
        ]
        if clashes:
            exit_error("\n".join(clashes))


def pipe(entry, column_instructions):
    """Insert columns described by column_instructions into their target loops and return the entry."""
    return apply_column_instructions(entry, column_instructions)
