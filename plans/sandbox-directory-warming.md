# Sandbox Directory Warming - Implementation Plan

## Executive Summary

**Goal:** Allow NEF-Pipelines commands to declare their directory requirements so library caches (matplotlib, JAX, etc.) don't trigger false-positive sandbox violations.

**Approach:** Per-command `@setup_sandbox` decorator + global `/tmp` exemption for tool caches

**Threat Model:** Protect USER data files (NEF, plots, results) from accidental AI damage. Tool cache files in `/tmp` are expendable.

---

## Part 1: Agreed Implementation

### Design Decisions (Final)

1. **Decorator name:** `@setup_sandbox` (clearer than `@setup_directories`)
2. **Execution model:** Setup runs at MCP layer (`nef_execute_pipeline`) BEFORE audit context, decorator is metadata only
3. **Cache location:** `/tmp/nef_pipelines_mcp_tmp/{instance_id}/` (configurable via `NEF_SANDBOX_TMP` env var)
4. **Global exemption:** Allow writes to `/tmp/nef_pipelines_mcp_tmp/*` for all commands (tool caches only)
5. **Critical separation:** Library caches → `/tmp` (exempt), User outputs → sandbox (protected)
6. **__pycache__ handling:** Validate against actual site-packages paths (not simple substring)
7. **Setup errors:** Distinct `SandboxSetupError` exception (not generic RuntimeError)
8. **Dynamic check:** Keep as discouraged escape hatch with safeguards
9. **Concurrency:** Deferred (verify thread model first via logging)

### Three-Tier Priority for Directory Handling

Commands should handle directories in this priority order:

1. **Redirect to /tmp** (preferred): Set env vars to force library caches into `/tmp/nef_pipelines_mcp_tmp/{instance}/`
   ```python
   os.environ['MPLCONFIGDIR'] = f'/tmp/nef_pipelines_mcp_tmp/{instance_id}/.matplotlib'
   os.environ['JAX_COMPILATION_CACHE_DIR'] = f'/tmp/nef_pipelines_mcp_tmp/{instance_id}/jax_cache'
   ```
   - Log on first use
   - Return paths created

2. **Dynamic discovery** (fallback): Call library APIs to discover/create directories
   ```python
   import matplotlib
   return [matplotlib.get_configdir(), matplotlib.get_cachedir()]
   ```

3. **Static paths** (last resort): Fixed paths when above not possible
   ```python
   return ["~/.cache/myapp"]
   ```

### Architecture

```
User request
    ↓
nef_execute_pipeline (MCP layer)
    ↓
1. Read command's @setup_sandbox metadata
2. Run setup callables → get allowed directories
3. Set env vars for /tmp redirection
4. Register allowed paths with audit hook
5. Install audit context
    ↓
6. Execute command (audit hook active)
    ↓
7. Command outputs go to sandbox (protected)
   Library caches go to /tmp (exempt)
```

**Key principle:** Decorator attaches metadata, MCP layer executes setup BEFORE audit context.

---

### Implementation Phase 1: Infrastructure

#### 1.1 Site-Packages Validation

Create helper to get valid site-packages paths:

```python
# In src/nef_pipelines/tools/ai/sandbox_lib.py
import sysconfig
import site
from pathlib import Path

def get_valid_site_packages() -> set[Path]:
    """Get absolute paths to valid site-packages directories.

    Used to validate that __pycache__ writes are legitimate library bytecode,
    not arbitrary paths chosen to bypass sandbox.

    Returns:
        Set of resolved site-packages paths that exist.
    """
    routes = set()

    # Global/virtualenv site-packages
    try:
        routes.update(Path(p).resolve() for p in site.getsitepackages())
    except AttributeError:
        pass

    # User local site-packages
    try:
        routes.add(Path(site.getusersitepackages()).resolve())
    except AttributeError:
        pass

    # Robust fallback via sysconfig
    try:
        routes.add(Path(sysconfig.get_paths()["purelib"]).resolve())
    except KeyError:
        pass

    return {p for p in routes if p.exists()}

# Cache at module load (before audit hook)
VALID_SITE_PACKAGES = get_valid_site_packages()
```

#### 1.2 Bootstrap Warmup

