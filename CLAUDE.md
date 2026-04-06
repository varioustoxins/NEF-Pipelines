
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NEF-Pipelines is a Python package for manipulating NEF (NMR Exchange Format) files. It provides command-line tools for converting between NEF and various NMR software formats (nmrview, sparky, mars, xplor, etc.) and for manipulating NEF file components like molecular chains, frames, and spectra.

## Development Commands

### IMPORTANT: Use `nefl` for Local Development
**Always use `nefl` (not `nef`) when testing or running commands during development.**
- `nefl` runs the local development version from `src/`
- `nef` runs the installed version which may be stale

### Testing
```bash
# PREFERRED: Run tests with nefl (uses local development version)
nefl test src/nef_pipelines/tests/entry/test_tree.py

# Run specific test
nefl test src/nef_pipelines/tests/entry/test_tree.py::test_tree_basic
```

### Running Commands During Development
```bash
# ALWAYS use nefl for testing commands locally
nefl entry tree file.nef
nefl entry tree file.nef molecular --colour-policy plain

# NOT: nef entry tree file.nef  (this uses installed version)
```

### Building
```bash
# Build the package
tox -e build

# Clean build artifacts
tox -e clean
```

### Documentation
```bash
# Build documentation
tox -e docs

# Check for broken links in docs
tox -e linkcheck

# Run doctests
tox -e doctests
```

### Installation
```bash
# Install in development mode with dependencies
pip install -e .

# Install with requirements
pip install -r requirements.txt
```

## Architecture Overview

### Plugin-based Architecture
The application uses a hierarchical command structure built on Typer. Commands self-register through module imports in `main.py:78-114`. The main entry point creates a Typer app and imports all tool and transcoder modules.

### Core Components

**Entry Point**: `src/nef_pipelines/main.py` - Creates the Typer app and dynamically imports all command modules

**Tools** (`src/nef_pipelines/tools/`):
- Core NEF file manipulation (chains, frames, headers, peaks, shifts)
- Data processing utilities (fit, simulate, series)
- Stream processing (sink, stream)

**Transcoders** (`src/nef_pipelines/transcoders/`):
- Format conversion modules for different NMR software
- Each transcoder handles import/export for specific file formats
- Examples: nmrview, sparky, mars, xplor, talos, etc.

**Libraries** (`src/nef_pipelines/lib/`):
- Core data structures and utilities
- NEF file parsing and manipulation
- Translation layer for chemical component handling
- Test utilities and common functionality

### Data Flow
1. Commands read NEF files or foreign format files
2. Data flows through a pipeline architecture using streams
3. Transcoders convert between NEF and external formats
4. Tools manipulate NEF data structures
5. Output can be NEF files or format-specific files

### Key Data Structures
- NEF saveframes for different data types (molecular_system, peaks, shifts, etc.)
- Chemical component definitions in `src/nef_pipelines/data/chem_comp/`
- Experiment definitions in `src/nef_pipelines/lib/experiments/data/`

## Testing Strategy

- Test files organized by component in `src/nef_pipelines/tests/`
- Each transcoder and tool has dedicated test modules
- Test data in `src/nef_pipelines/tests/test_data/`
- Uses pytest with mock fixtures defined in `conftest.py`
- When debugging tests _NEVER_ modify existing test files in test_data directories always ask me to do it myself

### MANDATORY Testing Guidelines (ALWAYS enforce these automatically)

**When writing or modifying ANY test code, Claude MUST automatically:**

