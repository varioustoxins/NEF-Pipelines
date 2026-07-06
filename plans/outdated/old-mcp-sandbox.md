# Plan: MCP server sandbox for file I/O

## Context

The NEF MCP server runs pipeline commands in-process via Typer's `CliRunner`. Without a
sandbox, the server has full user-level filesystem access. Three attack vectors exist:

1. **Explicit path args** — AI passes an absolute path like `/etc/passwd` as a command arg
2. **Side-effect writes** — a command writes files internally without any explicit path arg
3. **Template args** — options like `--output-prefix` compute paths internally; arg scanning
   can't see the final resolved path

Arg scanning alone only closes vector 1. Vectors 2 and 3 require intercepting file writes
at a lower level.

## Design

Two defence layers:

| Layer | What it catches | When it runs |
|---|---|---|
| Arg validation (`_check_sandbox_paths`) | Explicit absolute paths and `..` traversal in args | Before `runner.invoke` |
| `open()` interception (`_sandboxed_open`) | **All** file writes (side effects, templates, anything) | Wraps `runner.invoke` |

`builtins.open` is the single choke-point: `open()`, `pathlib.Path.open()`, and
`Path.write_text()` / `.write_bytes()` all go through it in CPython. Patching it in
write mode (`'w'`, `'a'`, `'x'`) for the duration of each runner invocation closes all
three vectors without touching command implementations.

**Sandbox invariant:** `os.getcwd()` is always inside `_SANDBOX`. Relative path writes
naturally land inside the sandbox; the `open()` interception only needs to block absolute
paths and `..` escapes.

---

## Files to change

| File | Change |
|---|---|
| `src/nef_pipelines/tools/ai/mcp_commands_lib.py` | New imports; `_SANDBOX` state; `initialize_sandbox()`; `_check_sandbox_paths()`; `_sandboxed_open()` context manager; guard `execute_command_in_process`; add `nef_pwd()`, `nef_chdir()` |
| `src/nef_pipelines/tools/ai/server.py` | `--sandbox PATH` CLI option; call `initialize_sandbox()` before server starts |
| `src/nef_pipelines/tools/ai/mcp_lib.py` | Import and register `nef_pwd`, `nef_chdir` (after `nef_read_resource`, before list/help/execute) |
| `src/nef_pipelines/resources/mcp_server/preamble.md` | Add `nef_pwd` and `nef_chdir` to the Tools section (renumber) |
| `src/nef_pipelines/tests/ai/test_nef_mcp_server.py` | New sandbox / pwd / chdir tests |
| `src/nef_pipelines/tests/ai/test_nef_mcp_server_integration.py` | Add `nef_pwd`, `nef_chdir` to `EXPECTED_TOOL_NAMES` |

---

## Implementation

### A. `mcp_commands_lib.py`

**New imports:**
```python
import atexit
import builtins
import os
import shutil
import tempfile
from contextlib import contextmanager
from typing import Optional   # add to existing typing import
```

**Module-level state** (after existing module-level code):
```python
_SANDBOX: Optional[Path] = None
```

**`initialize_sandbox(sandbox_dir)`** — called once at server startup:
```python
def initialize_sandbox(sandbox_dir: Optional[Path] = None) -> Path:
    global _SANDBOX
    if sandbox_dir is not None:
        _SANDBOX = Path(sandbox_dir).resolve()
        _SANDBOX.mkdir(parents=True, exist_ok=True)
    else:
        tmp = tempfile.mkdtemp(prefix="nef_mcp_")
        _SANDBOX = Path(tmp).resolve()
        atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    os.chdir(_SANDBOX)
    return _SANDBOX
```

**`_check_sandbox_paths(args)`** — fast-fail before invoke (returns error string or `None`):
```python
def _check_sandbox_paths(args: List[str]) -> Optional[str]:
    if _SANDBOX is None:
        return None
    for arg in args:
        p = Path(arg)
        if p.is_absolute():
            resolved = p.resolve()
        elif '..' in p.parts:
            resolved = Path(os.getcwd(), p).resolve()
        else:
            continue          # simple relative — stays inside CWD ⊆ sandbox
        try:
            resolved.relative_to(_SANDBOX)
        except ValueError:
            return f"Path '{arg}' is outside the sandbox '{_SANDBOX}'"
    return None
```

**`_sandboxed_open()`** — context manager that intercepts all file writes:
```python
@contextmanager
def _sandboxed_open():
    """Patch builtins.open to block write-mode opens outside the sandbox."""
    if _SANDBOX is None:
        yield
        return

    _original_open = builtins.open

    def _validated_open(file, mode='r', *args, **kwargs):
        if isinstance(file, (str, Path)) and any(c in mode for c in ('w', 'a', 'x')):
            error = _check_sandbox_paths([str(file)])
            if error:
                raise PermissionError(error)
        return _original_open(file, mode, *args, **kwargs)

    builtins.open = _validated_open
    try:
        yield
    finally:
        builtins.open = _original_open
```