System-level directories needed before any command:

```python
# In src/nef_pipelines/tools/ai/sandbox_bootstrap.py
"""System-level directory requirements - run once at server startup."""
import tempfile
import os

def get_tmp_base_dir() -> str:
    """Get base directory for tool caches.

    Defaults to /tmp/nef_pipelines_mcp_tmp, overridable via NEF_SANDBOX_TMP env var.
    """
    return os.environ.get('NEF_SANDBOX_TMP', '/tmp/nef_pipelines_mcp_tmp')

def warm_bootstrap_directories(instance_id: str):
    """Warm system-critical directories before installing audit hook.

    Args:
        instance_id: Unique identifier for this MCP session (for /tmp isolation)
    """
    # Warm tempfile cache (prevents /var/tmp probe during execution)
    tempfile.gettempdir()

    # Create instance-specific tmp directory
    from pathlib import Path
    tmp_base = Path(get_tmp_base_dir()) / instance_id
    tmp_base.mkdir(parents=True, exist_ok=True)

    return tmp_base
```

#### 1.3 Setup Sandbox Decorator

Decorator for command-level declarations (metadata only):

```python
# In src/nef_pipelines/tools/ai/sandbox_lib.py
from typing import Callable, Union

def setup_sandbox(
    setup_callables: list[Callable] | None = None,
    static_paths: list[str] | None = None,
    glob_patterns: list[str] | None = None,
    dynamic_check: Callable[[Path], bool] | None = None
):
    """Declare sandbox directory requirements for a command (metadata only).

    This decorator attaches metadata to the command function. Actual setup execution
    happens at the MCP layer (nef_execute_pipeline) BEFORE the audit context is installed.

    Args:
        setup_callables: List of setup functions that configure env vars, discover
            directories, and return list of paths to allow. Called with tmp_base_dir.
            Priority 1: Redirect to /tmp, Priority 2: Dynamic discovery
        static_paths: List of static directory paths (Priority 3: last resort)
        glob_patterns: List of glob patterns for audit exemptions (e.g., "**/site-packages/**/__pycache__")
        dynamic_check: Callable for runtime path validation (DISCOURAGED - last resort only).
            Must be fast (no I/O), safe (no exceptions), and documented (why alternatives don't work).

    Example:
        @plot_app.command()
        @setup_sandbox(
            setup_callables=[setup_matplotlib],  # Redirects to /tmp, returns paths
            static_paths=["~/.cache/nef_plots"]  # Fallback if needed
        )
        def correlations(...):
            ...

    Returns:
        Decorator that attaches _sandbox_setup metadata to function.
    """
    setup_callables = setup_callables or []
    static_paths = static_paths or []
    glob_patterns = glob_patterns or []

    def decorator(fn):
        # NO wrapper - just attach metadata
        fn._sandbox_setup = {
            'callables': setup_callables,
            'static': static_paths,
            'globs': glob_patterns,
            'dynamic_check': dynamic_check,
        }
        return fn  # Return original function unchanged

    return decorator
```

#### 1.4 Library Setup Functions

Callables that configure libraries to use `/tmp`:

