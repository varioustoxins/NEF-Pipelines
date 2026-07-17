"""
Persistent sandbox preference management for NEF-Pipelines MCP server.

Provides functions to manage default sandbox directory that persists across sessions,
plus sandbox directory access management via @setup_sandbox decorator.
"""

import atexit
import os
import shutil
import site
import sys
import sysconfig
import tempfile
import time
from functools import wraps
from pathlib import Path
from textwrap import dedent
from typing import Optional, Union

from nef_pipelines.lib.preferences_storage_lib import (
    delete_config_value,
    get_config_value,
    set_config_value,
)
from nef_pipelines.lib.util import info, warn
from nef_pipelines.tools.ai.sandbox_data import (
    _SANDBOX_DATA,
    SANDBOX_KEY,
    _current_command,
)
from nef_pipelines.tools.ai.sandbox_structures import (
    AllowedDirs,
    PendingSetup,
    SandboxSetupError,
    SetupResult,
)

# ============================================================================
# Site-Packages Discovery (Lazy)
# ============================================================================


def get_valid_site_packages() -> set[Path]:
    """Discover all site-packages directories for the current Python installation.

    Computed lazily on first call and cached. Used to register __pycache__
    glob patterns so Python can compile .pyc files during normal operation.

    Checks:
        - sys.path entries ending in 'site-packages' or 'dist-packages'
        - site.getsitepackages() (if available)
        - site.getusersitepackages() (if available)
        - sysconfig purelib and platlib

    Returns:
        Set of resolved site-packages paths that exist on the filesystem.
    """
    import nef_pipelines.tools.ai.sandbox_data as sd

    if sd._cached_site_packages is not None:
        return sd._cached_site_packages

    routes = set()

    # Primary: sys.path entries that look like site-packages
    for entry in sys.path:
        path = Path(entry)
        if path.name in {"site-packages", "dist-packages"}:
            try:
                routes.add(path.resolve())
            except (OSError, RuntimeError):
                pass

    # Fallback via site module (may not exist in some environments)
    try:
        for sp in site.getsitepackages():
            routes.add(Path(sp).resolve())
    except AttributeError:
        pass

    try:
        routes.add(Path(site.getusersitepackages()).resolve())
    except AttributeError:
        pass

    # Robust fallback via sysconfig (both pure Python and platform-specific)
    try:
        routes.add(Path(sysconfig.get_paths()["purelib"]).resolve())
    except KeyError:
        pass

    try:
        routes.add(Path(sysconfig.get_paths()["platlib"]).resolve())
    except KeyError:
        pass

    result = {p for p in routes if p.exists()}
    sd._cached_site_packages = result
    return result


def register_site_packages_pycache_patterns():
    """Register glob patterns for __pycache__ in site-packages.

    Called at module initialization (from sandbox_data) to allow Python bytecode
    compilation in installed libraries. Each pattern is paired with its specific
    base directory, so only __pycache__ writes are allowed, not all of site-packages.

    Patterns checked only on write (compilation time), so glob matching
    overhead is negligible compared to compilation cost.

    Why this is in sandbox_lib instead of sandbox_data:
    Keeps sandbox_data purely declarative (data structures and globals only).
    Functions that manipulate the registry belong in sandbox_lib.
    """
    # Pair the __pycache__ pattern with each site-packages base.
    # Do NOT add site-packages to directories (that would allow ALL writes there).
    for site_pkg in get_valid_site_packages():
        _SANDBOX_DATA.globals.glob_patterns.append((site_pkg, "**/__pycache__/**"))


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


