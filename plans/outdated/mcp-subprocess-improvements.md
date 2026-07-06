# Plan: MCP Server Subprocess Improvements

## Overview

Fix issues with the current subprocess-based MCP server architecture as identified by Gemini.

**Status**: Fallback/Alternative approach. Use if direct integration (see `mcp_direct_integration.md`) encounters issues.

## Problems Identified by Gemini

### 1. NEF_CMD Configuration
- **Issue**: Hardcoded `NEF_CMD = "nef"` assumes package installed on PATH
- **Impact**: Fails in development environments
- **Line**: `nef_mcp_server.py:79`

### 2. Plugin Loading Duplication
- **Issue**: Module list duplicated in `main.py` (lines 101-141) and `nef_mcp_server.py` (lines 31-70)
- **Impact**: Must update two files when adding plugins, easy to miss `tools.version` module
- **Count**: 39 modules duplicated

### 3. Fixed Timeouts
- **Issue**: Hardcoded 120s and 30s timeouts
- **Impact**: Insufficient for heavy NMR operations (simulate, fit, large datasets)
- **Lines**: 202 (subprocess.run), 324 (final step), 329 (intermediate steps)

### 4. Hardcoded Skill File Paths
- **Issue**: Searches hardcoded filesystem paths
- **Impact**: Won't work when installed via pip as package
- **Lines**: 232-236

## Solutions

### Solution 1: Flexible NEF_CMD Detection

**File**: `nef_mcp_server.py`

Replace line 79:
```python
NEF_CMD = "nef"
```

With:
```python
import os
import sys
import shutil

def _get_nef_command() -> list[str]:
    """
    Determine how to invoke NEF pipelines CLI.

    Priority order:
    1. NEF_COMMAND environment variable (user override)
    2. 'nef' on PATH (installed package)
    3. 'python -m nef_pipelines' (development/fallback)

    Returns:
        list[str]: Command tokens (e.g., ["nef"] or ["python", "-m", "nef_pipelines"])
    """
    # 1. Check environment variable override
    env_cmd = os.environ.get("NEF_COMMAND", "").strip()
    if env_cmd:
        return env_cmd.split()

    # 2. Check if 'nef' is on PATH
    if shutil.which("nef"):
        return ["nef"]

    # 3. Fall back to python module invocation
    return [sys.executable, "-m", "nef_pipelines"]


NEF_CMD = _get_nef_command()
```

**Update all subprocess calls** (lines 195, 297):
```python
# OLD:
cmd = [NEF_CMD, *args]

# NEW:
cmd = NEF_CMD + args  # NEF_CMD is now a list
```

**Update docstrings**:
```python
"""
NEF-Pipelines MCP Server

Environment Variables:
    NEF_COMMAND - Override CLI invocation (e.g., "nef" or "python -m nef_pipelines")
                  Useful for development or custom installations
"""
```

**Benefits**:
- ✅ Works in development (`python -m nef_pipelines`)
- ✅ Works when installed (`nef` on PATH)
- ✅ User can override via environment variable
- ✅ No hardcoded assumptions

### Solution 2: Shared Plugin Registry

**New File**: `src/nef_pipelines/lib/plugin_registry.py`

