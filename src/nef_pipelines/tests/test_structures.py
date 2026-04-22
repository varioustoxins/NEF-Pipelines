"""Tests for structures.py - SaveframeNameParts and EntryPartValues."""

import pytest

from nef_pipelines.lib.structures import EntryPart, EntryPartValues, SaveframeNameParts


@pytest.mark.parametrize(
    "namespace,category,identity,counter,expected_is_singleton",
    [
        # Singleton cases
        ("nef", "molecular_system", None, None, True),
        ("ccpn", "data", None, None, True),
        # Non-singleton: has identity
        ("nef", "molecular_system", "protein_A", None, False),
        ("nef", "chemical_shift_list", "default", None, False),
        # Non-singleton: has counter (but no identity)
        ("ccpn", "data", None, "1", False),
        ("nef", "molecular_system", None, "2", False),
        # Non-singleton: has both
        ("nef", "molecular_system", "protein_A", "1", False),
    ],
)
def test_is_singleton(namespace, category, identity, counter, expected_is_singleton):
    """\
    Test is_singleton property returns correct values.

    A frame is singleton if it has neither identity nor counter.
    """
    parts = SaveframeNameParts(
        namespace=namespace, category=category, identity=identity, counter=counter
    )
    assert parts.is_singleton == expected_is_singleton


@pytest.mark.parametrize(
    "namespace,category,identity,counter,expected_full_name",
    [
        # Singleton frames
        ("nef", "molecular_system", None, None, "nef_molecular_system"),
        ("ccpn", "data", None, None, "ccpn_data"),
        # Frames with identity only
        (
            "nef",
            "molecular_system",
            "protein_A",
            None,
            "nef_molecular_system_protein_A",
        ),
        (
            "nef",
            "chemical_shift_list",
            "default",
            None,
            "nef_chemical_shift_list_default",
        ),
        # Frames with counter only
        ("ccpn", "data", None, "1", "ccpn_data`1`"),
        # Frames with both identity and counter
        (
            "nef",
            "molecular_system",
            "protein_A",
            "1",
            "nef_molecular_system_protein_A`1`",
        ),
        ("nef", "nmr_spectrum", "k_ubi_hnco", "1", "nef_nmr_spectrum_k_ubi_hnco`1`"),
        # Frame with no namespace
        (None, "custom_frame", "instance", None, "custom_frame_instance"),
    ],
)
def test_full_name_reconstruction(
    namespace, category, identity, counter, expected_full_name
):
    """\
    Test that full_name property correctly reconstructs the original frame name.

    Includes namespace prefix in reconstruction.
    """
    parts = SaveframeNameParts(
        namespace=namespace, category=category, identity=identity, counter=counter
    )
    assert parts.full_name == expected_full_name


@pytest.mark.parametrize(
    "loop_category,tag_name,expected_entry_part",
    [
        (None, None, EntryPart.Saveframe),
        (None, "sf_category", EntryPart.FrameTag),
        ("_nef_sequence", None, EntryPart.Loop),
        ("_nef_sequence", "chain_code", EntryPart.LoopTag),
    ],
)
def test_entry_part_values_entry_part_derived(
    loop_category, tag_name, expected_entry_part
):
    """entry_part is derived correctly from loop_category and tag_name."""
    epv = EntryPartValues("frame_name", "frame_category", loop_category, tag_name)
    assert epv.entry_part == expected_entry_part
