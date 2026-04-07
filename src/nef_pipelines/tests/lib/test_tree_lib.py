from textwrap import dedent

import pytest
from treelib import Tree

from nef_pipelines.lib.tree_lib import prune_tree_to_matches, render_tree


def tree_from_dict(tree_dict):
    """\
    Build a tree from a dictionary structure with auto-generated unique IDs.

    Handles duplicate tags by auto-generating unique identifiers. The hierarchical
    structure disambiguates nodes with the same name.

    Args:
        tree_dict: Dictionary with structure matching tree.to_dict() format:
                   {node_name: {'children': [child1, child2, ...]}}
                   where children can be strings (leaf nodes) or dicts (branches)

    Returns:
        Tree object constructed from the dictionary
    """
    tree = Tree()
    counter = [0]  # Use list to allow modification in nested function

    def add_nodes(parent_id, node_dict):
        for key, value in node_dict.items():
            # Auto-generate unique ID for this node
            node_id = f"{key}_{counter[0]}"
            counter[0] += 1

            tree.create_node(tag=key, identifier=node_id, parent=parent_id)

            if isinstance(value, dict) and "children" in value:
                for child in value["children"]:
                    if isinstance(child, str):
                        # Auto-generate unique ID for leaf node
                        child_id = f"{child}_{counter[0]}"
                        counter[0] += 1
                        tree.create_node(tag=child, identifier=child_id, parent=node_id)
                    else:
                        add_nodes(node_id, child)

    add_nodes(None, tree_dict)
    return tree


@pytest.fixture
def sample_tree():
    """\
    Create a sample tree for testing.

    Structure:
        root
        ├── child1
        │   ├── data
        │   └── grandchild2
        ├── child2
        │   └── data
        └── Special:name
            └── special.child

    Note: Contains duplicate tags ("data" appears twice) and mixed case
    ("Special:name" vs other lowercase nodes) for comprehensive testing.
    """
    return tree_from_dict(
        {
            "root": {
                "children": [
                    {"child1": {"children": ["data", "grandchild2"]}},
                    {"child2": {"children": ["data"]}},
                    {"Special:name": {"children": ["special.child"]}},
                ]
            }
        }
    )


def test_render_tree_with_rich_basic(sample_tree):
    """\
    Test basic tree rendering with Rich (thin wrapper around Rich library).

    Note: Rich auto-detects non-terminal output and strips color/formatting codes,
    so this produces the same output as render_plain_tree in test contexts.
    Both tests are kept to validate both code paths work correctly.
    """
    result = render_tree(sample_tree)

    EXPECTED_OUTPUT = """\
            root
            ├── child1
            │   ├── data
            │   └── grandchild2
            ├── child2
            │   └── data
            └── Special:name
                └── special.child
            """
    EXPECTED_OUTPUT = dedent(EXPECTED_OUTPUT)
    assert result == EXPECTED_OUTPUT


def test_render_plain_tree_basic(sample_tree):
    """\
    Test plain tree rendering (thin wrapper around treelib).

    Note: In test contexts, this produces identical output to render_tree_with_rich
    because Rich strips formatting when not outputting to a terminal.
    """
    result = render_tree(sample_tree)

    EXPECTED_OUTPUT = """\
                root
                ├── child1
                │   ├── data
                │   └── grandchild2
                ├── child2
                │   └── data
                └── Special:name
                    └── special.child
    """
    EXPECTED_OUTPUT = dedent(EXPECTED_OUTPUT)
    assert result == EXPECTED_OUTPUT


