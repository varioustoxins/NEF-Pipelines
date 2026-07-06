# Plan: MCP server sandbox for file I/O (revised after security review)

**STATUS: IMPLEMENTED DIFFERENTLY** — Simpler approach taken without the full IoBackend abstraction.

**What was built:**
- ✅ Audit hooks in `sandbox_audit.py` with `audit_sandbox_writes` context manager
- ✅ Sandbox infrastructure in `sandbox_lib.py` (path validation, preference storage)
- ✅ `--sandbox-path` and `--preserve` CLI options
- ⚠️ `nef_list_files()` shows cwd/sandboxed status (similar to planned `nef_pwd`)
- ⚠️ `nef_change_sandbox()` uses OS dialog picker (not path-based like planned `nef_chdir`)

**What was NOT built:**
- ❌ IoBackend abstraction layer (`lib/io_backend.py`)
- ❌ Safe I/O helpers (`lib/io.py` with `safe_open()`)
- ❌ `nef_pwd()` and `nef_chdir(path)` tools as designed in plan
- ❌ `--symlinks` flag

The sandbox security mechanism works but without the pluggable backend architecture designed for future keystore/offline mode.

---

## Threat model

The MCP server runs NEF commands in-process for a (potentially remote) AI. The AI **cannot
execute arbitrary Python** — it only invokes NEF commands and supplies args. Therefore:

- ctypes / subprocess / native-extension bypass attempts by the AI are **out of scope**
- side-effect writes, template-derived paths, and I/O inside NEF code or its Python deps
  **are in scope**
- the operator (human launching the server) is trusted

This sandbox is **defense in depth against AI command misuse**, not an adversarial security
boundary. For real isolation, run the server inside a chroot or container — document this
in the user-facing docs.

## Decisions (clarified with user)

1. **Reads and writes** are both restricted to the sandbox. The AI's only window onto the
   FS is via NEF commands; constraining them at the I/O level closes the surface.
2. **Two-layer chokepoint**: a `nef_pipelines.lib.io` helper (explicit, refactorable) **plus**
   `sys.addaudithook` (catches every `open`/FS event from stdlib and unrefactored code).
3. **Symlinks fail by default** (path is `Path.resolve()`-ed before the boundary check).
   A `--symlinks` operator flag on `nef ai server` disables resolution (opt-in to follow).
4. **Fail closed**: refuse to execute commands if no I/O backend is active.
5. **Default sandbox** is `tempfile.mkdtemp(prefix="nef_mcp_")` (mode 0700) cleaned up
   on `atexit`.
6. **Non-stdio transports**: serialize tool invocations behind a lock; warn that
   process-global CWD makes multi-client use semantically risky.
7. **Forward-compatible with a future "offline mode"** where data lives in an in-memory
   keystore instead of the filesystem. The chokepoint design is an *I/O backend*
   abstraction with sandbox as the first concrete backend; a `KeystoreBackend` plugs in
   later without touching NEF command code that uses `safe_open`.

## Forward compatibility: in-memory keystore (future)

A future `--offline` mode will route all NEF I/O to an in-memory keystore. The design
must not preclude this. Consequences for *this* plan:

- All file I/O abstractions go through an `IoBackend` interface (defined now). The
  sandbox case is the first concrete implementation; the keystore case slots in later
  with no changes to NEF commands that use `safe_open`.
- `safe_open(name, mode)` resolves `name` via the active backend. In sandbox mode, `name`
  is a filesystem path. In keystore mode, `name` is treated as a keystore key (or a
  `keystore://` URI — TBD when offline mode is designed).
- `nef_pwd` / `nef_chdir` are sandbox-mode tools and should be **registered conditionally**
  on the active backend. In keystore mode they would not be exposed (or would return
  `success=False, mode="keystore"`). For this plan, register them unconditionally since
  only the sandbox backend exists; the registration site is the seam for the future
  switch.
- Layer-1 arg validation (path-shaped args) is sandbox-specific. Move it onto the backend
  (`backend.validate_args(args)`) so keystore mode can validate keys instead.
- The audit hook in sandbox mode restricts to a directory; in keystore mode the same hook
  would deny **all** filesystem access (since nothing should reach the FS). The hook is
  installed per-backend.

