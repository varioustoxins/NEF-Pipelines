"""\
Shared utilities for tree building and visualization.

Provides reusable functions for working with treelib Trees:
- Rich colored tree rendering with customizable styling
- Tree filtering with wildcard pattern matching
- Helper functions for tree manipulation
"""

import sys
from enum import auto
from fnmatch import fnmatchcase
from io import StringIO
from typing import Callable, List, Optional, Set

import wcmatch.fnmatch as fnmatch
from rich.console import Console
from rich.tree import Tree as RichTree
from treelib import Tree

from nef_pipelines.lib.typer_lib import is_rich_in_use


def render_tree_with_rich(
    tree: Tree,
    color_callback: Optional[Callable[[str, bool], str]] = None,
    plain: bool = False,
) -> str:
    """\
    Render tree using Rich with customizable node coloring.

    Args:
        tree: treelib.Tree object to render
        color_callback: Function (node_tag, is_leaf) -> styled_string for custom coloring
        plain: If True, disable colors (B&W output)

    Returns:
        Formatted tree string with ANSI codes (or plain if plain=True)
    """
    with StringIO() as output_buffer:
        if plain:
            console = Console(
                file=output_buffer, force_terminal=False, color_system=None
            )
        else:
            console = Console(file=output_buffer, force_terminal=True)

        root = tree.get_node(tree.root)
        root_styled = color_callback(root.tag, False) if color_callback else root.tag
        rich_tree = RichTree(root_styled)

        def add_children(treelib_node_id, rich_parent):
            children = tree.children(treelib_node_id)
            for child in children:
                if color_callback:
                    styled_label = color_callback(child.tag, child.is_leaf())
                else:
                    styled_label = child.tag

                new_branch = rich_parent.add(styled_label)
                add_children(child.identifier, new_branch)

        add_children(tree.root, rich_tree)
        console.print(rich_tree)
        return output_buffer.getvalue()


def render_plain_tree(tree: Tree) -> str:
    """\
    Render tree as plain text (B&W) using treelib's built-in formatting.

    Args:
        tree: Tree to render

    Returns:
        Plain text tree representation
    """
    if is_rich_in_use():
        return render_tree_with_rich(tree, plain=True)
    else:
        return tree.show(stdout=False)


def prune_tree_to_matches(
    tree: Tree,
    patterns: List[str],
    include_descendants: bool = True,
    exact: bool = False,
) -> Tree:
    # TODO: Add escape sequence support (use_escapes parameter) to allow matching

    """\
    Prune tree to keep only nodes matching patterns with optional descendants.

    Matched nodes always include their ancestors (required for valid tree structure).
    Uses case-sensitive matching.

    literal wildcards (e.g., ** to match literal *, \\? to match literal ? ).
    Would require NEGATE flag or custom escape handling in wcmatch.fnmatch.

    Args:
        tree: treelib.Tree to prune
        patterns: List of wildcard patterns (e.g., ["chain*", "*shift*"])
        include_descendants: If True, include all child nodes of matches
        exact: If True, match exact names only (no automatic wildcard wrapping)

    Returns:
        New Tree containing matched nodes with ancestors (and descendants if requested)
    """
    nodes_to_keep = _collect_matching_nodes_from_tree(
        tree, patterns, include_descendants, exact
    )
    return build_filtered_tree_from_retained_nodes(tree, nodes_to_keep)


def _collect_matching_nodes_from_tree(
    tree: Tree,
    patterns: List[str],
    include_descendants: bool,
    exact: bool,
) -> Set[str]:
    """\
    Collect node identifiers that match patterns (plus ancestors/descendants).

    Args:
        tree: Tree to search
        patterns: Wildcard patterns to match
        include_descendants: Whether to include child nodes
        exact: Whether to match exact names only

    Returns:
        Set of node identifiers to keep (always includes ancestors for valid tree structure)
    """
    nodes = set()

    for node in tree.all_nodes_itr():
        if _node_matches_patterns(node.tag, patterns, exact):
            nodes.add(node.identifier)
            nodes.update(_get_all_ancestors_of_node(tree, node.identifier))

            if include_descendants:
                nodes.update(get_all_descendants_of_node(tree, node.identifier))

    return nodes


def _node_matches_patterns(node_name: str, patterns: List[str], exact: bool) -> bool:
    """\
    Check if node name matches any pattern using case-sensitive matching.

    Args:
        node_name: Node tag string to match
        patterns: List of wildcard patterns
        exact: If True, match exact names only (no wildcard wrapping)

    Returns:
        True if node_name matches any pattern
    """
    for pattern in patterns:
        if exact:
            match_pattern = pattern  # Use pattern as-is for exact matching
        else:
            match_pattern = f"*{pattern}*"  # Wrap with wildcards for substring matching

        if fnmatchcase(node_name, match_pattern):
            return True
    return False


def _get_all_ancestors_of_node(tree: Tree, node_id: str) -> List[str]:
    """\
    Get all ancestor node identifiers from node to root.

    Args:
        tree: Tree to traverse
        node_id: Starting node identifier

    Returns:
        List of ancestor node identifiers
    """
    ancestors = []
    current = tree.parent(node_id)

    while current is not None:
        ancestors.append(current.identifier)
        current = tree.parent(current.identifier)

    return ancestors


def get_all_descendants_of_node(tree: Tree, node_id: str) -> List[str]:
    """\
    Get all descendant node identifiers recursively.

    Args:
        tree: Tree to traverse
        node_id: Starting node identifier

    Returns:
        List of descendant node identifiers
    """
    descendants = []

    for child in tree.children(node_id):
        descendants.append(child.identifier)
        descendants.extend(get_all_descendants_of_node(tree, child.identifier))

    return descendants


def build_filtered_tree_from_retained_nodes(
    tree: Tree, nodes_to_keep: Set[str]
) -> Tree:
    """\
    Build new tree containing only specified nodes.

    Args:
        tree: Source tree
        nodes_to_keep: Set of node identifiers to include

    Returns:
        New Tree with only specified nodes
    """
    filtered = Tree()

    for level in range(tree.depth() + 1):
        for node in tree.filter_nodes(lambda n: tree.level(n.identifier) == level):
            if node.identifier in nodes_to_keep:
                parent_node = tree.parent(node.identifier)

                if level == 0:
                    parent_id = None
                elif parent_node and parent_node.identifier in nodes_to_keep:
                    parent_id = parent_node.identifier
                else:
                    continue

                filtered.create_node(
                    tag=node.tag,
                    identifier=node.identifier,
                    parent=parent_id,
                    data=node.data,
                )

    return filtered