```python
# In src/nef_pipelines/tools/ai/sandbox_lib.py
import os
from pathlib import Path

def setup_matplotlib(tmp_base_dir: Path) -> list[Path]:
    """Configure matplotlib to use sandbox tmp directory.

    CRITICAL: This path is for LIBRARY CACHES ONLY (exempt from protection).
    All user-visible outputs (plots) MUST go to sandbox, never to MPLCONFIGDIR.

    Args:
        tmp_base_dir: Base /tmp directory for this instance

    Returns:
        List of paths matplotlib will use (for audit exemption)
    """
    mpl_dir = tmp_base_dir / '.matplotlib'
    mpl_dir.mkdir(parents=True, exist_ok=True)

    # Redirect matplotlib config/cache BEFORE importing
    os.environ['MPLCONFIGDIR'] = str(mpl_dir)

    # Log on first use
    import logging
    logging.info(f"Matplotlib cache redirected to: {mpl_dir}")

    return [mpl_dir]

def setup_jax(tmp_base_dir: Path) -> list[Path]:
    """Configure JAX/XLA/CUDA caches to use sandbox tmp directory.

    Args:
        tmp_base_dir: Base /tmp directory for this instance

    Returns:
        List of cache directories created
    """
    jax_cache = tmp_base_dir / 'jax_cache'
    cuda_cache = tmp_base_dir / 'cuda_cache'
    triton_cache = tmp_base_dir / 'triton_cache'

    # Set env vars BEFORE importing jax
    os.environ['JAX_COMPILATION_CACHE_DIR'] = str(jax_cache)
    os.environ['CUDA_CACHE_PATH'] = str(cuda_cache)
    os.environ['TRITON_CACHE_DIR'] = str(triton_cache)

    # Create directories
    for cache_dir in [jax_cache, cuda_cache, triton_cache]:
        cache_dir.mkdir(parents=True, exist_ok=True)

    import logging
    logging.info(f"JAX/accelerator caches redirected to: {tmp_base_dir}")

    return [jax_cache, cuda_cache, triton_cache]

def setup_numba(tmp_base_dir: Path) -> list[Path]:
    """Configure Numba cache to use sandbox tmp directory.

    Args:
        tmp_base_dir: Base /tmp directory for this instance

    Returns:
        List containing Numba cache directory
    """
    numba_cache = tmp_base_dir / '.numba'
    numba_cache.mkdir(parents=True, exist_ok=True)

    os.environ['NUMBA_CACHE_DIR'] = str(numba_cache)

    import logging
    logging.info(f"Numba cache redirected to: {numba_cache}")

    return [numba_cache]
```

#### 1.5 Setup Error Exception

Distinct exception type for setup failures:

```python
# In src/nef_pipelines/tools/ai/sandbox_lib.py

class SandboxSetupError(RuntimeError):
    """Raised when sandbox directory setup fails before command execution.

    This indicates a sandbox configuration issue, not a command implementation bug.
    Check the command's @setup_sandbox decorator and setup functions.
    """
    pass
```

#### 1.6 Audit Hook Updates

Update audit hook to use site-packages validation and `/tmp` exemption:

```python
# In src/nef_pipelines/tools/ai/sandbox_audit.py
from pathlib import Path
from fnmatch import fnmatchcase

def _sandbox_audit_hook(event: str, args: tuple):
    """Audit hook for sandbox file write monitoring."""
    if event not in ("open", "os.mkdir"):
        return

    path = Path(args[0]).resolve()

    # Global exemption: tool caches in /tmp
    tmp_base = os.environ.get('NEF_SANDBOX_TMP', '/tmp/nef_pipelines_mcp_tmp')
    if str(path).startswith(tmp_base):
        return  # Allow - expendable tool caches

    # Validated __pycache__: only in real site-packages
    if "__pycache__" in path.parts:
        from .sandbox_lib import VALID_SITE_PACKAGES
        if any(path.is_relative_to(site_pkg) for site_pkg in VALID_SITE_PACKAGES):
            return  # Allow - legitimate library bytecode
        # else: fall through to violation (fake __pycache__ to bypass sandbox)

    # Check command-specific allowed directories
    state = _get_audit_state()
    if state.allowed_directories:
        if any(path.is_relative_to(allowed) for allowed in state.allowed_directories):
            return  # Allow

    # Check command-specific glob patterns
    if state.glob_patterns:
        path_str = str(path)
        if any(fnmatchcase(path_str, pat) for pat in state.glob_patterns):
            return  # Allow

    # Check dynamic check (if provided, with safeguards)
    if state.dynamic_check:
        try:
            if state.dynamic_check(path):
                return  # Allow
        except Exception as e:
            # Log but don't crash - treat as "check failed, deny write"
            import logging
            logging.error(
                f"dynamic_check raised exception for {path}: {e}\n"
                f"Treating as denied write. Fix the dynamic_check function."
            )
            # Fall through to violation

    # Check sandbox boundary
    if not path.is_relative_to(state.sandbox_root):
        raise SandboxViolation(
            f"Attempt to write outside sandbox: {path}\n"
            f"Sandbox root: {state.sandbox_root}"
        )
```

---

### Implementation Phase 2: MCP Layer Integration