The seam: `nef_pipelines.lib.io_backend` defines the interface; `nef_pipelines.lib.io`
exposes the public helpers (`safe_open`, etc.) that delegate to the active backend.
`tools.ai.sandbox` becomes the concrete `SandboxBackend` implementation.

---

## Architecture overview

```
                      AI invokes nef_execute_command(...)
                                  │
   ┌──────────────── MCP tool entry point ────────────────┐
   │ Layer 1: backend.validate_args(args)                 │  fast fail on bad args
   │ Layer 2: serialize lock for non-stdio transports     │
   │ Layer 3: save CWD; runner.invoke(...) ; restore CWD  │  CWD-invariant defense (sandbox)
   └─────────────────────────┬────────────────────────────┘
                             │  (during invoke)
   ┌────────────── Inside the NEF command ────────────────┐
   │ Layer 4 (explicit): nef_pipelines.lib.io.safe_open   │  delegates to active IoBackend
   │ Layer 5 (catch-all): backend.audit_hook              │  catches every open + FS event
   └──────────────────────────────────────────────────────┘

   Active IoBackend  ──► SandboxBackend (this plan)
                    └─►  KeystoreBackend (future, --offline)
```

Layers 1, 3, and 5 are mandatory and ship together. Layer 4 ships as the helper module
plus a documented convention; existing-code refactor is an explicit follow-up.

The `IoBackend` interface is the only seam the future keystore backend needs.

---

## Files to change

| File | Change |
|---|---|
| `src/nef_pipelines/lib/io_backend.py` (new) | `IoBackend` ABC: `validate_args`, `enforce_path`, `open`, `audit_hook`, `pwd`, `chdir`, `info`. Module-level `get_active_backend` / `set_active_backend` registry |
| `src/nef_pipelines/lib/io.py` (new) | Public helpers: `safe_open`, `safe_read_text`, `safe_write_text`, `enforce_path` — all thin delegators to `get_active_backend()` |
| `src/nef_pipelines/tools/ai/sandbox.py` (new) | `SandboxBackend(IoBackend)` implementation; `initialize_sandbox(path, allow_symlinks)` constructs and registers it; `_invocation_lock`; `nef_pwd`, `nef_chdir` (delegate to active backend) |
| `src/nef_pipelines/tools/ai/mcp_commands_lib.py` | Guard `execute_command_in_process`: `backend.validate_args(args)` + CWD save/restore + lock; expose `nef_pwd`, `nef_chdir` |
| `src/nef_pipelines/tools/ai/server.py` | `--sandbox PATH` and `--symlinks` CLI options; call `initialize_sandbox(...)` before server starts |
| `src/nef_pipelines/tools/ai/mcp_lib.py` | Register `nef_pwd`, `nef_chdir` tools (after `nef_read_resource`, before list/help/execute) |
| `src/nef_pipelines/resources/mcp_server/preamble.md` | Add `nef_pwd` / `nef_chdir` to the Tools section (renumber) |
| `src/nef_pipelines/resources/mcp_server/skill.md` | Document the sandbox model and forward path to offline/keystore mode |
| `src/nef_pipelines/tests/ai/test_nef_mcp_server.py` | New sandbox / pwd / chdir / audit-hook tests |
| `src/nef_pipelines/tests/ai/test_nef_mcp_server_integration.py` | Add `nef_pwd`, `nef_chdir` to `EXPECTED_TOOL_NAMES` |
| `src/nef_pipelines/tests/lib/test_io_backend.py` (new) | Unit tests for the `IoBackend` registry; trivial `NullBackend` mock to verify dispatch works without a sandbox setup |

---

## Implementation

### A0. `src/nef_pipelines/lib/io_backend.py` (new — the seam for offline mode)

