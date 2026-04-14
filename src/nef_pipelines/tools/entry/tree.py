"""\
NEF entry tree visualization command.

Displays the hierarchical structure of NEF entries as a tree:
Entry → Frames → Loops → Tags
"""

from fnmatch import fnmatchcase
from pathlib import Path
from typing import List, Optional, Set, Tuple

import typer
from click import Context
from pynmrstar import Entry, Loop, Saveframe
from treelib import Node, Tree

from nef_pipelines.lib.cli_lib import parse_frame_loop_and_tags
from nef_pipelines.lib.namespace_lib import (
    NO_NAMESPACE,
    EntryPart,
    filter_namespaces,
    get_namespace,
)
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.tree_lib import (
    ENTRY_COLOUR,
    FRAME_COLOUR,
    LOOP_COLOUR,
    MATCHED_COLOUR,
    METADATA_COLOUR,
    TAG_COLOUR,
    ColourOutputPolicy,
    build_filtered_tree_from_retained_nodes,
    get_all_descendants_of_node,
    prune_tree_to_matches,
    render_tree,
)
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    find_substring_with_wildcard,
    parse_comma_separated_options,
    warn,
)
from nef_pipelines.tools.entry import entry_app

# TODO: Node type filtering feature - commented out for future consideration
# class NodeType(LowercaseStrEnum, KebabCaseStrEnum):
#     """\
#     Types of nodes in NEF tree for filtering.
#     """
#     FRAME = auto()
#     LOOP = auto()
#     FRAME_TAG = auto()
#     LOOP_TAG = auto()


class NefNode(Node):
    """\
    Custom tree node for NEF structure with typed properties.

    Extends treelib.Node to add NEF-specific metadata as properties
    instead of dictionary access.
    """

    def __init__(
        self,
        namespace: str,
        entry_part: EntryPart,
        frame_name: Optional[str] = None,
        loop_category: Optional[str] = None,
        saveframe: Optional[Saveframe] = None,
        loop: Optional[Loop] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.namespace = namespace
        self.entry_part = entry_part
        self.frame_name = frame_name
        self.loop_category = loop_category
        self.saveframe = saveframe
        self.loop = loop


@entry_app.command()
def tree(
    context: Context,
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="read NEF data from a file instead of stdin",
    ),
    selectors: Optional[List[str]] = typer.Argument(
        None,
        help="""\
            select nodes to display by frame/loop/tag names (wildcards are supported and you can use
            <FRAME>.<LOOP>:<TAG>[,<TAG>...] syntax)
        """,
    ),
    colour_policy: ColourOutputPolicy = typer.Option(
        ColourOutputPolicy.AUTO,
        "--colour-policy",
        help="colour output policy: plain (no colours), auto (detect terminal), colour (force colours)",
    ),
    no_highlight: bool = typer.Option(
        False,
        "--no-highlight",
        help="disable matched string highlighting (keep other colours)",
    ),
    children: bool = typer.Option(
        False,
        "--children",
        help="show all children of nodes found by the selectors",
    ),
    namespaces: Optional[List[str]] = typer.Option(
        None,
        "--namespace",
        help="""\
            filter frames by namespace (use +<NAMESPACE> to include a namespace, and -<NAMESPACE> to exclude a
            namespace. - excludes all name spaces and + adds to the set of included namespaces. By default all
            namespaces are included, and with --no-initial-selection the logic is inverted). Multiple filters can be
            added or removed by using the same option multiple times or separating filters / selectors with commas
            [no spaces!]
            ```
            e.g. -,+ccpn would just shown items in the ccpn namespace (clear all, add ccpn)
                 --no-initial-selection  --namespace +ccpn would do the same (start empty, add ccpn)
                 -ccpn would show all except ccpn frames
            ```
        """,
    ),
    no_initial_selection: bool = typer.Option(
        False,
        "--no-initial-selection",
        help="start with empty namespace selection instead of all",
    ),
    # node_type: Optional[List[NodeType]] = typer.Option(
    #     None,
    #     "--node-type",
    #     help="""\
    #         filter to show only matched nodes of specific types and their parents
    #         (frame, loop, frame_tag, loop_tag). Can be specified multiple times
    #     """,
    # ),
) -> None:
    """\
    - display the hierarchical tree structure of NEF entry

    Displays the structure  Entry → Frames → Loops → Tags  [values are not shown]

    Farme/Loop/Tag selectors use progressive AND refinement - each filter narrows the previous results.
    Supports both simple wildcards and the frame.loop:tag syntax

    Namespace filtering allows including/excluding frames by namespace prefix:
    - Starts with ALL namespaces by default
    - -namespace removes namespace from set
    - +namespace adds namespace to set
    - \\- alone clears all namespaces
    - \\+ alone adds all namespaces
    - --no-initial-selection starts with empty set instead of all

    Node type filtering restricts matches to specific node types (and their parents).
    Multiple types can be combined.

    Examples:
    ```bash
        nef entry tree file.nef                              # Full tree
        nef entry tree file.nef chain_code                   # Filter by tag name (highlights "chain" in bold red)
        nef entry tree file.nef molecular_system             # Filter by frame name
        nef entry tree file.nef shift chain_code             # Progressive: shift AND chain_code
        nef entry tree file.nef shift chain_code --children  # Show all shift children
        nef entry tree file.nef shift.chemical_shift:atom    # Using frame.loop:tag syntax
        nef entry tree file.nef --namespace -,+nef           # Show only nef frames (clear all, add nef)
        nef entry tree file.nef --namespace -ccpn            # Show all except ccpn frames
        nef entry tree file.nef --namespace +ccpn --no-initial-selection # Show only ccpn frames (start empty, add ccpn)
        nef entry tree file.nef chain --no-highlight         # Filter but don't highlight substring
e.g        nef entry tree file.nef chain --node-type loop-tag   # Only show loop tags matching "chain"
        nef entry tree file.nef shift --node-type frame --node-type loop  # Show frames and loops matching "shift"
        cat file.nef | nef entry tree                        # From stdin
    ```
    """

    if selectors and len(selectors) > 0 and Path(selectors[0]).is_file():
        if input != STDIN:
            msg = "you specified two inputs --input {input} and {putative_file} please choose only one!"
            exit_error(msg)
        else:
            input = selectors[0]
            selectors = selectors[1:]

    selectors = parse_comma_separated_options(selectors)

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    output = pipe(
        entry,
        selectors,
        colour_policy,
        no_highlight,
        children,
        namespaces,
        no_initial_selection,  # , node_type
    )
    print(output, end="")