Execute setup at MCP layer (in `nef_execute_pipeline`):

```python
# In src/nef_pipelines/tools/ai/mcp_commands.py or server_lib.py

def nef_execute_pipeline(steps: list[dict], ...):
    """Execute pipeline with sandbox setup before audit context."""

    # Get instance-specific tmp directory
    from .sandbox_bootstrap import warm_bootstrap_directories, get_tmp_base_dir
    instance_id = _get_or_create_instance_id()  # UUID for this session
    tmp_base_dir = warm_bootstrap_directories(instance_id)

    for step in steps:
        cmd_fn = _get_command_function(step['command'])

        # Check for sandbox setup metadata
        if hasattr(cmd_fn, '_sandbox_setup'):
            setup = cmd_fn._sandbox_setup
            allowed_dirs = []

            try:
                # Run setup callables (redirects, discovery)
                for setup_fn in setup['callables']:
                    dirs = setup_fn(tmp_base_dir)
                    allowed_dirs.extend(dirs if isinstance(dirs, list) else [dirs])

                # Add static paths
                for path_str in setup['static']:
                    path = Path(path_str).expanduser()
                    path.mkdir(parents=True, exist_ok=True)
                    allowed_dirs.append(path)

                # Register with audit hook state
                _register_command_allowances(
                    allowed_dirs,
                    setup['globs'],
                    setup.get('dynamic_check')
                )

            except Exception as e:
                # Setup failure - clear attribution
                from .sandbox_lib import SandboxSetupError
                setup_fn_names = [fn.__name__ for fn in setup['callables']]
                raise SandboxSetupError(
                    f"Sandbox setup failed for command '{step['command']}'.\n"
                    f"This is a sandbox configuration issue, not a command error.\n"
                    f"Setup functions: {setup_fn_names}\n"
                    f"Static paths: {setup['static']}\n"
                    f"Error: {e}"
                ) from e

        # NOW execute command with audit context
        with audit_context():
            _execute_command(step)
```

---

### Implementation Phase 3: Command Declarations

Add `@setup_sandbox` to commands that need it:

```python
# Example: plot command
# In src/nef_pipelines/tools/plot/correlations.py

from nef_pipelines.tools.ai.sandbox_lib import setup_sandbox, setup_matplotlib

@plot_app.command()
@setup_sandbox(
    setup_callables=[setup_matplotlib]  # Redirects to /tmp, returns paths
)
def correlations(
    input_file: Path = typer.Option(...),
    output: Path = typer.Option("correlation_plot.pdf"),
    ...
):
    """Create correlation plots from NEF shifts.

    Output file is written to sandbox (protected), NOT to matplotlib cache dir.
    """
    entry = read_entry(input_file)
    result = pipe(entry, ...)

    # CRITICAL: output goes to sandbox, never to os.environ['MPLCONFIGDIR']
    output_path = output.resolve()  # Relative to cwd (sandbox)
    plt.savefig(output_path)
    print(result)
```

```python
# Example: fit command using JAX
# In src/nef_pipelines/tools/fit/exponential.py

from nef_pipelines.tools.ai.sandbox_lib import setup_sandbox, setup_jax

@fit_app.command()
@setup_sandbox(
    setup_callables=[setup_jax]  # Redirects JAX/CUDA/Triton caches to /tmp
)
def exponential(
    input_file: Path = typer.Option(...),
    ...
):
    """Fit exponential decay to series data."""
    # JAX compilation cache now in /tmp, not ~/.cache or /var/tmp
    entry = read_entry(input_file)
    result = pipe(entry, ...)
    print(result)
```

---

### Migration Checklist

**Phase 1: Infrastructure (Priority)**
- [ ] Create `sandbox_lib.py` with:
  - [ ] `get_valid_site_packages()` and `VALID_SITE_PACKAGES` cache
  - [ ] `setup_sandbox()` decorator (metadata only, no wrapper)
  - [ ] `SandboxSetupError` exception
  - [ ] `setup_matplotlib()` callable
  - [ ] `setup_jax()` callable
  - [ ] `setup_numba()` callable
- [ ] Create `sandbox_bootstrap.py` with:
  - [ ] `get_tmp_base_dir()` (reads `NEF_SANDBOX_TMP` env var)
  - [ ] `warm_bootstrap_directories(instance_id)` (tempfile + tmp base)