def init_sandbox_instance(instance_id: str, test_mode: bool = False) -> None:
    """Initialize sandbox instance with unique ID and optionally create tmp base directory.

    After the tmp base is set, drains any setups recorded by @setup_sandbox
    decorators that ran before this instance existed.

    For non-test-mode instances, registers an atexit handler to clean up the tmp
    directory when the server exits.

    Args:
        instance_id: Unique identifier for this MCP server instance
        test_mode: If True, sets paths for display but skips directory creation
    """
    global _INSTANCE_ID, _TMP_BASE, _TEST_MODE
    _INSTANCE_ID = instance_id
    _TEST_MODE = test_mode

    tmp_base = Path(get_tmp_base_dir()) / instance_id
    if not test_mode:
        tmp_base.mkdir(parents=True, exist_ok=True)
        info(f"Initialized sandbox instance: {instance_id} at {tmp_base}")
        # Register cleanup handler to delete tmp directory on exit
        atexit.register(_cleanup_sandbox_instance, tmp_base, instance_id)
    _TMP_BASE = tmp_base

    drain_pending_setups_if_initialized()


def init_sandbox_instance_with_generated_id(
    prefix: str = "PID", test_mode: bool = False
) -> str:
    """Generate a PID-TIME instance ID and initialize the sandbox instance with it.

    Centralises the instance ID format (used identically by the real server,
    test session setup, and the diagnostic test instance in `sandbox show
    --verbose`) so it exists in exactly one place.

    Args:
        prefix: Prefix for the instance ID, e.g. "PID" for a real instance or
            "TEST-PID" for a throwaway diagnostic-only instance.
        test_mode: If True, sets paths for display but skips directory creation

    Returns:
        The generated instance_id, in case the caller wants to log or display it.
    """
    instance_id = f"{prefix}{os.getpid()}-TIME{time.time_ns()}"
    init_sandbox_instance(instance_id, test_mode=test_mode)
    return instance_id


def _cleanup_sandbox_instance(tmp_base: Path, instance_id: str) -> None:
    """Clean up sandbox instance tmp directory on server exit.

    Removes cache directories created by setup functions, except those marked as
    no_cleanup_paths. Then tries to remove the instance directory itself. Warns
    if the directory can't be removed because it contains persistent files.

    Args:
        tmp_base: Path to the instance tmp directory to remove
        instance_id: Instance ID (used to determine if we should log cleanup)
    """
    if not tmp_base.exists():
        return

    is_server = not instance_id.startswith("TEST-")

    try:
        # Remove subdirectories that are not marked as no_cleanup
        for item in tmp_base.iterdir():
            if item not in _SANDBOX_DATA.no_cleanup_paths:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

        # Try to remove instance directory (only succeeds if empty)
        tmp_base.rmdir()
        if is_server:
            info(f"Cleaned up sandbox instance directory: {tmp_base}")
    except OSError as e:
        # Directory not empty (contains no_cleanup_paths or other files)
        if is_server:

            msg = f"""
                    When cleaning up the MCP server sandbox it was not empty:
                    {e}
                    {tmp_base} will not be deleted as it contains files we could not
                    or didn't delete during cleanup.
                """
            msg = dedent(msg).strip()
            warn(msg)


def drain_pending_setups_if_initialized() -> None:
    """Execute pending setups recorded by @setup_sandbox.

    Command modules record their setups as pending at import time (imports must not
    fail); this runs them once _TMP_BASE is known — invoking each setup callable,
    creating directories, setting env vars, and registering allowed paths. Called
    from init_sandbox_instance and after late module loads (create_nef_pipelines_app).
    Both call sites are only ever reached after init_sandbox_instance has run.

    Runs outside load_nef_modules' exception handling, so any SandboxSetupError from
    _execute_setup propagates and crashes hard rather than being silently swallowed.

    Raises:
        SandboxSetupError: if called before init_sandbox_instance — a call-ordering
            bug, not a runtime condition to tolerate silently.
    """
    if not (_INSTANCE_ID and _TMP_BASE):
        raise SandboxSetupError(
            "drain_pending_setups_if_initialized() called before init_sandbox_instance(); "
            "this indicates a call-ordering bug, not a valid runtime state."
        )

    global _PENDING_DIRECTORY_SETUPS
    pending, _PENDING_DIRECTORY_SETUPS = _PENDING_DIRECTORY_SETUPS, []
    for setup in pending:
        _execute_setup(setup.command_id, setup.setup_callables, setup.static_items)


