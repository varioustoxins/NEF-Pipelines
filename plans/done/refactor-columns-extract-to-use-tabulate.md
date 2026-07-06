# Unify Table Formatting Across All Commands

## Context

Format handling is currently inconsistent across nef_pipelines commands:

- **`namespace catalog`**: Uses `TableOutputFormat` (5 formats: simple, pretty, markdown, ai, html)
- **`frames tabulate`**: Uses its own `FORMAT_TO_EXTENSION` dict (23 formats including csv, tsv, grid, latex, etc.)
- **`columns extract`**: Uses `ExtractFormat` (2 formats: csv, simple - where simple is single-column only, no headers)

This inconsistency creates:
- **User confusion**: Different commands have different format options
- **Code duplication**: Multiple format enums/dicts doing the same thing
- **Limited utility**: catalog and extract can't output TSV, grid, or other useful formats

The goal is to:
1. **Create single source of truth**: Expand `TableOutputFormat` to include all 23 formats from frames tabulate
2. **Migrate all commands**: catalog, frames tabulate, and columns extract all use the same enum
3. **Remove confusion**: Drop the confusing single-column SIMPLE format from columns extract
4. **Maximum consistency**: Same format options and names across all tabular output commands

## Implementation Plan

### 1. Expand TableOutputFormat to Include All 23 Formats

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/lib/table_format_lib.py`

Replace the current 5 formats with all 23 formats from `frames tabulate`:

```python
class TableOutputFormat(LowercaseStrEnum):
    """Shared output format for tabular data across NEF-Pipelines commands."""

    def __new__(cls, value: str, tablefmt: str, description: str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.tablefmt = tablefmt
        obj.description = description
        return obj

    # Common formats (keep existing)
    SIMPLE = ("simple", "simple", "plain text table (default)")
    PRETTY = ("pretty", "pretty", "boxed table")
    MARKDOWN = ("markdown", "pipe", "Markdown pipe table")
    AI = ("ai", "pipe", "optimised for AI / MCP tools")
    HTML = ("html", "html", "HTML table")

    # Add from frames tabulate
    CSV = ("csv", "csv", "comma-separated values")
    TSV = ("tsv", "tsv", "tab-separated values")
    GRID = ("grid", "grid", "grid table")
    FANCY_GRID = ("fancy_grid", "fancy_grid", "fancy grid with double lines")
    FANCY_OUTLINE = ("fancy_outline", "fancy_outline", "fancy outline table")
    GITHUB = ("github", "github", "GitHub-flavored Markdown")
    PIPE = ("pipe", "pipe", "pipe-separated table")
    PLAIN = ("plain", "plain", "plain table without lines")
    PRESTO = ("presto", "presto", "Presto SQL format")
    PSQL = ("psql", "psql", "PostgreSQL table format")
    RST = ("rst", "rst", "reStructuredText grid")
    ORGTBL = ("orgtbl", "orgtbl", "Emacs Org-mode table")
    MEDIAWIKI = ("mediawiki", "mediawiki", "MediaWiki table")
    MOINMOIN = ("moinmoin", "moinmoin", "MoinMoin wiki table")
    TEXTILE = ("textile", "textile", "Textile table")
    LATEX = ("latex", "latex", "LaTeX table")
    LATEX_BOOKTABS = ("latex_booktabs", "latex_booktabs", "LaTeX table with booktabs")
    LATEX_LONGTABLE = ("latex_longtable", "latex_longtable", "LaTeX longtable")
    LATEX_RAW = ("latex_raw", "latex_raw", "LaTeX table without decorations")
    UNSAFEHTML = ("unsafehtml", "unsafehtml", "HTML table without escaping")
```

This creates a single source of truth for all table formatting across nef_pipelines.

### 2. Remove ExtractFormat Enum

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/columns/columns_structures.py`

Delete the `ExtractFormat` enum (lines 23-25):

```python
class ExtractFormat(LowercaseStrEnum):
    CSV = auto()
    SIMPLE = auto()
```

This enum is only used by `columns extract` and will be replaced by `TableOutputFormat`.

### 3. Migrate frames tabulate to Use TableOutputFormat

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/frames/tabulate.py`

**Changes**:

a. **Add import** (after line 16):
```python
from nef_pipelines.lib.table_format_lib import TableOutputFormat
```

b. **Remove FORMAT_TO_EXTENSION dict** (lines 39-63):
Delete the entire `FORMAT_TO_EXTENSION` dictionary - this is now replaced by `TableOutputFormat`.

c. **Update command signature** (around line 192):
Replace the format parameter type from `str` to `TableOutputFormat`:
```python
out_format: TableOutputFormat = typer.Option(
    TableOutputFormat.SIMPLE,
    "--format",
    "-f",
    help="output format (see --help for full list)",
),
```

d. **Update format help generation** (lines 66-69):
Replace `FORMAT_HELP` with auto-generated help from TableOutputFormat:
```python
FORMAT_HELP = (
    "Output format:\n"
    + "\n".join(f"  {fmt.value:<20} - {fmt.description}" for fmt in TableOutputFormat)
)
```

e. **Update format check in _output_loop** (line 404):
Change from string comparison to enum check:
```python
# Before:
if args.out_format in ["csv", ""]:

# After:
if args.out_format.value in ["csv", ""]:
```

And for tabulate call (line 412):
```python
# Before:
tablefmt=args.out_format

# After:
tablefmt=args.out_format.tablefmt
```

f. **Remove `formats` variable** (line 65):
No longer needed since formats come from the enum.

### 4. Refactor columns extract to Use TableOutputFormat

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/columns/extract.py`

**Changes**:

a. **Update imports** (add at top):
```python
from tabulate import tabulate as tabulate_formatter
from nef_pipelines.lib.table_format_lib import TableOutputFormat
```

b. **Remove old import**:
```python
from nef_pipelines.tools.columns.columns_lib import ExtractFormat, _filter_tags
```

c. **Update command signature** (line 37):
```python
format: TableOutputFormat = typer.Option(
    TableOutputFormat.CSV,
    "--format",
    help="output format: csv, tsv, markdown, html, simple, pretty, ai",
),
```

d. **Update pipe function signature** (line 60):
```python
def pipe(
    entry: Entry,
    selections: List[FrameLoopsAndTags],
    format: TableOutputFormat = TableOutputFormat.CSV,
) -> Tuple[Entry, Dict[str, str]]:
```

e. **Refactor _format_columns function** (lines 84-103):

Replace the entire function with:

```python
def _format_columns(
    col_data: Dict[str, List[str]],
    format: TableOutputFormat,
) -> str:
    """Format column data using csv.writer or tabulate library.

    CSV and TSV use csv.writer for proper escaping.
    All other formats use tabulate library.
    """
    output = StringIO()
    headers = list(col_data.keys())
    rows = list(zip(*col_data.values()))

    if format.value in ["csv", "tsv"]:
        # Use csv.writer for proper quoting/escaping
        delimiter = '\t' if format.value == "tsv" else ','
        writer = csv.writer(output, delimiter=delimiter, lineterminator='\n')
        writer.writerow(headers)
        writer.writerows(rows)
    else:
        # Use tabulate for all other formats
        result = tabulate_formatter(rows, headers=headers, tablefmt=format.tablefmt)
        output.write(result)

    return output.getvalue()
```

**Pattern rationale**: This follows the same pattern as `frames tabulate` (csv.writer for CSV, tabulate for others) but uses the shared `TableOutputFormat` enum.

### 5. Update Tests

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/columns/test_extract.py`

**Status**: User has already removed SIMPLE format tests and cleaned up the test file. Tests now only cover CSV format.

**Remaining changes**:

a. **Update imports**:
```python
from nef_pipelines.lib.table_format_lib import TableOutputFormat
```

b. **Add tests for new formats**:

```python
def test_extract_tsv(tmp_path):
    """Test TSV format output."""
    out_path = tmp_path / "extracted.tsv"
    result = run_and_report(
        app,
        [
            "--in", "-",
            "--out", str(out_path),
            "--format", "tsv",
            "myshifts.chemical_shift:atom_name,value",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    assert result.exit_code == 0

    expected = """\
        atom_name\tvalue
        N\t123.22
        H\t8.90
    """
    assert_lines_match(expected, out_path.read_text())


def test_extract_markdown(tmp_path):
    """Test markdown format output."""
    out_path = tmp_path / "extracted.md"
    result = run_and_report(
        app,
        [
            "--in", "-",
            "--out", str(out_path),
            "--format", "markdown",
            "myshifts.chemical_shift:atom_name,value",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    assert result.exit_code == 0
    # Markdown pipe format includes headers and separator
    content = out_path.read_text()
    assert "atom_name" in content
    assert "value" in content
    assert "|" in content  # pipe table format


def test_extract_simple_format(tmp_path):
    """Test simple (plain text table) format."""
    out_path = tmp_path / "extracted.txt"
    result = run_and_report(
        app,
        [
            "--in", "-",
            "--out", str(out_path),
            "--format", "simple",
            "myshifts.chemical_shift:value",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    assert result.exit_code == 0
    # Simple format has headers (unlike old SIMPLE format)
    content = out_path.read_text()
    assert "value" in content
    assert "123.22" in content
    assert "8.90" in content
```

d. **Update existing test if needed**:

The existing `test_extract_single_column_to_file` and `test_extract_two_columns` tests should continue to work with minimal changes (just ensure they're not checking for the old SIMPLE format).

### 6. Verify namespace catalog Still Works

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/namespace/catalog.py`

No code changes needed - `catalog` already uses `TableOutputFormat` and will automatically gain access to all 23 formats when we expand the enum.

Just verify it still works and now supports the new formats (csv, tsv, grid, etc.).

### 7. Update Documentation/Help Text

The command help text will be auto-generated from `TableOutputFormat.description` fields, so no manual help text updates needed beyond the parameter definition.

Users will now see:
```
--format [csv|tsv|simple|pretty|markdown|ai|html]
```

With descriptions for each format available via `--help`.

## Files to Modify

1. `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/lib/table_format_lib.py` - Expand to 23 formats
2. `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/columns/columns_structures.py` - Remove ExtractFormat enum
3. `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/frames/tabulate.py` - Migrate to TableOutputFormat
4. `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/columns/extract.py` - Migrate to TableOutputFormat
5. `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/columns/test_extract.py` - Update tests

## Files to Verify (no changes needed)

1. `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/namespace/catalog.py` - Already uses TableOutputFormat, will automatically support new formats

## Verification Plan

After implementation:

1. **Run test suites**:
   ```bash
   # Test columns extract
   nefl test src/nef_pipelines/tests/columns/test_extract.py -v

   # Test frames tabulate
   nefl test src/nef_pipelines/tests/frames/test_tabulate.py -v

   # Test namespace catalog
   nefl test src/nef_pipelines/tests/namespace/test_catalog.py -v
   ```

2. **Verify columns extract** - test new formats work:
   ```bash
   # CSV (default)
   echo "$NEF_DATA" | nef columns extract --out test.csv myshifts.chemical_shift:value

   # TSV
   echo "$NEF_DATA" | nef columns extract --out test.tsv --format tsv myshifts.chemical_shift:atom_name,value

   # Grid
   echo "$NEF_DATA" | nef columns extract --out test.txt --format grid myshifts.chemical_shift:atom_name,value

   # Markdown
   echo "$NEF_DATA" | nef columns extract --out test.md --format markdown myshifts.chemical_shift:atom_name,value
   ```

3. **Verify frames tabulate** - ensure existing functionality preserved:
   ```bash
   # CSV still works
   nef frames tabulate --format csv test.nef frame.loop -o output.csv

   # New enum-based formats work
   nef frames tabulate --format grid test.nef frame.loop
   ```

4. **Verify namespace catalog** - check new formats available:
   ```bash
   # CSV now available
   nef namespace catalog --format csv

   # TSV now available
   nef namespace catalog --format tsv
   ```

5. **Verify consistency** - all three commands support the same formats:
   ```bash
   # Check --help shows same format options
   nef columns extract --help | grep -A 30 "format"
   nef frames tabulate --help | grep -A 30 "format"
   nef namespace catalog --help | grep -A 30 "format"
   ```

## Benefits

### For Users
- **Consistent format options**: All three commands (`catalog`, `frames tabulate`, `columns extract`) support the same 23 formats
- **No confusion**: Same format names work across all tabular output commands
- **More versatility**:
  - `catalog` gains CSV, TSV, grid, latex, etc. (previously only had 5 formats)
  - `columns extract` gains 21 new formats (previously only CSV + confusing SIMPLE)
  - `frames tabulate` gains consistency (same formats, just enum-based)
- **Better documentation**: Auto-generated help text with format descriptions

### For Developers
- **Single source of truth**: `TableOutputFormat` is the only place format definitions live
- **No duplication**: Eliminated `ExtractFormat` enum and `FORMAT_TO_EXTENSION` dict
- **Easier maintenance**: Adding a new format = one line in `TableOutputFormat`, all commands get it
- **Type safety**: Enum-based formats instead of string comparisons
- **Consistent patterns**: All commands use the same `.tablefmt` and `.description` properties

### For the Codebase
- **~50 lines of code removed**: Duplicate format definitions eliminated
- **Improved consistency**: All table formatting follows the same pattern
- **Future-proof**: New commands can immediately use all 23 formats by importing `TableOutputFormat`
