from pathlib import Path
from typing import List, Tuple

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    create_nef_save_frame,
    is_save_frame_name_in_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.structures import FrameAlreadyExistsError
from nef_pipelines.lib.util import (
    STDIN,
    chunks,
    exit_error,
    find_index_of_first_unescaped,
    parse_comma_separated_options,
    unescape_backslashes,
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

    try:
        result = pipe(entry, pairs, overwrite=force)
    except FrameAlreadyExistsError as e:
        msg = f"""\
            {e}
            use --force to overwrite it
        """
        exit_error(msg)

    print(result)


def pipe(
    entry: Entry,
    category_name_pairs: List[Tuple[str, str]],
    overwrite: bool = False,
) -> Entry:
    """Create one or more empty NEF saveframes and add them to entry.

    Raises:
        FrameAlreadyExistsError: If frame already exists and overwrite=False
    """

    for category, id_part in category_name_pairs:

        framecode = _build_framecode(category, id_part)

        _raise_if_frame_exists_and_no_overwrite(entry, framecode, overwrite)

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


def _raise_if_frame_exists_and_no_overwrite(
    entry: Entry, framecode: str, overwrite: bool
):
    """Raise FrameAlreadyExistsError if frame exists and overwrite is False."""
    if is_save_frame_name_in_entry(entry, framecode) and not overwrite:
        raise FrameAlreadyExistsError(framecode, entry.entry_id)


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
        unescaped_dot_pos = find_index_of_first_unescaped(spec, ".")

        if unescaped_dot_pos is not None:
            # Has unescaped dot: split into two components
            category = unescape_backslashes(spec[:unescaped_dot_pos])
            id_part = unescape_backslashes(spec[unescaped_dot_pos + 1 :])

            if not category:
                exit_error(
                    f"invalid frame specification '{spec}': expected 'category.id' format, but category was empty"
                )

            components.extend([category, id_part])
        else:
            # No unescaped dot: single component
            components.append(unescape_backslashes(spec))

    # Phase 2: Pair up components
    if not components:
        exit_error("no frame specifications provided")

    # If odd number of components, treat last one as singleton (empty id)
    if len(components) % 2 != 0:
        components.append("")

    pairs = list(chunks(components, 2))
    return pairs