def _raise_if_already_imported(module_name: str) -> None:
    """Crash hard if a library that reads its cache path at import time is already loaded.

    Setup functions like setup_matplotlib redirect a library's cache directory via an
    environment variable (e.g. MPLCONFIGDIR) that only has an effect if set before the
    library's first import. If the library is already in sys.modules, that import has
    already happened — the library resolved its cache to the default (unsandboxed)
    location — and setting the env var now would silently do nothing. Command modules
    must import such libraries lazily (inside the function body, not at module level)
    so this check passes; a failure here means that invariant was violated.

    Args:
        module_name: Top-level module name to check (e.g. "matplotlib", "jax")

    Raises:
        SandboxSetupError: if module_name is already present in sys.modules
    """
    if module_name in sys.modules:
        raise SandboxSetupError(
            f"'{module_name}' is already imported; its cache path cannot be "
            f"redirected into the sandbox. Command modules must import "
            f"'{module_name}' lazily (inside the function body), not at module level."
        )


def get_tmp_base_dir() -> str:
    """Get base directory for tool caches.

    Uses platform-specific temp directory (via tempfile.gettempdir()):
    - macOS: /var/folders/.../T/nef_pipelines_mcp_tmp
    - Linux: /tmp/nef_pipelines_mcp_tmp
    - Windows: %TEMP%/nef_pipelines_mcp_tmp

    Overridable via NEF_SANDBOX_TMP env var.
    """
    if "NEF_SANDBOX_TMP" in os.environ:
        return os.environ["NEF_SANDBOX_TMP"]

    # Use platform-specific temp directory
    return os.path.join(tempfile.gettempdir(), "nef_pipelines_mcp_tmp")


def _has_glob_chars(pattern: str) -> bool:
    """Check if string contains unescaped glob wildcard characters.

    Args:
        pattern: String to check for glob patterns

    Returns:
        True if pattern contains *, ?, or [ characters (glob wildcards)
    """
    return any(c in pattern for c in ["*", "?", "["])


def _register_path_or_pattern(
    path_or_pattern: Union[str, Path], command_id: str
) -> None:
    """Register a path or glob pattern to command-specific registry.

    Automatically routes to the appropriate registry:
    - Plain paths → command.directories (allow all writes in that directory)
    - Glob patterns → command.glob_patterns, paired with _TMP_BASE as the base
        directory (allow only writes matching the pattern relative to _TMP_BASE)

    Args:
        path_or_pattern: Either an exact path or a glob pattern string
        command_id: Command identifier ("module.function")
    """
    if _TMP_BASE is None:
        raise SandboxSetupError(
            "_register_path_or_pattern called before init_sandbox_instance"
        )

    # Ensure command has an entry in registry
    if command_id not in _SANDBOX_DATA.commands:
        _SANDBOX_DATA.commands[command_id] = AllowedDirs()

    path_str = str(path_or_pattern)

    if _has_glob_chars(path_str):
        # Has wildcards - pair with _TMP_BASE and add to command's glob patterns
        _SANDBOX_DATA.commands[command_id].glob_patterns.append((_TMP_BASE, path_str))
    else:
        # Plain path - add to command's allowed directories
        _SANDBOX_DATA.commands[command_id].directories.add(Path(path_str))