```python
"""
Central registry of all NEF pipelines plugin modules.

This list is used by:
- main.py: To load plugins when running the CLI
- nef_mcp_server.py: To discover available commands for MCP
- Testing: To verify plugin integrity

To add a new plugin:
1. Add module path to PLUGIN_MODULES list below
2. No other changes needed - both main.py and MCP server will pick it up
"""

PLUGIN_MODULES = [
    # Tools (19 modules)
    "nef_pipelines.tools.help",
    "nef_pipelines.tools.chains",
    "nef_pipelines.tools.entry",
    "nef_pipelines.tools.fit",
    "nef_pipelines.tools.frames",
    "nef_pipelines.tools.globals",
    "nef_pipelines.tools.header",
    "nef_pipelines.tools.loops",
    "nef_pipelines.tools.namespace",
    "nef_pipelines.tools.peaks",
    "nef_pipelines.tools.plot",
    "nef_pipelines.tools.save",
    "nef_pipelines.tools.series",
    "nef_pipelines.tools.shifts",
    "nef_pipelines.tools.simulate",
    "nef_pipelines.tools.sink",
    "nef_pipelines.tools.stream",
    "nef_pipelines.tools.test",
    "nef_pipelines.tools.version",

    # Transcoders (21 modules)
    "nef_pipelines.transcoders.csv",
    "nef_pipelines.transcoders.deep",
    "nef_pipelines.transcoders.echidna",
    "nef_pipelines.transcoders.fasta",
    "nef_pipelines.transcoders.mars",
    "nef_pipelines.transcoders.modelfree",
    "nef_pipelines.transcoders.nmrpipe",
    "nef_pipelines.transcoders.nmrview",
    "nef_pipelines.transcoders.pales",
    "nef_pipelines.transcoders.rcsb",
    "nef_pipelines.transcoders.rpf",
    "nef_pipelines.transcoders.shifty",
    "nef_pipelines.transcoders.shiftx2",
    "nef_pipelines.transcoders.sparky",
    "nef_pipelines.transcoders.nmrstar",
    "nef_pipelines.transcoders.talos",
    "nef_pipelines.transcoders.ucbshift",
    "nef_pipelines.transcoders.xcamshift",
    "nef_pipelines.transcoders.xeasy",
    "nef_pipelines.transcoders.xplor",
]
```

**Update**: `src/nef_pipelines/main.py`

Replace lines 101-141:
```python
from nef_pipelines.lib.plugin_registry import PLUGIN_MODULES

for module_name in PLUGIN_MODULES:
    try:
        import_module(module_name)
    except Exception:
        msg = f"plugin {module_name}\n{format_exc()}"
        warnings.append((module_name, msg))
```

**Update**: `nef_mcp_server.py`

Replace lines 31-75:
```python
from nef_pipelines.lib.plugin_registry import PLUGIN_MODULES

for module_name in PLUGIN_MODULES:
    try:
        import_module(module_name)
    except Exception:
        pass  # Silently ignore failed imports in MCP server
```

**Benefits**:
- ✅ Single source of truth
- ✅ No synchronization issues
- ✅ Adding plugins is easy (one location)
- ✅ Can be used by testing infrastructure
- ✅ Self-documenting (comments explain purpose)

### Solution 3: Configurable Timeouts

**File**: `nef_mcp_server.py`

#### Update `_run_subprocess()` (line 187):
```python
def _run_subprocess(
    args: list[str],
    stdin_text: str = "",
    timeout: int = 120,  # Add timeout parameter
) -> dict[str, Any]:
    """
    Run [NEF_CMD, *args] as a subprocess.

    Args:
        args: Command arguments (after 'nef')
        stdin_text: Input to pipe via stdin
        timeout: Maximum execution time in seconds (default: 120)

    Returns:
        {"stdout": str, "stderr": str, "returncode": int, "success": bool, "command": str}
    """
    cmd = NEF_CMD + args
    try:
        result = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,  # Use parameter
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0,
            "command": shlex.join(cmd),
        }
    except FileNotFoundError:
        return {
            "stdout": "",
            "stderr": f"'{NEF_CMD[0]}' not found",
            "returncode": -1,
            "success": False,
            "command": shlex.join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "returncode": -1,
            "success": False,
            "command": shlex.join(cmd),
        }
```

#### Update `nef_run_step()` (line 229):
```python
@mcp.tool()
def nef_run_step(
    args: list[str],
    nef_stream: str = "",
    timeout: int = 120,  # Add timeout parameter
) -> dict[str, Any]:
    """
    Run a single NEF pipeline step and return its output stream.

    Args:
        args: Command tokens (e.g., ["frames", "tabulate"])
        nef_stream: Optional NEF text to supply on stdin
        timeout: Maximum execution time in seconds (default: 120)
                 Increase for heavy operations like simulate (300-600s)

    Returns:
        {"stdout": str, "stderr": str, "returncode": int, "success": bool, "command": str}

    Example:
        nef_run_step(
            args=["simulate", "peaks", "--noise", "0.1"],
            nef_stream=nef_content,
            timeout=600  # 10 minutes for heavy simulation
        )
    """
    return _run_subprocess(args, stdin_text=nef_stream, timeout=timeout)
```

