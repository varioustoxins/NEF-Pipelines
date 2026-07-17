"""Sandbox write auditing via sys.addaudithook.

This is a *defense-in-depth* measure, not a security boundary. The
audit hook runs in-process at the Python level and only fires for
operations that CPython explicitly instruments. A determined caller
in the same process can always escape it; the goal is to catch
*accidental* writes outside the sandbox in trusted pipeline code,
not to contain hostile code.

What is NOT enforced
--------------------
1. **Subprocesses and exec.** ``subprocess.Popen``, ``os.system``,
   and ``os.exec*`` are not monitored. Anything that shells out can
   write anywhere on the filesystem. Acceptable here because the
   pipeline code is pure-Python and does not shell out.

2. **C extensions.** Extensions that call ``fopen``/``write`` in C
   without routing through ``_io.open`` do not trigger the ``open``
   audit event. Handled separately by the project; not this module's
   concern.

3. **Metadata-only changes.** ``os.chmod``, ``os.chown``, and
   ``os.utime`` are not monitored. They change permissions /
   ownership / timestamps but no file contents, so they fall outside
   the "writes outside the sandbox" scope. ``os.truncate`` *is*
   monitored because it does modify file contents.

4. **fd-based variants.** Operations that accept either a path or
   an fd (e.g. ``os.truncate``) are only enforced for the path form.
   The fd variant is allowed through on the assumption that the
   ``open()`` which produced the fd was itself audited and therefore
   the fd already points inside the sandbox.

5. **Threads and asyncio task switches.** State is stored in
   ``threading.local``. New threads start with empty state and bypass
   the hook. Asyncio task switches can also land continuations on
   different threads from the one that entered the sandbox context;
   inside a sandboxed coroutine, do not ``run_in_executor`` or
   ``asyncio.to_thread`` and assume the sandbox follows. If the
   pipeline ever grows real concurrency, this module needs to move
   to a ``ContextVar``.

TOCTOU
------
There is an inherent gap between the audit hook's path resolution
and the actual syscall. A concurrent thread (or a symlink swap
between resolve() and open()) can in principle race the check.
Acceptable for defense-in-depth; not acceptable if you were
relying on this as a hard guarantee.

mmap specifics
--------------
The ``mmap.__new__`` audit event provides only a file descriptor,
not a path. Path resolution is best-effort:

  - macOS: ``fcntl(fd, F_GETPATH)`` (constant value 50)
  - Linux: ``/proc/self/fd/{fd}`` symlink resolution
  - Windows / other: no resolution path; the call is allowed
    through (the ``fcntl`` module itself is unavailable on Windows,
    which is why the import is guarded)

When resolution fails, the call is allowed on the assumption that
the originating ``open()`` (or ``os.open()``) was already audited
and confined the fd to the sandbox.

The ``access`` argument (args[2]) determines whether the mapping
can write. ``ACCESS_READ`` is the only value treated as read-only;
``ACCESS_DEFAULT`` inherits from the underlying file's open mode
and is therefore conservatively treated as potentially writable,
as are ``ACCESS_WRITE`` and ``ACCESS_COPY``.

Case-insensitive filesystems
----------------------------
Path containment is checked via a helper that applies
``os.path.normcase`` to both sides. On Windows this folds case
(NTFS is case-insensitive); on POSIX it is a no-op, but
``Path.resolve()`` typically canonicalises case on macOS APFS
volumes so the comparison still works there. A trailing-separator
check prevents ``/foo/bar`` from incorrectly matching
``/foo/barbaz`` as a containing prefix.

Symlinks are resolved via ``Path.resolve()`` before the check, so
a symlink inside the sandbox pointing outside it is correctly
flagged as a violation when written through. Creating a symlink
or hardlink whose *destination path* is outside the sandbox is
itself blocked, via the ``os.symlink`` and ``os.link`` events.

Nesting
-------
Nested ``audit_sandbox_writes`` contexts are NOT supported. Attempting
to enter a second context while one is already active raises
``RuntimeError``.

Lifecycle
---------
``sys.addaudithook`` is irreversible — once installed, the hook
remains for the lifetime of the process. The ``is_active`` flag
gates whether the hook actually does anything, so the cost when
no sandbox is active is a single attribute lookup per audit event.

Path resolution errors
----------------------
``Path.resolve()`` can raise ``OSError`` (ELOOP on symlink cycles,
ENAMETOOLONG, etc.) as well as ``ValueError``. Both are caught and
converted into ``SandboxViolation`` sandbox violations rather than
allowed to propagate out of unrelated ``open()`` calls as confusing
failure modes.

Diagnostics
-----------
Violation messages include the offending path, the sandbox root,
the audit event name, and  stack frames from outside this
module showing which package and function attempted the write. The
caller frames are captured at the point of violation and stored in
``state.violation_error``, so the backstop raise on context exit
preserves them even if the original exception was swallowed by an
intervening library.

TODO: Delayed stack trace formatting
-------------------------------------
Currently, stack traces are formatted during the audit hook using
``traceback.StackSummary.extract(..., lookup_lines=False)`` to avoid
reading source files (which would trigger re-entrant audit events).
This produces stack traces without source code context.

**Improvement:** Delay formatting until after the audit hook is deactivated:

1. **During hook (minimal):**
   - Capture raw stack frames: ``list(traceback.walk_stack(None))``
   - Store in violation record (don't format yet)
   - Raise immediately or collect for later (design choice)

2. **After command execution (in __exit__):**
   - Format with ``lookup_lines=True`` (safe now, hook is off)
   - Include full source code context for better debugging

**Benefits:**
- Richer error messages with source code snippets
- Faster hook (less work during critical path)
- No re-entrance risk (formatting happens after hook deactivated)
- Can aggregate/filter multiple violations

**Implementation sketch:**
.. code-block:: python

    @dataclass
    class ViolationRecord:
        path: Path
        event: str
        raw_frames: list  # Captured during hook

    class audit_sandbox_writes:
        def __init__(self, ...):
            self.violations = []  # Collect here

        def __exit__(self, exc_type, exc_val, exc_tb):
            # Format violations AFTER hook deactivated
            for v in self.violations:
                stack = traceback.StackSummary.extract(
                    v.raw_frames,
                    lookup_lines=True  # Safe now!
                )
                detailed = ''.join(traceback.format_list(stack))
                logger.error(f"Violation: {v.path}\\n{detailed}")

            # Deactivate hook
            sys.removeaudithook(self._hook_id)

**Design decision needed:** Should violations raise immediately
(stopping command) or collect all violations and report after?
Current behavior is immediate raise; delayed formatting allows either.
"""

