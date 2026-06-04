"""
TOML-based configuration storage for NEF-Pipelines.

Provides simple functions for persisting user preferences across sessions.
"""

import sys
from pathlib import Path
from typing import Any, Dict

try:
    import platformdirs
except ImportError:
    platformdirs = None

import tomli_w

from nef_pipelines.lib.util import exit_error

# Handle Python 3.9/3.10 vs 3.11+ compatibility
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _get_config_path() -> Path:
    """Get platform-specific configuration directory."""
    if platformdirs is None:

        exit_error(
            "platformdirs is required for configuration storage but is not installed."
        )

    return Path(platformdirs.user_config_dir("nef-pipelines"))


def get_config_file_path(filename: str = "config.toml") -> Path:
    """
    Get the full path to a config file.

    Args:
        filename: Name of the TOML file (default: config.toml)

    Returns:
        Absolute path to the config file
    """
    path = _get_config_path() / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_config(filename: str = "config.toml") -> Dict[str, Any]:
    """
    Load configuration from TOML file.

    Args:
        filename: Name of the TOML file

    Returns:
        Dictionary of configuration values, empty dict if file doesn't exist.
    """
    path = get_config_file_path(filename)
    if not path.exists():
        return {}

    with open(path, "rb") as f:
        return tomllib.load(f)


def save_config(data: Dict[str, Any], filename: str = "config.toml") -> bool:
    """
    Save configuration to TOML file.

    Args:
        data: Dictionary to serialize to TOML
        filename: Name of the TOML file

    Returns:
        True if saved successfully.
    """
    path = get_config_file_path(filename)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)

    return True


def get_config_value(
    key: str, default: Any = None, filename: str = "config.toml"
) -> Any:
    """Get a configuration value."""
    config = load_config(filename)
    return config.get(key, default)


def set_config_value(key: str, value: Any, filename: str = "config.toml") -> bool:
    """Set a configuration value."""
    config = load_config(filename)
    config[key] = value
    return save_config(config, filename)


def delete_config_value(key: str, filename: str = "config.toml") -> bool:
    """Delete a configuration key."""
    config = load_config(filename)
    if key in config:
        del config[key]
        return save_config(config, filename)
    return True


def clear_config(filename: str = "config.toml") -> bool:
    """Clear all configuration."""
    path = get_config_file_path(filename)
    if path.exists():
        path.unlink()
    return True