```python
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class IoBackend(ABC):
    """Pluggable I/O policy. Sandbox is the first concrete backend; future
    KeystoreBackend will satisfy the same interface for offline mode."""

    name: str  # "sandbox", "keystore", ...

    # ---- gating tool args before invocation ---------------------------------
    @abstractmethod
    def validate_args(self, args: List[str]) -> Optional[str]:
        """Return error string if args are unacceptable, else None."""

    # ---- core I/O ------------------------------------------------------------
    @abstractmethod
    def enforce(self, name: Any) -> None:
        """Raise PermissionError if `name` (path or key) is not permitted."""

    @abstractmethod
    def open(self, name: Any, mode: str = "r", *args, **kwargs):
        """Open and return a file-like object. Backend may interpret `name`."""

    # ---- audit-hook integration ---------------------------------------------
    @abstractmethod
    def install_audit_hook(self) -> None:
        """Install a sys.addaudithook that enforces this backend's policy."""

    # ---- navigation (sandbox-only; no-ops/errors for keystore) ---------------
    def pwd(self) -> Dict[str, Any]:
        return {"mode": self.name, "supports_pwd": False, "success": True}

    def chdir(self, path: str) -> Dict[str, Any]:
        return {"mode": self.name, "success": False,
                "error": f"chdir is not supported in {self.name} mode"}

    # ---- diagnostics --------------------------------------------------------
    def info(self) -> Dict[str, Any]:
        return {"mode": self.name}


_active: Optional[IoBackend] = None
_lock = threading.Lock()


def set_active_backend(backend: IoBackend) -> None:
    global _active
    with _lock:
        _active = backend
        backend.install_audit_hook()


def get_active_backend() -> Optional[IoBackend]:
    return _active


def require_active_backend() -> IoBackend:
    if _active is None:
        raise RuntimeError("No I/O backend active — refusing to proceed (fail-closed).")
    return _active
```

### A1. `src/nef_pipelines/tools/ai/sandbox.py` (new — concrete `SandboxBackend`)

`SandboxBackend` implements `IoBackend`. State (sandbox root, symlink policy, hook flag)
lives on the instance. `initialize_sandbox()` constructs it and registers it active.

```python
import atexit
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from nef_pipelines.lib.io_backend import IoBackend, set_active_backend

_invocation_lock = threading.Lock()  # serialises non-stdio invocations

_PATH_EVENTS_FIRST = {
    "open", "os.chdir", "os.listdir", "os.mkdir", "os.rmdir",
    "os.remove", "os.unlink", "os.truncate", "os.chmod", "os.chown", "os.scandir",
}
_PATH_EVENTS_TWO = {
    "os.rename": (0, 1), "os.replace": (0, 1),
    "os.symlink": (0, 1), "os.link": (0, 1),
    "shutil.copyfile": (0, 1), "shutil.copytree": (0, 1), "shutil.move": (0, 1),
}


class SandboxBackend(IoBackend):
    name = "sandbox"

    def __init__(self, root: Path, allow_symlinks: bool = False):
        self.root = root.resolve()
        self.allow_symlinks = allow_symlinks
        self._hook_installed = False

    # ---- IoBackend API ------------------------------------------------------

    def validate_args(self, args: List[str]) -> Optional[str]:
        for a in args:
            if not isinstance(a, str):
                continue
            p = Path(a)
            if p.is_absolute() or ".." in p.parts:
                if not self._is_inside(a):
                    return f"Path arg '{a}' is outside sandbox '{self.root}'"
        return None

    def enforce(self, name: Any) -> None:
        if name is None or isinstance(name, int):
            return
        if isinstance(name, bytes):
            name = name.decode("utf-8", errors="replace")
        if not self._is_inside(str(name)):
            raise PermissionError(
                f"Path '{name}' is outside the NEF MCP sandbox '{self.root}'"
            )

    def open(self, name: Any, mode: str = "r", *args, **kwargs):
        self.enforce(name)
        return open(name, mode, *args, **kwargs)

    def install_audit_hook(self) -> None:
        if self._hook_installed:
            return
        sys.addaudithook(self._audit_hook)
        self._hook_installed = True

    def pwd(self) -> Dict[str, Any]:
        return {
            "mode": "sandbox", "supports_pwd": True, "success": True,
            "cwd": os.getcwd(), "sandbox": str(self.root),
            "symlinks_allowed": self.allow_symlinks,
        }

    def chdir(self, path: str) -> Dict[str, Any]:
        if not self._is_inside(path):
            return {"mode": "sandbox", "cwd": os.getcwd(), "sandbox": str(self.root),
                    "success": False, "error": f"Path '{path}' is outside the sandbox"}
        target = Path(path) if Path(path).is_absolute() else Path(os.getcwd()) / path
        target = target if self.allow_symlinks else target.resolve()
        if not target.is_dir():
            return {"mode": "sandbox", "cwd": os.getcwd(), "sandbox": str(self.root),
                    "success": False,
                    "error": f"'{target}' does not exist or is not a directory"}
        os.chdir(target)
        return {"mode": "sandbox", "cwd": os.getcwd(),
                "sandbox": str(self.root), "success": True}

    def info(self) -> Dict[str, Any]:
        return {"mode": "sandbox", "root": str(self.root),
                "symlinks_allowed": self.allow_symlinks}

    # ---- internals ----------------------------------------------------------

    def _is_inside(self, path: str) -> bool:
        p = Path(path)
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        candidate = p if self.allow_symlinks else p.resolve()
        try:
            candidate.relative_to(self.root)
            return True
        except ValueError:
            return False

    def _audit_hook(self, event: str, args: tuple) -> None:
        if event in _PATH_EVENTS_FIRST and args:
            self.enforce(args[0])
        elif event in _PATH_EVENTS_TWO and args:
            ia, ib = _PATH_EVENTS_TWO[event]
            if ia < len(args):
                self.enforce(args[ia])
            if ib < len(args):
                self.enforce(args[ib])


def initialize_sandbox(
    sandbox_dir: Optional[Path] = None,
    allow_symlinks: bool = False,
) -> SandboxBackend:
    """Construct a SandboxBackend and register it as the active backend."""
    if sandbox_dir is not None:
        root = Path(sandbox_dir).resolve()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    else:
        tmp = tempfile.mkdtemp(prefix="nef_mcp_")
        root = Path(tmp).resolve()
        atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    tempfile.tempdir = str(root)
    os.chdir(root)
    backend = SandboxBackend(root, allow_symlinks=allow_symlinks)
    set_active_backend(backend)  # also installs the audit hook
    return backend
```