def pipe(
    entry: Entry,
    node_selectors: Optional[List[str]] = None,
    colour_policy: ColourOutputPolicy = ColourOutputPolicy.AUTO,
    no_highlight: bool = False,
    show_children: bool = False,
    namespace_selectors: Optional[List[str]] = None,
    no_initial_selection: bool = False,
    # node_types: Optional[List[NodeType]] = None,
) -> str:
    """\
    Generate tree visualization of NEF structure.

    Args:
        entry: Input NEF entry
        node_selectors: List of filter patterns (progressive AND refinement - each filter narrows results)
        colour_policy: ColorPolicy for output (plain, auto, colour)
        no_highlight: If True, disable substring highlighting (keep other colours)
        show_children: If True, preserve all descendants of first filter matches
        namespace_selectors: List of namespace filters (+nef to include, -ccpn to exclude)
        no_initial_selection: If True, start with empty namespace selection instead of all
        node_types: Optional list of node types to restrict matches to (frame, loop, frame-tag, loop-tag)
                    [not implimented]

    Returns:
        Formatted tree as string
    """
    # Build tree from entry (no namespace filtering at entry level)
    full_tree = _build_nef_tree_structure(entry)

    # Apply node selector filtering if requested
    if node_selectors:
        filtered_tree = _filter_tree_by_node_selectors(
            full_tree, node_selectors, show_children
        )

        # Expand to include all frame children if --children flag set (for multi-filter case)
        # This ensures ALL descendants of frames from first match are shown, not just final matches
        if show_children and len(filtered_tree) > 0 and len(node_selectors) > 1:
            filtered_tree = _expand_filtered_tree_with_children_of_nodes(
                full_tree, filtered_tree
            )

        # Apply node type filtering if requested (after children expansion)
        # but preserve the originally matched nodes and their ancestors
        # if node_types:
        #     filtered_tree = _filter_by_node_type_preserving_matches(filtered_tree, node_types)
    else:
        filtered_tree = full_tree

    # Apply namespace filtering LAST (after all expansions and node selections)
    # This ensures tags/loops added by --children are also filtered by namespace
    if namespace_selectors:
        filtered_tree = _filter_tree_by_namespace(
            filtered_tree, namespace_selectors, no_initial_selection
        )

    # Render tree with optional highlighting
    highlight_patterns = None if no_highlight else node_selectors
    return _render_tree(filtered_tree, colour_policy, highlight_patterns)


