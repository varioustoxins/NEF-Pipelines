from enum import auto
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import typer
from pynmrstar import Entry, Loop
from strenum import LowercaseStrEnum

from nef_pipelines.lib.nef_lib import (
    SelectionType,
    loop_row_dict_iter,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
    select_loops_by_category,
)
from nef_pipelines.lib.structures import FrameLoopAndTagSelectors
from nef_pipelines.lib.util import STDIN, exit_error, oxford_join, warn
from nef_pipelines.tools.columns import columns_app
from nef_pipelines.tools.columns.columns_cli_lib import (
    _format_exception_with_context,
    _parse_reorder_arguments_or_exit_error,
)
from nef_pipelines.tools.columns.columns_lib import _rebuild_loop, _resolve_tag
from nef_pipelines.tools.columns.columns_structures import (
    NEFColumnsReorderDuplicateColumnsException,
    NEFColumnsReorderUnknownColumnsException,
)

# TYPICAL ordering groups - easily refined as needed
# Order determines output order; wildcards (*) match using fnmatch
TYPICAL_INDEX_GROUP = ["index", "combination_id", "serial", "*_id"]

TYPICAL_CHAIN_RESIDUE_ATOM_TEMPLATE = [
    "chain_code",
    "sequence_code",
    "residue_name",
    "atom_name",
    "isotope_number",
]

TYPICAL_MEASUREMENT_GROUP = [
    ["*value*", "{name}_uncertainty"],
    ["position", "{name}_uncertainty"],
    ["volume", "{name}_uncertainty"],
    ["height", "{name}_uncertainty"],
]

TYPICAL_REMAINING_GROUP_SENTINEL = "*"

TYPICAL_COMMENT_GROUP = ["*annotation*", "*comment*"]


TYPICAL_GROUPS = [
    TYPICAL_INDEX_GROUP,
    TYPICAL_CHAIN_RESIDUE_ATOM_TEMPLATE,
    TYPICAL_MEASUREMENT_GROUP,
    TYPICAL_REMAINING_GROUP_SENTINEL,
    TYPICAL_COMMENT_GROUP,
]


class ColumnOrderPolicy(LowercaseStrEnum):
    CUSTOM = auto()
    ALPHABETICAL = auto()
    TYPICAL = auto()


@columns_app.command()
def reorder(
    input: Path = typer.Option(
        STDIN,
        "--in",
        metavar="|PIPE|",
        help="read NEF data from a file or stdin",
    ),
    policy: ColumnOrderPolicy = typer.Option(
        ColumnOrderPolicy.CUSTOM,
        "--policy",
        help="ordering policy: 'custom' (you specify order), 'alphabetical' (A-Z), "
        "'typical' (standard NMR column order: index, atoms, measurements, comments)",
    ),
    selector: Optional[str] = typer.Option(
        None,
        "--selector",
        "-s",
        help="which loop to reorder, e.g. 'myshifts.chemical_shift' or just 'chemical_shift' for all frames",
    ),
    column_order: List[str] = typer.Argument(
        None,
        help="column names in desired order. Use '*' for 'all remaining columns'. "
        "If '*' is omitted, it's automatically added at the end",
    ),
) -> None:
    """**Rearrange columns** in a data loop to a different order.

    Makes data easier to read or match specific format requirements.

    ## Ordering Policies

    - **custom** (default) — You specify the exact order
    - **alphabetical** — Sorts columns A-Z
    - **typical** — Standard NMR/NEF conventions (index → atoms → measurements → comments)

    ## Selection Syntax

    You must specify which loop to reorder using one of these methods:

    **Method 1: --selector flag + column names as arguments**
    - `--selector <saveframe>.<loop>` followed by column names
    - Example: `--selector myshifts.chemical_shift atom_name value`
    - Selector must include both saveframe _AND_ loop (e.g., `myshifts.chemical_shift`)
    - Column names go in command arguments

    **Method 2: Combined syntax (no --selector needed)**
    - Format: `<saveframe>.<loop>:<col1>[,<col2>,...]`
    - Example: `myshifts.chemical_shift:atom_name,value`
    - Everything in one argument, columns separated by commas
    - Cannot mix with --selector

    > **NOTE For alphabetical/typical policies:**
    >
    > - You only need `--selector saveframe.loop` (no column names)
    > - Example: `--policy typical --selector myshifts.chemical_shift`

    ## Examples

    ```bash
        # Put specific columns first, rest stay in original order:
        nef columns reorder --selector myshifts.chemical_shift atom_name value

        # Same using compact syntax (no --selector flag):
        nef columns reorder myshifts.chemical_shift:atom_name,value

        # Sort all columns alphabetically:
        nef columns reorder --policy alphabetical --selector myshifts.chemical_shift

        # Use standard NMR ordering (good for publication):
        nef columns reorder --policy typical --selector myshifts.chemical_shift

        # Control exact order with * wildcard:
        nef columns reorder --selector myshifts.chemical_shift index atom_name * ccpn_comment
        # Result: index, atom_name, everything else, ccpn_comment
    ```

    ## TYPICAL Policy

    Orders columns following NMR/NEF conventions:

    1. **Index fields** — index, combination_id, serial, peak_id
    2. **Atom identifiers** — chain_code, sequence_code, residue_name, atom_name
    3. **Measurements** — value, position, volume, height (with _uncertainty pairs)
    4. **Other fields** — remaining columns in original order
    5. **Comments** — annotation and comment columns

    > **Notes:**
    > 1. Columns not explicitly specified keep their original relative order
    > 2. uncertainties appear just after their values
    > 3. for combined alphabetical+typical ordering, apply alphabetical first then typical
    """

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # Add implicit * at end if not present (only for custom policy)
    if policy == ColumnOrderPolicy.CUSTOM and column_order and "*" not in column_order:
        column_order.append("*")

    # Deduplicate column_order, warn about duplicates
    column_order = _deduplicate_column_order_request_and_warn_if_required(column_order)

    frame_loop_tags = _parse_reorder_arguments_or_exit_error(
        selector, column_order or [], policy.value, entry, input
    )

    _validate_reorder_or_exit_error(entry, frame_loop_tags, input)

    entry = pipe(entry, frame_loop_tags, policy)
    print(entry)


