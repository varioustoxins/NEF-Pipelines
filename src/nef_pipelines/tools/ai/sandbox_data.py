"""
Sandbox global registry and instances.

This module contains global variables and instances.
Type definitions live in sandbox_structures.py.
Functions live in sandbox_lib.py.
"""

from contextvars import ContextVar
from pathlib import Path
from typing import Optional, Set

from nef_pipelines.tools.ai.sandbox_structures import PendingSetup, SandboxData

# Configuration key for storing sandbox preference
SANDBOX_KEY = "mcp_sandbox_path"


# ============================================================================
# Global Registry
# ============================================================================

# Global sandbox registry
_SANDBOX_DATA = SandboxData()

# Current command context (set during command execution)
_current_command: ContextVar[Optional[str]] = ContextVar(
    "current_command", default=None
)

# Instance ID and tmp base for this server session (set at startup)
_INSTANCE_ID: str = ""
_TMP_BASE: Optional[Path] = None

# Flag indicating if we are in test mode, when in this mode
# - Path calculation: ✓ Still happens (so you can see what paths WOULD be created)
#  - Directory creation: ✗ Skipped (mkdir calls wrapped in if not _PREVIEW_MODE)
#  - Cleanup handlers: ✗ Not registered (atexit.register skipped)
#  - info() logging: ✗ Suppressed
_TEST_MODE: bool = False

# Pending setups recorded by @setup_sandbox at decoration time. Command modules are
# imported during app startup (load_nef_modules), which runs before init_sandbox_instance,
# so setup cannot execute at decoration time. Recording intent needs no instance; the
# directory creation / env-var work is drained here once _TMP_BASE exists.
_PENDING_DIRECTORY_SETUPS: list[PendingSetup] = []


# Lazy-loaded site-packages cache (computed on first access)
_cached_site_packages: Optional[Set[Path]] = None
