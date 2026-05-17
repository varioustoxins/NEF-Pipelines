import sys
from unittest.mock import patch

import pytest

from nef_pipelines.lib.preferences_storage_lib import (
    clear_config,
    delete_config_value,
    get_config_file_path,
    get_config_value,
    load_config,
    save_config,
    set_config_value,
)

if sys.version_info < (3, 10):
    pytest.skip(
        "AI sandbox features require Python 3.10 or later", allow_module_level=True
    )


@pytest.fixture
def mock_config_dir(tmp_path):
    """
    Mock platformdirs.user_config_dir to use a temporary directory.
    This ensures tests don't touch the real user configuration.
    """
    with patch("platformdirs.user_config_dir") as mock_dir:
        mock_dir.return_value = str(tmp_path / "nef-pipelines")
        yield tmp_path / "nef-pipelines"


def test_get_config_file_path(mock_config_dir):
    """Verify that the config file path is correctly resolved and parent dirs are created."""
    path = get_config_file_path("test_config.toml")

    assert path == mock_config_dir / "test_config.toml"
    assert path.parent.exists()
    assert path.parent.is_dir()


def test_save_and_load_config(mock_config_dir):
    """Verify round-trip saving and loading of a configuration dictionary."""
    data = {
        "user_name": "test_user",
        "iterations": 100,
        "enabled": True,
        "features": ["alpha", "beta"],
    }
    filename = "test_save.toml"

    assert save_config(data, filename) is True

    loaded_data = load_config(filename)
    assert loaded_data == data


def test_load_config_missing_file(mock_config_dir):
    """Ensure loading a non-existent config file returns an empty dictionary."""
    assert load_config("non_existent.toml") == {}


def test_get_set_config_value(mock_config_dir):
    """Test getting and setting individual configuration values."""
    filename = "test_values.toml"

    # Test setting a new value
    assert set_config_value("theme", "dark", filename) is True
    assert get_config_value("theme", filename=filename) == "dark"

    # Test getting a value with a default
    assert get_config_value("font_size", default=12, filename=filename) == 12

    # Test overwriting an existing value
    set_config_value("theme", "light", filename)
    assert get_config_value("theme", filename=filename) == "light"


def test_delete_config_value(mock_config_dir):
    """Test removing a specific key from the configuration."""
    filename = "test_delete.toml"
    set_config_value("key1", "val1", filename)
    set_config_value("key2", "val2", filename)

    # Delete an existing key
    assert delete_config_value("key1", filename) is True
    assert get_config_value("key1", filename=filename) is None
    assert get_config_value("key2", filename=filename) == "val2"

    # Deleting a non-existent key should complete without error
    assert delete_config_value("non_existent", filename) is True


def test_clear_config(mock_config_dir):
    """Verify that clearing the configuration removes the underlying file."""
    filename = "test_clear.toml"
    set_config_value("temp_key", "temp_value", filename)

    path = get_config_file_path(filename)
    assert path.exists()

    assert clear_config(filename) is True
    assert not path.exists()
    assert load_config(filename) == {}
