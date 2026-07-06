# Plan: Persistent Sandbox Preference via TOML Storage

Add persistent sandbox directory preference management with **dual interfaces**:
1. **CLI command**: `nef ai sandbox` for terminal users
2. **MCP tool**: `nef_sandbox_preference()` for AI sessions

The preference is stored in a TOML file and takes precedence over environment variables but can be overridden by command-line options.

## Changes From User Comments

1. ✅ **Function-based API** - `toml_storage.py` uses functions, not a class
2. ✅ **Location** - Preference code in `sandbox_lib.py` (not `sandbox_preference.py`), alongside `mcp_lib.py`
3. ✅ **CLI structure** - Command in standalone `sandbox.py` file, imported by `__init__.py`
4. ✅ **MCP clarification** - AI has NO control over CURRENT session. MCP tool sets preference for FUTURE sessions only. User can ask AI to show sandbox picker (`nef_change_sandbox`) to override current session. Runtime `--sandbox-path` also overrides preference for that session.
5. ✅ **Warning added** - Server warns when persistent preference overrides environment variable, including filename: `"(Note: NEF_MCP_SANDBOX=... is set but overridden by saved preference in the file <FILE-NAME>)"`
6. ✅ **No docs needed** - Self-documenting via docstrings (removed Stage 5 documentation)
7. ✅ **Test conventions** - Using EXPECTED result comparison pattern

## Goals

1. Allow users to set a persistent default sandbox directory
2. Provide both CLI and MCP interfaces for managing preferences
3. Store preference in a well-defined, cross-platform location
4. Integrate with existing sandbox resolution logic in `server.py`
5. Provide commands to set, get, and clear the preference
6. Maintain Python 3.9+ compatibility

## Priority Order (after implementation)

When starting `nef ai server`:

1. **--sandbox-path** command-line option (highest priority)
2. **Persistent TOML preference** (NEW - this plan)
3. **NEF_MCP_SANDBOX** environment variable
4. **Temporary directory** (lowest priority, fallback)

## Usage Examples

### Terminal (CLI Command)
```bash
# Set persistent sandbox
nef ai sandbox set /Users/me/nef-work

# Check current preference
nef ai sandbox get

# Clear preference
nef ai sandbox clear
```

### AI Session (MCP Tool)
```python
# Set persistent sandbox
nef_sandbox_preference("set", "/Users/me/nef-work")

# Check current preference
nef_sandbox_preference("get")

# Clear preference
nef_sandbox_preference("clear")
```

## Implementation Steps

### **Stage 1: TOML Storage Module**

Create `src/nef_pipelines/lib/toml_storage.py` with **function-based API** (simpler than class):

```python
"""
TOML-based configuration storage for NEF-Pipelines.

Provides simple functions for persisting user preferences across sessions.
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Handle Python 3.9/3.10 vs 3.11+ compatibility
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # pip install tomli
    except ImportError:
        tomllib = None  # Graceful degradation

try:
    import tomli_w  # pip install tomli-w
except ImportError:
    tomli_w = None  # Graceful degradation


def _get_config_path() -> Path:
    """Get platform-specific configuration directory."""
    if sys.platform == "darwin":
        # macOS: ~/Library/Application Support/nef-pipelines
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        # Windows: %APPDATA%/nef-pipelines
        appdata = os.getenv("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    else:
        # Linux/Unix: ~/.config/nef-pipelines
        base = Path.home() / ".config"

    return base / "nef-pipelines"


def get_config_file_path(filename: str = "config.toml") -> Path:
    """
    Get the full path to a config file.

    Args:
        filename: Name of the TOML file (default: config.toml)

    Returns:
        Absolute path to the config file
    """
    path  = _get_config_path() / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_toml_config(filename: str = "config.toml") -> Dict[str, Any]:
    """
    Load configuration from TOML file.

    Args:
        filename: Name of the TOML file

    Returns:
        Dictionary of configuration values, empty dict if file doesn't exist
        or TOML libraries not available.
    """
    if tomllib is None:
        return {}

    path = get_config_file_path(filename)
    if not path.exists():
        return {}

    with open(path, "rb") as f:
        return tomllib.load(f)


def save_toml_config(data: Dict[str, Any], filename: str = "config.toml") -> bool:
    """
    Save configuration to TOML file.

    Args:
        data: Dictionary to serialize to TOML
        filename: Name of the TOML file

    Returns:
        True if saved successfully, False if TOML writer not available
    """
    if tomli_w is None:
        return False

    path = get_config_file_path(filename)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)

    return True


def get_toml_value(key: str, default: Any = None, filename: str = "config.toml") -> Any:
    """Get a configuration value."""
    config = load_toml_config(filename)
    return config.get(key, default)


def set_toml_value(key: str, value: Any, filename: str = "config.toml") -> bool:
    """Set a configuration value."""
    config = load_toml_config(filename)
    config[key] = value
    return save_toml_config(config, filename)


def delete_toml_value(key: str, filename: str = "config.toml") -> bool:
    """Delete a configuration key."""
    config = load_toml_config(filename)
    if key in config:
        del config[key]
        return save_toml_config(config, filename)
    return True


def clear_toml_config(filename: str = "config.toml") -> bool:
    """Clear all configuration."""
    path = get_config_file_path(filename)
    if path.exists():
        path.unlink()
    return True
```

