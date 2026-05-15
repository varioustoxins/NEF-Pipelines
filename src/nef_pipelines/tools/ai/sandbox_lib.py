"""
Persistent sandbox preference management for NEF-Pipelines MCP server.

Provides functions to manage default sandbox directory that persists across sessions.
"""

import os
from pathlib import Path
from typing import Optional

from nef_pipelines.lib.preferences_storage_lib import (
    delete_config_value,
    get_config_value,
    set_config_value,
)

SANDBOX_KEY = "mcp_sandbox_path"


def get_sandbox_preference() -> Optional[Path]:
    """
    Get the stored sandbox preference.

    Returns:
        Path object if preference exists and is valid, None otherwise
    """
    result = None
    path_str = get_config_value(SANDBOX_KEY)

    if path_str:
        result = Path(path_str).expanduser().resolve()

    return result


def set_sandbox_preference(path: str) -> Optional[str]:
    """
    Set the sandbox preference. If path is empty, clears the preference.

    Args:
        path: Directory path to use as default sandbox, or empty string to clear

    Returns:
        Error message if failed, None if successful
    """
    error = None

    if not path:
        delete_config_value(SANDBOX_KEY)
    else:
        sandbox_path = Path(path).expanduser().resolve()
        set_config_value(SANDBOX_KEY, str(sandbox_path))

    return error


def validate_sandbox_path(path: Path) -> Optional[str]:
    """
    Validate if a path is a usable sandbox directory.
    Requirement 2: Server should error if not exist, not writable, or not a directory.

    Returns:
        Error message string if invalid, None if valid.
    """
    error = None

    if not path.exists():
        error = f"does not exist: {path}"
    elif not path.is_dir():
        error = f"is not a directory: {path}"
    elif not os.access(path, os.W_OK):
        error = f"is not writable: {path}"

    return error


def is_path_in_sandbox(path: Path, sandbox: Path) -> bool:
    """Check if a path is contained within a sandbox directory.

    Resolves both paths internally before checking containment. This is a
    minimal runtime containment check suitable for use in validation and
    audit hooks.

    Args:
        path: Path to check (will be resolved internally)
        sandbox: Sandbox root (will be resolved internally)

    Returns:
        True if path is inside or equal to sandbox, False otherwise.

    Notes:
        - Resolves both paths to handle symlinks and relative paths
        - Uses os.path.normcase() for explicit case-folding on Windows
        - Separator check prevents "/foo/bar" from matching "/foo/barbaz"
        - On POSIX, normcase() is a no-op; case handling via Path.resolve()
        - Returns True when path == sandbox (caller decides if that's valid)
    """
    path_resolved = path.resolve()
    sandbox_resolved = sandbox.resolve()

    path_norm = os.path.normcase(os.path.normpath(str(path_resolved)))
    sandbox_norm = os.path.normcase(os.path.normpath(str(sandbox_resolved)))
    if path_norm == sandbox_norm:
        return True
    return path_norm.startswith(sandbox_norm + os.sep)