import logging
import mmap
import os
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# fcntl is POSIX-only; the mmap fd → path resolution silently
# degrades to "allow through" on Windows.
try:
    import fcntl
except ImportError:
    fcntl = None

from nef_pipelines.tools.ai.sandbox_data import _SANDBOX_DATA, _current_command
from nef_pipelines.tools.ai.sandbox_lib import (
    is_path_in_sandbox,
    register_site_packages_pycache_patterns,
)

WRITE_EVENTS = {
    "open",
    "os.open",
    "pathlib.Path.write_text",
    "pathlib.Path.write_bytes",
    "os.mkdir",
    "os.makedirs",
    "os.replace",
    "os.rename",
    "os.remove",
    "os.rmdir",
    "os.unlink",
    "os.symlink",
    "os.link",
    "os.truncate",
    "shutil.copyfile",
    "shutil.copy",
    "shutil.copy2",
    "shutil.move",
    "shutil.rmtree",
    "mmap.__new__",
}

logger = logging.getLogger(__name__)


class SandboxViolation(PermissionError):
    """Raised when a write outside the active sandbox is attempted.

    Subclass of ``PermissionError`` so existing ``except PermissionError``
    handlers still catch it, but distinguishable for code that wants to
    handle sandbox violations specifically.

    Raised from two places:

      1. Inside the audit hook, at the moment a violating write is
         attempted. This is the primary signal.
      2. From ``audit_sandbox_writes.__exit__``, if a violation was
         recorded during the block but no ``SandboxViolation`` is
         currently propagating — i.e. some intervening code swallowed
         the original. This is a backstop against a library catching
         ``PermissionError`` / ``OSError`` / bare ``except`` and
         hiding the violation.
    """