**Dependencies to add:**
- `pyproject.toml`: Add `tomli ; python_version < "3.11"` and `tomli-w` to dependencies

### **Stage 2: Sandbox Preference Management**

Create `src/nef_pipelines/tools/ai/sandbox_lib.py` (alongside `mcp_lib.py` and `server.py`):

```python
"""
Persistent sandbox preference management for NEF-Pipelines MCP server.

Provides functions to manage default sandbox directory that persists across sessions.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nef_pipelines.lib.toml_storage import (
    get_config_file_path,
    get_toml_value,
    set_toml_value,
    delete_toml_value,
)

SANDBOX_KEY = "mcp_sandbox_path"


@dataclass
class SandboxPreferenceResult:
    """Result of sandbox preference operations."""

    success: bool = False
    path: str = ""
    error: str = ""
    message: str = ""
    config_location: str = ""


def get_sandbox_preference() -> Optional[Path]:
    """
    Get the stored sandbox preference.

    Returns:
        Path object if preference exists and is valid, None otherwise
    """
    path_str = get_toml_value(SANDBOX_KEY)

    if path_str:
        try:
            path = Path(path_str).expanduser().resolve()
            if path.exists() and path.is_dir():
                return path
        except (ValueError, OSError):
            pass

    return None


def set_sandbox_preference(path: str) -> SandboxPreferenceResult:
    """
    Set the sandbox preference.

    Args:
        path: Directory path to use as default sandbox

    Returns:
        SandboxPreferenceResult with success status and details
    """
    config_file = get_config_file_path()

    try:
        sandbox_path = Path(path).expanduser().resolve()

        # Validate path
        if not sandbox_path.exists():
            return SandboxPreferenceResult(
                success=False,
                error=f"Path does not exist: {sandbox_path}",
                config_location=str(config_file),
            )

        if not sandbox_path.is_dir():
            return SandboxPreferenceResult(
                success=False,
                error=f"Path is not a directory: {sandbox_path}",
                config_location=str(config_file),
            )

        # Save preference
        success = set_toml_value(SANDBOX_KEY, str(sandbox_path))

        if not success:
            return SandboxPreferenceResult(
                success=False,
                error="TOML writer not available (tomli-w not installed)",
                config_location=str(config_file),
            )

        return SandboxPreferenceResult(
            success=True,
            path=str(sandbox_path),
            message=f"Sandbox preference set to: {sandbox_path}",
            config_location=str(config_file),
        )

    except Exception as e:
        return SandboxPreferenceResult(
            success=False,
            error=f"Failed to set preference: {e}",
            config_location=str(config_file),
        )


def get_sandbox_preference_info() -> SandboxPreferenceResult:
    """
    Get information about the current sandbox preference.

    Returns:
        SandboxPreferenceResult with current preference or message if not set
    """
    config_file = get_config_file_path()
    path = get_sandbox_preference()

    if path:
        return SandboxPreferenceResult(
            success=True,
            path=str(path),
            message=f"Current sandbox preference: {path}",
            config_location=str(config_file),
        )
    else:
        path_str = get_toml_value(SANDBOX_KEY)
        if path_str:
            return SandboxPreferenceResult(
                success=False,
                path=path_str,
                error=f"Stored path is invalid or doesn't exist: {path_str}",
                config_location=str(config_file),
            )
        else:
            return SandboxPreferenceResult(
                success=True,
                message="No sandbox preference set",
                config_location=str(config_file),
            )


def clear_sandbox_preference() -> SandboxPreferenceResult:
    """
    Clear the sandbox preference.

    Returns:
        SandboxPreferenceResult indicating success
    """
    config_file = get_config_file_path()

    try:
        success = delete_toml_value(SANDBOX_KEY)

        if not success:
            return SandboxPreferenceResult(
                success=False,
                error="TOML writer not available (tomli-w not installed)",
                config_location=str(config_file),
            )

        return SandboxPreferenceResult(
            success=True,
            message="Sandbox preference cleared",
            config_location=str(config_file),
        )

    except Exception as e:
        return SandboxPreferenceResult(
            success=False,
            error=f"Failed to clear preference: {e}",
            config_location=str(config_file),
        )
```