**Why audit hooks** (not `builtins.open` patching): patches don't cover `io.open`,
`pathlib.Path.open`, `os.open`, `tempfile.*`, etc. — those have their own bindings.
`sys.addaudithook` is fired from CPython's C-level entry points and catches every path,
including from C-implemented stdlib. It is the canonical chokepoint for this in CPython.

**Why both reads and writes**: per decision #1 above. The AI's only FS surface is NEF
commands; restricting reads makes information-disclosure attempts via NEF commands fail too.

### A2. `nef_pwd()` and `nef_chdir(path)` MCP tools — delegate to active backend

Living in `tools/ai/sandbox.py` (or in a small `tools/ai/nav.py` if you prefer). Each
tool calls the active backend's `pwd`/`chdir`. In keystore mode the backend's defaults
(`success=False, supports_pwd=False`) are returned automatically — no per-tool branching.

```python
from nef_pipelines.lib.io_backend import require_active_backend

def nef_pwd() -> Dict[str, Any]:
    """
    Show where the server reads and writes data.
    Returns backend-specific shape; sandbox mode includes cwd/sandbox/symlinks_allowed.
    """
    return require_active_backend().pwd()


def nef_chdir(path: str) -> Dict[str, Any]:
    """
    Navigate within the sandbox. Cannot escape it.
    In keystore (offline) mode this is unsupported — backend returns success=False.
    """
    return require_active_backend().chdir(path)
```

### B. `src/nef_pipelines/lib/io.py` (new — public helpers, Layer 4)

Thin delegators to `get_active_backend()`. New NEF commands import these instead of
`builtins.open` etc. so the same code works under any backend.

```python
from pathlib import Path
from nef_pipelines.lib.io_backend import require_active_backend

def safe_open(name, mode='r', *args, **kwargs):
    """Backend-aware open. In sandbox mode `name` is a filesystem path;
    in offline/keystore mode it will be a keystore key."""
    return require_active_backend().open(name, mode, *args, **kwargs)

def safe_read_text(name, encoding='utf-8') -> str:
    with safe_open(name, 'r', encoding=encoding) as f:
        return f.read()

def safe_write_text(name, data: str, encoding='utf-8') -> int:
    with safe_open(name, 'w', encoding=encoding) as f:
        return f.write(data)

def enforce_path(name) -> None:
    """Raise PermissionError if `name` is not permitted by the active backend."""
    require_active_backend().enforce(name)
```

Document in the module docstring: **new NEF commands should use these helpers** rather
than `open()` / `Path.read_text()`. Existing code remains covered by the audit hook;
migration is a follow-up effort.

### C. `mcp_commands_lib.py` — guards around `execute_command_in_process`