@dataclass
class _AuditState:
    """Thread-local state for sandbox audit hook."""

    is_active: bool = False
    sandbox_path: Optional[Path] = None
    violation_error: Optional[str] = None


_audit_state = threading.local()
_audit_hook_installed = False
_install_lock = threading.Lock()


def _extract_path_from_audit_event(event: str, args: tuple) -> Optional[str]:
    """Extract file path from audit event arguments."""
    if event in (
        "open",
        "os.open",
        "os.mkdir",
        "os.makedirs",
        "os.remove",
        "os.rmdir",
        "os.unlink",
        "shutil.rmtree",
    ):
        return args[0] if args else None

    if event in (
        "os.replace",
        "os.rename",
        "shutil.copyfile",
        "shutil.copy",
        "shutil.copy2",
        "shutil.move",
        "os.symlink",
        "os.link",
    ):
        # Destination path is what's being written / created.
        return args[1] if len(args) > 1 else None

    if event in ("pathlib.Path.write_text", "pathlib.Path.write_bytes"):
        return str(args[0]) if args else None

    if event == "os.truncate":
        # Accepts either a path or an fd; skip the fd variant (the
        # open() that produced the fd was already audited).
        arg = args[0] if args else None
        if isinstance(arg, int):
            return None
        return str(arg) if arg is not None else None

    if event == "mmap.__new__":
        if not args or fcntl is None:  # Windows or no args
            logger.debug(
                "mmap fd resolution unavailable (fcntl=%s, args=%s); "
                "allowing through (assumes originating open() was audited)",
                fcntl is not None,
                bool(args),
            )
            return None
        fd = args[0]
        try:
            F_GETPATH = 50  # macOS
            try:
                path_buf = fcntl.fcntl(fd, F_GETPATH, b"\0" * 1024)
                return path_buf.split(b"\0", 1)[0].decode("utf-8")
            except (OSError, ValueError):
                proc_path = Path(f"/proc/self/fd/{fd}")
                if proc_path.exists():
                    return str(proc_path.resolve())
        except Exception as e:
            logger.debug("Could not resolve mmap fd %r to path: %s", fd, e)
        logger.debug(
            "mmap fd %r could not be resolved to path; "
            "allowing through (assumes originating open() was audited)",
            fd,
        )
        return None

    return None


def _is_write_operation(event: str, args: tuple) -> bool:
    if event == "open":
        mode = args[1] if len(args) > 1 else "r"
        # Python 3.9 can pass None as mode from pathlib.Path.open()
        if not mode:
            mode = "r"
        return any(c in mode for c in "wax+")

    if event == "os.open":
        flags = args[1] if len(args) > 1 else 0
        return bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC)
        )

    if event == "mmap.__new__":
        # Audit args are (fd, size, access, offset). access=1 is
        # ACCESS_READ; everything else (DEFAULT=0, WRITE=2, COPY=3)
        # is potentially writable. ACCESS_DEFAULT inherits from the
        # underlying file's open mode, so conservatively treated as
        # writable.
        if len(args) < 3:
            return True
        return args[2] != mmap.ACCESS_READ

    return True


_THIS_FILE = os.path.normcase(os.path.abspath(__file__))


