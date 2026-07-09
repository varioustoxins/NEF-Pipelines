
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NEF-Pipelines is a Python package for manipulating NEF (NMR Exchange Format) files. It provides command-line tools for converting between NEF and various NMR software formats (nmrview, sparky, mars, xplor, etc.) and for manipulating NEF file components like molecular chains, frames, and spectra.

## NEF Format Documentation

**Essential reading for working with NEF files:**

- [STAR File Format](src/nef_pipelines/resources/mcp_server/star-file-format%20-%20STAR%20format%20reference%20-%20read%20before%20working%20with%20NEF%20files%20.md) - STAR format reference
- [NEF File Format](src/nef_pipelines/resources/mcp_server/nef-file-format%20-%20NEF%20STAR%20dialect%20reference%20-%20%20read%20before%20working%20with%20NEF%20files.md) - NEF STAR dialect reference (read before working with NEF files)
- [CLI Idioms](src/nef_pipelines/resources/mcp_server/cli-idioms%20-%20NEF-Pipelines%20CLI%20common%20idioms%20and%20patterns.md) - Common NEF-Pipelines command patterns and idioms
- [NEF NMR Data Model](src/nef_pipelines/resources/mcp_server/nef-nmr-data-model%20-%20NEF%20Molecular%20Structure%20and%20NMR%20Data%20Model.md) - NEF molecular structure and NMR data model


## Development Commands

### IMPORTANT: Use `nefl` for Local Development
**Always use `nefl` (not `nef`) when testing or running commands during development.**
- `nefl` runs the local development version from `src/`
- `nef` runs the installed version which may be stale

### Testing

**CRITICAL: `nefl` vs `nef` for Testing**

on a __developers__ machine

- `nef` is the **installed/production** version (what end users see after `uv tool install nef-pipelines`)
- `nefl` is the **local development** version (tests your current uncommitted changes in `src/`)

**For development work, ONLY `nefl test` results matter** - those test against the current local changes.
The `nef test` results would be testing the old installed version, which doesn't have any of the current
refactoring or changes. Ignore `nef test` results during development - they may be broken or out of sync.

```bash
# CORRECT: Run tests with nefl (uses local development version)
nefl test src/nef_pipelines/tests/entry/test_tree.py

# Run specific test
nefl test src/nef_pipelines/tests/entry/test_tree.py::test_tree_basic

# WRONG: Do NOT use nef test during development
# nef test <...>  # This tests the OLD installed version!
```
>NOTE: nefl is on the global path and there are versions for various version of python nefl39 nefl314 etc.

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
The application uses a hierarchical command structure built on Typer. Commands self-register through module imports in
`main.py:78-114`. The main entry point creates a Typer app and imports all tool and transcoder modules.
>Note Typer commands should be created with the more modern annotation style of definitions.

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
   **this includes error messages**. If used _once_ the `EXPECTED` strings can just be `EXPECTED` and be embedded in the test functio. For
   shared `EXPECTED` strings they should be names and be a the module _scope_ just before first use and tests that share
   an `EXPECTED` string should follow each other sequentially in the file
3. **NEVER use implicit string joining** - For long strings that exceed line length limits, use explicit concatenation with `+`
   operator inside parentheses. Implicit string joining (adjacent string literals) is dangerous:
   ```python
   # CORRECT: Explicit concatenation with + inside parentheses
   EXPECTED_WARNING = (
       "WARNING: no columns specified for 'nef_chemical_shift_list_myshifts.nef_chemical_shift'; "
       + "adding placeholder column 'place_holder'"
   )

   # WRONG: Implicit string joining, joing string should be indicated by an operation
   EXPECTED_WARNING = (
       "WARNING: no columns specified for 'nef_chemical_shift_list_myshifts.nef_chemical_shift'; "
       "adding placeholder column 'place_holder'"
   )
   ```
