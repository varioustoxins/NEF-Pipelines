"""Test to verify pure pynmrstar behaviour when adding duplicate saveframes.

This test documents what pynmrstar's entry.add_saveframe() does when attempting
to add a saveframe with a name that already exists in the entry.
"""

import pytest
from pynmrstar import Entry, Saveframe


def test_entry_add_saveframe_raises_on_duplicate_name():
    """Test that pynmrstar's entry.add_saveframe() raises ValueError for duplicate names.

    This documents the native pynmrstar behavior: attempting to add a saveframe
    with a name that already exists raises ValueError.
    """
    entry = Entry.from_scratch("test_entry")

    # Create first saveframe using pure pynmrstar
    frame1 = Saveframe.from_scratch("test_frame")
    entry.add_saveframe(frame1)

    # Verify first frame was added
    assert len(entry.frame_list) == 1
    assert entry.frame_list[0].name == "test_frame"

    # Create second saveframe with the SAME name
    frame2 = Saveframe.from_scratch("test_frame")

    # Attempting to add duplicate should raise ValueError with specific message
    with pytest.raises(ValueError) as exc_info:
        entry.add_saveframe(frame2)

    EXPECTED = (
        "Cannot add a saveframe with name 'test_frame' since a saveframe with that "
        + "name already exists in the entry."
    )

    assert str(exc_info.value) == EXPECTED