def _filter_tree_by_node_selectors(
    tree: Tree, selectors: List[str], show_children: bool = False
) -> Tree:
    """\
    Apply progressive AND filtering with node selectors.

    Each selector narrows the results further.

    Args:
        tree: Tree to filter
        selectors: List of patterns to match (applied sequentially as AND)
        show_children: If True, include all descendants in final result

    Returns:
        Filtered tree
    """
    # For intermediate filters, include descendants so next filter can match
    # For the last filter, only include descendants if show_children is True
    for i, pattern in enumerate(selectors):
        is_last = i == len(selectors) - 1
        include_descendants = show_children if is_last else True

        if i == 0:
            filtered_tree = _filter_tree_with_strings_or_selectors(
                tree, pattern, include_descendants
            )
        else:
            filtered_tree = _filter_tree_with_strings_or_selectors(
                filtered_tree, pattern, include_descendants
            )

        if len(filtered_tree) == 0:
            break

    return filtered_tree


def _expand_filtered_tree_with_children_of_nodes(
    full_tree: Tree, filtered_tree: Tree
) -> Tree:
    """\
    Expand filtered tree to include all children of matched frames.

    When using --children flag, all descendants of frames matching the
    first filter are preserved, even if they don't match subsequent filters.

    Args:
        full_tree: Complete unfiltered tree
        filtered_tree: Tree after node selector filtering

    Returns:
        Filtered tree with all frame descendants preserved
    """

    descendants = set()
    matched_frames = set()

    for node in filtered_tree.all_nodes_itr():
        if node.identifier.startswith("frame:"):
            matched_frames.add(node.identifier)

    for frame_id in matched_frames:
        descendants.update(get_all_descendants_of_node(full_tree, frame_id))

    return _expand_tree_with_children(full_tree, filtered_tree, descendants)


def _warn_null_namespaces(null_namespace_nodes: List[str]) -> None:
    """\
    Warn about frames/loops with null namespace (illegal in NEF format).

    Args:
        null_namespace_nodes: List of node identifiers with null namespace
    """
    if null_namespace_nodes:
        count = len(null_namespace_nodes)
        count_str = "lots of" if count > 10 else str(count)

        examples = [n.split(":", 1)[1] for n in null_namespace_nodes[:3]]
        examples_str = ", ".join(f'"{e}"' for e in examples)
        if count > 3 and count <= 10:
            examples_str += f" (and {count - 3} more)"
        elif count > 10:
            examples_str += " ..."

        msg = f"""\
            Found {count_str} frames/loops with no namespace in their names: {examples_str}
            NEF saveframes/loops should have the format "<namespace>_<category_and_id>",
        e.g. "nef_chemical_shift_list_default" [namespace: nef, category: shift_list, id: default].
        """
        warn(msg)


def _collect_namespaces_from_tree(tree: Tree) -> Tuple[Set[str], List[str]]:
    """\
    Collect all namespaces from tree nodes and identify null namespace nodes.

    Args:
        tree: Tree to scan

    Returns:
        Tuple of (all_namespaces, null_namespace_nodes)
        - all_namespaces: Set of namespace strings found
        - null_namespace_nodes: List of node IDs with NO_NAMESPACE
    """
    all_namespaces = set()
    null_namespace_nodes = []

    for node in tree.all_nodes_itr():
        if node.identifier == "entry" or not isinstance(node, NefNode):
            continue

        namespace = node.namespace
        if namespace == NO_NAMESPACE:
            if node.entry_part in (EntryPart.Saveframe, EntryPart.Loop):
                null_namespace_nodes.append(node.identifier)
        else:
            all_namespaces.add(namespace)

    return all_namespaces, null_namespace_nodes


def _filter_frames_by_namespace(tree: Tree, included_namespaces: Set[str]) -> Set[str]:
    """\
    Filter frame nodes by namespace.

    Args:
        tree: Tree to filter
        included_namespaces: Set of namespaces to keep

    Returns:
        Set of frame node IDs matching namespace criteria
    """
    kept_frames = set()

    for node in tree.all_nodes_itr():
        if isinstance(node, NefNode) and node.entry_part == EntryPart.Saveframe:
            if node.namespace in included_namespaces:
                kept_frames.add(node.identifier)

    return kept_frames