### **Stage 3A: CLI Command**

Create `src/nef_pipelines/tools/ai/sandbox.py` (standalone file):

```python
"""
CLI command for managing persistent sandbox preference.
"""
from typing import Optional

import typer

from nef_pipelines.tools.ai import ai_app


@ai_app.command(name="sandbox")
def sandbox_cli(
    action: str = typer.Argument(
        ...,
        help="Action to perform: set, get, or clear"
    ),
    path: Optional[str] = typer.Argument(
        None,
        help="Directory path (required for 'set' action)"
    ),
):
    """- manage persistent sandbox directory preference"""
    from nef_pipelines.tools.ai.sandbox_lib import (
        set_sandbox_preference,
        get_sandbox_preference_info,
        clear_sandbox_preference,
    )

    action = action.lower().strip()

    if action == "set":
        if not path:
            typer.echo("Error: Path required for 'set' action", err=True)
            raise typer.Exit(1)
        result = set_sandbox_preference(path)
    elif action == "get":
        result = get_sandbox_preference_info()
    elif action == "clear":
        result = clear_sandbox_preference()
    else:
        typer.echo(f"Error: Unknown action '{action}'. Valid: set, get, clear", err=True)
        raise typer.Exit(1)

    if result.error:
        typer.echo(f"Error: {result.error}", err=True)
        if result.config_location:
            typer.echo(f"Config: {result.config_location}", err=True)
        raise typer.Exit(1)

    typer.echo(result.message)
    if result.path and action == "get":
        typer.echo(f"Path: {result.path}")
    if result.config_location:
        typer.echo(f"Config: {result.config_location}")
```

Update `src/nef_pipelines/tools/ai/__init__.py` to import the command:

```python
# ...existing imports...
from nef_pipelines.tools.ai import sandbox  # noqa: F401
```

**Usage Examples:**
```bash
# Set persistent sandbox
nef ai sandbox set /Users/me/nef-work

# Get current preference
nef ai sandbox get

# Clear preference
nef ai sandbox clear
```

### **Stage 3B: MCP Command Integration**

**Note:** The MCP server does NOT control sandbox configuration. If a sandbox is set via `--sandbox-path` at runtime, it overrides the persistent preference for that session only.

Add to `src/nef_pipelines/tools/ai/mcp_commands.py`:

```python
from nef_pipelines.tools.ai.sandbox_lib import (
    SandboxPreferenceResult,
    set_sandbox_preference,
    get_sandbox_preference_info,
    clear_sandbox_preference,
)

@mcp_tool
def nef_sandbox_preference(
    action: str,
    path: str = "",
) -> SandboxPreferenceResult:
    """
    Manage persistent sandbox directory preference.

    The preference sets the default sandbox for future sessions.
    It takes priority over the environment variable but can be
    overridden by --sandbox-path option when starting the server.

    IMPORTANT: The AI has NO control over the CURRENT session's sandbox.
    This command sets the preference for FUTURE sessions only.

    To change the current session's sandbox, the user must ask the AI to
    show the sandbox picker (nef_change_sandbox), which overrides the
    current sandbox if successful. The runtime --sandbox-path option also
    overrides the preference for that specific session.

    Args:
        action: Action to perform: 'set', 'get', or 'clear'
        path: Directory path (required for 'set' action)

    Returns:
        SandboxPreferenceResult with operation status and details

    Examples:
        nef_sandbox_preference("set", "/Users/me/nef-work")
        nef_sandbox_preference("get")
        nef_sandbox_preference("clear")
    """
    action = action.lower().strip()

    if action == "set":
        if not path:
            return SandboxPreferenceResult(
                success=False,
                error="Path required for 'set' action",
            )
        return set_sandbox_preference(path)

    elif action == "get":
        return get_sandbox_preference_info()

    elif action == "clear":
        return clear_sandbox_preference()

    else:
        return SandboxPreferenceResult(
            success=False,
            error=f"Unknown action '{action}'. Valid actions: set, get, clear",
        )
```