- [ ] Update `sandbox_audit.py`:
  - [ ] Add `/tmp/nef_pipelines_mcp_tmp/*` global exemption
  - [ ] Add site-packages validation for `__pycache__`
  - [ ] Add glob pattern matching
  - [ ] Add dynamic_check with try/except safeguard
  - [ ] Add `SandboxSetupError` import

**Phase 2: MCP Integration**
- [ ] Update `nef_execute_pipeline()` in `mcp_commands.py`:
  - [ ] Generate/cache instance_id (UUID)
  - [ ] Call `warm_bootstrap_directories(instance_id)`
  - [ ] Check for `_sandbox_setup` metadata on command functions
  - [ ] Execute setup callables with `tmp_base_dir`
  - [ ] Register allowed directories with audit state
  - [ ] Catch exceptions → raise `SandboxSetupError` with context
- [ ] Update `server.py`:
  - [ ] Remove matplotlib pre-import (no longer needed)
  - [ ] Remove `tempfile.gettempdir()` from import block (moved to bootstrap)
  - [ ] Keep `set_mplconfigdir()` for sandbox changes (still needed for base config)

**Phase 3: Command Declarations**
- [ ] Add `@setup_sandbox(setup_callables=[setup_matplotlib])` to plot commands:
  - [ ] `plot/correlations.py`
  - [ ] `plot/bar.py`
  - [ ] (Other plot commands when committed)
- [ ] Add `@setup_sandbox(setup_callables=[setup_jax])` to fit commands:
  - [ ] `fit/exponential.py`
  - [ ] (Other fit commands using JAX)
- [ ] Verify output paths never use cache env vars:
  - [ ] Grep: `grep -r "MPLCONFIGDIR.*savefig" src/nef_pipelines/tools/`
  - [ ] Should return nothing

**Phase 4: Testing & Verification**
- [ ] Verify thread model (add logging to check serialization):
  - [ ] Log thread ID in `server.py` startup
  - [ ] Log thread ID in `_execute_command_in_process`
  - [ ] Run concurrent MCP requests, verify same thread
  - [ ] If concurrent → implement ContextVar, else defer
- [ ] Test cache vs output separation:
  - [ ] Write test: output goes to sandbox, not `/tmp`
  - [ ] Test that matplotlib writes to `/tmp/.../` are allowed
  - [ ] Test that user plot files land in sandbox
- [ ] Meta-test for decorator usage:
  - [ ] Test: commands with `import matplotlib` must have `@setup_sandbox`
  - [ ] Test: commands with `import jax` must have `@setup_sandbox`
- [ ] Document pattern in `CLAUDE.md`:
  - [ ] Three-tier priority (redirect → dynamic → static)
  - [ ] Decorator usage examples
  - [ ] Cache vs output separation rule
  - [ ] dynamic_check discouraged (use glob_patterns instead)
  - [ ] Code review checklist for `dynamic_check`

---

### Safeguards & Documentation

#### Code Review Checklist for `dynamic_check`

If a PR adds `dynamic_check` to `@setup_sandbox`:

- [ ] **Justification documented:** Why can't static paths / glob patterns / redirection work?
- [ ] **Performance verified:** No I/O, no expensive calls (< 10µs per invocation)
- [ ] **Safety verified:** Returns False on error, doesn't raise exceptions
- [ ] **Testing added:** Parameterized test covering both allowed and denied paths
- [ ] **Documentation added:** Docstring explains why this is necessary

#### Critical Comments to Add

In `setup_matplotlib()` and other setup functions:
```python
# CRITICAL: These paths are for LIBRARY CACHES ONLY (exempt from protection).
# All user-visible outputs (plots, results, NEF files) MUST go to sandbox.
# Commands must never use these env vars as output locations.
```

In `@setup_sandbox` docstring:
```python
"""
...
Note: setup_callables should redirect libraries to /tmp (Priority 1), use dynamic
discovery (Priority 2), or return static paths (Priority 3). Prefer redirection.

WARNING: dynamic_check runs on EVERY file write (audit hook hot path). Only use
as last resort when static/glob patterns cannot express the requirement. Must be
fast (no I/O), safe (no exceptions), and documented.
"""
```