def pipe(
    entry: Entry,
    frame_loop_tags: FrameLoopAndTagSelectors,
    policy: ColumnOrderPolicy = ColumnOrderPolicy.CUSTOM,
) -> Entry:
    """Reorder columns in a clear pipeline: find → compute → apply.

    Assumes CLI has validated:
    - Frame/loop exist
    - All columns in loop_tags exist
    - No duplicates
    """
    # Safety: Add implicit * for CUSTOM policy to prevent silent data loss
    if (
        policy == ColumnOrderPolicy.CUSTOM
        and frame_loop_tags.loop_tags
        and "*" not in frame_loop_tags.loop_tags
    ):
        frame_loop_tags.loop_tags.append("*")

    # Pipeline stage 1: Find all target loops
    target_loops = _find_target_loops(entry, frame_loop_tags)

    # Pipeline stage 2: Compute new column orders
    reorder_instructions = _compute_reorders(target_loops, frame_loop_tags, policy)

    # Pipeline stage 3: Apply all reorders
    _apply_reorders(reorder_instructions)

    return entry


def _deduplicate_column_order_request_and_warn_if_required(
    column_order: list[str],
) -> list[Any]:
    if column_order:
        seen = set()
        duplicates = []
        deduped = []
        for col in column_order:
            if col in seen:
                duplicates.append(col)
            else:
                seen.add(col)
                deduped.append(col)

        if duplicates:
            quoted = [f"'{d}'" for d in duplicates]
            dup_str = oxford_join(quoted, conjunction="and")
            verb = "is" if len(duplicates) == 1 else "are"
            warn(
                f"Ignoring subsequent duplicate column order requests: {dup_str} {verb} repeated"
            )
            column_order = deduped
    return column_order


def _find_target_loops(entry: Entry, frame_loop_tags: FrameLoopAndTagSelectors):
    """Pipeline stage 1: Find all loops matching the selector.

    Returns list of (frame, loop) tuples.
    """
    target_loops = []
    frames = select_frames(entry, [frame_loop_tags.frame_name], SelectionType.ANY)

    for frame in frames:
        loops = select_loops_by_category(
            frame.loops,
            [frame_loop_tags.loop_name] if frame_loop_tags.loop_name else [],
        )
        for loop in loops:
            target_loops.append((frame, loop))

    return target_loops


def _compute_reorders(
    target_loops, frame_loop_tags: FrameLoopAndTagSelectors, policy: ColumnOrderPolicy
):
    """Pipeline stage 2: Compute new column order for each loop.

    Returns list of (frame, loop, new_order) tuples.
    """
    reorder_instructions = []

    for frame, loop in target_loops:
        if policy == ColumnOrderPolicy.ALPHABETICAL:
            new_order = sorted(loop.tags)
        elif policy == ColumnOrderPolicy.TYPICAL:
            new_order = _compute_typical_order(loop)
        else:
            new_order = _compute_new_column_order(loop, frame_loop_tags.loop_tags)
        reorder_instructions.append((frame, loop, new_order))

    return reorder_instructions