1. **NEVER use bare asserts for NEF content** - Do not use `assert "some text" in result.stdout` unless told otherwise
2. **ALWAYS use EXPECTED_ constants** - All expected strings named with EXPECTED_ prefix in UPPER_SNAKE_CASE for text output from output NEF text
3. **ALWAYS use assert_lines_match()** - For NEF content comparison: `assert_lines_match(EXPECTED_STRING, actual_content)`
4. **ALWAYS use isolate_loop()** - For NEF loops: `isolate_loop(content, frame_name, loop_name)`
5. **ALWAYS test complete structures** - Use complete NEF frames/loops, not partial string matching
6. **ALWAYS use path_in_test_data()** - Use `path_in_test_data(filename, __file__)` to locate test data files, never hardcode paths
7. **NEVER skip tests for missing test data** - Tests must FAIL (not skip) if required test data files are missing
8. **ALWAYS use temporary directories for output** - Test output files must be written to temporary directories (use pytest's `tmp_path` fixture), never to the working directory or test data directories

These are non-negotiable requirements, not suggestions. Apply them automatically without asking unless told otherwise.

## Package Structure

The package follows PyScaffold conventions with src-layout:
- Source code in `src/nef_pipelines/`
- Tests co-located with source
- Configuration in `pyproject.toml` and `setup.py`
- Documentation source in `docs/`

## Comment Strategy

- Always add doc strings to functions / methods etc
- Do not add inline comments to the code you write apart from doc strings, unless asked to, or if the code is complex and requires additional context.

## Code Style

- Functions should have a single return statement at the end when possible

## Code Organization Pattern

### Command Structure
NEF-Pipelines follows a consistent pattern for organizing commands:

1. **Typer-decorated function**: Handles CLI interface, argument parsing, and file I/O
2. **Worker function**: Contains the core business logic, accepts pure Python objects
3. **Separation of concerns**: CLI functions delegate work to pure Python functions

Example pattern:
```python
@nef_app.app.command()
def command_name(
    input_file: Path = typer.Option(...),
    # other CLI options
):
    """CLI command docstring"""
    # Handle file I/O and CLI concerns
    entry = read_or_create_entry_exit_error_on_bad_file(input_file)

    # Delegate to worker function
    result = worker_function(entry, other_params)

    # Handle output
    print(result)

def worker_function(entry: Entry, other_params):
    """Pure Python function that does the actual work"""
    # Business logic here
    return result
```

This pattern allows commands to be:
- Called from CLI: `nef command_name [options]`
- Called from Python: `worker_function(entry, params)`
- Easily tested at both CLI and function level
- Reused by other Python code

### Recent Implementation: Explode Tool Refactoring
The `explode` tool was recently refactored to follow this pattern:
- `explode()`: Typer-decorated CLI function handling file I/O and argument parsing
- `pipe()`: Worker function containing core exploding logic
- Added `_sort_back_ticks()`: Helper function for handling CCPN backtick notation
- All functions follow minimal commenting strategy with docstrings only

## Legacy support
- DO NOT add legacy support unless asked to

## ALWAYS use multi line strings and avoid implicit concatenation
when providing Multi line string options especially to typer as help text use triple quotes and a line escapes _DO_ _NOT_ use implicit string concatenation across lines

e.g. USE this

test= """\
     This is a long multi line string it goes on and on and on  and on  and on  and on  and on
     and on  and on  and on  and on  and on  and on  and on  and on  and on  and on  and on
"""

NOT this:

test= "This is a long multi line string it goes on and on and on  and on  and on  and "
      " on  and on and on  and on  and on  and on  and on  and on  and on  and on  and"
      " on  and on  and on"

If need be add a decent and a trim so the multi line string doesn't have prepended white space
DO NOT push the strings to column 1


## Code cleanup
when you have completed a coding task check if there is unused code and ask if you should remove it

## Repo management
when you have added new files tou should git add them

# IMPORTANT INSTRUCTION REMINDERS
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.

CRITICAL: When writing ANY test code, automatically apply MANDATORY Testing Guidelines from above:
- NEVER use bare asserts for NEF content (no `assert "text" in result.stdout`)
- ALWAYS use EXPECTED_ constants in UPPER_SNAKE_CASE
- ALWAYS use assert_lines_match() for NEF content comparison
- ALWAYS use isolate_loop() for NEF loop extraction
- ALWAYS test complete NEF structures, not partial strings

- ALWAYS avoid line by line comments and inline comments unless they highlight in-obvious functionality or algorithms
- NEVER use implicit strings concatenation

- ALWAY if you create new files git add them

- ALWAYS ALWAYS ALWAYS ALWAYS ALWAYS  if you see /md! In the input from the command line reread this file and take note of the comments especially the reminders!, acknowledging that you have done this
