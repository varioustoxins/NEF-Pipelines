import pytest
from pynmrstar import Entry, Loop

from nef_pipelines.lib.namespace_lib import (
    NO_NAMESPACE,
    REGISTERED_NAMESPACES,
    collect_namespaces_from_frames,
    filter_namespaces,
    get_namespace,
    if_separator_conflicts_get_message,
)
from nef_pipelines.lib.nef_lib import create_nef_save_frame
from nef_pipelines.lib.structures import EntryPart, EntryPartValues

# A nef frame that contains a cross-namespace ccpn loop alongside its own nef loop.
# pynmrstar requires all tags within one loop to share the same category prefix,
# so cross-namespace tags appear as separate loops, not as mixed-category tags.
CROSS_NAMESPACE_NEF = """\
data_test

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code

         1   A

       stop_

       loop_
          _ccpn_chain_data.index
          _ccpn_chain_data.chain_code

         1   A

       stop_

    save_

"""

# Four frames in file order: nef, custom, test, aria — used to verify dict key order
FILE_ORDER_NEF = """\
data_test

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system
    save_

    save_custom_data_frame
       _custom_data_frame.sf_category   custom_data_frame
       _custom_data_frame.sf_framecode  custom_data_frame
    save_

    save_test_experiment
       _test_experiment.sf_category   test_experiment
       _test_experiment.sf_framecode  test_experiment
    save_

    save_aria_distance_restraints
       _aria_distance_restraints.sf_category   aria_distance_restraints
       _aria_distance_restraints.sf_framecode  aria_distance_restraints
    save_

"""


def test_registered_namespaces_contains_nef():
    """Test that registered namespaces includes standard NEF."""
    assert "nef" in REGISTERED_NAMESPACES
    assert REGISTERED_NAMESPACES["nef"] == ("NEF Standard", "Data Exchange")


def test_registered_namespaces_contains_nefpls():
    """Test that registered namespaces includes NEF Pipelines."""
    assert "nefpls" in REGISTERED_NAMESPACES
    assert REGISTERED_NAMESPACES["nefpls"] == (
        "NEF Pipelines",
        "Format transcoding and NEF manipulation",
    )


@pytest.mark.parametrize(
    "value,node_type,parent,expected",
    [
        # Saveframes (strings)
        ("nef_molecular_system", EntryPart.Saveframe, None, "nef"),
        ("ccpn_assignment", EntryPart.Saveframe, None, "ccpn"),
        ("custom_data_frame", EntryPart.Saveframe, None, "custom"),
        # Loops (strings)
        ("_nef_sequence", EntryPart.Loop, None, "nef"),
        ("_nmr_chain", EntryPart.Loop, None, "nmr"),
        # Frame tags with registered namespace prefix
        ("ccpn_peaklist_name", EntryPart.FrameTag, "nef", "ccpn"),
        ("nefpls_version", EntryPart.FrameTag, "ccpn", "nefpls"),
        # Frame tags inheriting from parent (silent NEF)
        ("chain_code", EntryPart.FrameTag, "nef", "nef"),
        ("custom_field", EntryPart.FrameTag, "ccpn", "ccpn"),
        # Loop tags with registered namespace prefix
        ("ccpn_comment", EntryPart.LoopTag, "nef", "ccpn"),
        ("nefpls_serial", EntryPart.LoopTag, "ccpn", "nefpls"),
        # Loop tags inheriting from parent (silent NEF)
        ("chain_code", EntryPart.LoopTag, "nef", "nef"),
        ("serial", EntryPart.LoopTag, "ccpn", "ccpn"),
        # Tags without parent default to nef
        ("chain_code", EntryPart.FrameTag, None, "nef"),
        ("atom_name", EntryPart.LoopTag, None, "nef"),
        # Loop objects
        (Loop.from_scratch("_nef_sequence"), EntryPart.Loop, None, "nef"),
        (Loop.from_scratch("_ccpn_data"), EntryPart.Loop, None, "ccpn"),
        # Saveframe objects
        (
            create_nef_save_frame("nef_molecular_system"),
            EntryPart.Saveframe,
            None,
            "nef",
        ),
        (create_nef_save_frame("ccpn_assignment"), EntryPart.Saveframe, None, "ccpn"),
        # Tags with Loop object parent
        ("serial", EntryPart.LoopTag, Loop.from_scratch("_ccpn_data"), "ccpn"),
        # Tags with Saveframe object parent
        ("note", EntryPart.FrameTag, create_nef_save_frame("ccpn_assignment"), "ccpn"),
        # Null namespace cases (saveframes/loops without underscore separator)
        ("nef", EntryPart.Saveframe, None, NO_NAMESPACE),
        ("ccpn", EntryPart.Saveframe, None, NO_NAMESPACE),
        ("test", EntryPart.Saveframe, None, NO_NAMESPACE),
        ("_sequence", EntryPart.Loop, None, NO_NAMESPACE),
        ("_data", EntryPart.Loop, None, NO_NAMESPACE),
        # Tags inheriting null namespace from parent
        ("note", EntryPart.FrameTag, NO_NAMESPACE, NO_NAMESPACE),
        ("serial", EntryPart.LoopTag, NO_NAMESPACE, NO_NAMESPACE),
    ],
)
def test_get_namespace(value, node_type, parent, expected):
    """Test get_namespace for various node types and inheritance patterns."""
    assert get_namespace(value, node_type, parent) == expected