def _execute_setup(command_id: str, setup_callables: list, static_items: list) -> None:
    """Run a command's setup callables and static items against the current _TMP_BASE.

    Creates directories, sets env vars (via the callables), and registers allowed
    paths/patterns and descriptions in the per-command registry. Requires an
    initialized instance.

    Args:
        command_id: Command identifier ("module.function")
        setup_callables: Zero-argument setup functions, each returning a SetupResult
        static_items: Literal paths or glob patterns declared on the decorator
    """
    paths_or_patterns = []
    descriptions = []
    try:
        # Run setup callables — each self-reports its paths/patterns and a
        # description of what it did (env vars set, etc.), so --verbose can show
        # it without guessing via os.environ diffing.
        for setup_fn in setup_callables:
            result = setup_fn()  # No args - use global _TMP_BASE
            paths_or_patterns.extend(result.paths_or_patterns)
            descriptions.append([setup_fn.__name__, result.description.split()])
            # Collect paths that should not be cleaned up on exit
            _SANDBOX_DATA.no_cleanup_paths.update(result.no_cleanup_paths)

        # Add static paths/patterns from args
        for item in static_items:
            # If it's a plain path (no glob chars), create directory if needed
            if isinstance(item, str) and not _has_glob_chars(item):
                path = Path(item).expanduser()
                if not _TEST_MODE:
                    path.mkdir(parents=True, exist_ok=True)
            paths_or_patterns.append(item)

        # Ensure the command has a registry entry even if it registered nothing
        # (e.g. a setup callable that only sets an env var with no path to allow).
        if command_id not in _SANDBOX_DATA.commands:
            _SANDBOX_DATA.commands[command_id] = AllowedDirs()

        # Register with per-command registry
        for item in paths_or_patterns:
            _register_path_or_pattern(item, command_id)

        _SANDBOX_DATA.commands[command_id].descriptions.extend(descriptions)

    except Exception as e:
        raise SandboxSetupError(
            f"Sandbox setup failed for command '{command_id}'.\n"
            f"Setup functions: {[f.__name__ for f in setup_callables]}\n"
            f"Error: {e}"
        ) from e


def setup_sandbox(*items):
    """Declare sandbox directory setup for a command.

    Command modules are imported during app startup (before init_sandbox_instance),
    so this decorator only *records* intent at decoration time. The directory
    creation and env-var work is executed later, when init_sandbox_instance drains
    the pending list (or immediately if the instance already exists). The returned
    wrapper sets the current-command context during execution for the audit hook.

    Args:
        *items: Variable arguments dispatched by type:
            - Callable: Setup function (no args), must return a SetupResult
            - str: Path (plain) or glob pattern (with *, ?, [)
            - Path: Directory path

    Setup functions must return a SetupResult, whose paths_or_patterns may contain:
        - Single path/pattern (str or Path) or a list of them
        - Patterns with ** for recursive matching (e.g., "/path/**/__pycache__/**")
    Its description is a human-readable summary of what the function did (env vars
    set, etc.), shown by `nef ai sandbox show --verbose`.

    Example:
        @plot_app.command()
        @setup_sandbox(
            setup_matplotlib,              # Callable - setup function
            "~/.cache/nef_plots",          # str - static path
            "/usr/share/fonts/**/*.ttf"    # str - glob pattern
        )
        def correlations(...):
            ...

    Returns:
        Decorator that records setup intent and returns a context-setting wrapper.
    """
    # Separate callables from paths/patterns
    setup_callables = [item for item in items if callable(item)]
    static_items = [item for item in items if not callable(item)]

    def decorator(fn):
        # Compute command identifier (persistent across executions)
        command_id = f"{fn.__module__}.{fn.__qualname__}"

        # Record intent only — never execute setup during import. Command modules are
        # imported inside load_nef_modules_and_build_failure, which downgrades import
        # exceptions to warnings; executing here would let a setup failure be swallowed
        # silently. Execution happens exclusively via drain (init_sandbox_instance /
        # drain_pending_setups_if_initialized), which runs outside that try/except so
        # a SandboxSetupError always propagates and crashes hard.
        _PENDING_DIRECTORY_SETUPS.append(
            PendingSetup(command_id, setup_callables, static_items)
        )

        # Wrap function to set command context during execution
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _current_command.set(command_id)
            try:
                return fn(*args, **kwargs)
            finally:
                _current_command.reset(token)

        return wrapper

    return decorator