#### Update `nef_run_pipeline()` (line 256):
```python
@mcp.tool()
def nef_run_pipeline(
    steps: list[dict[str, Any]],
    input_file: str | None = None,
    timeout_final: int = 120,         # Add timeout parameters
    timeout_intermediate: int = 30,
) -> dict[str, Any]:
    """
    Run a fully composed NEF pipeline with true stdin→stdout chaining.

    Args:
        steps: Ordered list of {"args": list[str]} descriptors
        input_file: Optional path to seed first step's stdin
        timeout_final: Timeout in seconds for final step (default: 120)
        timeout_intermediate: Timeout in seconds for intermediate steps (default: 30)

    For pipelines with heavy processing (simulate, fit, large datasets),
    increase timeout_final to 300-600 seconds.

    Returns:
        {"stdout": str, "stderr": str, "returncode": int, "success": bool,
         "commands": list[str], "step_return_codes": list[int]}
    """
    if not steps:
        return {
            "stdout": "",
            "stderr": "No steps provided",
            "returncode": -1,
            "success": False,
            "commands": [],
        }

    processes: list[subprocess.Popen] = []
    commands: list[str] = []
    all_stderr_parts: list[str] = []

    try:
        for i, step in enumerate(steps):
            args = step.get("args", [])
            cmd = NEF_CMD + args  # NEF_CMD is now a list
            commands.append(shlex.join(cmd))

            # Determine stdin
            if i == 0:
                if input_file:
                    first_stdin = open(input_file, "r")  # noqa: WPS515
                else:
                    first_stdin = subprocess.DEVNULL
            else:
                first_stdin = processes[-1].stdout  # type: ignore[assignment]

            p = subprocess.Popen(
                cmd,
                stdin=first_stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            processes.append(p)

            if i == 0 and input_file and hasattr(first_stdin, "close"):
                first_stdin.close()

        # Collect output from final process with configurable timeout
        final_stdout, final_stderr = processes[-1].communicate(timeout=timeout_final)
        all_stderr_parts.append(f"[step {len(steps)}] {final_stderr}")

        # Wait for intermediate processes with shorter timeout
        for i, p in enumerate(processes[:-1]):
            _, stderr = p.communicate(timeout=timeout_intermediate)
            if stderr:
                all_stderr_parts.append(f"[step {i + 1}] {stderr}")

        return_codes = [p.returncode for p in processes]
        success = all(rc == 0 for rc in return_codes)

        return {
            "stdout": final_stdout,
            "stderr": "\n".join(filter(None, all_stderr_parts)),
            "returncode": processes[-1].returncode,
            "success": success,
            "commands": commands,
            "step_return_codes": return_codes,
        }

    except subprocess.TimeoutExpired:
        for p in processes:
            p.kill()
        return {
            "stdout": "",
            "stderr": "Pipeline timed out",
            "returncode": -1,
            "success": False,
            "commands": commands,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "success": False,
            "commands": commands,
        }
```

**Update MCP instructions**:
```python
mcp = FastMCP(
    "nef-pipelines",
    instructions=(
        # ... existing instructions ...
        "\n**Timeout Customization:**\n"
        "- Default: 120s for single commands, 30s for pipeline steps\n"
        "- Heavy operations (simulate, fit): Use timeout=300-600\n"
        "- Large datasets: Increase timeout_final for pipelines\n"
    ),
)
```

**Benefits**:
- ✅ AI can adjust timeouts for heavy operations
- ✅ Defaults remain reasonable (120s/30s)
- ✅ Per-command and per-pipeline customization
- ✅ Clear error messages on timeout

### Solution 4: Bundled Skill File via importlib.resources

**Step 1: Create resources directory**
```bash
mkdir -p src/nef_pipelines/resources
```

**Step 2: Copy skill file**
```bash
cp .claude/skill/nef.md src/nef_pipelines/resources/nef_skill.md
```

**Step 3: Update `nef_get_skill_file()`** in `nef_mcp_server.py`:

Replace existing function (around line 231):
```python
import sys

@mcp.tool()
def nef_get_skill_file() -> dict[str, Any]:
    """
    Get the NEF Pipelines skill file with expert guidance and best practices.

    Returns:
        {
            "skill_content": str,
            "success": bool,
            "source": str,
            "error": str | None
        }
    """
    try:
        # Try bundled package resource (works when pip installed)
        if sys.version_info >= (3, 9):
            # Python 3.9+ approach
            from importlib.resources import files
            resource = files("nef_pipelines").joinpath("resources/nef_skill.md")
            content = resource.read_text()
        else:
            # Python 3.8 fallback
            from importlib.resources import read_text
            content = read_text("nef_pipelines.resources", "nef_skill.md")

        return {
            "skill_content": content,
            "success": True,
            "source": "bundled package resource",
            "error": None,
        }

    except Exception as e:
        # Fallback: Try development filesystem path
        from pathlib import Path
        dev_path = Path(__file__).parent / ".claude" / "skill" / "nef.md"

        if dev_path.exists():
            try:
                content = dev_path.read_text()
                return {
                    "skill_content": content,
                    "success": True,
                    "source": f"development file: {dev_path}",
                    "error": None,
                }
            except Exception as read_error:
                return {
                    "skill_content": "",
                    "success": False,
                    "source": "none",
                    "error": f"Found file but failed to read: {read_error}",
                }

        # Nothing worked
        return {
            "skill_content": "",
            "success": False,
            "source": "none",
            "error": f"Skill file not found. Package resource error: {e}",
        }
```

**Step 4: Update `setup.cfg`**

Add to `[options.package_data]` section:
```ini
[options.package_data]
nef_pipelines = resources/*.md
```

Or if section doesn't exist, add:
```ini
[options.package_data]
nef_pipelines = resources/*.md
```