---

## Part 2: Appendix - Design Discussion

This appendix documents the design process, options considered, and rationale.

### Context & Problem Statement

The MCP server runs NEF-Pipelines commands in a sandboxed environment with an audit hook
that monitors file writes. Some libraries (matplotlib, tempfile, JAX) need to write to specific
directories during normal operation:

- `tempfile.gettempdir()` probes candidate directories including `/var/tmp` on first call
- `matplotlib` writes config/cache files to `~/.matplotlib` and `.pyc` to `__pycache__`
- JAX writes JIT compilation caches
- Python writes bytecode `.pyc` files to `__pycache__` in site-packages

Without pre-warming or exemptions, these legitimate writes trigger false-positive sandbox
violations.

**Current scattered approach:**
- `mcp_lib.py`: `tempfile.gettempdir()` called at import time
- `server.py`: matplotlib pre-imported before audit hook installed
- `mcp_commands.py`: `set_mplconfigdir()` called on sandbox change
- `sandbox_audit.py`: `__pycache__` hardcoded as exemption

**Issues:**
1. Hard to audit what directories are warmed/exempted
2. No clear ownership (system vs command responsibility)
3. Warms directories even if never used
4. Adding commands with new directory needs requires editing multiple files
5. No declarative way for commands to specify their requirements

---

### Design Options Evaluated

#### Option 1: Current Scattered Approach

**Pros:**
- ✅ Simple to implement initially
- ✅ Works for immediate needs

**Cons:**
- ❌ Hard to audit what directories are exempt/warmed
- ❌ No clear ownership
- ❌ Warms directories even if never used
- ❌ Adding new command requires editing multiple files

**Verdict:** Current state - works but doesn't scale

---

#### Option 2: Central Registry

One file lists all system-wide directory requirements:

```python
# sandbox_config.py
SYSTEM_REQUIRED_DIRS = ["~/.matplotlib", "tempfile"]
AUDIT_EXEMPTIONS = ["__pycache__"]
```

**Pros:**
- ✅ Single source of truth
- ✅ Easy to audit what's allowed
- ✅ Simple mental model

**Cons:**
- ❌ Still centralized - command authors must remember to update
- ❌ Warms everything upfront even if unused
- ❌ No connection between command code and requirements
- ❌ Can't lazy-load command-specific needs

**Verdict:** Better than scattered, but still centralization issues

---

#### Option 3: Command-Level Declaration

Commands declare needs via decorator:

```python
@requires_directories(warm=["~/.matplotlib"])
def command(...):
    ...
```

**Pros:**
- ✅ Clear ownership - command declares its own needs
- ✅ Co-located with code that uses directories
- ✅ Lazy warming - only when command runs
- ✅ Self-documenting
- ✅ Testable

**Cons:**
- ❌ System-wide needs (tempfile) still awkward
- ❌ More complex implementation
- ❌ Need to hook into command execution path

**Verdict:** Best for command-specific needs

---

#### Option 4: Hybrid Approach (SELECTED)

System bootstrap for critical paths + command-level declarations.

**Pros:**
- ✅ Best of both: critical paths warmed early, command-specific lazy-loaded
- ✅ Clear separation: system vs command responsibilities
- ✅ Commands self-document their needs
- ✅ Fast startup (only bootstrap warming)
- ✅ Easy to audit
- ✅ Scales well

**Cons:**
- ❌ Most complex to implement
- ❌ Two mechanisms to understand

**Decision criteria:**
- System: Used by infrastructure before any command runs (tempfile cache)
- Command: Used only by specific commands (matplotlib for plot, JAX for fit)

**Verdict:** SELECTED - balances simplicity, performance, and maintainability

---

### Key Design Decisions

#### Decorator vs Attribute

**Chosen:** Decorator (`@setup_sandbox`)

**Why:**
- More Pythonic and conventional
- Visible at function definition
- Can validate at decoration time
- IDE support
- Harder to forget

**Important:** Must use `@wraps(fn)` to preserve function metadata for Typer

---

#### CLI Command Level vs Pipe Function Level