def test_get_namespace_loop_object_with_wrong_node_type():
    """Test that passing Loop object with non-Loop node_type raises error."""
    loop = Loop.from_scratch("_nef_sequence")
    with pytest.raises(
        ValueError,
        match="Loop object provided but node_type is.*expected EntryPart.Loop",
    ):
        get_namespace(loop, EntryPart.Saveframe)


def test_get_namespace_saveframe_object_with_wrong_node_type():
    """Test that passing Saveframe object with non-Saveframe node_type raises error."""
    frame = create_nef_save_frame("nef_molecular_system")
    with pytest.raises(
        ValueError,
        match="Saveframe object provided but node_type is.*expected EntryPart.Saveframe",
    ):
        get_namespace(frame, EntryPart.Loop)


def test_filter_namespaces_no_selectors():
    """Test filter with no selectors returns all namespaces."""
    all_namespaces = {"nef", "custom", "test"}
    result = filter_namespaces(all_namespaces, [], False, False)
    assert result == {"nef", "custom", "test"}


def test_filter_namespaces_include():
    """Test filter with include selectors."""
    all_namespaces = {"nef", "custom", "test"}
    result = filter_namespaces(all_namespaces, ["-", "+nef", "+custom"], False, False)
    assert result == {"nef", "custom"}


def test_filter_namespaces_exclude():
    """Test filter with exclude selectors."""
    all_namespaces = {"nef", "custom", "test"}
    result = filter_namespaces(all_namespaces, ["-nef"], False, False)
    assert result == {"custom", "test"}


def test_filter_namespaces_wildcard():
    """Test filter with wildcard pattern."""
    all_namespaces = {"nef", "nefpls", "custom", "test"}
    result = filter_namespaces(all_namespaces, ["-", "+nef*"], False, False)
    assert result == {"nef", "nefpls"}


def test_filter_namespaces_invert():
    """Test filter with no_initial_selection flag."""
    all_namespaces = {"nef", "custom", "test"}
    # Start with empty, add custom and test
    result = filter_namespaces(all_namespaces, ["custom", "test"], False, True)
    assert result == {"custom", "test"}


def test_check_separator_conflicts_no_conflicts():
    """Test no conflicts when separators not in names."""
    result = if_separator_conflicts_get_message(
        ["nef", "custom"], [",", ":"], use_escapes=False
    )
    assert result is None


def test_check_separator_conflicts_with_comma():
    """Test conflict detection with comma in name."""
    result = if_separator_conflicts_get_message(
        ["my,namespace"], [","], use_escapes=False
    )
    assert result is not None
    conflicting_names, found_separators, escape_sequences = result
    assert conflicting_names == ["my,namespace"]
    assert found_separators == [","]
    assert escape_sequences == [(",", ",,")]


def test_check_separator_conflicts_multiple_separators():
    """Test conflict detection with multiple separator types."""
    result = if_separator_conflicts_get_message(
        ["my,ns", "your:ns"], [",", ":"], use_escapes=False
    )
    assert result is not None
    conflicting_names, found_separators, escape_sequences = result
    assert conflicting_names == ["my,ns", "your:ns"]
    assert found_separators == [",", ":"]
    assert escape_sequences == [(",", ",,"), (":", "::")]


