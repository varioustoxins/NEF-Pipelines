"""
Sandbox data structures.

Pure type definitions with no dependencies. Imported by both sandbox_data
and sandbox_lib to avoid circular imports.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple, Union


@dataclass
class AllowedDirs:
    """Registry of allowed directories and glob patterns for sandbox access."""

    directories: set[Path] = field(default_factory=set)
    glob_patterns: list[Tuple[Path, str]] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SetupResult:
    """Result of a @setup_sandbox setup callable.

    Setup callables self-report what they did, rather than having callers infer it
    (e.g. by diffing os.environ) — this generalises to any side effect, not just
    environment variables, and stays accurate as setup functions change.

    Attributes:
        paths_or_patterns: Directories or glob patterns to register as allowed
        description: Human-readable summary of what this setup did (env vars set,
            directories created, or anything else), shown by
            `nef ai sandbox show --verbose`
        no_cleanup_paths: Paths that should persist across server restarts (e.g.,
            expensive caches). These won't be removed on exit. Defaults to empty set.
    """

    paths_or_patterns: list[Union[Path, str]]
    description: str
    no_cleanup_paths: set[Path] = field(default_factory=set)


@dataclass
class PendingSetup:
    """Pending sandbox setup recorded by @setup_sandbox decorator.

    Records setup intent at decoration time (during module import), executed later
    when the sandbox instance is initialized.

    Attributes:
        command_id: Fully qualified command identifier (module.function)
        setup_callables: Setup functions that return SetupResult
        static_items: Static paths or glob patterns (str or Path)
    """

    command_id: str
    setup_callables: List[Callable[[], SetupResult]]
    static_items: List[Union[str, Path]]


@dataclass
class SandboxData:
    """Complete sandbox directory access registry.

    Attributes:
        globals: System-wide allowlist (__pycache__, safe /dev/ devices)
        commands: Per-command allowlist keyed by "module.function"
                  (e.g., "nef_pipelines.tools.plot.bar.bar" → matplotlib caches)
        sandbox_path: User's working directory (set at runtime by audit context)
        no_cleanup_paths: Paths that should persist across restarts (not cleaned on exit)
    """

    globals: AllowedDirs = field(default_factory=AllowedDirs)
    commands: Dict[str, AllowedDirs] = field(default_factory=dict)
    sandbox_path: Optional[Path] = None
    no_cleanup_paths: Set[Path] = field(default_factory=set)


class SandboxSetupError(RuntimeError):
    """Raised when sandbox setup fails or is called in wrong order."""

    pass
