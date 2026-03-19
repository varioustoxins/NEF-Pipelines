from fnmatch import fnmatch
from typing import Dict, List, Optional, Tuple

from pynmrstar import Saveframe

from nef_pipelines.lib.cli_lib import parse_selector_lists

# TODO: Move separator escaping functionality to cli_lib and consolidate
#       namespace separator handling there. This will provide a unified
#       approach for handling separators across all commands.

# Registered namespace mapping from NEF specification
# TODO [long term] we should download from the NEF website and use this as a fallback
REGISTERED_NAMESPACES = {
    "nef": ("NEF Standard", "Data Exchange"),
    "nefpls": ("NEF Pipelines", "Format transcoding and NEF manipulation"),
    "amber": ("Amber", "Structure modelling and refinement"),
    "aria": ("Aria", "Structure calculation"),
    "ccpn": ("CcpNmr Analysis", "NMR spectra processing and data analysis"),
    "csrosetta": ("CS-Rosetta", "Structure calculation"),
    "cyana": ("Cyana", "Structure calculation"),
    "meld": ("MELD", "Structure modelling and refinement"),
    "NMRFx": ("NMRFx", "Structure calculation"),
    "pdbstat": ("PDBStat", "NMR data validation"),
    "unio": ("Unio NMR", "Structure calculation"),
    "unres": ("Unres", "Structure modelling and refinement"),
    "pdbx": ("wwPDB/BMRB", "Database"),
    "XplorNIH": ("Xplor-NIH", "Structure calculation and refinement"),
    "yasara": ("Yasara", "Structure refinement"),
}


def extract_namespace(name: str) -> Optional[str]:
    """
    Extract namespace from a tag, loop, or frame name.

    Patterns:
        - Loop/tag: _<namespace>_<rest> → namespace
        - Frame category: <namespace>_<rest> → namespace

    Examples:
        _nef_sequence → nef (loop category)
        _custom_data → custom (loop category)
        _nef_peak.position → nef (tag name)
        nef_molecular_system → nef (frame category)
        custom_data_frame → custom (frame category)

    Args:
        name: Tag, loop category, or frame category

    Returns:
        Namespace string or None if pattern doesn't match
    """
    # Handle loop categories and tags (start with _)
    if name.startswith("_"):
        parts = name[1:].split("_", 1)
        if len(parts) >= 2:
            return parts[0]
        return None

    # Handle frame categories (no leading _)
    # Extract namespace as first part before underscore
    parts = name.split("_", 1)
    if len(parts) >= 2:
        return parts[0]

    return None


def collect_namespaces_from_frames(
    frames: List[Saveframe],
) -> Dict[str, List[Tuple[str, str, Optional[str], str]]]:
    """
    Collect all namespaces from frames, loops, and tags.

    Args:
        frames: List of saveframes to process

    Returns:
        Dict mapping namespace → list of (frame_name, frame_category, loop_category, level_type) tuples
        where:
        - frame_category is frame.category
        - loop_category is loop.category for loops, None for frames
        - level_type is 'frame', 'loop', 'column-tag', or 'tag'
    """
    namespaces = {}
    seen = set()

    for frame in frames:
        # Check frame.category for namespace
        frame_ns = extract_namespace(frame.category)
        if frame_ns:
            key = (frame_ns, frame.name, frame.category, None, "frame")
            if key not in seen:
                namespaces.setdefault(frame_ns, []).append(
                    (frame.name, frame.category, None, "frame")
                )
                seen.add(key)

        # Note: Frame tags (like sf_category, note, description) are NOT namespace-prefixed
        # They are just plain tags within the frame. We only extract namespaces from
        # tags that start with underscore (which appear in loops).

        for loop in frame.loops:
            # Check loop.category for namespace
            loop_ns = extract_namespace(loop.category)
            if loop_ns:
                key = (loop_ns, frame.name, frame.category, loop.category, "loop")
                if key not in seen:
                    namespaces.setdefault(loop_ns, []).append(
                        (frame.name, frame.category, loop.category, "loop")
                    )
                    seen.add(key)

            # Note: Loop tags (accessed via loop.tags) are plain names like 'chain_code', 'atom_name'
            # They do NOT have namespace prefixes - they inherit the loop's namespace
            # So we don't extract namespaces from loop.tags

    return namespaces


def filter_namespaces(
    all_namespaces: set,
    namespace_selectors: List[str],
    use_separator_escapes: bool,
    invert: bool,
) -> set:
    """
    Filter namespaces based on selector patterns.

    Args:
        all_namespaces: Set of all namespace strings to filter
        namespace_selectors: Optional namespace patterns with +/- prefixes
        use_separator_escapes: If True, process escape sequences
        invert: If True, invert namespace selection logic

    Returns:
        Set of filtered namespace strings
    """

    result = all_namespaces

    if namespace_selectors:
        include, exclude = parse_selector_lists(
            namespace_selectors, use_separator_escapes, invert
        )

        filtered_namespaces = set()
        for ns in all_namespaces:
            if include:
                for pattern in include:
                    if fnmatch(ns, pattern):
                        filtered_namespaces.add(ns)
                        break
            else:
                filtered_namespaces.add(ns)

            if ns in filtered_namespaces:
                for pattern in exclude:
                    if fnmatch(ns, pattern):
                        filtered_namespaces.discard(ns)
                        break

        result = filtered_namespaces

    return result


def if_separator_conflicts_get_message(
    names: List[str], separators: List[str], use_escapes: bool
) -> Optional[tuple[list[str], list[str], list[tuple[str, str]]]]:
    """
    Check if any separator characters appear in names without escape flag enabled.

    Args:
        names: List of names to check
        separators: List of separator characters to check for
        use_escapes: If True, escapes are enabled so no error

    Returns:
        Tuple of (conflicting_names, found_separators, escape_sequences) if conflicts found,
        None if no conflicts or escapes enabled.
        - conflicting_names: List of names containing separators (up to 5, with count if more)
        - found_separators: List of separator characters that were found
        - escape_sequences: List of (separator, escape) tuples for building help message
    """
    result = None

    if not use_escapes:
        conflicts = []
        for name in names:
            for sep in separators:
                if sep in name:
                    conflicts.append((name, sep))

        if conflicts:
            # Get unique separators that were actually found in names
            found_separators = sorted(set(sep for _, sep in conflicts))

            # Get conflicting names (up to 5)
            unique_names = []
            seen = set()
            for name, _ in conflicts:
                if name not in seen:
                    unique_names.append(name)
                    seen.add(name)
                if len(unique_names) >= 5:
                    break

            # Build escape sequence info for found separators
            escape_sequences = [(sep, f"{sep}{sep}") for sep in found_separators]

            result = (unique_names, found_separators, escape_sequences)

    return result
