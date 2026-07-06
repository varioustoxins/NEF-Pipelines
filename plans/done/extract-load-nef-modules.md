# Plan: Extract `load_nef_modules()` to eliminate mcp_lib duplication

## Context

`mcp_lib.create_nef_pipelines_app()` was introduced to initialise the NEF app and load plugins
for the server path. It duplicates (and degrades) the equivalent logic in `main.main()`:

| Feature | `main.main()` | `mcp_lib.create_nef_pipelines_app()` |
|---|---|---|
| removes `ai` command in server mode (security — AI must not access sandbox controls) | ✅ via `main_callback(--server)` | ❌ |
| `format_exc()` traceback on failure | ✅ | ❌ |
| `_if_commands_are_bad_report_and_exit_error()` | ✅ | ❌ |
| reports failures | via `_report_warnings()` (stderr **plus one stdout line**¹) | via bare `warn()` |

¹ `_report_warnings()` line 276 has `print(header)` with no `file=sys.stderr` — a pre-existing
stdout-pollution bug. The server path must NOT call it (would break stdio MCP transport).

The `ai` command removal is the most critical gap. When the MCP server runs, the AI must not
have access to the `ai` subcommand — it contains sandbox-management controls (`nef ai sandbox`,
`nef ai server`) that would allow the AI to change or escape the sandbox.

## Security fix approach

**Option A (build then remove)**: load modules, then strip `ai` from `nef_app.app.registered_groups`. Touches typer internals.

**Option B (conditional load — chosen)**: guard `ai/__init__.py` so it skips registration when
`main.in_server_mode` is `True`. The `ai` group never enters the command tree at all.

**Policy ownership**: `in_server_mode = True` is set by `server.py` BEFORE calling
`create_nef_pipelines_app()` — NOT inside `create_nef_pipelines_app()` itself. This is critical
because `create_nef_pipelines_app()` is also called by the test `conftest.py`, which must load
the `ai` group normally (tests in `test_sandbox_cli.py` import `ai_app` directly).

**Belt-and-braces**: after `create_nef_pipelines_app()` returns, `server.py` checks that `ai`
is NOT registered. If it is (e.g., because `ai/__init__.py` was already imported before
`in_server_mode` was set), the server refuses to start.

## Note on `app_lib` / `main_lib` refactoring

Splitting `create_nef_app()` and `load_nef_modules()` into a separate library is the right
long-term architecture. However, `create_nef_app()` depends on `main_callback` (via a local
import to break circular references), and `main.py` has significant module-level side effects
(lines 31-54: `typer_debug_mode`, logging, version check, `patch_rich_code_theme()`). Extracting
cleanly would require moving `main_callback` too — a larger refactor. Deferred to a separate
task; `load_nef_modules()` stays in `main.py` for now.

## Changes

### 1. Add `load_nef_modules()` to `main.py`

**File:** `src/nef_pipelines/main.py`

Add after `create_nef_app()`, before `main()`:

```python
def load_nef_modules() -> list[tuple[str, str]]:
    """Load all registered plugin modules.

    Caller must ensure create_nef_app() was called first.
    Returns list of (module_name, warning_msg) for each module that failed to load.
    """
    warnings = []
    for module_name in get_registerd_modules():
        try:
            import_module(module_name)
        except Exception:
            msg = f"plugin {module_name}\n{format_exc()}"
            warnings.append((module_name, msg))

    _if_commands_are_bad_report_and_exit_error(nef_app)
    return warnings
```

Update `main()` — replace the `warnings = []` block with:

```python
try:
    warnings = load_nef_modules()
except Exception as e:
    msg = """\
         Initialisation error: failed to load a plugin, remove the plugin or contact the developer
         """
    do_exit_error(msg, e)
```

### 2. Guard `ai/__init__.py` against server-mode loading

**File:** `src/nef_pipelines/tools/ai/__init__.py`

```python
# After:
import nef_pipelines.main as _main
from nef_pipelines.lib.util import ToolCategory
from nef_pipelines.main import nef_app
from typer import Typer

if not _main.in_server_mode:
    ai_app = Typer()
    nef_app.app.add_typer(ai_app, name="ai", help="- AI tools for NEF pipelines",
                           rich_help_panel=ToolCategory.GENERAL)
    from nef_pipelines.tools.ai import sandbox  # noqa
    from nef_pipelines.tools.ai import server   # noqa
```