def setup_matplotlib() -> SetupResult:
    """Configure matplotlib to use sandbox tmp directory.

    CRITICAL: This path is for LIBRARY CACHES ONLY (exempt from protection).
    All user-visible outputs (plots) MUST go to sandbox, never to MPLCONFIGDIR.

    Raises:
        SandboxSetupError: if matplotlib is already imported. MPLCONFIGDIR only takes
            effect if set before matplotlib's first import; setting it after means
            matplotlib already resolved its cache to the default (unsandboxed)
            location, so we must stop rather than silently leave it unredirected.

    Returns:
        SetupResult with the matplotlib cache directory and a description of the
        MPLCONFIGDIR redirect (for audit exemption and `sandbox show --verbose`).
    """
    if _TMP_BASE is None:
        raise SandboxSetupError("setup_matplotlib called before init_sandbox_instance")

    if not _TEST_MODE:
        _raise_if_already_imported("matplotlib")

    matplotlib_dir = _TMP_BASE / ".matplotlib"
    if not _TEST_MODE:
        matplotlib_dir.mkdir(parents=True, exist_ok=True)
        # Redirect matplotlib config/cache BEFORE importing
        os.environ["MPLCONFIGDIR"] = str(matplotlib_dir)

    return SetupResult(
        paths_or_patterns=[matplotlib_dir],
        description=f"MPLCONFIGDIR={matplotlib_dir}",
    )


def setup_jax() -> SetupResult:
    """Configure JAX/XLA/CUDA caches to use sandbox tmp directory.

    Raises:
        SandboxSetupError: if jax is already imported. The cache env vars only take
            effect if set before jax's first import; setting them after means jax
            already resolved its caches to the default (unsandboxed) location, so we
            must stop rather than silently leave them unredirected.

    Returns:
        SetupResult with the cache directories and a description of the env vars set.
    """

    if _TMP_BASE is None:
        raise SandboxSetupError("setup_jax called before init_sandbox_instance")

    if not _TEST_MODE:
        _raise_if_already_imported("jax")

    jax_cache = _TMP_BASE / "jax_cache"
    cuda_cache = _TMP_BASE / "cuda_cache"
    triton_cache = _TMP_BASE / "triton_cache"

    if not _TEST_MODE:
        # Set env vars BEFORE importing jax
        os.environ["JAX_COMPILATION_CACHE_DIR"] = str(jax_cache)
        os.environ["CUDA_CACHE_PATH"] = str(cuda_cache)
        os.environ["TRITON_CACHE_DIR"] = str(triton_cache)

        # Create directories
        for cache_dir in [jax_cache, cuda_cache, triton_cache]:
            cache_dir.mkdir(parents=True, exist_ok=True)

    return SetupResult(
        paths_or_patterns=[jax_cache, cuda_cache, triton_cache],
        description=dedent(
            f"""
                JAX_COMPILATION_CACHE_DIR={jax_cache}
                CUDA_CACHE_PATH={cuda_cache}
                TRITON_CACHE_DIR={triton_cache}
            """
        ),
    )


def setup_numba() -> SetupResult:
    """Configure Numba cache to use sandbox tmp directory.

    Raises:
        SandboxSetupError: if numba is already imported. NUMBA_CACHE_DIR only takes
            effect if set before numba's first import; setting it after means numba
            already resolved its cache to the default (unsandboxed) location, so we
            must stop rather than silently leave it unredirected.

    Returns:
        SetupResult with the Numba cache directory and a description of the env var set.
    """
    if _TMP_BASE is None:
        raise SandboxSetupError("setup_numba called before init_sandbox_instance")

    if not _TEST_MODE:
        _raise_if_already_imported("numba")

    numba_cache = _TMP_BASE / ".numba"
    if not _TEST_MODE:
        numba_cache.mkdir(parents=True, exist_ok=True)
        os.environ["NUMBA_CACHE_DIR"] = str(numba_cache)

    return SetupResult(
        paths_or_patterns=[numba_cache],
        description=f"NUMBA_CACHE_DIR={numba_cache}",
    )