def _format_caller_frames() -> str:
    """Return the complete call stack outside this module, plus any active exception chain.

    Captures all frames (no depth cap) so the full path from the nef pipeline
    code down to the violating stdlib call is visible.  Frames inside this module
    are excluded — they are hook internals, not the caller of interest.

    Uses ``traceback.StackSummary.extract`` with ``lookup_lines=False`` to avoid
    reading source files from disk during the hook (reading files would itself
    fire audit events and could cause re-entrant violations).

    Any exception that is actively being handled at the time of the violation
    (``sys.exc_info()``) is appended as a "Nested exception" section so chained
    errors — e.g. ``tempfile`` swallowing an earlier OSError — are visible.
    """
    parts: list = []

    # --- full call stack ---
    try:
        summary = traceback.StackSummary.extract(
            traceback.walk_stack(None),
            lookup_lines=False,
        )
        stack_lines = []
        for fs in summary:
            filename = os.path.normcase(os.path.abspath(fs.filename))
            if filename != _THIS_FILE:
                stack_lines.append(f"  {fs.filename}:{fs.lineno} in {fs.name}")
        parts.append("\n".join(stack_lines) if stack_lines else "  <no frames>")
    except Exception as exc:
        parts.append(f"  <could not capture stack: {exc}>")

    # --- any active exception being handled at violation time ---
    exc_type, exc_val, exc_tb = sys.exc_info()
    if exc_val is not None:
        try:
            exc_lines = traceback.format_exception(exc_type, exc_val, exc_tb)
            parts.append(
                "Nested exception at time of violation:\n" + "".join(exc_lines)
            )
        except Exception:
            pass

    return "\n".join(parts)


def _sandbox_audit_hook(event: str, args: tuple) -> None:
    state = getattr(_audit_state, "current", None)
    if not state or not state.is_active:
        return

    if event not in WRITE_EVENTS:
        return

    path_str = _extract_path_from_audit_event(event, args)
    if not path_str:
        return

    # fd-based operations (subprocess pipes, dup'd handles) pass an int, not a path.
    # These are internal fd operations audited when the originating open() already
    # passed sandbox checks, so skip them rather than attempting Path resolution.
    if not isinstance(path_str, (str, bytes, os.PathLike)):
        return

    if not _is_write_operation(event, args):
        return

    # Resolve the path. PermissionError is an OSError subclass, so
    # the violation raise must happen OUTSIDE this try/except —
    # otherwise the resolution-failure handler would catch our own
    # SandboxViolation and double-wrap it.
    try:
        path = Path(path_str).resolve()
    except (ValueError, OSError) as e:
        caller = _format_caller_frames()
        state.violation_error = (
            f"Sandbox violation: resolution failed for {path_str} "
            f"during {event}: {e}\n"
            f"Caller:\n  {caller}"
        )
        raise SandboxViolation(state.violation_error)

    # Check global allowlist (system-wide directories)
    if _SANDBOX_DATA.globals.directories:
        if any(
            path.is_relative_to(allowed)
            for allowed in _SANDBOX_DATA.globals.directories
        ):
            return  # Allow - global system directory (all writes allowed)

    # Check global glob patterns (paired with their base directories)
    if _SANDBOX_DATA.globals.glob_patterns:
        for base_dir, pattern in _SANDBOX_DATA.globals.glob_patterns:
            if path.is_relative_to(base_dir):
                relative_path = path.relative_to(base_dir)
                if relative_path.match(pattern):
                    return  # Allow - matches global pattern

    # Check per-command allowlist (command-specific caches)
    current_cmd_id = _current_command.get()
    if current_cmd_id and current_cmd_id in _SANDBOX_DATA.commands:
        cmd_allowed = _SANDBOX_DATA.commands[current_cmd_id]

        # Check command's directories
        if cmd_allowed.directories:
            if any(path.is_relative_to(allowed) for allowed in cmd_allowed.directories):
                return  # Allow - command-specific directory (all writes allowed)

        # Check command's glob patterns (paired with their base directories)
        if cmd_allowed.glob_patterns:
            for base_dir, pattern in cmd_allowed.glob_patterns:
                if path.is_relative_to(base_dir):
                    relative_path = path.relative_to(base_dir)
                    if relative_path.match(pattern):
                        return  # Allow - matches command pattern

    # Final check: is the path in the user sandbox?
    if not is_path_in_sandbox(path, state.sandbox_path):
        caller = _format_caller_frames()
        state.violation_error = (
            f"Sandbox violation: attempted write outside sandbox: {path}\n"
            f"Sandbox root: {state.sandbox_path}\n"
            f"Operation: {event}\n"
            f"Caller:\n  {caller}"
        )
        raise SandboxViolation(state.violation_error)