def _filter_frame_descendants_by_namespace(
    tree: Tree, frame_ids: Set[str], included_namespaces: Set[str]
) -> Set[str]:
    """\
    Filter descendants within frames by namespace.

    For each frame, include descendants (loops/tags) whose namespace
    is in the included set.

    Args:
        tree: Tree containing frames
        frame_ids: Set of frame IDs to process
        included_namespaces: Set of namespaces to keep

    Returns:
        Set of node IDs to keep (frames + filtered descendants)
    """
    nodes_to_keep = {"entry"}
    nodes_to_keep.update(frame_ids)

    for frame_id in frame_ids:
        frame_subtree = tree.subtree(frame_id)

        for node in frame_subtree.all_nodes():
            if node.identifier == frame_id:
                continue

            if isinstance(node, NefNode) and node.namespace in included_namespaces:
                current = tree.get_node(node.identifier)
                while current and current.identifier != frame_id:
                    nodes_to_keep.add(current.identifier)
                    current = tree.parent(current.identifier)

    return nodes_to_keep


def _filter_tree_by_namespace(
    tree: Tree, namespace_selectors: List[str], no_initial_selection: bool
) -> Tree:
    """\
    Filter tree hierarchically by namespace (frames → loops → tags).

    Hierarchical filtering: First filter frames by namespace, then within kept frames,
    filter descendants (loops/tags) by their namespace.

    Args:
        tree: Tree to filter
        namespace_selectors: List of namespace selectors (+nef, -ccpn, -, etc.)
        no_initial_selection: If True, start with empty set instead of all namespaces

    Returns:
        Filtered tree with only nodes matching namespace criteria
    """
    all_namespaces, null_namespace_nodes = _collect_namespaces_from_tree(tree)
    _warn_null_namespaces(null_namespace_nodes)

    included_namespaces = filter_namespaces(
        all_namespaces,
        namespace_selectors,
        use_separator_escapes=False,
        no_initial_selection=no_initial_selection,
    )

    kept_frames = _filter_frames_by_namespace(tree, included_namespaces)
    nodes_to_keep = _filter_frame_descendants_by_namespace(
        tree, kept_frames, included_namespaces
    )

    return build_filtered_tree_from_retained_nodes(tree, nodes_to_keep)


# TODO: Node type filtering functions - commented out for future consideration
#
# def _filter_by_node_type_preserving_matches(tree: Tree, node_types: List[NodeType]) -> Tree:
#     """\
#     Filter tree to show only nodes of specific types and their parents,
#     but preserve all matched nodes (from the original selector filtering) and their ancestors.
#
#     This ensures that nodes matching the selector are always visible, even if they
#     don't match the node type filter.
#
#     Args:
#         tree: Tree already filtered by node selectors (all nodes here matched the selector)
#         node_types: List of NodeType values to filter for (FRAME, LOOP, FRAME_TAG, LOOP_TAG)
#
#     Returns:
#         Filtered tree with nodes of specified types plus all matched leaf nodes and their ancestors
#     """
#     from nef_pipelines.lib.tree_lib import _get_all_ancestors_of_node
#
#     nodes_to_keep = set()
#
#     for node in tree.all_nodes_itr():
#         node_id = node.identifier
#
#         if node_id == "entry":
#             nodes_to_keep.add(node_id)
#             continue
#
#         node_type = _classify_node_type(node_id)
#
#         # Keep nodes that match the requested types
#         if node_type in node_types:
#             nodes_to_keep.add(node_id)
#             nodes_to_keep.update(_get_all_ancestors_of_node(tree, node_id))
#         # Also keep leaf nodes (these are the actual matches) and their ancestors
#         elif node.is_leaf():
#             nodes_to_keep.add(node_id)
#             nodes_to_keep.update(_get_all_ancestors_of_node(tree, node_id))
#
#     return build_filtered_tree_from_retained_nodes(tree, nodes_to_keep)
#
#
# def _classify_node_type(node_id: str) -> Optional[NodeType]:
#     """\
#     Classify a node identifier into its NodeType.
#
#     Args:
#         node_id: Node identifier (e.g., "frame:name", "tag:frame:loop:tag")
#
#     Returns:
#         NodeType or None if unclassifiable
#     """
#     if node_id == "entry":
#         return None
#
#     if node_id.startswith("frame:"):
#         return NodeType.FRAME
#
#     if node_id.startswith("loop:"):
#         return NodeType.LOOP
#
#     if node_id.startswith("tag:"):
#         parts = node_id.split(":", 3)
#         if len(parts) == 3:
#             return NodeType.FRAME_TAG
#         elif len(parts) == 4:
#             return NodeType.LOOP_TAG
#
#     return None
#
#
# def _find_hidden_node_types(tree: Tree, shown_node_types: List[NodeType]) -> Set[NodeType]:
#     """\
#     Find which matched node types will be hidden by node type filtering.
#
#     Args:
#         tree: Tree with matched nodes (before node type filtering)
#         shown_node_types: Node types that will be shown
#
#     Returns:
#         Set of NodeType values that exist in tree but won't be shown
#     """
#     all_matched_types = set()
#
#     for node in tree.all_nodes_itr():
#         if node.identifier == "entry":
#             continue
#
#         node_type = _classify_node_type(node.identifier)
#         if node_type:
#             all_matched_types.add(node_type)
#
#     # Return types that are matched but not shown
#     return all_matched_types - set(shown_node_types)
#
#
# def _format_hidden_nodes_warning(hidden_types: Set[NodeType]) -> str:
#     """\
#     Format warning message about hidden matched nodes.
#
#     Args:
#         hidden_types: Set of NodeType values that are hidden
#
#     Returns:
#         Formatted warning string
#     """
#     if not hidden_types:
#         return ""
#
#     # Convert node types to readable names with hyphens
#     type_names = sorted([str(nt) for nt in hidden_types])
#     types_str = ", ".join(type_names)
#
#     if len(hidden_types) == 1:
#         return f"Note: Matched {types_str} nodes are hidden by --node-type filtering.
#                  Remove --node-type to see all matches."
#     else:
#         return f"Note: Matched nodes of types ({types_str}) are hidden by --node-type filtering.
#                  Remove --node-type to see all matches."