`_main.in_server_mode` is read at import time (module-level code runs once). `server.py`
sets it to `True` before `create_nef_pipelines_app()` triggers the import.

**Note on test impact**: `test_sandbox_cli.py` does `from nef_pipelines.tools.ai import ai_app`.
This import must happen when `in_server_mode=False` (test context). Since `server.py` owns the
policy — not `create_nef_pipelines_app()` — the test conftest never sets `in_server_mode=True`,
so `ai_app` is always created during test runs. ✅

### 3. Rewrite `create_nef_pipelines_app()` in `mcp_lib.py`

**File:** `src/nef_pipelines/tools/ai/mcp_lib.py`

```python
def create_nef_pipelines_app():
    from nef_pipelines.main import load_nef_modules
    create_nef_app()                     # idempotent; populates nef_pipelines.nef_app singleton
    module_warnings = load_nef_modules()
    for module_name, msg in module_warnings:
        warn(f"module {module_name} failed to load:\n{msg}")
```

Note: does NOT set `in_server_mode`. That is the caller's responsibility.

### 4. Update `server.py` to set server mode and add belt-and-braces check

**File:** `src/nef_pipelines/tools/ai/server.py`

Before the existing `install_audit_hook()` + `create_nef_pipelines_app()` calls:

```python
import nef_pipelines.main as _main
_main.in_server_mode = True      # must be set before create_nef_pipelines_app()

install_audit_hook()
create_nef_pipelines_app()

# Belt-and-braces: ai group must not be registered in server mode
import nef_pipelines
ai_registered = any(
    g.name == "ai" for g in nef_pipelines.nef_app.app.registered_groups
)
if ai_registered:
    exit_error(
        "Security error: the 'ai' command is registered in server mode. "
        "The 'ai' module was imported before in_server_mode was set. "
        "The server cannot start safely."
    )
```

### 5. Eliminate `_nef_app` global in `mcp_lib.py`

`_nef_app` is only used in `_execute_command_in_process` as `_nef_app.app`.
`create_nef_app()` populates the `nef_pipelines.nef_app` singleton, so the local global
is redundant.

**File:** `src/nef_pipelines/tools/ai/mcp_lib.py`

1. Remove: `_nef_app = None` (module-level global)
2. Remove `global _nef_app` from `create_nef_pipelines_app()`
3. Add `import nef_pipelines` at the top of the file (if not already there)
4. In `_execute_command_in_process`, replace both `_nef_app.app` uses with
   `nef_pipelines.nef_app.app`
5. Remove imports that become unused after this change:
   - `from importlib import import_module`
   - `from nef_pipelines.module_registry import get_registerd_modules`

## Affected files

| File | Change |
|---|---|
| `src/nef_pipelines/main.py` | add `load_nef_modules()`, simplify `main()` |
| `src/nef_pipelines/tools/ai/__init__.py` | guard registration with `if not _main.in_server_mode` |
| `src/nef_pipelines/tools/ai/mcp_lib.py` | rewrite `create_nef_pipelines_app()`, remove `_nef_app` global, update invocations, clean unused imports |
| `src/nef_pipelines/tools/ai/server.py` | set `in_server_mode=True` before startup, add belt-and-braces check |

## Pre-existing bug (not fixed here)

`_report_warnings()` line 276: `print(header)` writes to stdout (missing `file=sys.stderr`).
Not fixed here — the server path avoids it by using `warn()` directly.

## Future work

- Extract `create_nef_app()`, `load_nef_modules()`, and `main_callback` into `nef_app_lib.py`
  so `mcp_lib.py` does not need to import from `main.py` and trigger its module-level side effects.
- The module registry could also expose sub-command names for early CLI pre-parsing (detect
  `--server` before the first sub-command token in `sys.argv`) to eliminate the explicit
  `in_server_mode = True` call in `server.py`.

## Verification

```bash
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines
python -m pytest src/nef_pipelines/tests/ai/ -x -q
```
