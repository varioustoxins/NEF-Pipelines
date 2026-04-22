from fnmatch import fnmatchcase
from typing import Dict, List, Optional, Tuple, Union

from pynmrstar import Loop, Saveframe

from nef_pipelines.lib.cli_lib import (
    ALL_NAMESPACES,
    SelectorAction,
    parse_selector_lists,
)
from nef_pipelines.lib.structures import EntryPart, EntryPartValues

# TODO: [for future] Move separator escaping functionality to cli_lib and consolidate
#       namespace separator handling there. This will provide a unified
#       approach for handling separators across all commands.

# Null namespace constant - represents saveframes/loops without namespace separator
NO_NAMESPACE = ""

# Registered namespace mapping from NEF specification
# TODO [for future] we should download from the NEF website and use this as a fallback
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


def get_registered_namespaces():
    return {**REGISTERED_NAMESPACES}


def get_namespace(
    value: Union[str, Loop, Saveframe],
    node_type: EntryPart,
    parent_namespace: Optional[Union[str, Loop, Saveframe]] = None,
    known_namespaces: Optional[dict] = None,
) -> str:
    """\
    Determine the namespace for a saveframe, loop, or tag.

    For saveframes and loops: first token before _ is namespace (or "" if no underscore)
    For tags: if first token is registered namespace, use it; otherwise inherit from parent

    Args:
        value: Name string, Loop object, or Saveframe object
        node_type: EntryPart enum value (Saveframe, Loop, FrameTag, LoopTag)
        parent_namespace: Namespace string, Loop, or Saveframe (for tag inheritance)
        known_namespaces: Dict of registered namespaces (defaults to REGISTERED_NAMESPACES)

    Returns:
        Namespace string. Returns "" (null namespace) for saveframes/loops without underscore separator.
        Tags inherit from parent (including null namespace "") or default to "nef" if no parent.

    Examples:
        get_namespace("nef_molecular_system", EntryPart.Saveframe) → "nef"
        get_namespace("nef", EntryPart.Saveframe) → ""
        get_namespace("_nef_sequence", EntryPart.Loop) → "nef"
        get_namespace("_sequence", EntryPart.Loop) → ""
        get_namespace("ccpn_peaklist_name", EntryPart.FrameTag, "nef") → "ccpn"
        get_namespace("chain_code", EntryPart.LoopTag, "nef") → "nef"
        get_namespace("note", EntryPart.FrameTag, "") → ""
    """
    known_namespaces = (
        get_registered_namespaces() if not known_namespaces else known_namespaces
    )

    # Validate object type matches node_type
    if isinstance(value, Loop) and node_type != EntryPart.Loop:
        raise ValueError(
            f"Loop object provided but node_type is {node_type}, expected EntryPart.Loop"
        )
    if isinstance(value, Saveframe) and node_type != EntryPart.Saveframe:
        raise ValueError(
            f"Saveframe object provided but node_type is {node_type}, expected EntryPart.Saveframe"
        )

    # Convert value to string if it's a Loop or Saveframe object
    if isinstance(value, Loop):
        value_str = value.category
    elif isinstance(value, Saveframe):
        value_str = value.category
    else:
        value_str = value

    # Convert parent_namespace to string if needed
    if isinstance(parent_namespace, Loop):
        parent_namespace_str = get_namespace(
            parent_namespace.category, EntryPart.Loop, None, known_namespaces
        )
    elif isinstance(parent_namespace, Saveframe):
        parent_namespace_str = get_namespace(
            parent_namespace.category, EntryPart.Saveframe, None, known_namespaces
        )
    else:
        parent_namespace_str = parent_namespace

    # Extract first token using existing _extract_namespace function
    extracted = _extract_namespace(value_str)

    # Determine namespace based on node type
    if node_type == EntryPart.Saveframe:
        # Saveframes always use their own extracted namespace
        result = extracted
    elif node_type == EntryPart.Loop:
        if extracted and extracted in known_namespaces:
            # Loop has a recognised namespace prefix — use it
            result = extracted
        elif parent_namespace_str is not None:
            # Loop prefix is unregistered or absent — inherit from parent frame
            result = parent_namespace_str
        else:
            result = extracted
    elif extracted and extracted in known_namespaces:
        # For tags: if extracted namespace is a registered namespace, use it (explicit prefix)
        result = extracted
    else:
        # Otherwise inherit from parent (including null namespace), or default to nef if no parent
        result = parent_namespace_str if parent_namespace_str is not None else "nef"

    return result