4. **ALWAYS use assert_lines_match()** - For NEF content comparison: `assert_lines_match(EXPECTED_STRING, actual_content)`
5. **ALWAYS use isolate_loop()** - For NEF loops: `isolate_loop(content, frame_name, loop_name)`
6. **ALWAYS test complete structures** - Use complete NEF frames/loops, not partial string matching
7. **ALWAYS use path_in_test_data()** - Use `path_in_test_data(filename, __file__)` to locate test data files, never hardcode paths
8. **NEVER skip tests for missing test data** - Tests must FAIL (not skip) if required test data files are missing
9. **ALWAYS use temporary directories for output** - Test output files must be written to temporary directories (use pytest's `tmp_path` fixture), never to the working directory or test data directories
10. **ALWAYS use pytest parameterisation for related tests** - When multiple tests follow the same pattern with different inputs, use `@pytest.mark.parametrize` instead of writing separate test functions.
     This improves readability and makes tests easier to extend.
11. **ALWAYS compare result dataclasses and structures by equality if possible** - Build a complete expected instance and use
    `assert result == expected`, not a series of individual field assertions. For fields with dynamic values (error
    messages, generated paths), capture the value first, include it in the expected instance, then separately check
    anything else required:
    ```python
    EXPECTED = ChangeSandboxResult(error=result.error, old_path=str(old_cwd))
    assert result == EXPECTED
    assert EXPECTED_ERROR_CANCELLED in result.error.lower()
    ```
12. **ALWAYS use nef_pipelines.lib.test_lib.run_and_report** don't use typer.testing.CliRunner
13. **ALWAYS include test IDs in parametrized test data** - Do NOT use separate `ids=` lists. Instead, structure test data
    as tuples with the ID as the first element. This keeps IDs co-located with test data and prevents sync issues:
    ```python
    # CORRECT: ID is part of the test data
    TEST_CASES = [
        ("test-id-1", input_1, expected_1),
        ("test-id-2", input_2, expected_2),
    ]

    @pytest.mark.parametrize("test_id, input, expected", TEST_CASES, ids=lambda x: x[0])
    def test_foo(test_id, input, expected):
        ...

    # WRONG: Separate ids list that can get out of sync
    @pytest.mark.parametrize("input, expected", [
        (input_1, expected_1),
        (input_2, expected_2),
    ], ids=["test-id-1", "test-id-2"])  # DON'T DO THIS
    ```

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

### Docstring Style
**ALWAYS use Google-style docstrings** (not NumPy or Sphinx).

```python
def function_name(param1, param2):
    """Brief one-line description.

    Longer description if needed. Use LaTeX for math:

    .. math::
        y = A \cdot e^{-k \cdot x}

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value
    """
```

**Rationale:** Compatible with great-docs documentation generator (`parser: google` in great-docs.yml).

**Note:** Some existing files use Sphinx-style (`:param:`, `:return:`). When editing those files, convert to Google-style.

### Math Notation in Docstrings
Use LaTeX math in docstrings:
- Inline: `:math:`y = A \cdot e^{-k \cdot x}``
- Display block: `.. math::\n    y = A \cdot e^{-k \cdot x}`

Renders properly in great-docs.

## Code Style

- Functions should have a single return statement at the end when possible
- **ALWAYS use British spelling** for all user-facing text, variable names, function names, and documentation
  - Examples: `colour` not `color`, `colour_policy` not `color_policy`, `ColourOutputPolicy` not `ColorOutputPolicy`
  - This applies to: CLI option names (`--colour-policy`), parameter names, class names, enum values, docstrings, help text, and comments
- Favour dataclasses as opposed to full classes unless needed NEF-Piplines is designed around  **simple data structures and functions**
  when possible they should be immutable and sortable

### Assert Statements

- **NEVER use `assert` statements in production/runtime code** - asserts are ONLY for test files
- Asserts can be disabled with `python -O` (optimize flag) and should never be relied upon for runtime validation
- In production code, use proper error handling instead:
  ```python
  # WRONG: assert in runtime code
  assert value is not None, "value cannot be None"

  # CORRECT: proper error handling
  if value is None:
      raise ValueError("value cannot be None")
  ```
- Asserts are acceptable ONLY in test files (`test_*.py` or `*_test.py`)

### Import Guidelines

- **Imports MUST be at the top level of the module** unless there is a specific technical reason
- The ONLY valid reasons for imports inside functions are:
  1. **Lazy loading of large packages** to improve startup time
  2. **Avoiding circular import dependencies**
- **When imports are inside functions, add clear comments explaining why:**
  ```python
  def some_function():
      # Import inside function to avoid circular dependency with module_x
      from nef_pipelines.lib.module_x import SomeClass

      # Lazy import of heavy package to improve startup time
      import large_package
  ```
- Do NOT put imports inside functions for any other reason (code organization, "cleanliness", etc.)

### Pattern Matching Guidelines

- **ALWAYS use `fnmatchcase` instead of `fnmatch.fnmatch`**
  - `fnmatchcase` provides consistent case-sensitive matching across all platforms
  - `fnmatch.fnmatch` is case-insensitive on Windows and case-sensitive on Unix, causing platform-specific bugs
  - Use `from fnmatch import fnmatchcase` at module level
  - Example:
    ```python
    from fnmatch import fnmatchcase

    # CORRECT: Always case-sensitive, platform-independent
    if fnmatchcase(name, pattern):
        ...

    # WRONG: Platform-dependent behavior (banned)
    from fnmatch import fnmatch
    if fnmatch(name, pattern):  # DO NOT USE
        ...
    ```
  - An AST-based test (`test_banned_functions.py`) enforces this rule

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

## Warning & Output

- **ALWAYS use `nef_pipelines.lib.util.warn`** for user-facing warnings - never `from warnings import warn` (Python's
  standard library warn).
  - The custom `warn` prints `WARNING: <msg>` to stderr and is consistent with how all other nef tools report problems.
  - Using `warnings.warn` instead leaks `UserWarning` exceptions into pytest's warning summary, making test noise that
    is hard to distinguish from real issues.
  - In tests, mock a custom warn via `monkeypatch.setattr("module.path.warn", ...)` and assert on the captured message.

- **ALWAYS use `print_output_or_exit_error` for display-command output** - never write the routing logic inline.
  Import from `nef_pipelines.lib.cli_lib`. Full details in `docs/design_overview.md`
  under *"Handling Display Output"*.

## Temp files are banned in production code

**NEVER write data to temporary files in production / pipeline code.**  All data must flow
in memory (Python objects, `io.StringIO`, `io.BytesIO`).

- Do **not** use `tempfile.gettempdir()`,`tempfile.NamedTemporaryFile`, `tempfile.mkstemp`,
 `tempfile.TemporaryFile`, `tempfile.SpooledTemporaryFile`, `tempfile.TemporaryDirectory`,
  or `tempfile.mkdtemp` in any production (non-test) module without asking.
- Test files (`test_*.py`) **may** use any of these freely — the ban applies
  only to the tools they exercise, not the test harness itself.
- An AST meta-test (`test_meta_no_tempfile_writes.py`) enforces this rule automatically.

**Why:** writing temp files in a sandboxed MCP process triggers sandbox violations because
`/var/tmp` is outside the MCP sandbox root.  In-memory data flow also avoids I/O overhead
and file-cleanup boilerplate.

## Module-level ordering
In every Python module, keep top-level definitions in this order: imports, then constants/type
definitions/dataclasses, then functions. Do not interleave constants or type definitions with
function bodies or after functions.

## Legacy support
- DO NOT add legacy support unless asked to

## ALWAYS use multi line strings and avoid implicit concatenation
when multi line strings are needed use triple quotes and a line escapes _DO_ _NOT_ use implicit string concatenation
across lines. Also multiline strings should be indented for readability.

e.g. USE this

test= """\
     This is a long multi line string it goes on and on and on  and on  and on  and on  and on
     and on  and on  and on  and on  and on  and on  and on  and on  and on  and on  and on
"""

NOT this:

test= "This is a long multi line string it goes on and on and on  and on  and on  and "
      " on  and on and on  and on  and on  and on  and on  and on  and on  and on  and"
      " on  and on  and on"

If needs be add a decent and a strip so the multi line string doesn't have prepended white space
DO NOT push the strings to column 1


## Code cleanup
when you have completed a coding task check if there is unused code and ask if you should remove it

## Plans
When writing a plan or design document, save it to the `plans/` folder at the root of the repository.

## Repo management
when you have added new files you should git add them

## Worktrees
After any Agent tool call that uses `isolation: "worktree"`, always remove the worktree when the work is done:
`git worktree remove --force <path>`

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
- ALWAYS compare result dataclasses and structures by equality if possible (== against a complete expected instance,
  not field-by-field asserts)

- ALWAYS avoid line by line comments and inline comments unless they highlight in-obvious functionality or algorithms
- NEVER use implicit strings concatenation

- ALWAY if you create new files git add them

- ALWAYS ALWAYS ALWAYS ALWAYS ALWAYS  if you see /md! In the input from the command line reread this file and take note of the comments especially the reminders!, acknowledging that you have done this

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