**Chosen:** CLI command level

**Why:**
- CLI command is the entry point (what user/MCP invokes)
- Has access to parsed options (can determine needs dynamically)
- Typer-registered function (natural hook point)
- Multiple CLI commands might share a pipe
- Testing framework hooks CLI commands

---

#### Strings vs Callables for Directory Specs

**Chosen:** Both

**Why:**
- Strings for static paths (`"~/.cache/myapp"`)
- Callables for dynamic discovery (library APIs, env var redirection)
- Maximum flexibility

Example callable:
```python
def setup_matplotlib(tmp_base_dir):
    mpl_dir = tmp_base_dir / '.matplotlib'
    os.environ['MPLCONFIGDIR'] = str(mpl_dir)
    mpl_dir.mkdir(parents=True, exist_ok=True)
    return [mpl_dir]
```

---

#### Wildcards and Glob Patterns

**Question:** Do we need wildcard support?

**For `warm` - NO**
- Warming is about specific concrete paths
- Callables handle dynamic discovery

**For audit exemptions - YES (glob patterns)**
- Need to match patterns like `**/site-packages/**/__pycache__`
- Prevents fake `__pycache__` bypass
- Use `fnmatchcase` for consistent cross-platform behavior

**User feedback:** "anyone could stick a __pycache__ in a path and it would be exempt, we need to limit __pycache__ to paths under the site-packages path"

**Solution:** Validate against actual site-packages paths (via `site.getsitepackages()`, `site.getusersitepackages()`, `sysconfig.get_paths()["purelib"]`)

---

#### Dynamic Directory Requirements (Option-Dependent)

**Example:** Only need matplotlib if `--format pdf`

**Solution:** Setup callables can check options, but warming must happen BEFORE audit context

**User feedback:** "this warming would be too late it needs to be in something called by @requires_directories"

**Implementation:** Setup callables executed at MCP layer before audit context, have access to parsed options

---

#### Disabling .pyc Writing

**Option:** Set `sys.dont_write_bytecode = True` to eliminate `__pycache__` entirely

**Pros:**
- ✅ Eliminates __pycache__ writes
- ✅ Simpler - no exemption patterns
- ✅ Clean audit log

**Cons:**
- ❌ One-time recompile cost per import

**User feedback:** "switching off pycache seems a bit extreme"

**Decision:** Keep .pyc enabled, use site-packages validation instead

---

#### JAX and Dynamic Imports

**Problem:** JAX lazy-loads backends (CPU/GPU/TPU) dynamically, can't predict all imports

**Gemini suggestion:** Redirect JAX caches to `/tmp` via env vars BEFORE import:
```python
os.environ['JAX_COMPILATION_CACHE_DIR'] = '/tmp/nef_pipelines_mcp_tmp/{instance}/jax_cache'
os.environ['CUDA_CACHE_PATH'] = '/tmp/nef_pipelines_mcp_tmp/{instance}/cuda_cache'
os.environ['TRITON_CACHE_DIR'] = '/tmp/nef_pipelines_mcp_tmp/{instance}/triton_cache'
```

**User feedback:** "the path should have a default and also be settable by an ENV variable. `/tmp/nef_pipelines_mcp_tmp` would be a better name"

**Decision:** Implement `setup_jax()` callable that sets env vars, configurable via `NEF_SANDBOX_TMP`

---

### Opus Review Feedback

#### 1. /tmp Redirection - Accepted with Conditions

**Opus initial concern:** "Redirection to /tmp still requires exemption, defeats purpose"

**User clarification:** Threat model is protecting USER data, not tool caches

**Threat model:**
- ✅ Protect: User's NEF files, plots, results
- ❌ Don't care: Library cache files in /tmp (expendable, regenerated)
- Goal: Prevent accidental AI damage to user files, not maximum sandboxing

**Opus acceptance:** "Your threat model is sound IF you maintain strict separation"

**Critical requirement:** Commands must NEVER put user outputs in `/tmp/nef_pipelines_mcp_tmp/`

**Safeguards:**
1. Command convention: outputs from args or default to cwd (sandbox)
2. Review pattern: `grep -r "MPLCONFIGDIR.*savefig" src/`
3. Test coverage: verify outputs land in sandbox
4. Add comment in setup code warning about cache vs output separation