def _apply_reorders(reorder_instructions) -> None:
    """Pipeline stage 3: Apply all computed reorders.

    Takes list of (frame, loop, new_order) tuples.
    """
    for frame, loop, new_order in reorder_instructions:
        _apply_column_reorder(frame, loop, new_order)


def _validate_reorder_or_exit_error(
    entry: Entry, frame_loop_tags: FrameLoopAndTagSelectors, input_file: Path
) -> None:
    """Validate reorder can be performed, exit with formatted error if not."""
    target_loops = _find_target_loops(entry, frame_loop_tags)

    for frame, loop in target_loops:
        # Resolve and validate columns exist
        resolved_order = [
            _resolve_tag(c, loop.tags) if c != "*" else "*"
            for c in frame_loop_tags.loop_tags
        ]
        unknown = [c for c in resolved_order if c != "*" and c not in loop.tags]
        if unknown:
            try:
                raise NEFColumnsReorderUnknownColumnsException(
                    unknown, loop.category.lstrip("_"), loop.tags
                )
            except NEFColumnsReorderUnknownColumnsException as e:
                msg = _format_exception_with_context(e, entry, input_file)
                exit_error(msg)


def _expand_star(spec: List[str], current_tags: List[str]) -> List[str]:
    """Expand * to all tags not explicitly named, in their original relative order.

    Integer entries in spec are resolved to tag names by index before expansion.
    Raises NEFColumnsReorderDuplicateColumnsException if duplicates detected (including multiple *).
    """
    resolved = [_resolve_tag(c, current_tags) if c != "*" else "*" for c in spec]

    # Check for duplicates (including multiple *)
    seen = set()
    duplicates = []
    for item in resolved:
        if item in seen:
            duplicates.append(item)
        seen.add(item)

    if duplicates:
        raise NEFColumnsReorderDuplicateColumnsException(duplicates)

    explicit = {c for c in resolved if c != "*"}
    remaining = [t for t in current_tags if t not in explicit]
    result: List[str] = []
    for col in resolved:
        result.extend(remaining if col == "*" else [col])
    return result


def _compute_new_column_order(loop, column_order: List[str]) -> List[str]:
    """Compute new column order: ordered_tags first, then remaining in current order."""
    resolved_order = [
        _resolve_tag(c, loop.tags) if c != "*" else "*" for c in column_order
    ]
    return _expand_star(resolved_order, loop.tags)


def _apply_column_reorder(frame, loop, new_order: List[str]) -> None:
    """Apply new column order to loop."""
    rows = list(loop_row_dict_iter(loop, convert=False))
    new_rows = [{t: row.get(t, ".") for t in new_order} for row in rows]
    _rebuild_loop(frame, loop, new_order, new_rows)


def _extract_suffix(col_name: str) -> Tuple[str, Optional[int]]:
    """Extract base name and numeric suffix from column.

    Returns (base, suffix_num) or (col_name, None) if no suffix.
    Example: "chain_code_1" → ("chain_code", 1)
    """
    parts = col_name.split("_")
    if parts[-1].isdigit():
        base = "_".join(parts[:-1])
        return (base, int(parts[-1]))

    return (col_name, None)


def _matches_group(col: str, group: List[str]) -> bool:
    """Check if column matches any pattern in the group.

    Matches exact names or wildcard patterns (* using fnmatch).
    """
    return any(fnmatchcase(col, pattern) for pattern in group)


def _is_comment_column(col: str) -> bool:
    """Check if column matches comment group."""
    return _matches_group(col, TYPICAL_COMMENT_GROUP)


def _find_measurement_pairs(
    columns: List[str],
) -> Tuple[List[Tuple[str, str]], Set[str]]:
    """Find measurement/uncertainty pairs (non-suffixed columns only).

    Processes columns in the order defined by TYPICAL_MEASUREMENT_GROUP.
    Each group entry is [pattern, pairing_pattern] where {name} in pairing_pattern
    is replaced with the matched column name.

    Returns (pairs, used_cols) where pairs is [(val, unc), ...] and used_cols
    is a set of all columns consumed into pairs.

    Only pairs columns without numeric suffixes (_1, _2, etc.).
    Suffixed measurements are handled within dimensional groups.
    """
    pairs = []
    used = set()
    col_set = set(columns)
    processed = set()

    # Process in group order (maintains pattern order from the list)
    for pattern_spec in TYPICAL_MEASUREMENT_GROUP:
        pattern, pairing_pattern = pattern_spec

        for col in columns:
            if col in processed:
                continue

            base, suffix = _extract_suffix(col)
            if suffix is not None:
                continue

            # Check if column matches this pattern
            if not fnmatchcase(col, pattern):
                continue

            processed.add(col)

            # Replace {name} with the matched column name
            pair_col = pairing_pattern.replace("{name}", col)

            if pair_col in col_set:
                pairs.append((col, pair_col))
                used.add(col)
                used.add(pair_col)

    return pairs, used