**Alternative: Use MANIFEST.in** (if setup.cfg doesn't work):
```
include src/nef_pipelines/resources/*.md
```

**Benefits**:
- ✅ Works when installed via pip
- ✅ Works in development (fallback to filesystem)
- ✅ No filesystem assumptions in production
- ✅ Standard Python packaging approach
- ✅ Compatible with Python 3.8+ (with fallback)

## Implementation Steps

### Phase 1: Plugin Registry
1. Create `src/nef_pipelines/lib/plugin_registry.py`
2. Copy module list from `main.py` lines 101-141
3. Ensure `"nef_pipelines.tools.version"` is included
4. Update `main.py` to import from plugin_registry
5. Update `nef_mcp_server.py` to import from plugin_registry
6. Test: `nef --help` shows all commands

### Phase 2: NEF_CMD Flexibility
1. Add `_get_nef_command()` function to `nef_mcp_server.py`
2. Replace `NEF_CMD = "nef"` with `NEF_CMD = _get_nef_command()`
3. Update all `[NEF_CMD, *args]` to `NEF_CMD + args`
4. Update module docstring to mention NEF_COMMAND
5. Test in development: `NEF_COMMAND="python -m nef_pipelines" python nef_mcp_server.py`

### Phase 3: Configurable Timeouts
1. Add `timeout` parameter to `_run_subprocess()` (default 120)
2. Add `timeout` parameter to `nef_run_step()` (default 120)
3. Add `timeout_final` and `timeout_intermediate` to `nef_run_pipeline()` (defaults 120/30)
4. Update all `subprocess.run()` and `.communicate()` calls
5. Update docstrings with timeout guidance
6. Update MCP instructions to mention timeouts

### Phase 4: Skill File Resource
1. Create `src/nef_pipelines/resources/` directory
2. Copy `.claude/skills/nef.md` to `src/nef_pipelines/resources/nef_skill.md`
3. Update `nef_get_skill_file()` to use importlib.resources
4. Add `package_data` to `setup.cfg`
5. Test with: `python -c "from importlib.resources import files; print(files('nef_pipelines').joinpath('resources/nef_skill.md').read_text()[:100])"`
6. Keep `.claude/skills/nef.md` as master for editing

## Files to Create/Modify

### New Files
- `src/nef_pipelines/lib/plugin_registry.py` - Shared module list
- `src/nef_pipelines/resources/` - Resource directory
- `src/nef_pipelines/resources/nef_skill.md` - Bundled skill file

### Modified Files
- `nef_mcp_server.py` - All four improvements
- `src/nef_pipelines/main.py` - Use plugin_registry
- `setup.cfg` - Add package_data for resources

## Testing Strategy

### Unit Tests
```python
# Test plugin registry
def test_plugin_registry_completeness():
    from nef_pipelines.lib.plugin_registry import PLUGIN_MODULES
    assert "nef_pipelines.tools.help" in PLUGIN_MODULES
    assert "nef_pipelines.tools.version" in PLUGIN_MODULES
    assert len(PLUGIN_MODULES) == 40  # 19 tools + 21 transcoders

# Test NEF_CMD detection
def test_nef_cmd_fallback():
    import os
    os.environ.pop("NEF_COMMAND", None)
    # Reload module to test detection
    import importlib
    import nef_mcp_server
    importlib.reload(nef_mcp_server)
    assert isinstance(nef_mcp_server.NEF_CMD, list)
    assert len(nef_mcp_server.NEF_CMD) >= 1
```

### Integration Tests
```bash
# Test development mode
NEF_COMMAND="python -m nef_pipelines" python nef_mcp_server.py

# Test with MCP Inspector
# Start server and test tools with various timeouts

# Test skill file resource
python -c "
from importlib.resources import files
content = files('nef_pipelines').joinpath('resources/nef_skill.md').read_text()
assert 'NEF Pipelines Expert' in content
print('✓ Skill file resource works')
"

# Test plugin registry consistency
python -c "
from nef_pipelines.lib.plugin_registry import PLUGIN_MODULES
# Ensure both files use same list
print(f'Plugin count: {len(PLUGIN_MODULES)}')
assert 'nef_pipelines.tools.version' in PLUGIN_MODULES
print('✓ Plugin registry complete')
"
```

## Verification Checklist

- [ ] `nef --help` shows all commands (plugin registry works)
- [ ] MCP server starts without errors
- [ ] `nef_list_commands()` returns full command tree
- [ ] `nef_get_skill_file()` returns content from bundled resource
- [ ] `nef_run_step()` with custom timeout works
- [ ] `nef_run_pipeline()` with custom timeouts works
- [ ] NEF_COMMAND environment variable overrides default
- [ ] Development mode works (`python -m nef_pipelines`)
- [ ] Installed mode works (`nef` on PATH)
- [ ] Plugin registry has same count in both files
- [ ] Skill file accessible via importlib.resources

## Benefits Summary

| Issue | Before | After | Benefit |
|-------|--------|-------|---------|
| **NEF_CMD** | Hardcoded `"nef"` | Auto-detect with env override | Works in dev and prod |
| **Plugins** | Duplicated (2 files) | Shared registry (1 file) | Single source of truth |
| **Timeouts** | Fixed 120s/30s | Configurable parameters | Handles heavy operations |
| **Skill File** | Hardcoded paths | Bundled resource | Works when pip installed |

## Coexistence with Direct Integration

These improvements can **coexist** with direct integration (see `mcp_direct_integration.md`):

- Subprocess tools remain as `nef_run_step()` and `nef_run_pipeline()`
- Direct integration tools are `nef_call_command()` and `nef_call_pipeline()`
- Both share the same plugin registry
- Both share the same skill file resource
- AI can choose which approach to use based on:
  - Use direct integration for speed and simplicity
  - Use subprocess for commands not yet in worker registry

## Future Enhancements

- Dynamic timeout suggestions based on command type
- Subprocess pooling for parallel execution
- Progress reporting for long-running commands
- Resource bundling for other assets (templates, schemas)
- Configuration file for custom plugin paths

## Dependencies

- **No new dependencies**: All fixes use Python stdlib
- `importlib.resources`: Built into Python 3.8+
- `shutil.which()`: Built into Python 3.3+

## Success Criteria

✅ NEF_COMMAND environment variable works
✅ Plugin registry eliminates duplication
✅ Timeout parameters allow customization
✅ Skill file bundled correctly
✅ Works in development mode
✅ Works when installed via pip
✅ No regressions in functionality
✅ All 4 issues fixed