def _filter_tree_with_strings_or_selectors(
    tree: Tree, pattern: str, include_descendants: bool = False
) -> Tree:
    """\
    Filter tree trying simple pattern first, then frame.loop:tag syntax if no matches.

    Args:
        tree: Tree to filter
        pattern: Pattern string (simple or frame.loop:tag syntax)
        include_descendants: If True, include all child nodes of matches

    Returns:
        Filtered tree
    """
    simple_result = prune_tree_to_matches(
        tree,
        [pattern],
        include_descendants=include_descendants,
    )

    if len(simple_result) > 0:
        return simple_result

    try:
        selector = parse_frame_loop_and_tags(pattern)
        nodes_to_keep = _match_nodes_by_selector(tree, selector)

        if nodes_to_keep:
            from nef_pipelines.lib.tree_lib import (
                build_filtered_tree_from_retained_nodes,
            )

            return build_filtered_tree_from_retained_nodes(tree, nodes_to_keep)
    except Exception:
        pass

    return simple_result


def _match_nodes_by_selector(tree: Tree, selector) -> Set[str]:
    """\
    Match tree nodes using parsed frame.loop:tag selector.

    Uses case-sensitive matching.

    Args:
        tree: Tree to search
        selector: Parsed FrameLoopAndTags selector

    Returns:
        Set of matching node IDs (with ancestors and descendants)
    """
    from nef_pipelines.lib.tree_lib import (
        _get_all_ancestors_of_node,
        get_all_descendants_of_node,
    )

    nodes_to_keep = set()

    for node in tree.all_nodes_itr():
        node_id = node.identifier

        if node_id.startswith("tag:"):
            parts = node_id.split(":", 3)
            if len(parts) == 4:
                _, frame_name, loop_name, tag_name = parts

                frame_match = fnmatchcase(frame_name, f"*{selector.frame_name}*")

                loop_match = True
                if selector.loop_name:
                    loop_match = fnmatchcase(loop_name, f"*{selector.loop_name}*")

                tag_match = False
                for tag_pattern in selector.loop_tags or []:
                    if fnmatchcase(tag_name, f"*{tag_pattern}*"):
                        tag_match = True
                        break

                if frame_match and loop_match and tag_match:
                    nodes_to_keep.add(node_id)
                    nodes_to_keep.update(_get_all_ancestors_of_node(tree, node_id))
                    nodes_to_keep.update(get_all_descendants_of_node(tree, node_id))

    return nodes_to_keep