def _group_by_suffix(columns: List[str], exclude: Set[str]) -> Dict[int, List[str]]:
    """Group columns by numeric suffix, excluding already-categorized columns.

    Returns {suffix_num: [col1, col2, ...]} preserving original order within each group.
    """
    groups: Dict[int, List[str]] = {}

    for col in columns:
        if col in exclude:
            continue

        base, suffix = _extract_suffix(col)
        if suffix is None:
            continue

        if suffix not in groups:
            groups[suffix] = []
        groups[suffix].append(col)

    return groups


def _compute_typical_order(loop: Loop) -> List[str]:
    """Compute TYPICAL column order for NMR/NEF data.

    Order:
      1. Index group: index, serial, combination_id, peak_id
      2. Chain/residue/atom group: non-suffixed, then suffixed by number (_1, _2, ...)
      3. Measurement group: value, position, volume, height (with _uncertainty/_error)
      4. Other group: remaining columns in original order
      5. Comment group: any column with "comment" in name
    """
    all_cols = loop.tags
    result = []
    categorized = set()

    suffix_groups = _group_by_suffix(all_cols, set())

    # 1. Index group - process in list order (maintains pattern order)
    for pattern in TYPICAL_INDEX_GROUP:
        for col in all_cols:
            if col in categorized:
                continue
            base, suffix = _extract_suffix(col)
            if suffix is not None:
                continue
            if fnmatchcase(col, pattern):
                result.append(col)
                categorized.add(col)

    # 2. Chain/residue/atom group - non-suffixed first
    for template_base in TYPICAL_CHAIN_RESIDUE_ATOM_TEMPLATE:
        if template_base in all_cols:
            has_suffixed = any(
                f"{template_base}_{num}" in all_cols for num in suffix_groups.keys()
            )
            if has_suffixed:
                warn(
                    f"Loop has both '{template_base}' and suffixed versions "
                    f"(e.g., '{template_base}_1') - non-suffixed appears first"
                )
            result.append(template_base)
            categorized.add(template_base)

    # 2. Chain/residue/atom group - suffixed by number
    for suffix_num in sorted(suffix_groups.keys()):
        for template_base in TYPICAL_CHAIN_RESIDUE_ATOM_TEMPLATE:
            col = f"{template_base}_{suffix_num}"
            if col in all_cols:
                result.append(col)
                categorized.add(col)

    # 3. Measurement group - non-suffixed with uncertainties
    pairs, pair_cols = _find_measurement_pairs(all_cols)
    for val, unc in pairs:
        if val not in categorized:
            result.append(val)
            result.append(unc)
            categorized.add(val)
            categorized.add(unc)

    # 3. Measurement group - suffixed by number with uncertainties
    # Process in group order (maintains pattern order from TYPICAL_MEASUREMENT_GROUP)
    for suffix_num in sorted(suffix_groups.keys()):
        for pattern_spec in TYPICAL_MEASUREMENT_GROUP:
            pattern, pairing_pattern = pattern_spec

            for col in all_cols:
                if col in categorized:
                    continue
                base, suf = _extract_suffix(col)
                if suf != suffix_num:
                    continue
                if not fnmatchcase(base, pattern):
                    continue

                result.append(col)
                categorized.add(col)

                # Replace {name} with base name and add suffix
                pair_col = pairing_pattern.replace("{name}", base) + f"_{suffix_num}"
                if pair_col in all_cols and pair_col not in categorized:
                    result.append(pair_col)
                    categorized.add(pair_col)

    # 4. Other group (remaining columns)
    # 5. Comment group (wildcard patterns: *annotation*, *comment*)
    comments = []
    remaining = []
    for col in all_cols:
        if col in categorized:
            continue
        if _is_comment_column(col):
            comments.append(col)
        else:
            remaining.append(col)

    result.extend(remaining)
    result.extend(comments)

    return result
