# Plugin-Based Architecture: Migrate to Entry Points

## Overview

Migrate NEF-Pipelines from hardcoded module list to Python entry points for plugin discovery. This enables external
extensibility while maintaining robust error handling.

## Current Architecture

**Flow:**
1. `main.py` imports modules from hardcoded list (lines 105-142) or `main_imports.py`
2. Each module's `__init__.py` self-registers with `nef_app.app.add_typer()`
3. Per-module try/except catches errors, collects warnings, continues with reduced functionality

**Problem:**
- Manual maintenance when adding plugins
- External packages cannot extend NEF-Pipelines
- Test needed to catch missing registrations

## Solution: Entry Points Plugin System

Use `importlib.metadata.entry_points()` for automatic plugin discovery.

**Benefits:**
- Standard Python mechanism (used by Flask, pytest, Sphinx)
- External packages can add plugins
- No hardcoded lists to maintain
- **Maintains same error handling robustness**

## Implementation Steps

### Step 1: Add Entry Points to setup.cfg

**File:** `setup.cfg`

Add under `[options.entry_points]` section (after console_scripts):

```ini
[options.entry_points]
console_scripts =
   nef = nef_pipelines.main:main

# NEF-Pipelines plugin entry points
nef_pipelines.tools =
    chains = nef_pipelines.tools.chains
    entry = nef_pipelines.tools.entry
    filter = nef_pipelines.tools.filter
    fit = nef_pipelines.tools.fit
    frames = nef_pipelines.tools.frames
    globals = nef_pipelines.tools.globals
    header = nef_pipelines.tools.header
    help = nef_pipelines.tools.help
    loops = nef_pipelines.tools.loops
    peaks = nef_pipelines.tools.peaks
    plot = nef_pipelines.tools.plot
    save = nef_pipelines.tools.save
    series = nef_pipelines.tools.series
    shifts = nef_pipelines.tools.shifts
    simulate = nef_pipelines.tools.simulate
    sink = nef_pipelines.tools.sink
    stream = nef_pipelines.tools.stream
    test = nef_pipelines.tools.test

nef_pipelines.transcoders =
    csv = nef_pipelines.transcoders.csv
    deep = nef_pipelines.transcoders.deep
    echidna = nef_pipelines.transcoders.echidna
    fasta = nef_pipelines.transcoders.fasta
    mars = nef_pipelines.transcoders.mars
    modelfree = nef_pipelines.transcoders.modelfree
    nmrpipe = nef_pipelines.transcoders.nmrpipe
    nmrstar = nef_pipelines.transcoders.nmrstar
    nmrview = nef_pipelines.transcoders.nmrview
    pales = nef_pipelines.transcoders.pales
    rcsb = nef_pipelines.transcoders.rcsb
    rpf = nef_pipelines.transcoders.rpf
    shifty = nef_pipelines.transcoders.shifty
    shiftx2 = nef_pipelines.transcoders.shiftx2
    sparky = nef_pipelines.transcoders.sparky
    talos = nef_pipelines.transcoders.talos
    ucbshift = nef_pipelines.transcoders.ucbshift
    xcamshift = nef_pipelines.transcoders.xcamshift
    xeasy = nef_pipelines.transcoders.xeasy
    xplor = nef_pipelines.transcoders.xplor
```

### Step 2: Update main.py Plugin Loading

**File:** `src/nef_pipelines/main.py`

Replace lines 102-149 (the hardcoded module loading) with:

```python
warnings = []
try:
    from importlib.metadata import entry_points

    # Load tool plugins
    for ep in entry_points(group='nef_pipelines.tools'):
        try:
            ep.load()
        except Exception:
            msg = f"plugin {ep.name} (from {ep.value})\n{format_exc()}"
            warnings.append((ep.name, msg))

    # Load transcoder plugins
    for ep in entry_points(group='nef_pipelines.transcoders'):
        try:
            ep.load()
        except Exception:
            msg = f"plugin {ep.name} (from {ep.value})\n{format_exc()}"
            warnings.append((ep.name, msg))

except Exception as e:
    msg = """\

         Initialisation error: failed to load plugins
         """
    do_exit_error(msg, e)
```

**Key points:**
- Maintains same per-plugin try/except pattern
- Same warnings collection mechanism
- Same `_report_warnings()` call later
- `ep.load()` does the module import

### Step 3: Remove main_imports.py

**File:** `src/nef_pipelines/main_imports.py`

**Option A (Recommended):** Delete the file entirely
- No longer needed since plugins declared in setup.cfg

**Option B:** Keep as documentation with header:
```python
"""
DEPRECATED: This file is no longer used.

Plugin registration has moved to setup.cfg entry points.
See [options.entry_points] section.

This file is kept for reference only.
"""
```

### Step 4: Update test_command_registration.py

**File:** `src/nef_pipelines/tests/test_command_registration.py`

Update `test_all_modules_with_commands_are_in_main()` to check entry points:

```python
def test_all_modules_with_commands_are_in_entry_points():
    """Verify that all tool and transcoder modules are declared as entry points in setup.cfg."""

    from importlib.metadata import entry_points

    # Get registered entry points
    tool_eps = {ep.value for ep in entry_points(group='nef_pipelines.tools')}
    transcoder_eps = {ep.value for ep in entry_points(group='nef_pipelines.transcoders')}

    registered_modules = tool_eps | transcoder_eps

    missing_from_entry_points = []

    for base_package, base_dir_name in [
        ("nef_pipelines.tools", "tools"),
        ("nef_pipelines.transcoders", "transcoders"),
    ]:
        base_dir = Path(__file__).parent.parent / base_dir_name

        for module_dir in base_dir.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue

            init_file = module_dir / "__init__.py"
            if not init_file.exists():
                continue

            imports = _get_imports_from_file(init_file)
            module_base = f"{base_package}.{module_dir.name}"

            # Check if this module has submodule imports (indicates it's a command group)
            if any(imp.startswith(module_base) for imp in imports):
                if module_base not in registered_modules:
                    missing_from_entry_points.append(module_base)

    if missing_from_entry_points:
        error_msg = (
            "The following modules are not declared as entry points in setup.cfg:\n  "
            + "\n  ".join(missing_from_entry_points)
        )
        error_msg += "\n\nAdd them to [options.entry_points] in setup.cfg under nef_pipelines.tools or nef_pipelines.transcoders"
        assert False, error_msg
```

### Step 5: Update CLAUDE.md Documentation

**File:** `CLAUDE.md`

Add new section after "Architecture Overview":

```markdown
## Plugin Architecture

NEF-Pipelines uses Python entry points (setuptools) for plugin discovery and loading.

### How Plugins Work

1. **Declaration**: Plugins declared in `setup.cfg` under `[options.entry_points]`
2. **Discovery**: At startup, `main.py` uses `importlib.metadata.entry_points()` to find plugins
3. **Loading**: Each plugin's `ep.load()` imports the module
4. **Registration**: Module's `__init__.py` calls `nef_app.app.add_typer()` to register commands

### Adding a New Internal Plugin

1. Create module in `src/nef_pipelines/tools/` or `src/nef_pipelines/transcoders/`
2. Add entry point to `setup.cfg`:
   ```ini
   [options.entry_points]
   nef_pipelines.tools =
       my_tool = nef_pipelines.tools.my_tool
   ```
3. Reinstall in dev mode: `pip install -e .`
4. Module's `__init__.py` should follow existing pattern (see tools/chains)

### External Plugins

Third-party packages can extend NEF-Pipelines:

```python
# In external package's setup.cfg
[options.entry_points]
nef_pipelines.tools =
    custom_analyzer = my_nef_package.analyzer
```

When installed alongside nef-pipelines, the custom command automatically appears.

### Error Handling

- Failed plugins are logged as warnings
- NEF continues with reduced functionality
- Working plugins remain available
```

Update existing "Plugin-based Architecture" section (line 57) to reference entry points instead of import in main.py.

## Critical Files to Modify

1. **`setup.cfg`** - Add entry point declarations
2. **`src/nef_pipelines/main.py`** - Replace module list with entry_points() calls
3. **`src/nef_pipelines/main_imports.py`** - Delete or deprecate
4. **`src/nef_pipelines/tests/test_command_registration.py`** - Update test to check entry points
5. **`CLAUDE.md`** - Add plugin documentation

## Verification Steps

### 1. Initial Setup
```bash
# Add entry points to setup.cfg (Step 1)
# Update main.py (Step 2)
# Reinstall package in development mode
pip install -e .
```

### 2. Basic Functionality Test
```bash
# Check all commands appear
nef --help

# Test a few commands
nef chains --help
nef sparky export shifts --help
nef frames list --help
```

### 3. Run Tests
```bash
# Test that entry points are checked
pytest src/nef_pipelines/tests/test_command_registration.py -xvs

# Run full test suite
pytest src/nef_pipelines/tests/ -x
```

### 4. Test Error Handling (Optional)
```bash
# Temporarily break a plugin entry point in setup.cfg
# Change: chains = nef_pipelines.tools.chains
# To:     chains = nef_pipelines.tools.broken_module

# Reinstall
pip install -e .

# Run nef - should show warning but continue
nef --help

# Revert the change
```

### 5. Verify External Plugin Support
```bash
# Create test external package (optional advanced test)
# Verify it can register via entry points
```

## Migration Benefits

1. **Maintainability**: No manual list to maintain
2. **Extensibility**: External packages can add plugins
3. **Standard**: Uses established Python packaging patterns
4. **Testable**: test_command_registration validates completeness
5. **Robust**: Same error handling as current approach
6. **Discoverable**: `pip show nef-pipelines` shows all entry points

## Rollback Plan

If issues arise:
1. Revert main.py changes
2. Restore use of main_imports.py
3. Keep entry points in setup.cfg (they don't hurt)
4. Entry points can coexist with old approach during transition