def _add_frame_to_tree(tree: Tree, frame: Saveframe) -> None:
    """\
    Add a frame and its tags to the tree.

    Args:
        tree: Tree to add to
        frame: Saveframe to add
    """
    frame_id = f"frame:{frame.name}"
    loop_count = len(frame.loops)
    loops_text = "loop" if loop_count == 1 else "loops"

    frame_namespace = get_namespace(frame, EntryPart.Saveframe)

    frame_node = NefNode(
        tag=f"{frame.name} \\[frame: {loop_count} {loops_text}]",
        identifier=frame_id,
        namespace=frame_namespace,
        entry_part=EntryPart.Saveframe,
        frame_name=frame.name,
        saveframe=frame,
    )
    tree.add_node(frame_node, parent="entry")

    for tag_name, _tag_value in frame.tag_iterator():
        tag_id = f"tag:{frame.name}:{tag_name}"
        tag_namespace = get_namespace(tag_name, EntryPart.FrameTag, frame_namespace)

        tag_node = NefNode(
            tag=tag_name,
            identifier=tag_id,
            namespace=tag_namespace,
            entry_part=EntryPart.FrameTag,
            frame_name=frame.name,
        )
        tree.add_node(tag_node, parent=frame_id)


def _add_loop_to_tree(tree: Tree, frame: Saveframe, loop: Loop) -> None:
    """\
    Add a loop and its tags to the tree.

    Args:
        tree: Tree to add to
        frame: Parent saveframe
        loop: Loop to add
    """
    frame_id = f"frame:{frame.name}"
    loop_id = f"loop:{frame.name}:{loop.category}"

    row_count = len(loop.data)
    rows_text = "row" if row_count == 1 else "rows"
    display_category = loop.category.lstrip("_")

    loop_namespace = get_namespace(loop, EntryPart.Loop)

    loop_node = NefNode(
        tag=f"{display_category} \\[loop: {row_count} {rows_text}]",
        identifier=loop_id,
        namespace=loop_namespace,
        entry_part=EntryPart.Loop,
        frame_name=frame.name,
        loop_category=loop.category,
        loop=loop,
    )
    tree.add_node(loop_node, parent=frame_id)

    for tag in loop.tags:
        tag_id = f"tag:{frame.name}:{loop.category}:{tag}"
        tag_namespace = get_namespace(tag, EntryPart.LoopTag, loop_namespace)

        tag_node = NefNode(
            tag=tag,
            identifier=tag_id,
            namespace=tag_namespace,
            entry_part=EntryPart.LoopTag,
            frame_name=frame.name,
            loop_category=loop.category,
        )
        tree.add_node(tag_node, parent=loop_id)


def _build_nef_tree_structure(entry: Entry) -> Tree:
    """\
    Build complete tree from NEF entry.

    Tree structure:
        entry_id (root)
        ├── frame_name [frame]
        │   ├── sf_category = value
        │   ├── other_tag = value
        │   └── _loop_category [loop]
        │       ├── column_1
        │       ├── column_2
        │       └── (N rows)

    Args:
        entry: pynmrstar Entry object

    Returns:
        Tree with complete NEF structure
    """
    tree = Tree()
    tree.create_node(tag=entry.entry_id, identifier="entry")

    for frame in entry.frame_list:
        _add_frame_to_tree(tree, frame)

        for loop in frame.loops:
            _add_loop_to_tree(tree, frame, loop)

    return tree


def _render_tree(
    tree: Tree,
    colour_policy: ColourOutputPolicy,
    filter_patterns: Optional[List[str]] = None,
) -> str:
    """\
    Render tree as string (coloured or plain).

    Args:
        tree: Tree to render
        colour_policy: ColorPolicy for output (plain, auto, colour)
        filter_patterns: Optional filter patterns used for highlighting

    Returns:
        Formatted tree string
    """
    if len(tree) == 0:
        return "No matching nodes found.\n"

    return render_tree(
        tree,
        _colour_nef_node,
        colour_policy,
        filter_patterns=filter_patterns,
    )


