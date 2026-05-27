from pathlib import Path
from typing import List, Optional, Tuple

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    create_nef_save_frame,
    is_save_frame_name_in_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.util import (
    STDIN,
    chunks,
    exit_error,
    parse_comma_separated_options,
)
from nef_pipelines.tools.frames import frames_app


@frames_app.command()
def create(
    input: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read input from [- is stdin]"
    ),
    entry_name: str = typer.Option(
        "nef", "--entry", help="entry name when creating a new entry from scratch"
    ),
    force: bool = typer.Option(False, "--force", help="overwrite existing frames"),
    category_names: List[str] = typer.Argument(
        ...,
        help="frame specifications: category.name or category name pairs (comma-separated supported)",
    ),
) -> None:
    """- create one or more empty NEF saveframes

    Accepts multiple input formats:
    - Dot notation: category.id [e.g., nef_chemical_shift_list.default]
    - Pairs: category id [e.g., nef_chemical_shift_list default]
    - Singletons: category. or category "" [e.g., nef_molecular_system.]
    - Comma-separated: category.id,category.id
    - Mixed combinations

    For singleton frames (nef_molecular_system, nef_nmr_meta_data), use empty id:
    - nef_molecular_system. (trailing dot)
    - nef_molecular_system "" (explicit empty string)
    - nef_molecular_system,, (double comma in list)

    Examples:
        nef frame create nef_molecular_system.
        nef frame create nef_molecular_system ""
        nef frame create nef_chemical_shift_list.default
        nef frame create nef_chemical_shift_list default
        nef frame create nef_molecular_system.,nef_chemical_shift_list.default
        nef frame create nef_molecular_system. nef_chemical_shift_list default
    """

    category_names = parse_comma_separated_options(category_names)
    pairs = _parse_category_name_specs(category_names)

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name=entry_name)

    result = pipe(entry, pairs, overwrite=force)

    print(result)


def pipe(
    entry: Entry,
    category_name_pairs: List[Tuple[str, str]],
    overwrite: bool = False,
) -> Entry:
    """Create one or more empty NEF saveframes and add them to entry."""

    for category, id_part in category_name_pairs:

        framecode = _build_framecode(category, id_part)

        _exit_error_if_frame_exists_and_no_force(entry, framecode, overwrite)

        _delete_save_frame_if_exists(entry, framecode)

        _add_save_frame(category, entry, id_part)

    return entry


def _add_save_frame(category: str, entry: Entry, id_part: str):
    frame = create_nef_save_frame(category, id_part)
    add_frames_to_entry(entry, [frame])


def _delete_save_frame_if_exists(entry: Entry, framecode: str):
    if is_save_frame_name_in_entry(entry, framecode):
        existing = entry.get_saveframe_by_name(framecode)
        entry.remove_saveframe(existing)


def _build_framecode(category: str, id_part: str) -> str:
    # Singleton frames have no id component: sf_category == sf_framecode
    return category if not id_part else f"{category}_{id_part}"


def _exit_error_if_frame_exists_and_no_force(
    entry: Entry, framecode: str, overwrite: bool
):
    if is_save_frame_name_in_entry(entry, framecode) and not overwrite:
        msg = f"""\
                a frame with the name {framecode} already exists in entry {entry.entry_id}
                use --force to overwrite it
            """
        exit_error(msg)


def _parse_category_name_specs(specs: List[str]) -> List[Tuple[str, str]]:
    """Parse frame specifications into category/id pairs using two-phase processing.

    Phase 1: Split args into flat component list based on unescaped dots
    Phase 2: Pair up components as (category, id)

    Rules:
    - If arg contains unescaped '.': split at first unescaped dot → two components
    - If arg has no unescaped '.': → one component
    - Escaped '\\.' is treated as literal dot in the name
    - Components are then paired up left-to-right

    Args:
        specs: List of specifications

    Returns:
        List of (category, id) tuples
    """
    # Phase 1: Split into flat component list
    components = []
    for spec in specs:
        unescaped_dot_pos = _find_first_unescaped_dot(spec)

        if unescaped_dot_pos is not None:
            # Has unescaped dot: split into two components
            category = _unescape_back_slashes(spec[:unescaped_dot_pos])
            id_part = _unescape_back_slashes(spec[unescaped_dot_pos + 1 :])

            if not category:
                exit_error(
                    f"invalid frame specification '{spec}': expected 'category.id' format, but category was empty"
                )

            components.extend([category, id_part])
        else:
            # No unescaped dot: single component
            components.append(_unescape_back_slashes(spec))

    # Phase 2: Pair up components
    if not components:
        exit_error("no frame specifications provided")

    # If odd number of components, treat last one as singleton (empty id)
    if len(components) % 2 != 0:
        components.append("")

    pairs = list(chunks(components, 2))
    return pairs


def _find_first_unescaped_dot(s: str) -> Optional[int]:
    """Find position of first dot not escaped by backslash.

    A dot is escaped if preceded by an odd number of backslashes.

    Returns:
        Position of first unescaped dot, or None if no unescaped dot found
    """
    consecutive_backslashes = 0

    for i, char in enumerate(s):
        if char == "\\":
            consecutive_backslashes += 1
        elif char == ".":
            # Check if this dot is escaped (odd number of backslashes)
            if consecutive_backslashes % 2 == 0:
                return i
            consecutive_backslashes = 0
        else:
            consecutive_backslashes = 0

    return None


def _unescape_back_slashes(s: str) -> str:
    """Remove escape sequences from string.

    Processes:
    - \\\\ → \\
    - \\. → .
    - \\<any> → <any>
    """
    result = []
    it = iter(s)
    for char in it:
        if char == "\\":
            # Next character is escaped
            next_char = next(it, None)
            if next_char is not None:
                result.append(next_char)
            else:
                # Trailing backslash - keep it
                result.append(char)
        else:
            result.append(char)
    return "".join(result)
