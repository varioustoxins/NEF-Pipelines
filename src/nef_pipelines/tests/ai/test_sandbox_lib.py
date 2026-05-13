"""Tests for persistent sandbox preference system."""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "AI sandbox features require Python 3.10 or later", allow_module_level=True
    )

from nef_pipelines.lib import preferences_storage_lib
from nef_pipelines.tools.ai.sandbox_lib import (
    SANDBOX_KEY,
    get_sandbox_preference,
    set_sandbox_preference,
    validate_sandbox_path,
)


@pytest.fixture
def temp_config_dir(monkeypatch, tmp_path):
    """Fixture to use a temporary directory for config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(preferences_storage_lib, "_get_config_path", lambda: config_dir)
    return config_dir


def test_set_sandbox_preference_success(temp_config_dir, tmp_path):
    """Test setting preference saves to TOML."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    error = set_sandbox_preference(str(sandbox))

    assert error is None
    assert preferences_storage_lib.get_config_value(SANDBOX_KEY) == str(sandbox)


def test_set_sandbox_preference_nonexistent(temp_config_dir, tmp_path):
    """
    Test setting nonexistent path.
    Requirement 1: Should be possible to set a nonexistent path.
    """
    nonexistent = tmp_path / "does_not_exist"

    error = set_sandbox_preference(str(nonexistent))

    assert error is None
    assert preferences_storage_lib.get_config_value(SANDBOX_KEY) == str(nonexistent)


def test_set_sandbox_preference_empty_path(temp_config_dir, tmp_path):
    """Test setting empty path clears the preference."""
    # First set a preference
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    set_sandbox_preference(str(sandbox))
    assert preferences_storage_lib.get_config_value(SANDBOX_KEY) == str(sandbox)

    # Setting empty string should clear it
    error = set_sandbox_preference("")

    assert error is None
    assert preferences_storage_lib.get_config_value(SANDBOX_KEY) is None


def test_get_sandbox_preference_when_set(temp_config_dir, tmp_path):
    """Test retrieving stored preference."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    set_sandbox_preference(str(sandbox))
    retrieved = get_sandbox_preference()

    assert retrieved == sandbox


def test_get_sandbox_preference_when_not_set(temp_config_dir):
    """Test retrieving when no preference exists."""
    assert get_sandbox_preference() is None


def test_preference_persists_across_calls(temp_config_dir, tmp_path):
    """Test that preference persists across function calls."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Set
    error = set_sandbox_preference(str(sandbox))
    assert error is None

    # Retrieve
    retrieved = get_sandbox_preference()

    assert retrieved == sandbox


def test_validate_sandbox_path(tmp_path):
    """Test validation logic."""
    # Valid
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    assert validate_sandbox_path(sandbox) is None

    # Nonexistent
    nonexistent = tmp_path / "does_not_exist"
    assert "does not exist" in validate_sandbox_path(nonexistent)

    # Not a directory
    file = tmp_path / "file.txt"
    file.write_text("content")
    assert "not a directory" in validate_sandbox_path(file)