def test_check_separator_conflicts_with_escapes_enabled():
    """Test no error when use_escapes=True."""
    result = if_separator_conflicts_get_message(
        ["my,namespace"], [","], use_escapes=True
    )
    assert result is None


def test_check_separator_conflicts_truncation():
    """Test that long conflict lists are truncated to first 5 names."""
    names = [f"ns{i},conflict" for i in range(10)]
    result = if_separator_conflicts_get_message(names, [","], use_escapes=False)
    assert result is not None
    conflicting_names, found_separators, escape_sequences = result
    assert conflicting_names == [
        "ns0,conflict",
        "ns1,conflict",
        "ns2,conflict",
        "ns3,conflict",
        "ns4,conflict",
    ]
    assert found_separators == [","]
    assert escape_sequences == [(",", ",,")]


EXPECTED_FILE_ORDER_NAMESPACES = {
    "nef": [
        EntryPartValues("nef_molecular_system", "nef_molecular_system"),
        EntryPartValues(
            "nef_molecular_system", "nef_molecular_system", tag_name="sf_category"
        ),
        EntryPartValues(
            "nef_molecular_system", "nef_molecular_system", tag_name="sf_framecode"
        ),
    ],
    "custom": [
        EntryPartValues("custom_data_frame", "custom_data_frame"),
        EntryPartValues(
            "custom_data_frame", "custom_data_frame", tag_name="sf_category"
        ),
        EntryPartValues(
            "custom_data_frame", "custom_data_frame", tag_name="sf_framecode"
        ),
    ],
    "test": [
        EntryPartValues("test_experiment", "test_experiment"),
        EntryPartValues("test_experiment", "test_experiment", tag_name="sf_category"),
        EntryPartValues("test_experiment", "test_experiment", tag_name="sf_framecode"),
    ],
    "aria": [
        EntryPartValues("aria_distance_restraints", "aria_distance_restraints"),
        EntryPartValues(
            "aria_distance_restraints",
            "aria_distance_restraints",
            tag_name="sf_category",
        ),
        EntryPartValues(
            "aria_distance_restraints",
            "aria_distance_restraints",
            tag_name="sf_framecode",
        ),
    ],
}

EXPECTED_CROSS_NAMESPACE_NAMESPACES = {
    "nef": [
        EntryPartValues("nef_molecular_system", "nef_molecular_system"),
        EntryPartValues(
            "nef_molecular_system", "nef_molecular_system", tag_name="sf_category"
        ),
        EntryPartValues(
            "nef_molecular_system", "nef_molecular_system", tag_name="sf_framecode"
        ),
        EntryPartValues(
            "nef_molecular_system", "nef_molecular_system", "_nef_sequence"
        ),
        EntryPartValues(
            "nef_molecular_system", "nef_molecular_system", "_nef_sequence", "index"
        ),
        EntryPartValues(
            "nef_molecular_system",
            "nef_molecular_system",
            "_nef_sequence",
            "chain_code",
        ),
    ],
    "ccpn": [
        EntryPartValues(
            "nef_molecular_system", "nef_molecular_system", "_ccpn_chain_data"
        ),
        EntryPartValues(
            "nef_molecular_system", "nef_molecular_system", "_ccpn_chain_data", "index"
        ),
        EntryPartValues(
            "nef_molecular_system",
            "nef_molecular_system",
            "_ccpn_chain_data",
            "chain_code",
        ),
    ],
}


def test_collect_namespaces_file_order():
    """Namespace dict keys and entries follow file first-occurrence order, not alphabetical."""
    entry = Entry.from_string(FILE_ORDER_NEF)
    result = collect_namespaces_from_frames(entry.frame_list)
    assert list(result.keys()) == list(EXPECTED_FILE_ORDER_NAMESPACES.keys())
    assert result == EXPECTED_FILE_ORDER_NAMESPACES


def test_collect_namespaces_cross_namespace():
    """Cross-namespace loops and their tags are attributed to the loop's own namespace, not the parent frame."""
    entry = Entry.from_string(CROSS_NAMESPACE_NEF)
    assert (
        collect_namespaces_from_frames(entry.frame_list)
        == EXPECTED_CROSS_NAMESPACE_NAMESPACES
    )