def _extract_namespace(name: str) -> str:
    """
    Extract namespace token from a tag, loop, or frame name (private helper).

    This is a low-level string parser. External code should use get_namespace()
    which implements the full namespace determination algorithm.

    Patterns:
        - Loop/tag: _<namespace>_<rest> → namespace
        - Frame category: <namespace>_<rest> → namespace
        - No underscore separator → "" (null namespace)

    Examples:
        _nef_sequence → nef (loop category)
        _custom_data → custom (loop category)
        _nef_peak.position → nef (tag name)
        nef_molecular_system → nef (frame category)
        custom_data_frame → custom (frame category)
        nef → "" (null namespace)
        _sequence → "" (null namespace)

    Args:
        name: Tag, loop category, or frame category

    Returns:
        Namespace string, or "" (NO_NAMESPACE) if pattern doesn't match
    """
    # Guard against None input (malformed saveframes)
    if name is None:
        return NO_NAMESPACE

    if name.startswith("_"):
        name = name[1:]

    parts = name.split("_", 1)
    result = parts[0] if len(parts) >= 2 else NO_NAMESPACE

    return result


def collect_namespaces_from_frames(
    frames: List[Saveframe],
) -> Dict[str, List[EntryPartValues]]:
    """
    Collect all namespaces from frames, loops, and tags.

    Args:
        frames: List of saveframes to process

    Returns:
        Dict mapping namespace → list of EntryPartValues objects describing
        where each namespace occurs (frame, loop, or tag level)
    """
    namespaces = {}
    seen = set()

    for frame in frames:
        # Get frame namespace
        frame_namespace = get_namespace(frame, EntryPart.Saveframe)
        key = (frame_namespace, frame.name, frame.category, None, EntryPart.Saveframe)
        if key not in seen:
            namespaces.setdefault(frame_namespace, []).append(
                EntryPartValues(
                    frame_name=frame.name,
                    frame_category=frame.category,
                )
            )
            seen.add(key)

        # Collect frame tags (can have explicit namespace prefixes like ccpn_peaklist_name)
        for tag_name, _tag_value in frame.tag_iterator():
            tag_namespace = get_namespace(tag_name, EntryPart.FrameTag, frame_namespace)
            key = (
                tag_namespace,
                frame.name,
                frame.category,
                None,
                EntryPart.FrameTag,
                tag_name,
            )
            if key not in seen:
                namespaces.setdefault(tag_namespace, []).append(
                    EntryPartValues(
                        frame_name=frame.name,
                        frame_category=frame.category,
                        tag_name=tag_name,
                    )
                )
                seen.add(key)

        for loop in frame.loops:
            # Get loop namespace, inheriting from the parent frame if unregistered
            loop_namespace = get_namespace(loop, EntryPart.Loop, frame_namespace)
            key = (
                loop_namespace,
                frame.name,
                frame.category,
                loop.category,
                EntryPart.Loop,
            )
            if key not in seen:
                namespaces.setdefault(loop_namespace, []).append(
                    EntryPartValues(
                        frame_name=frame.name,
                        frame_category=frame.category,
                        loop_category=loop.category,
                    )
                )
                seen.add(key)

            # Collect loop tags (can have explicit namespace prefixes like ccpn_comment)
            for tag_name in loop.tags:
                tag_namespace = get_namespace(
                    tag_name, EntryPart.LoopTag, loop_namespace
                )
                key = (
                    tag_namespace,
                    frame.name,
                    frame.category,
                    loop.category,
                    EntryPart.LoopTag,
                    tag_name,
                )
                if key not in seen:
                    namespaces.setdefault(tag_namespace, []).append(
                        EntryPartValues(
                            frame_name=frame.name,
                            frame_category=frame.category,
                            loop_category=loop.category,
                            tag_name=tag_name,
                        )
                    )
                    seen.add(key)

    return namespaces


# TODO [for future consideration] what should happen about errors e.g. you list a thing to add that doesn't exist
#      and are the selectors
# fnmatch wildcards? if so we need to escape * and ?
def filter_namespaces(
    all_namespaces: set,
    namespace_selectors: List[str],
    use_separator_escapes: bool,
    no_initial_selection: bool = False,
) -> set:
    """
    Filter namespaces based on selector patterns.

    Args:
        all_namespaces: Set of all namespace strings to filter
        namespace_selectors: Optional namespace patterns with +/- prefixes
        use_separator_escapes: If True, process escape sequences
        no_initial_selection: If True, start with empty set; otherwise start with all

    Returns:
        Set of filtered namespace strings
    """

    result = all_namespaces

    if namespace_selectors:
        operations = parse_selector_lists(
            namespace_selectors, use_separator_escapes, no_initial_selection
        )

        filtered_namespaces = all_namespaces.copy()

        for action, pattern in operations:

            if action == SelectorAction.INCLUDE:
                if pattern is ALL_NAMESPACES:
                    filtered_namespaces = all_namespaces.copy()
                else:
                    for namespace in all_namespaces:
                        if fnmatchcase(namespace, pattern):
                            filtered_namespaces.add(namespace)
            elif action == SelectorAction.EXCLUDE:
                if pattern is ALL_NAMESPACES:
                    filtered_namespaces.clear()
                else:
                    for namespace in list(filtered_namespaces):
                        if fnmatchcase(namespace, pattern):
                            filtered_namespaces.discard(namespace)

        result = filtered_namespaces

    return result


def if_separator_conflicts_get_message(
    names: List[str], separators: List[str], use_escapes: bool
) -> Optional[Tuple[List[str], List[str], List[Tuple[str, str]]]]:
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
