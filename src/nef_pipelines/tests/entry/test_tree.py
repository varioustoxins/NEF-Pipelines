import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.entry.tree import tree

runner = CliRunner()
app = typer.Typer()
app.command()(tree)

EXPECTED_OUTPUT_MINIMAL = """\
      minimal_test
      ├── nef_nmr_meta_data [frame: 0 loops]
      │   ├── sf_category
      │   ├── sf_framecode
      │   ├── format_name
      │   └── format_version
      └── nef_molecular_system [frame: 1 loop]
          ├── sf_category
          ├── sf_framecode
          └── nef_sequence [loop: 1 row]
              ├── chain_code
              └── residue_name
  """


def test_tree_basic():
    """\
    Test basic tree output with all nodes using minimal NEF file.
    """

    path = path_in_test_data(__file__, "minimal_tree.nef")
    result = run_and_report(app, ["--colour-policy", "plain", str(path)])

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT_MINIMAL, result.stdout)


def test_tree_stdin():
    """\
    Test reading from stdin.
    """

    path = path_in_test_data(__file__, "minimal_tree.nef")

    with open(path) as f:
        input_data = f.read()

    result = run_and_report(app, ["--colour-policy", "plain"], input=input_data)

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT_MINIMAL, result.stdout)


def test_tree_polymorphic_file_arg():
    """\
    Test file as first positional argument.
    """

    path = path_in_test_data(__file__, "minimal_tree.nef")
    result = run_and_report(app, [str(path), "--colour-policy", "plain"])

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT_MINIMAL, result.stdout)


