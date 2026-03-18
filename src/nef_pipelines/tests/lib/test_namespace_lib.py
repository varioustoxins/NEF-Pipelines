from nef_pipelines.lib.namespace_lib import (
    REGISTERED_NAMESPACES,
    extract_namespace,
    filter_namespaces,
    if_separator_conflicts_get_message,
)


def test_extract_namespace_standard_nef():
    """Test extraction from standard NEF loop category."""
    assert extract_namespace("_nef_sequence") == "nef"


def test_extract_namespace_custom():
    """Test extraction from custom namespace."""
    assert extract_namespace("_custom_data") == "custom"


def test_extract_namespace_nested_tag():
    """Test extraction from nested tag (namespace determined by prefix before second _)."""
    assert extract_namespace("_nef_peak.position") == "nef"


def test_extract_namespace_frame_category():
    """Test extraction from frame category (no leading underscore)."""
    assert extract_namespace("nef_molecular_system") == "nef"
    assert extract_namespace("custom_data_frame") == "custom"


def test_extract_namespace_single_underscore():
    """Test that names with only one underscore return None."""
    assert extract_namespace("_sequence") is None


def test_extract_namespace_empty():
    """Test empty string returns None."""
    assert extract_namespace("") is None


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
    """Test filter with invert flag."""
    all_namespaces = {"nef", "custom", "test"}
    result = filter_namespaces(all_namespaces, ["nef"], False, True)
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
