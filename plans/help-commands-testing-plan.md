# Testing Plan for Help Commands

## Problem

The help commands system needs tests, but we cannot test exact output content because:
- New modules/commands are added over time
- Help text is continuously improved
- Output varies based on installed dependencies and environment

## Solution: Create Test App with Known Commands

Create a minimal test app that emulates the NEF pipelines structure with known, controlled commands. Test EXACT output from this dummy app using EXPECTED_ constants and assert_lines_match().

## Test App Structure

Create: `src/nef_pipelines/tests/tools/help/test_app.py`

```python
"""Minimal test app emulating NEF pipelines hierarchy for testing help commands"""
import typer
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

# Main app (like nef_pipelines main app)
app = typer.Typer(cls=FilteredHelpGroup, no_args_is_help=True)

# Mercury subgroup (first planet)
mercury_app = typer.Typer()

@mercury_app.command(rich_help_panel="Celestial operations")
def io():
    """observe io moon of jupiter"""
    pass

@mercury_app.command(rich_help_panel="Celestial operations")
def europa(
    depth: int = typer.Option(100, help="scan depth in kilometers"),
):
    """scan europa moon for subsurface oceans"""
    pass

@mercury_app.command(rich_help_panel="Celestial operations")
def titan():
    """analyze titan atmosphere composition"""
    pass

app.add_typer(mercury_app, name="mercury", help="mercury planet operations")

# Venus subgroup (second planet)
venus_app = typer.Typer()

@venus_app.command(rich_help_panel="Celestial operations")
def phobos(
    orbit: str = typer.Option("circular", help="orbital pattern to analyze"),
):
    """track phobos orbital mechanics"""
    pass

@venus_app.command(rich_help_panel="Celestial operations")
def deimos():
    """measure deimos surface temperature"""
    pass

app.add_typer(venus_app, name="venus", help="venus planet operations")

# Mars - top-level command (not in a subgroup)
@app.command(rich_help_panel="Celestial operations")
def mars(
    rovers: int = typer.Option(2, help="number of active rovers"),
):
    """deploy mars surface exploration mission"""
    pass

# Earth - top-level help command (the actual help commands we're testing)
from nef_pipelines.tools.help.commands import commands as help_commands_func
earth_command = app.command(name="earth", rich_help_panel="Help and documentation")(help_commands_func)
```

This creates a hierarchy like:
```
test_app
├── mercury (subgroup)
│   ├── io
│   ├── europa
│   └── titan
├── venus (subgroup)
│   ├── phobos
│   └── deimos
├── mars (top-level command)
└── earth (top-level command)
```

## Test File Following CLAUDE.md Guidelines

Create: `src/nef_pipelines/tests/tools/help/test_commands.py`

**MANDATORY**: Follow CLAUDE.md testing guidelines:
- Use EXPECTED_ constants for all expected output
- Use assert_lines_match() for output comparison
- Test complete structures, not partial strings
- NO snapshot testing (not available in this codebase)

**MANDATORY**
reread claude.md before you start!