def test_tree_filter_tag():
    """\
    Test filtering by tag name (atom_name only in shift loops, not in sequence).
    """
    EXPECTED_OUTPUT = """\
        multi_shift_test
        ├── nef_chemical_shift_list_default [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 4 rows]
        │       └── atom_name
        ├── nef_chemical_shift_list_simulated [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 2 rows]
        │       └── atom_name
        └── nef_chemical_shift_list_predicted [frame: 1 loop]
            └── nef_chemical_shift [loop: 2 rows]
                └── atom_name
    """

    path = path_in_test_data(__file__, "multi_shift_frames.nef")
    result = run_and_report(app, ["--colour-policy", "plain", str(path), "atom_name"])

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_filter_loop():
    """\
    Test filtering by loop category (matches nef_sequence loop and sequence_code tags).
    Without --children, shows only matched nodes, not all loop descendants.
    """
    EXPECTED_OUTPUT = """\
        multi_shift_test
        ├── nef_molecular_system [frame: 1 loop]
        │   └── nef_sequence [loop: 2 rows]
        │       └── sequence_code
        ├── nef_chemical_shift_list_default [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 4 rows]
        │       └── sequence_code
        ├── nef_chemical_shift_list_simulated [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 2 rows]
        │       └── sequence_code
        └── nef_chemical_shift_list_predicted [frame: 1 loop]
            └── nef_chemical_shift [loop: 2 rows]
                └── sequence_code
    """

    path = path_in_test_data(__file__, "multi_shift_frames.nef")
    result = run_and_report(app, ["--colour-policy", "plain", str(path), "sequence"])

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_filter_frame():
    """\
    Test filtering by frame name.
    Without --children, shows only the matched frame, not its contents.
    """
    EXPECTED_OUTPUT = """\
        multi_shift_test
        └── nef_molecular_system [frame: 1 loop]
    """

    path = path_in_test_data(__file__, "multi_shift_frames.nef")
    result = run_and_report(
        app, ["--colour-policy", "plain", str(path), "molecular_system"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_multiple_filters():
    """\
    Test multiple filter patterns with AND logic (progressive refinement).
    """
    EXPECTED_OUTPUT = """\
        multi_shift_test
        ├── nef_molecular_system [frame: 1 loop]
        │   └── nef_sequence [loop: 2 rows]
        │       └── chain_code
        ├── nef_chemical_shift_list_default [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 4 rows]
        │       └── chain_code
        ├── nef_chemical_shift_list_simulated [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 2 rows]
        │       └── chain_code
        └── nef_chemical_shift_list_predicted [frame: 1 loop]
            └── nef_chemical_shift [loop: 2 rows]
                └── chain_code
    """

    path = path_in_test_data(__file__, "multi_shift_frames.nef")
    result = run_and_report(
        app, ["--colour-policy", "plain", str(path), "shift", "chain_code"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_case_sensitive():
    """\
    Test case-sensitive matching (must use exact case).
    """
    EXPECTED_OUTPUT = """\
        multi_shift_test
        ├── nef_molecular_system [frame: 1 loop]
        │   └── nef_sequence [loop: 2 rows]
        │       └── chain_code
        ├── nef_chemical_shift_list_default [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 4 rows]
        │       └── chain_code
        ├── nef_chemical_shift_list_simulated [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 2 rows]
        │       └── chain_code
        └── nef_chemical_shift_list_predicted [frame: 1 loop]
            └── nef_chemical_shift [loop: 2 rows]
                └── chain_code
    """

    path = path_in_test_data(__file__, "multi_shift_frames.nef")
    result = run_and_report(app, ["--colour-policy", "plain", str(path), "chain_code"])

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_children_flag():
    """\
    Test --children flag preserves all descendants from first filter.
    """
    EXPECTED_WITHOUT_CHILDREN = """\
        multi_shift_test
        └── nef_molecular_system [frame: 1 loop]
            └── nef_sequence [loop: 2 rows]
                ├── residue_name
                └── residue_variant
    """

    EXPECTED_WITH_CHILDREN = """\
        multi_shift_test
        └── nef_molecular_system [frame: 1 loop]
            ├── sf_category
            ├── sf_framecode
            └── nef_sequence [loop: 2 rows]
                ├── index
                ├── chain_code
                ├── sequence_code
                ├── residue_name
                ├── linking
                ├── residue_variant
                └── cis_peptide
    """

    path = path_in_test_data(__file__, "multi_shift_frames.nef")

    result_without = run_and_report(
        app, ["--colour-policy", "plain", str(path), "molecular_system", "residue"]
    )
    result_with = run_and_report(
        app,
        [
            "--colour-policy",
            "plain",
            str(path),
            "molecular_system",
            "residue",
            "--children",
        ],
    )

    assert result_without.exit_code == 0
    assert result_with.exit_code == 0

    assert_lines_match(EXPECTED_WITHOUT_CHILDREN, result_without.stdout)
    assert_lines_match(EXPECTED_WITH_CHILDREN, result_with.stdout)


def test_tree_selector_syntax():
    """\
    Test frame.loop:tag selector syntax as fallback.
    """
    EXPECTED_OUTPUT = """\
        multi_shift_test
        ├── nef_chemical_shift_list_default [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 4 rows]
        │       └── chain_code
        ├── nef_chemical_shift_list_simulated [frame: 1 loop]
        │   └── nef_chemical_shift [loop: 2 rows]
        │       └── chain_code
        └── nef_chemical_shift_list_predicted [frame: 1 loop]
            └── nef_chemical_shift [loop: 2 rows]
                └── chain_code
    """

    path = path_in_test_data(__file__, "multi_shift_frames.nef")
    result = run_and_report(
        app, ["--colour-policy", "plain", str(path), "shift.chemical_shift:chain_code"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_namespace_include():
    """\
    Test --namespace with -,+nef to show only nef frames.
    """
    EXPECTED_OUTPUT = """\
        namespace_test
        └── nef_molecular_system [frame: 1 loop]
            ├── sf_category
            ├── sf_framecode
            └── nef_sequence [loop: 1 row]
                └── chain_code
    """

    path = path_in_test_data(__file__, "namespace_test.nef")
    result = run_and_report(
        app, ["--colour-policy", "plain", str(path), "--namespace", "-,+nef"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_namespace_exclude():
    """\
    Test --namespace with -ccpn to exclude ccpn frames.
    """
    EXPECTED_OUTPUT = """\
        namespace_test
        └── nef_molecular_system [frame: 1 loop]
            ├── sf_category
            ├── sf_framecode
            └── nef_sequence [loop: 1 row]
                └── chain_code
    """

    path = path_in_test_data(__file__, "namespace_test.nef")
    result = run_and_report(
        app, ["--colour-policy", "plain", str(path), "--namespace", "-ccpn"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_namespace_invert():
    """\
    Test --no-initial-selection flag starts with empty set.

    Default starts with ALL namespaces, --no-initial-selection starts with EMPTY.
    Using -ccpn with default removes ccpn, showing only nef frames.
    """
    EXPECTED_OUTPUT = """\
        namespace_test
        └── nef_molecular_system [frame: 1 loop]
            ├── sf_category
            ├── sf_framecode
            └── nef_sequence [loop: 1 row]
                └── chain_code
    """

    path = path_in_test_data(__file__, "namespace_test.nef")
    result = run_and_report(
        app, ["--colour-policy", "plain", str(path), "--namespace", "-ccpn"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_namespace_with_filter():
    """\
    Test combining --namespace with regular filters.
    """
    EXPECTED_OUTPUT = """\
        namespace_test
        └── ccpn_additional_data [frame: 1 loop]
            └── ccpn_data [loop: 1 row]
                └── key
    """

    path = path_in_test_data(__file__, "namespace_test.nef")
    result = run_and_report(
        app, ["--colour-policy", "plain", str(path), "--namespace", "-,+ccpn", "key"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_namespace_hierarchical():
    """\
    Test hierarchical namespace filtering: ccpn frame with nef children should be excluded.

    When filtering with -ccpn, a ccpn frame should be excluded even if it contains
    nef-namespace loops/tags. The frame namespace takes precedence.
    """
    EXPECTED_OUTPUT = """\
        namespace_hierarchical_test
        └── nef_molecular_system [frame: 1 loop]
            ├── sf_category
            ├── sf_framecode
            └── nef_sequence [loop: 1 row]
                └── chain_code
    """

    path = path_in_test_data(__file__, "namespace_hierarchical_test.nef")
    result = run_and_report(
        app, ["--colour-policy", "plain", str(path), "--namespace", "-ccpn"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_highlight_matched_substring():
    """\
    Test that matched substrings are highlighted in colored output (minimal test).
    Uses --colour-policy color to get colored output in tests.
    """
    EXPECTED_OUTPUT = """\
        \x1b[1;36mhighlight_test\x1b[0m
        └── \x1b[33mnef_molecular_system\x1b[0m \x1b[2m[frame: 1 loop]\x1b[0m
            └── \x1b[34mnef_sequence\x1b[0m \x1b[2m[loop: 1 row]\x1b[0m
                └── \x1b[1;31mchain\x1b[0m\x1b[32m_code\x1b[0m
    """

    path = path_in_test_data(__file__, "highlight_test.nef")
    result = run_and_report(app, ["--colour-policy", "color", str(path), "chain"])

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


def test_tree_no_highlight_flag():
    """\
    Test --no-highlight flag disables substring highlighting but keeps other colors.
    Uses --colour-policy color to get colored output in tests.
    """
    EXPECTED_OUTPUT = """\
        \x1b[1;36mhighlight_test\x1b[0m
        └── \x1b[33mnef_molecular_system\x1b[0m \x1b[2m[frame: 1 loop]\x1b[0m
            └── \x1b[34mnef_sequence\x1b[0m \x1b[2m[loop: 1 row]\x1b[0m
                └── \x1b[32mchain_code\x1b[0m
    """

    path = path_in_test_data(__file__, "highlight_test.nef")
    result = run_and_report(
        app, ["--colour-policy", "color", "--no-highlight", str(path), "chain"]
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_OUTPUT, result.stdout)


# def test_tree_node_type_loop_tag():
#     """\
#     Test --node-type loop-tag to show only loop tags matching the selector.
#     """
#     EXPECTED_OUTPUT = """\
#         multi_shift_test
#         ├── nef_molecular_system [frame: 1 loop]
#         │   └── nef_sequence [loop: 2 rows]
#         │       └── chain_code
#         ├── nef_chemical_shift_list_default [frame: 1 loop]
#         │   └── nef_chemical_shift [loop: 4 rows]
#         │       └── chain_code
#         ├── nef_chemical_shift_list_simulated [frame: 1 loop]
#         │   └── nef_chemical_shift [loop: 2 rows]
#         │       └── chain_code
#         └── nef_chemical_shift_list_predicted [frame: 1 loop]
#             └── nef_chemical_shift [loop: 2 rows]
#                 └── chain_code
#     """
#
#     path = path_in_test_data(__file__, "multi_shift_frames.nef")
#     result = run_and_report(
#         app, ["--colour-policy", "plain", str(path), "chain", "--node-type", "loop-tag"]
#     )
#
#     assert result.exit_code == 0
#     assert_lines_match(EXPECTED_OUTPUT, result.stdout)
#
#
# def test_tree_node_type_frame_tag():
#     """\
#     Test --node-type frame-tag to show only frame tags matching the selector.
#     """
#     EXPECTED_OUTPUT = """\
#         multi_shift_test
#         ├── nef_nmr_meta_data [frame: 1 loop]
#         │   └── sf_category
#         ├── nef_molecular_system [frame: 1 loop]
#         │   └── sf_category
#         ├── nef_chemical_shift_list_default [frame: 1 loop]
#         │   └── sf_category
#         ├── nef_chemical_shift_list_simulated [frame: 1 loop]
#         │   └── sf_category
#         └── nef_chemical_shift_list_predicted [frame: 1 loop]
#             └── sf_category
#     """
#
#     path = path_in_test_data(__file__, "multi_shift_frames.nef")
#     result = run_and_report(
#         app, ["--colour-policy", "plain", str(path), "category", "--node-type", "frame-tag"]
#     )
#
#     assert result.exit_code == 0
#     assert_lines_match(EXPECTED_OUTPUT, result.stdout)
#
#
# @pytest.mark.skip(reason="Node type filtering feature temporarily disabled")
# def test_tree_node_type_frame():
#     """\
#     Test --node-type frame to show only frames matching the selector.
#     """
#     EXPECTED_OUTPUT = """\
#         multi_shift_test
#         └── nef_molecular_system [frame: 1 loop]
#     """
#
#     path = path_in_test_data(__file__, "multi_shift_frames.nef")
#     result = run_and_report(
#         app, ["--colour-policy", "plain", str(path), "molecular", "--node-type", "frame"]
#     )
#
#     assert result.exit_code == 0
#     assert_lines_match(EXPECTED_OUTPUT, result.stdout)
#
#
# def test_tree_node_type_loop():
#     """\
#     Test --node-type loop to show only loops matching the selector.
#     """
#     EXPECTED_OUTPUT = """\
#         multi_shift_test
#         ├── nef_molecular_system [frame: 1 loop]
#         │   └── nef_sequence [loop: 2 rows]
#         ├── nef_chemical_shift_list_default [frame: 1 loop]
#         │   └── nef_chemical_shift [loop: 4 rows]
#         ├── nef_chemical_shift_list_simulated [frame: 1 loop]
#         │   └── nef_chemical_shift [loop: 2 rows]
#         └── nef_chemical_shift_list_predicted [frame: 1 loop]
#             └── nef_chemical_shift [loop: 2 rows]
#     """
#
#     path = path_in_test_data(__file__, "multi_shift_frames.nef")
#     result = run_and_report(
#         app, ["--colour-policy", "plain", str(path), "sequence", "--node-type", "loop"]
#     )
#
#     assert result.exit_code == 0
#     assert_lines_match(EXPECTED_OUTPUT, result.stdout)
#
#
# def test_tree_node_type_multiple():
#     """\
#     Test multiple --node-type options (frame and loop).
#     """
#     EXPECTED_OUTPUT = """\
#         multi_shift_test
#         ├── nef_nmr_meta_data [frame: 1 loop]
#         │   └── nef_program_script [loop: 1 row]
#         ├── nef_molecular_system [frame: 1 loop]
#         │   └── nef_sequence [loop: 2 rows]
#         ├── nef_chemical_shift_list_default [frame: 1 loop]
#         │   └── nef_chemical_shift [loop: 4 rows]
#         ├── nef_chemical_shift_list_simulated [frame: 1 loop]
#         │   └── nef_chemical_shift [loop: 2 rows]
#         └── nef_chemical_shift_list_predicted [frame: 1 loop]
#             └── nef_chemical_shift [loop: 2 rows]
#     """
#
#     path = path_in_test_data(__file__, "multi_shift_frames.nef")
#     result = run_and_report(
#         app, [
#             "--colour-policy", "plain", str(path), "shift",
#             "--node-type", "frame", "--node-type", "loop"
#         ]
#     )
#
#     assert result.exit_code == 0
#     assert_lines_match(EXPECTED_OUTPUT, result.stdout)
#
#
# def test_tree_node_type_with_children():
#     """\
#     Test --node-type with --children flag (children expansion, then node type filtering).
#     """
#     EXPECTED_OUTPUT = """\
#         multi_shift_test
#         ├── nef_molecular_system [frame: 1 loop]
#         │   └── nef_sequence [loop: 2 rows]
#         ├── nef_chemical_shift_list_default [frame: 1 loop]
#         │   └── nef_chemical_shift [loop: 4 rows]
#         ├── nef_chemical_shift_list_simulated [frame: 1 loop]
#         │   └── nef_chemical_shift [loop: 2 rows]
#         └── nef_chemical_shift_list_predicted [frame: 1 loop]
#             └── nef_chemical_shift [loop: 2 rows]
#     """
#
#     path = path_in_test_data(__file__, "multi_shift_frames.nef")
#     result = run_and_report(
#         app, [
#             "--colour-policy", "plain", str(path), "sequence",
#             "--node-type", "loop", "--children"
#         ]
#     )
#
#     assert result.exit_code == 0
#     assert_lines_match(EXPECTED_OUTPUT, result.stdout)
#
#
# def test_tree_node_type_no_matches():
#     """\
#     Test --node-type when no nodes of that type match the selector.
#     """
#     EXPECTED_OUTPUT = """\
#         No matching nodes found.
#     """
#
#     path = path_in_test_data(__file__, "multi_shift_frames.nef")
#     result = run_and_report(
#         app, [
#             "--colour-policy", "plain", str(path), "nonexistent",
#             "--node-type", "frame"
#         ]
#     )
#
#     assert result.exit_code == 0
#     assert_lines_match(EXPECTED_OUTPUT, result.stdout)
#


def test_tree_null_namespace_warning():
    """\
    Test that null/bad namespace frames generate a warning to stderr when namespace filtering is used.
    """
    EXPECTED_STDOUT = """\
        bad_namespace
        └── nef_nmr_meta_data [frame: 0 loops]
            ├── sf_category
            ├── sf_framecode
            ├── format_name
            └── format_version
    """

    EXPECTED_STDERR = """\
        WARNING: Found 1 frames/loops with no namespace in their names: "badframe"
        NEF saveframes/loops should have the format "<namespace>_<category_and_id>",
        e.g. "nef_chemical_shift_list_default" [namespace: nef, category: shift_list, id: default].
    """

    path = path_in_test_data(__file__, "bad_namespace.nef")
    # Use --namespace filtering to trigger the null namespace check
    result = run_and_report(
        app,
        ["--colour-policy", "plain", str(path), "--namespace", "+nef"],
        merge_stderr=False,
    )

    assert result.exit_code == 0
    assert_lines_match(EXPECTED_STDOUT, result.stdout)
    assert_lines_match(EXPECTED_STDERR, result.stderr)