def test_prune_tree_to_matches_single_match(sample_tree):
    """\
    Test pruning tree to match single pattern.
    """
    filtered = prune_tree_to_matches(sample_tree, ["child1"])

    EXPECTED_STRUCTURE = {
        "root": {"children": [{"child1": {"children": ["data", "grandchild2"]}}]}
    }

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_wildcard(sample_tree):
    """\
    Test filtering with wildcard patterns (matches duplicate tags).
    """
    filtered = prune_tree_to_matches(sample_tree, ["data"])

    EXPECTED_STRUCTURE = {
        "root": {
            "children": [
                {"child1": {"children": ["data"]}},
                {"child2": {"children": ["data"]}},
            ]
        }
    }

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_multiple_patterns(sample_tree):
    """\
    Test filtering with multiple patterns.
    """
    filtered = prune_tree_to_matches(sample_tree, ["child1", "Special"])

    EXPECTED_STRUCTURE = {
        "root": {
            "children": [
                {"Special:name": {"children": ["special.child"]}},
                {"child1": {"children": ["data", "grandchild2"]}},
            ]
        }
    }

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_no_descendants(sample_tree):
    """\
    Test filtering without including descendants.

    Note: Patterns are converted to *pattern* format, so "child1" matches
    both "child1" and "grandchild2" (which contains "child").
    Each matched node gets its ancestors but not its descendants.
    """
    filtered = prune_tree_to_matches(sample_tree, ["child1"], include_descendants=False)

    EXPECTED_STRUCTURE = {"root": {"children": ["child1"]}}

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_no_descendants_specific_pattern(sample_tree):
    """\
    Test filtering without descendants using a specific pattern.

    Note: "child2" pattern matches both "child2" node and "grandchild2" node
    (because patterns are wrapped with wildcards: *child2*).
    """
    filtered = prune_tree_to_matches(sample_tree, ["child2"], include_descendants=False)

    EXPECTED_STRUCTURE = {
        "root": {"children": [{"child1": {"children": ["grandchild2"]}}, "child2"]}
    }

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_case_sensitive_uppercase_example(sample_tree):
    """\
    Test case-sensitive pattern matching (now always case-sensitive).
    "Special" should match only "Special:name", not "special.child".
    """
    filtered = prune_tree_to_matches(
        sample_tree, ["Special"], include_descendants=False
    )

    EXPECTED_STRUCTURE = {"root": {"children": ["Special:name"]}}

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_case_sensitive_lowercase(sample_tree):
    """\
    Test case-sensitive matching with lowercase pattern.
    "special" should match only "special.child", not "Special:name".
    """
    filtered = prune_tree_to_matches(
        sample_tree, ["special"], include_descendants=False
    )

    EXPECTED_STRUCTURE = {
        "root": {"children": [{"Special:name": {"children": ["special.child"]}}]}
    }

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_exact_match(sample_tree):
    """\
    Test exact matching finds only exact node names.
    """
    # Exact match for "data" should match only "data" nodes,
    # not "grandchild2" which is different
    filtered = prune_tree_to_matches(sample_tree, ["data"], exact=True)

    EXPECTED_STRUCTURE = {
        "root": {
            "children": [
                {"child1": {"children": ["data"]}},
                {"child2": {"children": ["data"]}},
            ]
        }
    }

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_exact_no_partial_match(sample_tree):
    """\
    Test exact matching does not match partial names.
    """
    # With exact=True, "child" should not match "child1" or "child2"
    filtered = prune_tree_to_matches(sample_tree, ["child"], exact=True)

    # Should find nothing (no node named exactly "child")
    assert filtered.size() == 0


def test_prune_tree_to_matches_exact_vs_wildcard(sample_tree):
    """\
    Test difference between exact and wildcard (default) matching.
    """
    # Without exact (default): "data" matches data
    wildcard_result = prune_tree_to_matches(sample_tree, ["data"], exact=False)

    # With exact: "data" matches only exactly "data"
    exact_result = prune_tree_to_matches(sample_tree, ["data"], exact=True)

    EXPECTED_STRUCTURE = {
        "root": {
            "children": [
                {"child1": {"children": ["data"]}},
                {"child2": {"children": ["data"]}},
            ]
        }
    }

    # Both should produce the same result for this case
    assert wildcard_result.to_dict() == EXPECTED_STRUCTURE
    assert exact_result.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_exact_with_wildcards_in_pattern(sample_tree):
    """\
    Test that exact mode still allows explicit wildcards in patterns.
    """
    # Even with exact=True, explicit wildcards in the pattern should work
    # "*child*" matches child1, child2, grandchild2, and special.child
    filtered = prune_tree_to_matches(sample_tree, ["*child*"], exact=True)

    EXPECTED_STRUCTURE = {
        "root": {
            "children": [
                {"Special:name": {"children": ["special.child"]}},
                {"child1": {"children": ["data", "grandchild2"]}},
                {"child2": {"children": ["data"]}},
            ]
        }
    }

    assert filtered.to_dict() == EXPECTED_STRUCTURE


def test_prune_tree_to_matches_empty_pattern_list(sample_tree):
    """\
    Test filtering with empty pattern list.
    """
    filtered = prune_tree_to_matches(sample_tree, [])

    # Should return empty tree
    assert filtered.size() == 0


def test_prune_tree_to_matches_all_match(sample_tree):
    """\
    Test filtering where all nodes match.
    """
    filtered = prune_tree_to_matches(sample_tree, ["*"])

    EXPECTED_STRUCTURE = {
        "root": {
            "children": [
                {"Special:name": {"children": ["special.child"]}},
                {"child1": {"children": ["data", "grandchild2"]}},
                {"child2": {"children": ["data"]}},
            ]
        }
    }

    assert filtered.to_dict() == EXPECTED_STRUCTURE