class audit_sandbox_writes:
    """Context manager that activates sandbox write auditing.

    While active, any file write operation outside ``sandbox_path`` will:
    1. Set the ``violation_error`` field on the returned state.
    2. Raise ``SandboxViolation`` (a ``PermissionError`` subclass)
       to stop the operation.

    On exit, if a violation was recorded but no ``SandboxViolation``
    is currently propagating out of the block, this context manager
    re-raises a fresh ``SandboxViolation`` as a backstop. This guards
    against the (unlikely but possible) case of a library inside the
    block catching ``PermissionError`` / ``OSError`` and swallowing
    the original. ``__exit__`` receives the propagating exception
    directly as ``exc_val``, so no ``sys.exc_info()`` call is needed.

    Args:
        sandbox_path: Root directory of the sandbox.

    Returns (from ``__enter__``):
        ``_AuditState`` object with a ``violation_error`` field.

    Raises:
        RuntimeError: if a sandbox context is already active (nesting not supported).
        SandboxViolation: from inside the block at the point of the
            offending write, OR from ``__exit__`` if the original was
            swallowed.
    """

    def __init__(self, sandbox_path: Path) -> None:
        """Initialise with the root directory of the sandbox."""
        self._sandbox_path = sandbox_path
        self._state: Optional[_AuditState] = None

    def __enter__(self) -> "_AuditState":
        """Activate the sandbox and return the audit state."""
        if not hasattr(_audit_state, "current"):
            _audit_state.current = _AuditState()

        state = _audit_state.current
        self._state = state

        if state.is_active:
            raise RuntimeError(
                "audit_sandbox_writes does not support nesting - a sandbox context is already active"
            )

        # Nested sandbox support was removed because nesting is not needed and the
        # extra complexity masked the bug where the backstop re-raised after a
        # violation was already handled (the save/restore of prev_active/prev_sandbox
        # meant sandbox_path was restored on exit, so the backstop fired against the
        # wrong sandbox root). If nesting is ever required, restore the block below
        # and update _execute_command_in_process to match.
        #
        # Save previous state for nested calls [marked with *s].
        # *prev_active = state.is_active
        # *prev_sandbox = state.sandbox_path

        state.is_active = True
        state.sandbox_path = self._sandbox_path.resolve()
        state.violation_error = None

        return state

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Deactivate the sandbox; re-raise as backstop if violation was swallowed."""
        state = self._state

        # Deactivate first so any audit events fired by garbage
        # collection / finalizers running between these assignments
        # see an inactive sandbox rather than an inconsistent
        # (is_active=True, sandbox_path=stale) state.
        state.is_active = False
        state.sandbox_path = None
        # *state.is_active = prev_active  # restore for nested support
        # *state.sandbox_path = prev_sandbox  # restore for nested support
        # violation_error intentionally not restored; caller reads it.

        # Backstop: if a violation was recorded but the original
        # SandboxViolation isn't currently propagating, something
        # swallowed it. Re-raise so the failure is impossible to miss.
        if state.violation_error is not None and not isinstance(
            exc_val, SandboxViolation
        ):
            raise SandboxViolation(state.violation_error)

        return False


def install_audit_hook():
    """Install sandbox write audit hook. Idempotent.

    The hook is permanent for the process lifetime and cannot be
    removed (CPython invariant). It remains dormant — a single
    attribute lookup per audit event — when no sandbox is active.
    """
    global _audit_hook_installed
    with _install_lock:
        if not _audit_hook_installed:

            register_site_packages_pycache_patterns()

            sys.addaudithook(_sandbox_audit_hook)
            _audit_hook_installed = True
            logger.info("Sandbox write audit hook installed")