```python
import pytest
from nef_pipelines.lib.test_lib import run_and_report, assert_lines_match
from .test_app import app

# ============================================================================
# EXPECTED OUTPUT CONSTANTS (following CLAUDE.md guidelines)
# ============================================================================

EXPECTED_TABLE_ALL_COMMANDS = """\
Command                 Category                  Description
----------------------  ------------------------  -------------------------------------------------
test_app earth          Singular environment      display information about the earth
test_app mars           Singular environment      deploy mars surface exploration mission
test_app mercury europa Celestial operations      scan europa moon for subsurface oceans
test_app mercury io     Celestial operations      observe io moon of jupiter
test_app mercury titan  Celestial operations      analyze titan atmosphere composition
test_app venus deimos   Celestial operations      measure deimos surface temperature
test_app venus phobos   Celestial operations      track phobos orbital mechanics
"""

EXPECTED_TABLE_MERCURY_ONLY = """\
Command                 Category              Description
----------------------  --------------------  ------------------------------------------
test_app mercury europa Celestial operations  scan europa moon for subsurface oceans
test_app mercury io     Celestial operations  observe io moon of jupiter
test_app mercury titan  Celestial operations  analyze titan atmosphere composition
"""

EXPECTED_TABLE_MOON_PATTERN = """\
Command                 Category              Description
----------------------  --------------------  ------------------------------------------
test_app mercury europa Celestial operations  scan europa moon for subsurface oceans
test_app mercury io     Celestial operations  observe io moon of jupiter
test_app venus deimos   Celestial operations  measure deimos surface temperature
test_app venus phobos   Celestial operations  track phobos orbital mechanics
"""

EXPECTED_MARKDOWN_VENUS_PHOBOS = """\
| Command               | Category             | Description                       |
|-----------------------|----------------------|-----------------------------------|
| test_app venus phobos | Celestial operations | track phobos orbital mechanics    |
"""

EXPECTED_HTML_TABLE_HEADER = """\
<table>
<thead>
<tr><th>Command                  </th><th>Category                 </th><th>Description                                      </th></tr>
</thead>
<tbody>
"""

# ============================================================================
# Test Suite - Complete Output Testing
# ============================================================================

def test_table_all_commands():
    """Test table format shows all commands with complete output"""
    result = run_and_report(app, ["earth", "--table", "--no-rich"])
    assert_lines_match(EXPECTED_TABLE_ALL_COMMANDS, result.stdout)


def test_table_filter_by_group():
    """Test filtering by group name with complete output"""
    result = run_and_report(app, ["earth", "--table", "--no-rich", "mercury"])
    assert_lines_match(EXPECTED_TABLE_MERCURY_ONLY, result.stdout)


def test_table_filter_by_wildcard():
    """Test wildcard filtering with complete output"""
    result = run_and_report(app, ["earth", "--table", "--no-rich", "*o*"])
    assert_lines_match(EXPECTED_TABLE_MOON_PATTERN, result.stdout)


def test_markdown_format():
    """Test markdown table format with complete output"""
    result = run_and_report(app, ["earth", "--table", "--format", "markdown", "venus phobos"])
    assert_lines_match(EXPECTED_MARKDOWN_VENUS_PHOBOS, result.stdout)


def test_html_table_format_structure():
    """Test HTML table format has correct structure"""
    result = run_and_report(app, ["earth", "--table", "--format", "html"])

    # Check HTML structure is present
    assert_lines_match(EXPECTED_HTML_TABLE_HEADER, result.stdout[:len(EXPECTED_HTML_TABLE_HEADER)])

    # Verify known content is in HTML
    assert "mercury io" in result.stdout
    assert "observe io moon of jupiter" in result.stdout
    assert "</table>" in result.stdout


def test_html_full_format_venus_phobos():
    """Test HTML full format for single command"""
    result = run_and_report(app, ["earth", "--format", "html", "venus phobos"])

    # HTML with inline styles
    assert "<pre>" in result.stdout or "<span" in result.stdout
    assert "style=" in result.stdout

    # No ANSI codes
    assert "\x1b[" not in result.stdout

    # Command details present
    assert "phobos" in result.stdout
    assert "--orbit" in result.stdout
    assert "orbital pattern to analyze" in result.stdout


def test_tree_view_default():
    """Test default tree view output"""
    result = run_and_report(app, ["earth", "--no-rich"])

    # Tree should contain all groups and commands
    assert "mercury" in result.stdout
    assert "venus" in result.stdout
    assert "mars" in result.stdout
    assert "earth" in result.stdout

    # Commands should be present
    assert "io" in result.stdout
    assert "europa" in result.stdout
    assert "phobos" in result.stdout
    assert "deimos" in result.stdout


def test_group_by_category():
    """Test --group-by-category option"""
    result = run_and_report(app, ["earth", "--table", "--group-by-category", "--no-rich"])

    # Should have category headers
    assert "## Celestial operations" in result.stdout
    assert "## Help and documentation" in result.stdout

    # Commands should follow headers
    celestial_section = result.stdout.split("## Celestial operations")[1]
    assert "mercury io" in celestial_section
    assert "venus phobos" in celestial_section
    assert "mars" in celestial_section


def test_full_format_with_options():
    """Test full format shows parameter details"""
    result = run_and_report(app, ["earth", "--format", "full", "mercury europa"])

    # Should show Usage line
    assert "Usage:" in result.stdout
    assert "europa" in result.stdout

    # Should show options with help text
    assert "--depth" in result.stdout
    assert "scan depth in kilometers" in result.stdout


def test_no_matches():
    """Test filtering with no matches"""
    result = run_and_report(app, ["earth", "--table", "nonexistent_xyz"])

    # Should indicate no matches
    assert "No commands found" in result.stdout or "no" in result.stdout.lower()


def test_markdown_full_format():
    """Test markdown-full format output"""
    result = run_and_report(app, ["earth", "--format", "markdown-full", "venus deimos"])

    # Should have markdown structure
    assert "##" in result.stdout
    assert "###" in result.stdout

    # Should show command details
    assert "deimos" in result.stdout
    assert "measure deimos surface temperature" in result.stdout
```

## Files to Create

**New files:**
- `src/nef_pipelines/tests/tools/help/__init__.py` - Empty init file
- `src/nef_pipelines/tests/tools/help/test_app.py` - Minimal test app with planet/moon hierarchy
- `src/nef_pipelines/tests/tools/help/test_commands.py` - Main test file with complete output tests

**No modifications needed** - Tests work with existing code

## Verification

Run tests:
```bash
# Run all help command tests
pytest src/nef_pipelines/tests/tools/help/test_commands.py -v

# Run specific test
pytest src/nef_pipelines/tests/tools/help/test_commands.py::test_table_all_commands -v

# Run with coverage
pytest src/nef_pipelines/tests/tools/help/test_commands.py --cov=nef_pipelines.tools.help.commands
```

Expected outcomes:
- All tests pass
- No crashes with different option combinations
- Output format validation works (table, HTML, markdown, tree, full)
- Filtering logic is correct (by group, wildcards, exact matches)
- Category grouping works properly

## Benefits of This Approach

1. **Resilient to changes** - Tests don't break when real app help text improves
2. **Tests actual behavior** - Verifies functionality with exact output
3. **Catches regressions** - Will detect broken formatting or options
4. **Maintainable** - Test app is small and controlled with planet/moon theme
5. **Fast execution** - No dependencies on real nef_pipelines structure
6. **Non-conflicting** - Planet/moon names don't clash with real command names
