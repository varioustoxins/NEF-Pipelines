"""Meta-meta-test: Verify that test_meta_test_data_files_committed.py actually catches missing files."""

from pathlib import Path
from textwrap import dedent

import pytest

from nef_pipelines.tests.meta_tests.test_meta_test_data_files_committed import (
    test_all_test_data_files_in_git,
)


def test_meta_test_catches_missing_files():
    """Verify the meta-test correctly detects tests referencing missing data files.

    Creates a temporary test file that references a non-existent data file,
    runs the meta-test, and verifies it fails with the expected error message.
    """
    # Create a temporary test file that references a missing data file
    temp_test_dir = Path(__file__).parent
    temp_test_file = temp_test_dir / "test_temporary_for_meta_validation.py"

    try:
        # Write a test that references a missing data file
        temp_file_text = '''
                """Temporary test for meta-test validation."""
                from nef_pipelines.lib.test_lib import path_in_test_data


                def test_with_missing_data():
                    """References a non-existent data file."""
                    missing = path_in_test_data(__file__, "meta_test_validation_missing.nef")
                    assert missing is not None
            '''
        temp_test_file.write_text(dedent(temp_file_text))

        # Run the meta-test - it should fail and catch the missing file
        with pytest.raises(pytest.fail.Exception) as exc_info:
            test_all_test_data_files_in_git()

        # Verify the error message contains the expected information
        error_msg = str(exc_info.value)

        EXPECTED_HEADER = "Test data files referenced but not tracked in git"
        EXPECTED_TEST_FILE = "test_temporary_for_meta_validation.py"
        EXPECTED_DATA_FILE = "meta_test_validation_missing.nef"
        EXPECTED_MISSING_INDICATOR = "MISSING"
        EXPECTED_RESOLVED_INDICATOR = "path_in_test_data() resolved to"

        assert EXPECTED_HEADER in error_msg
        assert EXPECTED_TEST_FILE in error_msg
        assert EXPECTED_DATA_FILE in error_msg
        assert (
            EXPECTED_MISSING_INDICATOR in error_msg
            or EXPECTED_RESOLVED_INDICATOR in error_msg
        )

    finally:
        # Clean up: remove the temporary test file
        if temp_test_file.exists():
            temp_test_file.unlink()

    # After clean-up, the meta-test should pass
    # (assuming all real test data files are properly tracked)
    test_all_test_data_files_in_git()