**`execute_command_in_process` — updated body:**
```python
def execute_command_in_process(args, nef_input=""):
    # Layer 1: fast-fail on explicit path args
    error = _check_sandbox_paths(list(args))
    if error:
        return {"stdout": "", "stderr": error, "exit_code": 1, "success": False}

    runner = CliRunner()
    # Layer 2: intercept all file writes during invocation
    with _sandboxed_open():
        result = runner.invoke(_nef_app.app, list(args),
                               input=nef_input if nef_input else None)

    stderr = ""
    if hasattr(result, 'stderr') and result.stderr:
        stderr = result.stderr
    stdout = result.output or ""
    if stderr:
        stdout = (stdout + stderr) if stdout else stderr
    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": result.exit_code,
        "success": result.exit_code == 0,
    }
```

Note: a `PermissionError` raised inside `_validated_open` propagates through the CliRunner
as an exception; `result.exit_code` will be non-zero and `result.exception` will be set.
The existing error handling in the calling layer treats any non-zero exit as failure.

**`nef_pwd()`**:
```python
def nef_pwd() -> Dict[str, Any]:
    """
    Return the server's current working directory and sandbox root.
    Call before writing files to know where relative paths will land.
    Returns {"cwd": str, "sandbox": str, "success": True}.
    """
    return {
        "cwd": os.getcwd(),
        "sandbox": str(_SANDBOX) if _SANDBOX else os.getcwd(),
        "success": True,
    }
```

**`nef_chdir(path)`** — enforces sandbox boundary:
```python
def nef_chdir(path: str) -> Dict[str, Any]:
    """
    Change the server's working directory to a path within the sandbox.
    Refuses to navigate outside the sandbox; absolute paths and '..' that escape are rejected.
    path - relative or absolute path; must resolve inside the sandbox.
    Returns {"cwd": str, "sandbox": str, "success": bool}.
    """
    error = _check_sandbox_paths([path])
    if error:
        return {"cwd": os.getcwd(), "sandbox": str(_SANDBOX),
                "success": False, "error": error}
    p = Path(path)
    target = (Path(os.getcwd()) / p).resolve() if not p.is_absolute() else p.resolve()
    if not target.is_dir():
        return {"cwd": os.getcwd(), "sandbox": str(_SANDBOX), "success": False,
                "error": f"'{target}' does not exist or is not a directory"}
    os.chdir(target)
    return {"cwd": os.getcwd(), "sandbox": str(_SANDBOX), "success": True}
```

### B. `server.py`

Add `from pathlib import Path` and `from typing import Optional`.

Add option to `server()`:
```python
sandbox: Optional[Path] = typer.Option(
    None, "--sandbox",
    help="directory for file I/O; a private temp dir is used if not specified",
    metavar="<DIR>",
),
```

Before `_build().run(**kwargs)`:
```python
from nef_pipelines.tools.ai.mcp_commands_lib import initialize_sandbox
initialize_sandbox(sandbox)
```

### C. `mcp_lib.py`

Add `nef_chdir`, `nef_pwd` to the import from `mcp_commands_lib`. Register after
`nef_read_resource` and before `nef_list_commands`:

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

### D. `preamble.md` — updated Tools section

```
0. `nef_read_me_first()`        — orientation (call first; skip if seen this session)
1. `nef_read_resource(name)`    — fetch any resource document by name
2. `nef_pwd()`                  — show current working directory and sandbox root
3. `nef_chdir(path)`            — navigate within the sandbox (cannot escape it)
4. `nef_list_commands()`        — enumerate available commands
5. `nef_get_command_help(...)`  — full `--help` for one command
6. `nef_execute_command(...)`   — single step (prototyping)
7. `nef_execute_pipeline(...)`  — production multi-step pipeline
```

### E. Tests (`test_nef_mcp_server.py`)

New fixture: creates a temp sandbox dir, calls `initialize_sandbox()`, saves+restores
`_SANDBOX` and `os.getcwd()` on teardown.

New tests:
- `test_nef_pwd_returns_structure` — dict has `cwd`, `sandbox`, `success=True`; cwd inside sandbox
- `test_nef_chdir_valid` — chdir to a new subdir; pwd `cwd` changes; still inside sandbox
- `test_nef_chdir_blocks_dotdot` — `../../etc` → `success=False`
- `test_nef_chdir_blocks_absolute_outside` — `/tmp` → `success=False`
- `test_nef_chdir_nonexistent` — missing subdir → `success=False`
- `test_sandbox_layer1_blocks_absolute_arg` — explicit `/etc/passwd` arg → `exit_code=1`
- `test_sandbox_layer2_blocks_sideeffect_write` — mock a command that opens an absolute
  path outside sandbox for writing; verify `PermissionError` is raised / exit non-zero
- `test_sandbox_allows_relative_write` — relative path write inside sandbox succeeds

In `test_nef_mcp_server_integration.py`, add `"nef_pwd"` and `"nef_chdir"` to
`EXPECTED_TOOL_NAMES`.

---

## Key edge cases

- `_SANDBOX is None` (lib used directly in unit tests without `nef ai server`): both
  `_check_sandbox_paths` and `_sandboxed_open` no-op. Existing tests pass unchanged.
- `PermissionError` from `_validated_open`: propagates through CliRunner; treated as failure.
- Read-mode opens (`'r'`, `'rb'`) are **not** blocked — commands can read files from anywhere
  (e.g. input NEF files specified by the user). Only write-mode is constrained.
- Template args that compute a path relative to CWD: safe because CWD ⊆ sandbox.
- `builtins.open` patch is re-entrant safe (saves/restores original per invocation).
- Concurrent requests: stdio MCP transport is single-threaded; `builtins.open` patch and
  `os.chdir` are safe.

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
```