# TODO [future] move to tree_lib
def _expand_tree_with_children(
    full_tree: Tree, filtered_tree: Tree, descendants: set
) -> Tree:
    """\
    Merge descendant nodes back into filtered tree.

    Child nodes that would normally be filtered out by additional filter
    patterns are preserved due to the --children flag.

    When using --children with multiple filters:
    1. First filter matches some nodes (e.g., "molecular_system")
    2. Second filter further refines matches (e.g., "residue")
    3. Without --children: only nodes matching BOTH filters are shown
    4. With --children: all descendants of first-filter matches are kept
       (even if they don't match subsequent filters)

    Example:
        nef entry tree file.nef molecular_system residue --children
        Shows molecular_system frame and ALL its children (even non-residue tags),
        not just residue-related children.

    Args:
        full_tree: Complete unfiltered tree
        filtered_tree: Tree after filtering
        descendants: Set of node IDs to preserve (descendants from first match)

    Returns:
        Tree with descendants added back
    """

    nodes_to_keep = set()
    for node in filtered_tree.all_nodes_itr():
        nodes_to_keep.add(node.identifier)

    nodes_to_keep.update(descendants)

    return build_filtered_tree_from_retained_nodes(full_tree, nodes_to_keep)


# TODO [future] move to tree_lib
def _apply_highlight_to_match(
    text: str, match_span: Tuple[int, int], base_colour: Optional[str] = None
) -> str:
    """\
    Apply highlight to matched portion.

    If base_colour provided, applies it to non-matched portions.

    Args:
        text: Text to highlight
        match_span: Tuple of (start, end) indices
        base_colour: Optional Rich colour for non-matched portions

    Returns:
        Text with Rich markup highlighting the matched portion
    """
    start, end = match_span
    before = text[:start]
    matched = text[start:end]
    after = text[end:]

    result = ""
    if base_colour and before:
        result += f"[{base_colour}]{before}[/{base_colour}]"
    else:
        result += before

    result += f"[{MATCHED_COLOUR}]{matched}[/{MATCHED_COLOUR}]"

    if base_colour and after:
        result += f"[{base_colour}]{after}[/{base_colour}]"
    else:
        result += after

    return result


# TODO [future] move to tree_lib
def _apply_colour_with_optional_highlight(
    text: str,
    colour: str,
    match_span: Optional[Tuple[int, int]],
    metadata: Optional[str] = None,
) -> str:
    """\
    Apply colour to text with optional highlighting of matched portion and optional metadata.

    Args:
        text: Text to colour
        colour: Rich colour name
        match_span: Optional (start, end) tuple for highlighting portion of text
        metadata: Optional metadata string to append in dimmed colour

    Returns:
        Rich-formatted string
    """
    if match_span:
        result = _apply_highlight_to_match(text, match_span, colour)
    else:
        result = f"[{colour}]{text}[/{colour}]"

    if metadata:
        result = f"{result} [{METADATA_COLOUR}]{metadata}[/{METADATA_COLOUR}]"

    return result


def _colour_nef_node(node: Node, filter_patterns: Optional[List[str]]) -> str:
    """\
    Apply rich colour markup to NEF tree node based on type.
    Highlights matched substring if filter patterns are provided.

    Colour constants are imported from tree_lib:
    - Entry (root): ENTRY_COLOUR
    - Frame names: FRAME_COLOUR (metadata in METADATA_COLOUR)
    - Loop names: LOOP_COLOUR (metadata in METADATA_COLOUR)
    - Tags: TAG_COLOUR
    - Matched substrings: MATCHED_COLOUR
    - Metadata ([frame: ...], [loop: ...], counts): METADATA_COLOUR

    Args:
        node: Node object with tag and is_leaf info
        filter_patterns: Optional list of filter patterns for highlighting

    Returns:
        Rich-formatted string with colour markup
    """
    node_tag = node.tag
    is_leaf = node.is_leaf()

    # Determine node type and extract name/metadata
    if "\\[frame:" in node_tag:
        parts = node_tag.split(" ", 1)
        name = parts[0]
        metadata = parts[1] if len(parts) > 1 else None
        colour = FRAME_COLOUR
    elif "\\[loop:" in node_tag:
        parts = node_tag.split(" ", 1)
        name = parts[0]
        metadata = parts[1] if len(parts) > 1 else None
        colour = LOOP_COLOUR
    elif is_leaf:
        name = node_tag
        metadata = None
        colour = TAG_COLOUR
    else:
        name = node_tag
        metadata = None
        colour = ENTRY_COLOUR

    # Find matched substring in the name (not the full tag with metadata)
    match_span = None
    if filter_patterns:
        for pattern in filter_patterns:
            match_span = find_substring_with_wildcard(name, pattern)
            if match_span:
                break  # Highlight first matching pattern only

    result = _apply_colour_with_optional_highlight(name, colour, match_span, metadata)

    return result