### **Stage 4: Integrate with Server Startup**

Update `src/nef_pipelines/tools/ai/server.py` in `_get_sandbox_path()`:

**Key changes:**
- Check persistent preference between CLI arg and env var
- Warn when persistent preference overrides (hides) env variable

```python
def _get_sandbox_path(path_arg: Optional[str]) -> SandboxPathResult:
    """
    Determine the sandbox path from (in priority order):
    1. --sandbox-path command line argument
    2. Persistent TOML preference
    3. NEF_MCP_SANDBOX environment variable
    4. Temporary directory (fallback)
    """
    warning = None

    # 1. Command line takes priority
    if path_arg is not None:
        try:
            sandbox = Path(path_arg).resolve()
            if not sandbox.exists():
                warning = f"Specified {NEF_MCP_SANDBOX_PATH_OPTION} does not exist: {sandbox}"
            elif not sandbox.is_dir():
                warning = f"Specified {NEF_MCP_SANDBOX_PATH_OPTION} is not a directory: {sandbox}"
            else:
                return SandboxPathResult(
                    path=sandbox, path_source=f"{NEF_MCP_SANDBOX_PATH_OPTION} option"
                )
        except Exception as e:
            warning = f"Invalid {NEF_MCP_SANDBOX_PATH_OPTION} argument: {e}"

    # 2. Check persistent preference (NEW)
    from nef_pipelines.tools.ai.sandbox_lib import get_sandbox_preference
    from nef_pipelines.lib.toml_storage import get_config_file_path

    pref_path = get_sandbox_preference()
    if pref_path:
        # Check if we're hiding an environment variable
        env_path = os.environ.get(NEF_MCP_SANDBOX_ENV_VAR_NAME)
        env_warning = ""
        if env_path and not warning:
            config_file = get_config_file_path()
            env_warning = f" (Note: {NEF_MCP_SANDBOX_ENV_VAR_NAME}={env_path} is set but overridden by saved preference in the file {config_file})"

        if warning:
            warning += f" — falling back to saved preference: {pref_path}{env_warning}"
        else:
            warning = env_warning if env_warning else None

        return SandboxPathResult(
            path=pref_path,
            warning=warning,
            path_source="saved preference (use 'nef ai sandbox' to change)",
        )

    # 3. Check environment variable
    env_path = os.environ.get(NEF_MCP_SANDBOX_ENV_VAR_NAME)
    if env_path:
        try:
            sandbox = Path(env_path).resolve()
            if sandbox.exists() and sandbox.is_dir():
                if warning:
                    warning += f" — falling back to {NEF_MCP_SANDBOX_ENV_VAR_NAME}: {sandbox}"
                return SandboxPathResult(
                    path=sandbox,
                    warning=warning,
                    path_source=f"{NEF_MCP_SANDBOX_ENV_VAR_NAME} environment variable",
                )
        except Exception:
            pass

    # 4. Signal that a temporary directory is needed
    return SandboxPathResult(warning=warning, is_temp=True)
```

### **Stage 5: Documentation Updates**

**No MCP resource documentation changes needed** - The MCP tool `nef_sandbox_preference()` is self-documenting via its docstring and will appear in tool listings automatically.

**CLI documentation** via `--help` is automatic from the command definition.



### **Stage 6A: Testing - Core Functionality**

Create `src/nef_pipelines/tests/ai/test_sandbox_lib.py`:

```python
"""Tests for persistent sandbox preference system."""
from pathlib import Path

import pytest

from nef_pipelines.lib import toml_storage
from nef_pipelines.tools.ai.sandbox_lib import (
    SANDBOX_KEY,
    SandboxPreferenceResult,
    clear_sandbox_preference,
    get_sandbox_preference,
    get_sandbox_preference_info,
    set_sandbox_preference,
)


@pytest.fixture
def temp_config_dir(monkeypatch, tmp_path):
    """Redirect config storage to temp directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    def mock_get_config_path():
        return config_dir

    monkeypatch.setattr(
        toml_storage,
        "_get_config_path",
        mock_get_config_path,
    )

    return config_dir


def test_set_sandbox_preference_success(temp_config_dir, tmp_path):
    """Test setting a valid sandbox preference."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    result = set_sandbox_preference(str(sandbox))

    EXPECTED = SandboxPreferenceResult(
        success=True,
        path=str(sandbox),
        message=f"Sandbox preference set to: {sandbox}",
        config_location=result.config_location,
    )
    assert result == EXPECTED


def test_set_sandbox_preference_nonexistent(temp_config_dir, tmp_path):
    """Test setting preference to nonexistent path fails."""
    nonexistent = tmp_path / "does_not_exist"

    result = set_sandbox_preference(str(nonexistent))

    assert not result.success
    assert "does not exist" in result.error.lower()


def test_set_sandbox_preference_not_directory(temp_config_dir, tmp_path):
    """Test setting preference to file fails."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")

    result = set_sandbox_preference(str(file_path))

    assert not result.success
    assert "not a directory" in result.error.lower()


def test_get_sandbox_preference_when_set(temp_config_dir, tmp_path):
    """Test getting preference after it's been set."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    set_sandbox_preference(str(sandbox))
    retrieved = get_sandbox_preference()

    assert retrieved == sandbox


def test_get_sandbox_preference_when_not_set(temp_config_dir):
    """Test getting preference when none is set."""
    retrieved = get_sandbox_preference()

    assert retrieved is None


def test_get_sandbox_preference_info(temp_config_dir, tmp_path):
    """Test getting preference info."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Not set
    result = get_sandbox_preference_info()
    assert result.success
    assert "no" in result.message.lower() or "not set" in result.message.lower()

    # After setting
    set_sandbox_preference(str(sandbox))
    result = get_sandbox_preference_info()

    EXPECTED = SandboxPreferenceResult(
        success=True,
        path=str(sandbox),
        message=f"Current sandbox preference: {sandbox}",
        config_location=result.config_location,
    )
    assert result == EXPECTED


def test_clear_sandbox_preference(temp_config_dir, tmp_path):
    """Test clearing preference."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    set_sandbox_preference(str(sandbox))
    assert get_sandbox_preference() is not None

    result = clear_sandbox_preference()

    EXPECTED = SandboxPreferenceResult(
        success=True,
        message="Sandbox preference cleared",
        config_location=result.config_location,
    )
    assert result == EXPECTED
    assert get_sandbox_preference() is None


def test_preference_persists_across_calls(temp_config_dir, tmp_path):
    """Test that preference persists across function calls."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Set
    set_sandbox_preference(str(sandbox))

    # Retrieve
    retrieved = get_sandbox_preference()

    assert retrieved == sandbox
```

### **Stage 6B: Testing - CLI Command**

Create `src/nef_pipelines/tests/ai/test_sandbox_cli.py`:

```python
"""Tests for the nef ai sandbox CLI command."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nef_pipelines.lib import toml_storage
from nef_pipelines.tools.ai import ai_app


@pytest.fixture
def temp_config_dir(monkeypatch, tmp_path):
    """Redirect config storage to temp directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    def mock_get_config_path():
        return config_dir

    monkeypatch.setattr(
        toml_storage,
        "_get_config_path",
        mock_get_config_path,
    )

    return config_dir


def test_sandbox_cli_set(temp_config_dir, tmp_path):
    """Test setting sandbox via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    runner = CliRunner()
    result = runner.invoke(ai_app, ["sandbox", "set", str(sandbox)])

    assert result.exit_code == 0
    assert "set to" in result.stdout.lower()
    assert str(sandbox) in result.stdout


def test_sandbox_cli_set_nonexistent(temp_config_dir, tmp_path):
    """Test setting nonexistent path fails."""
    nonexistent = tmp_path / "does_not_exist"

    runner = CliRunner()
    result = runner.invoke(ai_app, ["sandbox", "set", str(nonexistent)])

    assert result.exit_code == 1
    assert "does not exist" in result.stdout.lower()


def test_sandbox_cli_set_no_path(temp_config_dir):
    """Test set without path fails."""
    runner = CliRunner()
    result = runner.invoke(ai_app, ["sandbox", "set"])

    assert result.exit_code != 0
    assert "required" in result.stdout.lower() or "missing argument" in result.stdout.lower()


def test_sandbox_cli_get_when_set(temp_config_dir, tmp_path):
    """Test getting preference via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    runner = CliRunner()
    # Set first
    set_result = runner.invoke(ai_app, ["sandbox", "set", str(sandbox)])
    assert set_result.exit_code == 0

    # Get
    result = runner.invoke(ai_app, ["sandbox", "get"])

    assert result.exit_code == 0
    assert str(sandbox) in result.stdout


def test_sandbox_cli_get_when_not_set(temp_config_dir):
    """Test getting preference when not set."""
    runner = CliRunner()
    result = runner.invoke(ai_app, ["sandbox", "get"])

    assert result.exit_code == 0
    assert "no" in result.stdout.lower() or "not set" in result.stdout.lower()


def test_sandbox_cli_clear(temp_config_dir, tmp_path):
    """Test clearing preference via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    runner = CliRunner()
    # Set first
    set_result = runner.invoke(ai_app, ["sandbox", "set", str(sandbox)])
    assert set_result.exit_code == 0

    # Clear
    result = runner.invoke(ai_app, ["sandbox", "clear"])

    assert result.exit_code == 0
    assert "cleared" in result.stdout.lower()

    # Verify cleared
    result = runner.invoke(ai_app, ["sandbox", "get"])
    assert "no" in result.stdout.lower() or "not set" in result.stdout.lower()


def test_sandbox_cli_invalid_action(temp_config_dir):
    """Test invalid action fails."""
    runner = CliRunner()
    result = runner.invoke(ai_app, ["sandbox", "invalid"])

    assert result.exit_code == 1
    assert "unknown action" in result.stdout.lower()
```

## Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ...existing dependencies...
    'tomli ; python_version < "3.11"',
    'tomli-w',
]
```

## Success Criteria

1. ✅ Users can set persistent sandbox preference via:
   - CLI command: `nef ai sandbox set <path>`
   - MCP tool: `nef_sandbox_preference("set", path)` (sets PREFERENCE for future sessions; AI has NO control over current session)
2. ✅ Preference stored in platform-appropriate config directory (function-based API, no classes)
3. ✅ Preference survives server restarts
4. ✅ Priority order: CLI option > preference > env var > temp dir
5. ✅ Warning displayed when preference hides environment variable (including config filename)
6. ✅ Current session can be changed via sandbox picker (`nef_change_sandbox`) when user asks AI
7. ✅ Runtime `--sandbox-path` overrides preference for that session
8. ✅ Users can query current preference from CLI or MCP
9. ✅ Users can clear preference from CLI or MCP
10. ✅ Graceful degradation if TOML libraries missing
11. ✅ All tests pass using EXPECTED result comparison pattern
12. ✅ No new documentation files needed (self-documenting via docstrings)

## File Structure Summary

**New Files:**
- `src/nef_pipelines/lib/toml_storage.py` - Function-based TOML config API
- `src/nef_pipelines/tools/ai/sandbox_lib.py` - Sandbox preference management
- `src/nef_pipelines/tools/ai/sandbox.py` - CLI command
- `src/nef_pipelines/tests/ai/test_sandbox_lib.py` - Core tests
- `src/nef_pipelines/tests/ai/test_sandbox_cli.py` - CLI tests

**Modified Files:**
- `src/nef_pipelines/tools/ai/__init__.py` - Import sandbox command
- `src/nef_pipelines/tools/ai/mcp_commands.py` - Add `nef_sandbox_preference()` MCP tool
- `src/nef_pipelines/tools/ai/server.py` - Integrate preference into `_get_sandbox_path()`
- `pyproject.toml` - Add tomli/tomli-w dependencies

## Benefits

- **Dual Interface**: Works from both terminal (CLI) and AI sessions (MCP tool)
- **User convenience**: Set once, use everywhere
- **Professional UX**: No need to remember paths or set environment variables
- **Platform-aware**: Uses OS-appropriate config locations
- **Non-intrusive**: Doesn't break existing workflows, just adds convenience
- **Discoverable**:
  - Users can find it via `nef ai --help`
  - AI can suggest the MCP tool during sessions

## Migration Notes

- Existing users unaffected (no breaking changes)
- Environment variable still works (lower priority than preference)
- Command-line option still highest priority
- Temporary fallback still available