```python
import os
from contextlib import contextmanager
from nef_pipelines.tools.ai.sandbox import (
    _SANDBOX, _check_sandbox_paths_for_args, _invocation_lock,
)


def _check_sandbox_paths_for_args(args):
    """Layer 1: fast fail when an explicit arg looks like a path that escapes."""
    if _SANDBOX is None:
        return "sandbox not initialised — refusing to execute"
    for a in args:
        if not isinstance(a, str):
            continue
        p = Path(a)
        if p.is_absolute() or '..' in p.parts:
            if not _is_inside_sandbox(a):
                return f"Path arg '{a}' is outside sandbox '{_SANDBOX}'"
    return None


@contextmanager
def _preserve_cwd():
    saved = os.getcwd()
    try:
        yield
    finally:
        # Force CWD back inside sandbox even if a command escaped via os.chdir()
        try:
            os.chdir(saved)
        except OSError:
            os.chdir(_SANDBOX)


def execute_command_in_process(args, nef_input=""):
    error = _check_sandbox_paths_for_args(list(args))
    if error:
        return {"stdout": "", "stderr": error, "exit_code": 1, "success": False}

    with _invocation_lock, _preserve_cwd():
        runner = CliRunner()
        result = runner.invoke(_nef_app.app, list(args),
                               input=nef_input if nef_input else None)

    # ... existing stderr / stdout handling unchanged ...
```

The lock makes layered patching safe under HTTP/SSE transports without serialising stdio
(stdio is single-flight already, the lock is uncontended there).

### D. `server.py` — CLI options

```python
sandbox: Optional[Path] = typer.Option(
    None, "--sandbox",
    help="directory for file I/O; a private temp dir is used if not specified",
    metavar="<DIR>",
),
symlinks: bool = typer.Option(
    False, "--symlinks/--no-symlinks",
    help="follow symlinks within the sandbox (default: deny)",
),
```

In the function body, before `_build().run(**kwargs)`:

```python
from nef_pipelines.tools.ai.sandbox import initialize_sandbox
initialize_sandbox(sandbox, allow_symlinks=symlinks)

if transport != "stdio":
    typer.echo(
        "WARNING: --transport != stdio with sandbox enabled is multi-client risky. "
        "CWD and the audit hook are process-global. Tool invocations are serialised.",
        err=True,
    )
```

### E. `mcp_lib.py` — register tools

Import `nef_pwd`, `nef_chdir` from `tools.ai.sandbox`. Register order:

```python
mcp_server.tool()(nef_read_me_first)
mcp_server.tool()(nef_read_resource)
mcp_server.tool()(nef_pwd)
mcp_server.tool()(nef_chdir)
mcp_server.tool()(nef_list_commands)
mcp_server.tool()(nef_get_command_help)
mcp_server.tool()(nef_execute_command)
mcp_server.tool()(nef_execute_pipeline)
```

### F. Preamble — updated Tools section

```
0. `nef_read_me_first()`        — orientation (call first; skip if seen this session)
1. `nef_read_resource(name)`    — fetch any resource document by name
2. `nef_pwd()`                  — show working dir, sandbox root, symlink policy
3. `nef_chdir(path)`            — navigate within the sandbox (cannot escape it)
4. `nef_list_commands()`        — enumerate available commands
5. `nef_get_command_help(...)`  — full --help for one command
6. `nef_execute_command(...)`   — single step (prototyping)
7. `nef_execute_pipeline(...)`  — production multi-step pipeline
```

Add a one-paragraph "Sandbox" section: AI reads/writes confined; call `nef_pwd` first
to know where files land.

### G. Tests

New fixture in `test_nef_mcp_server.py` (`mcp_sandbox`) creates a tmp dir, calls
`initialize_sandbox(tmp, allow_symlinks=False)`, saves+restores `_SANDBOX`, `_ALLOW_SYMLINKS`,
and `os.getcwd()` on teardown. Audit hook installation is one-shot per process — accept it.

Tests:

| Layer | Test | Expectation |
|---|---|---|
| init | `test_initialize_sandbox_default_creates_temp_dir` | `_SANDBOX` set, dir exists, mode 0700 |
| init | `test_initialize_sandbox_explicit` | `_SANDBOX` matches resolved arg |
| init | `test_fail_closed_no_sandbox` | `nef_execute_command` returns failure when `_SANDBOX is None` |
| arg | `test_layer1_blocks_absolute_arg` | `["save","/etc/foo"]` → exit_code != 0, error mentions sandbox |
| arg | `test_layer1_blocks_dotdot_arg` | `["save","../../etc/foo"]` → blocked |
| arg | `test_layer1_allows_relative` | `["save","out.nef"]` passes layer 1 |
| audit | `test_layer5_blocks_open_outside_via_path` | `pathlib.Path("/etc/foo").write_text("x")` raises `PermissionError` while sandbox active |
| audit | `test_layer5_blocks_io_open_outside` | `io.open("/etc/foo","w")` raises |
| audit | `test_layer5_blocks_os_rename_outside` | `os.rename("in.nef","/tmp/leak")` raises |
| audit | `test_layer5_blocks_os_chdir_outside` | `os.chdir("/tmp")` raises |
| audit | `test_layer5_allows_inside_sandbox` | writing/reading within sandbox succeeds |
| symlink | `test_symlink_outside_blocked_default` | symlink in sandbox → /etc; resolve+check denies |
| symlink | `test_symlink_outside_allowed_with_flag` | with `_ALLOW_SYMLINKS=True`, same op succeeds |
| chdir | `test_nef_chdir_valid` | chdir to subdir; `nef_pwd()["cwd"]` updates |
| chdir | `test_nef_chdir_blocks_escape` | `/tmp` → `success=False`, cwd unchanged |
| chdir | `test_nef_chdir_nonexistent` | missing dir → `success=False` |
| chdir | `test_nef_chdir_via_symlink_blocked` | symlink-to-/etc → blocked |
| pwd | `test_nef_pwd_structure` | dict has cwd, sandbox, symlinks_allowed, success |
| cwd | `test_cwd_restored_after_command_chdir` | command that calls `os.chdir(/tmp)` (caught by audit) cannot persist; CWD restored after invoke |
| helper | `test_safe_open_inside` | works |
| helper | `test_safe_open_outside_raises` | `PermissionError` |
| integ | `EXPECTED_TOOL_NAMES` | adds `nef_pwd`, `nef_chdir` |

---

## Edge cases addressed

| Concern from review | Handled by |
|---|---|
| `builtins.open` patch misses `io.open` / `pathlib.Path.open` | Audit hook |
| `r+` / `rb+` opens not blocked | Audit hook fires regardless of mode (we check on every open) |
| `os.open`, `os.rename`, `os.symlink`, `os.link` bypass | Audit hook |
| `tempfile` writes outside sandbox | `tempfile.tempdir = str(_SANDBOX)` at init |
| Symlink in sandbox → outside | Default `Path.resolve()` before check; `--symlinks` opts out |
| `_SANDBOX is None` fail-open | Layer-1 check returns error, refusing execution |
| `os.chdir` escape persisting after a command | `_preserve_cwd()` context manager + audit hook |
| HTTP/SSE multi-client races | `_invocation_lock` serialises invocations + warning |
| `nef_chdir` to symlink pointing out | Uses `_is_inside_sandbox` which resolves first |
| `mode` strings with `+` / non-string `file` arg | Audit hook checks paths regardless of mode/type |
| ctypes / subprocess / arbitrary Python by AI | **Out of scope** (AI cannot write Python; documented) |

---

## Out of scope / explicit non-goals

- Adversarial security (use chroot / container — documented in `skill.md`)
- Refactoring all existing NEF I/O calls to use `safe_open` (follow-up; audit hook covers
  the gap)
- `subprocess`-spawned children inheriting sandbox (Python audit hooks don't propagate;
  out of scope per threat model)
- ctypes / native-extension bypass (out of scope per threat model)

---

## Verification

```bash
# Full test suite
.venv311/bin/python -m pytest src/nef_pipelines/tests/ai/ -q

# Boot with default temp sandbox
.venv311/bin/nef ai server </dev/null

# Boot with explicit sandbox
mkdir -p /tmp/nef_test_sandbox
.venv311/bin/nef ai server --sandbox /tmp/nef_test_sandbox </dev/null

# Boot with symlink follow enabled
.venv311/bin/nef ai server --sandbox /tmp/nef_test_sandbox --symlinks </dev/null

# Manual layer-5 verification (with sandbox active in-process)
.venv311/bin/python -c "
from nef_pipelines.tools.ai.sandbox import initialize_sandbox
initialize_sandbox()
import io
try:
    io.open('/etc/passwd', 'r').read()
except PermissionError as e:
    print('blocked:', e)
"
```
