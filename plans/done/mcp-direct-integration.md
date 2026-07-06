# Plan: MCP Server Direct Integration - Simplified

## Overview

Refactor the MCP server to run Typer-decorated commands **in-process** instead of subprocess execution,
using temporary files for I/O.

**Status**: ACTIVE - Simplified approach focusing on local file I/O

## Problem

Current MCP server uses subprocess execution:
- Slow (process spawn overhead ~50-100ms per command)
- Complex (stdin/stdout piping, timeout management)
- Brittle (depends on PATH, shell environment)
- Hard to debug (stderr capture, exit codes)
- Requires `nef` command on PATH

## Solution (Simplified)

Run Typer-decorated commands in-process by:
1. Writing NEF content to temporary files on disk
2. Calling Typer commands directly (no subprocess)
3. Capturing stdout instead of printing to terminal
4. Keeping the Typer CLI interface unchanged for both humans and AI

**Key Simplifications (v1):**
- ✅ Use local disk for temporary files (no memory:// URLs)
- ✅ No custom URL schemes or content registry
- ✅ Minimal changes to existing code
- ✅ Focus on in-process execution only

**Future Enhancements (v2+):**
- Memory-based I/O with memory:// URLs
- Content registry for zero-disk I/O
- Custom URL schemes for resources

## Key Discovery

### Command Architecture

NEF pipelines commands use Typer decorators for CLI:

```python
@app.command()
def command_name(input: Path, ...):
    """Typer-decorated command"""
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    entry = pipe(entry, param1, param2)  # Worker function
    print(entry)  # Stdout
```

### File I/O Infrastructure

All file reading goes through centralized functions in `nef_lib.py`:

```python
# Line 689-701: Main entry point
def read_entry_from_file_or_stdin_or_exit_error(file: Path) -> Entry:
    """Dispatches to stdin or file reading"""
    if file is None or file == Path("-"):
        return read_entry_from_stdin_or_raise()
    return read_entry_from_file_or_raise(file)

# Line 284-319: Stdin reading
def read_entry_from_stdin_or_raise() -> Entry:
    """Reads entire stdin with sys.stdin.read()"""
    lines = sys.stdin.read()
    entry = Entry.from_string(lines)
    return entry

# Line 704-717: File reading
def read_entry_from_file_or_raise(file) -> Entry:
    """Uses Entry.from_file(fh)"""
    with open(file, "r") as fh:
        entry = Entry.from_file(fh)
    return entry
```

### PyNMRStar Entry API

```python
# Already supports in-memory operations
Entry.from_file(file_handle)      # Works with TextIO/StringIO
Entry.from_string(text_string)    # Parse from string
Entry.__str__()                   # Serialize to STAR format
```

### Existing StringIO Usage

`util.py` already has StringIO utilities:
- `StringIteratorIO` class (line 143) - iterator to file-like adapter
- Direct StringIO usage (line 261) for testing

## Architecture

### Before (Subprocess)
```
MCP Tool → subprocess.run(["nef", "frames", "tabulate"], stdin=nef_text) → Parse stdout
```

### After v1 (Temporary Files)
```
MCP Tool → Write content to temporary file
         → Call Typer command with file path
         → Command reads from disk normally
         → Capture stdout to return to MCP
         → Clean up temporary file
```

### After v2+ (In-Memory I/O - Future)
```
MCP Tool → Register content with "memory://uuid"
         → Call Typer command with "memory://uuid" as input path
         → Command reads from in-memory registry
         → Capture stdout to return to MCP
```

### v1 Implementation: Temporary File I/O

**Implementation**:

1. **Temporary File Creation**: Write NEF content to temp file on disk
2. **In-Process Command Execution**: Call Typer command function directly
3. **Output Capture**: Redirect stdout to capture command output
4. **Cleanup**: Remove temporary files after execution
5. **Unchanged Typer Commands**: Commands use normal file paths

**Example Flow**:

```python
import tempfile
from pathlib import Path

# MCP tool creates temporary file
with tempfile.NamedTemporaryFile(mode='w', suffix='.nef', delete=False) as f:
    f.write(nef_content)
    temp_path = Path(f.name)

try:
    # MCP tool calls Typer command directly (in-process)
    result = call_command_in_process(
        ["frames", "tabulate", "--input", str(temp_path)]
    )

    # Output captured from stdout
    print(result["stdout"])  # NEF output
finally:
    # Cleanup
    temp_path.unlink(missing_ok=True)
```

**No changes needed to reading functions** - they work with normal file paths!

## Implementation (v1 - Simplified)

### Phase 1: Stdout Capture Utility

**File**: `src/nef_pipelines/lib/stdout_capture.py` (NEW)

Add stdout/stderr capturing for in-process command execution.

```python
"""
Stdout/stderr capture utilities for in-process command execution.
"""

import sys
import io
from contextlib import contextmanager
from typing import Generator

@contextmanager
def capture_stdout() -> Generator[io.StringIO, None, None]:
    """
    Context manager to capture stdout.

    Usage:
        with capture_stdout() as output:
            print("hello")
        captured = output.getvalue()  # "hello\n"
    """
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield sys.stdout
    finally:
        sys.stdout = old_stdout


@contextmanager
def capture_stdout_and_stderr():
    """
    Context manager to capture both stdout and stderr.

    Usage:
        with capture_stdout_and_stderr() as (out, err):
            print("normal")
            print("error", file=sys.stderr)
        print(out.getvalue())  # "normal\n"
        print(err.getvalue())  # "error\n"
    """
    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture
    try:
        yield stdout_capture, stderr_capture
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
```

### Phase 2: In-Process Command Executor with Temporary Files

**File**: `src/nef_pipelines/lib/mcp_execution.py` (NEW)

Execute Typer commands in-process using temporary files on disk.

```python
"""
In-process command execution for MCP server using temporary files.

Executes Typer commands directly in the current process with output capture,
avoiding subprocess overhead. Uses temporary files on disk for NEF content.
"""

import sys
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from nef_pipelines.main import app as nef_app
from nef_pipelines.lib.stdout_capture import capture_stdout_and_stderr


def execute_command_in_process(
    args: List[str],
    nef_input: str = "",
) -> Dict[str, Any]:
    """
    Execute a NEF command in-process with captured output using temporary files.

    Args:
        args: Command arguments (e.g., ["frames", "tabulate", "--show-all"])
        nef_input: NEF content to use as input (will be written to temp file)

    Returns:
        {
            "stdout": str,       # Captured stdout
            "stderr": str,       # Captured stderr
            "exit_code": int,    # 0 for success
            "success": bool,
        }
    """
    temp_file = None
    try:
        # Write NEF content to temporary file if provided
        if nef_input:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.nef', delete=False
            ) as f:
                f.write(nef_input)
                temp_file = Path(f.name)

            # Add temp file as input argument if not already specified
            if '--in' not in args and '-i' not in args and '--input' not in args:
                args = args + ['--in', str(temp_file)]

        # Capture stdout and stderr
        with capture_stdout_and_stderr() as (stdout_capture, stderr_capture):
            try:
                # Execute command in-process
                nef_app(args, standalone_mode=False)
                exit_code = 0
                success = True
            except SystemExit as e:
                exit_code = e.code if e.code is not None else 1
                success = exit_code == 0
            except Exception as e:
                # Unexpected error
                stderr_capture.write(f"Error: {e}\n")
                exit_code = 1
                success = False

        return {
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "exit_code": exit_code,
            "success": success,
        }

    finally:
        # Cleanup temporary file
        if temp_file and temp_file.exists():
            temp_file.unlink(missing_ok=True)
```

### Phase 3: Update MCP Server Tools

**File**: `nef_mcp_server.py` (MODIFY)

Add new MCP tools that use in-process execution.

#### Tool 1: nef_execute_command

```python
@mcp.tool()
def nef_execute_command(
    args: list[str],
    nef_input: str = "",
) -> dict[str, Any]:
    """
    Execute a NEF command in-process with captured output.

    args      - Command arguments (e.g., ["frames", "tabulate", "--show-all"])
    nef_input - NEF content as string (optional, will be passed via memory URL)

    Returns:
        {
            "stdout": str,       # Command output (usually NEF content)
            "stderr": str,       # Error messages
            "success": bool,
            "exit_code": int
        }

    Example:
        nef_execute_command(
            args=["frames", "tabulate", "--show-all"],
            nef_input=nef_content
        )

        # Equivalent to CLI: nef frames tabulate --show-all < input.nef
    """
    from nef_pipelines.lib.mcp_execution import execute_command_in_process

    result = execute_command_in_process(args, nef_input)

    return {
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "success": result["success"],
        "exit_code": result["exit_code"],
    }
```

#### Tool 2: nef_execute_pipeline

```python
@mcp.tool()
def nef_execute_pipeline(
    steps: list[list[str]],
    nef_input: str = "",
) -> dict[str, Any]:
    """
    Execute a pipeline of NEF commands in-process.

    steps     - list of command argument lists
    nef_input - initial NEF content (optional)

    Each step receives output from previous step as input.

    Returns:
        {
            "stdout": str,           # Final output
            "stderr": str,           # Accumulated errors
            "success": bool,
            "exit_code": int,
            "step_results": list     # Per-step status
        }

    Example:
        nef_execute_pipeline(
            steps=[
                ["chains", "clone", "--chain-code", "A", "--new-chain-code", "B"],
                ["frames", "tabulate", "--show-all"],
            ],
            nef_input=initial_nef
        )

        # Equivalent to CLI:
        # nef chains clone --chain-code A --new-chain-code B < input.nef | \\
        # nef frames tabulate --show-all
    """
    from nef_pipelines.lib.mcp_execution import execute_command_in_process

    step_results = []
    accumulated_stderr = []
    current_output = nef_input

    for i, args in enumerate(steps):
        result = execute_command_in_process(args, current_output)

        step_results.append({
            "step": i + 1,
            "args": args,
            "success": result["success"],
            "exit_code": result["exit_code"],
        })

        if result["stderr"]:
            accumulated_stderr.append(f"Step {i+1}: {result['stderr']}")

        if not result["success"]:
            return {
                "stdout": result["stdout"],
                "stderr": "\n".join(accumulated_stderr),
                "success": False,
                "exit_code": result["exit_code"],
                "step_results": step_results,
            }

        # Pass output to next step
        current_output = result["stdout"]

    return {
        "stdout": current_output,
        "stderr": "\n".join(accumulated_stderr) if accumulated_stderr else "",
        "success": True,
        "exit_code": 0,
        "step_results": step_results,
    }
```

#### Existing Tools (No Changes)

These tools remain unchanged and continue to work:
- `nef_get_command_help(pattern)` - Get help for commands
- `nef_get_readme()` - Get README content
- `nef_get_skill_file()` - Get skill file with examples

#### Legacy Tools (Keep for Compatibility)

Keep existing subprocess-based tools for backward compatibility:
- `nef_run_step()` - Single subprocess command
- `nef_run_pipeline()` - Chained subprocess pipeline

### Phase 6: Update MCP Instructions

Update FastMCP initialization in `nef_mcp_server.py`:

```python
mcp = FastMCP(
    "nef-pipelines",
    instructions=(
        "Tools for NEF NMR data pipelines with in-process execution.\n\n"

        "**CRITICAL: Start Here**\n"
        "1. Call nef_get_readme() for overview\n"
        "2. Call nef_get_skill_file() for expert guidance\n"
        "3. Call nef_get_command_help(pattern) for specific commands\n\n"

        "**In-Process Execution Workflow (RECOMMENDED):**\n"
        "1. nef_get_command_help(pattern) - get detailed help\n"
        "2. nef_execute_command(args, nef_input) - execute single command\n"
        "3. nef_execute_pipeline(steps, nef_input) - chain multiple commands\n\n"

        "**Key Concepts:**\n"
        "- Commands run in-process (no subprocess overhead)\n"
        "- Fast execution (~50-100x faster than subprocess)\n"
        "- NEF content passed as strings via temporary files\n"
        "- stdout captured and returned\n"
        "- Same CLI interface as human users\n\n"

        "**Command Format:**\n"
        "Use standard CLI argument lists:\n"
        "- ['frames', 'tabulate', '--show-all']\n"
        "- ['chains', 'clone', '--chain-code', 'A', '--new-chain-code', 'B']\n"
        "- ['shifts', 'average', '--frames', '*', '--frame-name', 'averaged']\n\n"

        "**Legacy Subprocess Tools (Still Available):**\n"
        "- nef_run_step() - single subprocess command\n"
        "- nef_run_pipeline() - chained subprocess pipeline\n"
        "Use these only if in-process execution has issues."
    ),
)
```

## Benefits

| Aspect | Subprocess | v1 (Temp Files) | v2+ (Memory URLs) |
|--------|-----------|----------------|-------------------|
| **Speed** | 50-100ms overhead | 5-20ms (disk I/O) | <1ms (in-memory) |
| **Memory** | Multiple processes | Single process | Single process |
| **Debugging** | stderr + exit codes | Python exceptions | Python exceptions |
| **Timeout** | Required (120s) | Not needed | Not needed |
| **PATH** | Must have `nef` command | No dependency | No dependency |
| **Development** | Needs NEF_COMMAND env | Works out of box | Works out of box |
| **Chaining** | stdin/stdout pipes | Python strings | Python strings |
| **Error Detail** | Limited (stderr) | Full stack traces | Full stack traces |
| **Implementation** | Done | Low risk | Requires file I/O changes |

## Implementation Steps (v1 - Simplified)

### Step 1: Create Stdout Capture Utility

1. Create `src/nef_pipelines/lib/stdout_capture.py`
2. Implement `capture_stdout()` context manager
3. Implement `capture_stdout_and_stderr()` context manager

### Step 2: Create In-Process Command Executor

1. Create `src/nef_pipelines/lib/mcp_execution.py`
2. Implement `execute_command_in_process()` function
   - Write NEF content to temporary file on disk
   - Call Typer command with file path
   - Capture stdout/stderr
   - Clean up temporary file

### Step 3: Update MCP Server

1. Add `nef_execute_command()` to `nef_mcp_server.py`
2. Add `nef_execute_pipeline()` to `nef_mcp_server.py`
3. Update MCP instructions to reflect temporary file approach
4. Keep legacy subprocess tools for compatibility

**No changes to existing file reading functions needed** - they work with normal file paths!

### Step 4: Testing

```python
# Test 1: Single command
result = nef_execute_command(
    args=["frames", "tabulate", "--show-all"],
    nef_input=TEST_NEF
)
assert result["success"]
assert result["exit_code"] == 0
assert "nef_molecular_system" in result["stdout"]

# Test 2: Pipeline
result = nef_execute_pipeline(
    steps=[
        ["chains", "clone", "--chain-code", "A", "--new-chain-code", "B"],
        ["frames", "tabulate", "--show-all"],
    ],
    nef_input=TEST_NEF
)
assert result["success"]
assert len(result["step_results"]) == 2
assert all(s["success"] for s in result["step_results"])

# Test 3: Error handling (invalid arguments)
result = nef_execute_command(
    args=["frames", "nonexistent-subcommand"],
    nef_input=TEST_NEF
)
assert not result["success"]
assert result["exit_code"] != 0
```

### Step 5: Performance Testing

```python
import time
import subprocess

# Subprocess baseline
start = time.time()
subprocess.run(
    ["nef", "frames", "tabulate"],
    input=TEST_NEF,
    capture_output=True,
    text=True
)
subprocess_time = time.time() - start

# In-process execution with temporary files
start = time.time()
nef_execute_command(
    args=["frames", "tabulate"],
    nef_input=TEST_NEF
)
inprocess_time = time.time() - start

print(f"Subprocess: {subprocess_time:.3f}s")
print(f"In-process: {inprocess_time:.3f}s")
print(f"Speedup: {subprocess_time / inprocess_time:.1f}x")

# Expected: 5-10x faster (subprocess overhead eliminated, but still uses disk I/O)
# Note: v2+ with memory:// URLs will be even faster (50-100x)
```

### Step 6: Documentation Update

Update `.claude/skills/nef.md`:

```markdown
## Using NEF Pipelines via MCP

### In-Process Execution (Recommended)

Execute commands in-process with in-memory I/O:

```python
# Single command
nef_execute_command(
    args=["frames", "tabulate", "--show-all"],
    nef_input=nef_content
)

# Pipeline
nef_execute_pipeline(
    steps=[
        ["chains", "clone", "--chain-code", "A", "--new-chain-code", "B"],
        ["frames", "delete", "--frame-selectors", "*distance*"],
        ["frames", "tabulate"],
    ],
    nef_input=initial_nef
)
```

### Command Format

Use standard CLI argument lists:
- `["frames", "tabulate", "--show-all"]`
- `["chains", "clone", "--chain-code", "A", "--new-chain-code", "B"]`
- `["shifts", "average", "--frames", "*", "--frame-name", "averaged"]`

### Available Commands

Use `nef_get_command_help(pattern)` to see available commands and their options.

Common tools:
- `frames` - Frame operations
- `chains` - Chain manipulation
- `shifts` - Chemical shift processing
- Transcoders for various NMR software formats
```

## Files to Create/Modify

### v1 - Temporary Files Approach

**New Files:**
- `src/nef_pipelines/lib/stdout_capture.py` - Stdout/stderr capture utilities
- `src/nef_pipelines/lib/mcp_execution.py` - In-process command executor using temp files

**Modified Files:**
- `nef_mcp_server.py` - Add 2 new MCP tools (nef_execute_command, nef_execute_pipeline)
- `.claude/skills/nef.md` - Update with in-process execution examples

**No changes needed:**
- `src/nef_pipelines/lib/nef_lib.py` - Works with normal file paths!

### v2+ - Memory URLs Approach (Future)

**Additional New Files:**
- `src/nef_pipelines/lib/memory_io.py` - Memory content registry

**Additional Modified Files:**
- `src/nef_pipelines/lib/nef_lib.py` - Add memory URL support to reading functions
- `src/nef_pipelines/lib/mcp_execution.py` - Switch from temp files to memory URLs

## Testing Strategy

### Unit Tests (v1 - Temporary Files)
```python
def test_execute_command_with_temp_files():
    from nef_pipelines.lib.mcp_execution import execute_command_in_process

    # Test simple command execution
    result = execute_command_in_process(
        args=["frames", "tabulate"],
        nef_input=TEST_NEF_CONTENT
    )

    assert result["success"]
    assert result["exit_code"] == 0
    assert len(result["stdout"]) > 0

    # Verify no temp files left behind
    import tempfile
    temp_dir = tempfile.gettempdir()
    nef_files = list(Path(temp_dir).glob("*.nef"))
    # Should be empty or only files from other processes
    # (our files should be cleaned up)
```

### Unit Tests (v2+ - Memory URLs)
```python
def test_memory_io_registration():
    from nef_pipelines.lib.memory_io import (
        register_memory_content,
        get_memory_content,
        is_memory_url,
        clear_memory_content
    )

    # Test registration
    content = "test NEF content"
    url = register_memory_content(content)
    assert is_memory_url(url)
    assert url.startswith("memory://")

    # Test retrieval
    retrieved = get_memory_content(url)
    assert retrieved == content

    # Test cleanup
    assert clear_memory_content(url)
    assert get_memory_content(url) is None


def test_memory_url_in_file_reading():
    from nef_pipelines.lib.memory_io import register_memory_content
    from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
    from pathlib import Path

    nef_content = """
    data_test
    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
    save_
    """

    # Register and read
    url = register_memory_content(nef_content)
    entry = read_entry_from_file_or_stdin_or_exit_error(Path(url))

    assert entry is not None
    assert "nef_molecular_system" in str(entry)


def test_in_process_command_execution():
    from nef_pipelines.lib.mcp_execution import execute_command_in_process

    nef_content = "..."  # Valid NEF content
    result = execute_command_in_process(
        args=["frames", "tabulate"],
        nef_input=nef_content
    )

    assert result["success"]
    assert result["exit_code"] == 0
    assert len(result["stdout"]) > 0
```

### Integration Tests
```bash
# Test via MCP Inspector
# 1. Start server: python nef_mcp_server.py
# 2. Open MCP Inspector
# 3. Test nef_execute_command() with test NEF
# 4. Test nef_execute_pipeline() with multi-step
# 5. Compare performance with subprocess tools
```

## Verification Checklist

- [ ] Memory I/O module created with registry and helpers
- [ ] In-process execution module handles commands correctly
- [ ] File reading functions support memory URLs
- [ ] `nef_execute_command()` executes successfully
- [ ] `nef_execute_pipeline()` chains commands correctly
- [ ] stdout/stderr captured correctly
- [ ] Exit codes propagate properly
- [ ] Memory cleanup works (no leaks)
- [ ] Performance is 50-100x faster than subprocess
- [ ] Existing file/stdin behavior unchanged
- [ ] MCP Inspector shows new tools
- [ ] Skill file updated with examples

## Migration Strategy

1. **Phase 1**: Deploy new tools alongside old ones
2. **Phase 2**: Update skill file to recommend new tools
3. **Phase 3**: Mark subprocess tools as deprecated
4. **Phase 4**: Keep subprocess tools for backward compatibility

## Future Enhancements (v2+)

### Memory-Based I/O (v2)

Replace temporary files with in-memory URLs for zero-disk I/O:

**Benefits:**
- 50-100x faster (no disk I/O overhead)
- No temporary file cleanup needed
- Better for high-frequency operations

**Implementation:**
1. Create `src/nef_pipelines/lib/memory_io.py`
   - Memory content registry (thread-local)
   - `register_memory_content(content) → "memory://uuid"`
   - `get_memory_content("memory://uuid") → content`
   - `is_memory_url(path) → bool`

2. Modify file reading functions in `nef_lib.py`:
   - `read_entry_from_file_or_stdin_or_exit_error()` (line 689)
   - `read_or_create_entry_exit_error_on_bad_file()` (line 734)
   - `read_entry_from_file_or_raise()` (line 704)
   - `read_file_or_exit()` (line 264)

3. Add memory URL check before file/stdin logic:
   ```python
   if file is not None and is_memory_url(file):
       content = get_memory_content(str(file))
       if content is None:
           exit_error(f"Memory content not found: {file}")
       return Entry.from_string(content)
   # Fallthrough to existing file/stdin logic
   ```

4. Update `execute_command_in_process()` to use memory URLs instead of temp files

**Migration path**: Keep temp file approach as fallback for compatibility

### Additional Future Features

- Support for output files (not just stdout)
- Support for multiple input files
- Streaming for very large NEF files
- Command composition helpers
- Performance profiling per command
- Caching mechanisms for repeated operations
- Thread pool for parallel pipeline execution

## Dependencies

- **pynmrstar**: Already in requirements (for Entry objects)
- **No new dependencies**: Uses existing NEF pipelines code

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Typer/sys.argv conflicts | Careful sys.argv save/restore in execution |
| stdout capture issues | Use proper context managers (redirect_stdout) |
| Memory leaks from registry | Implement cleanup after each command |
| Thread safety issues | Use threading.local for registry |
| Commands that write files | Handle normally, only capture stdout |
| Exit calls in commands | Catch SystemExit properly |

## Success Criteria (v1)

✅ Temporary file I/O works reliably
✅ All commands execute in-process successfully
✅ Performance 5-10x faster than subprocess (process overhead eliminated)
✅ stdout/stderr captured correctly
✅ Exit codes propagate properly
✅ No file descriptor leaks
✅ Temporary files cleaned up properly
✅ Error messages are clear and actionable
✅ Pipeline chaining works correctly
✅ MCP tools work in production

## Codebase Analysis Results (For v2+ Memory URLs)

### File Reading Operations Audit

A comprehensive exploration of the codebase identified all file reading operations for future memory URL implementation:

**Core findings**:
- **7 utility functions** in `nef_lib.py` handle NEF file reading
- **5 utility functions** in `util.py` handle general file I/O
- **25+ naked `open()` calls** in importers (for non-NEF formats like Sparky, Mars, NMRView)
- **2 critical entry points** route ~35 commands through them

**Architecture insight**: File reading is highly centralized in utility functions. When implementing v2+ memory URLs, updating 2-4 key functions will enable memory URL support for the majority of commands without needing to modify individual command implementations.

**Naked reads**: Importers that read non-NEF formats (peaks, shifts from other software) do direct `open()` calls. These are low priority for memory URL support since they're reading external format files.

**Key insight**: The centralized architecture makes in-memory URL support (v2+) a targeted, low-risk change affecting only utility functions, not command logic.

**Note for v1**: Temporary file approach requires NO changes to existing file reading functions - they work with normal file paths!

## Design Rationale

### Why Typer-Decorated Commands + File I/O vs Direct pipe() Calls?

**User's requirement**: "for the in process server i was still thinking of using the typer decorated commands and providing an in memory url that could be read, this would would require changing some of the basic low lying text reading routines but would keep the interfce for humands and the ai the same"

**Key benefits of this approach** (applies to both v1 temp files and v2+ memory URLs):

1. **Interface consistency**: Humans use `nef frames tabulate --show-all`, AI uses `["frames", "tabulate", "--show-all"]` - identical interface
2. **Full CLI features**: Gets all Typer features (validation, help, error messages) automatically
3. **No API surface changes**: Commands don't need modification or registration
4. **Easier maintenance**: Changes to CLI automatically reflected in MCP
5. **Lower risk**: Only modifying execution layer (v1) or low-level I/O (v2+), not command architecture
6. **Long-term flexibility**: Can switch to pipe() functions later for performance if needed

**v1 Temporary Files Advantage**:
- Zero code changes to file reading infrastructure
- Minimal implementation risk
- Faster time to deployment

**v2+ Memory URLs Advantage**:
- Maximum performance (50-100x faster)
- No disk I/O overhead
- No temporary file cleanup needed

**Alternative considered** (NOT chosen):
- Calling `pipe()` functions directly
- Would require building a command registry
- Would bypass CLI validation and features
- User indicated this is for "long term plan to have pipelines as a python library"

**Implementation strategy**:
- **v1**: Use temporary files on disk, capture stdout, keep commands unchanged
- **v2+**: Modify reading functions in `nef_lib.py` to accept memory URLs
- Keep all Typer-decorated commands unchanged across all versions
- Capture stdout for results instead of subprocess piping