**Opus verdict:** "/tmp redirection + global exemption is acceptable for your threat model"

---

#### 2. Concurrency - Verify Before Deferring

**Opus:** "Need to verify FastMCP truly serializes requests"

**Action:** Add thread logging to verify before deferring:
```python
import threading
logger.info(f"Server started on thread {threading.current_thread().name}")
logger.debug(f"Executing {args} on thread {threading.current_thread().name}")
```

**If concurrent → implement ContextVar now**
**If serialized → document assumption and defer**

**Opus:** "Acceptable IF you've verified serialization"

---

#### 3. Setup Errors - Accepted

**Opus:** "Excellent refinement, adopt without reservation"

`SandboxSetupError` with clear attribution is correct approach.

---

#### 4. Dynamic Check - Accepted with Safeguards

**Opus initial objection:** Too risky even for trusted code (performance trap, unauditable, hard to test)

**Opus recommendation:** Use `glob_patterns` instead for 95% of cases

**User preference:** Keep as escape hatch for trusted code

**Compromise:** Keep `dynamic_check` BUT:
- Document as "code smell" / last resort
- Add safeguards (try/except in audit hook)
- Require code review checklist
- Prefer static > glob > dynamic

**Opus acceptance:** "With these safeguards, I accept keeping dynamic_check as the escape hatch"

---

### User Comments & Requirements

#### Priority Order (User Feedback)

"in general in order of priority:
1. if tools can specify a directory to use they should use the one in /tmp/nef_pipelines_mcp_tmp and return it, this should be logged at first use
2. dynamically warm and return paths
3. return fixed directories"

**Implemented as three-tier priority in setup callables**

---

#### Exemptions Part of Command Declaration

"**COMMENT** part of the command declaration"

**Decision:** `exempt` parameter in `@setup_sandbox` as `glob_patterns` and optional `dynamic_check`

---

#### Transitive Dependencies

"**COMMENT** that's the tool with the decorations problem"

**Decision:** Command declares all dependencies (including transitive). Command owns all its requirements.

---

#### Warming Should Return Exempt Directories

"**COMMENT** tools can warm and return exempt directories [maybe setup is a better name]"

**Decision:** Renamed to `setup_sandbox`, callables return list of paths they created/configured

---

#### Testing Strategy

"**COMMENT** yes both [meta-test catches obvious cases, test failures catch edge cases]"

**Implementation:** Both meta-tests (scan imports) and functional tests (run commands with audit active)

---

### Gemini Contributions

#### Site-Packages Discovery

Gemini provided code for discovering site-packages paths:
- `site.getsitepackages()` - global/venv paths
- `site.getusersitepackages()` - user local
- `sysconfig.get_paths()["purelib"]` - robust fallback

**Implemented in `get_valid_site_packages()`**

---

#### JAX/Accelerator Cache Redirection

Gemini suggested env vars for JAX/CUDA/Triton caches:
```python
os.environ['JAX_COMPILATION_CACHE_DIR'] = ...
os.environ['CUDA_CACHE_PATH'] = ...
os.environ['TRITON_CACHE_DIR'] = ...
```

**Implemented in `setup_jax()`**

---

#### Rename to `@setup_sandbox`

Gemini: "should rename the decorator to something more structural—like @setup_sandbox"

**Adopted - clearer than `@setup_directories`**

---

### Future Enhancements

1. **Auto-discovery of directory requirements**
   - Static analysis to detect directory usage
   - Suggest decorator additions

2. **Warming cache**
   - Remember what's already warmed this session
   - Skip redundant warming

3. **Performance metrics**
   - Log warming time per directory
   - Identify slow warmers

4. **Concurrency support**
   - Migrate to ContextVar when concurrent command execution needed
   - Thread-safe state management

---

### References

- [Python site module docs](https://docs.python.org/3/library/site.html)
- [Python sysconfig module docs](https://docs.python.org/3/library/sysconfig.html)
- [fnmatch pattern matching](https://docs.python.org/3/library/fnmatch.html)
- [Audit hooks (PEP 578)](https://peps.python.org/pep-0578/)
