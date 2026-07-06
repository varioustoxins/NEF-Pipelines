# Plan: Support headerless files in `columns insert` with automatic detection

**STATUS: NOT IMPLEMENTED**

## Context

`nef columns insert` currently assumes all input files have a header row. When reading columns via `@file:N` (integer index), the code:
1. Treats the first row (after `--skip`/`--comment` filtering) as a header
2. Uses that row to determine column count and generate column names
3. Skips that row when reading data

**Problem**: For headerless files, this consumes the first data row as a "header," silently losing it from the output.

**Example**: File `/Users/garythompson/files_for_claude/repro_data.txt` has 4 columns of pure data (no header). Running:
```bash
columns insert --selector loop.data value=@repro_data.txt:4
```
Currently loses row 1 (`1 G C1' 91.38`) because it's consumed as the header.

**Solution**: When all column references to a given file use integer indices (no name-based references), infer the file is headerless. Read data directly by column position without treating any row as a header.

---

## Detection Algorithm

**Where**: `insert()` CLI function in `insert.py` at line ~80, BEFORE calling `pipe()`.

**Logic**: For each file path referenced in the instructions, collect all column references. If all are integer indices, mark the file as headerless:

```python
def _detect_headerless_files(instructions: List[Tuple[str, str, Optional[str]]]) -> Set[Path]:
    """Detect which files have only integer column references (no name-based refs).

    Returns set of Path objects for files that should be treated as headerless.
    """
    path_col_refs: Dict[Path, List[str]] = {}

    for col_spec, _, _ in instructions:
        col_name, value_spec = _split_col_spec(col_spec)
        if value_spec and value_spec.startswith("@"):
            path_str, _, cols = value_spec[1:].partition(":")
            path = Path(path_str)
            if cols:  # @file:col or @file:1,2
                path_col_refs.setdefault(path, []).extend(c.strip() for c in cols.split(","))
            else:  # bare @file (imports all columns, uses header names)
                path_col_refs.setdefault(path, []).append("__NAME_BASED__")

    headerless_files: Set[Path] = set()
    for path, col_refs in path_col_refs.items():
        # If all refs are integers, infer headerless
        if col_refs and all(c.isdigit() for c in col_refs if c != "__NAME_BASED__"):
            if "__NAME_BASED__" not in col_refs:
                headerless_files.add(path)

    return headerless_files
```

**Call site**: Add after line 80 in `insert.py`:
```python
instructions = _parse_interleaved(ctx.args)
headerless_files = _detect_headerless_files(instructions)
entry = pipe(entry, selector, instructions, default, force=force, skip=skip, comment=comment, headerless_files=headerless_files)
```

---

## Propagation Path

Thread `headerless_files: Optional[Set[Path]] = None` through the call chain (mirroring existing `skip`/`comment` parameters):

| Function | Location | Signature Change |
|----------|----------|------------------|
| `pipe()` | `insert.py:84` | Add `headerless_files=None` parameter |
| `_expand_bare_file_refs()` | `columns_lib.py:603` | Add `headerless_files=None` parameter |
| `_apply_instructions()` | `columns_lib.py:694` | Add `headerless_files=None` parameter |
| `_resolve_values()` | `columns_lib.py:209` | Add `headerless_files=None` parameter |
| `_read_column_from_file()` | `columns_lib.py:269` | Add `headerless_files=None` parameter |

Note: `_csv_column_names()` does NOT need the parameter - headerless files bypass it entirely.

---

## Implementation Details

### 1. Modify `_read_column_from_file()` at line 269

Add early branch for headerless mode that reads data by position directly:

```python
def _read_column_from_file(
    path: Path, col_name: Optional[str], format: ExtractFormat = ExtractFormat.CSV,
    skip: int = 0, comment: str = "", headerless_files: Optional[Set[Path]] = None
) -> List[str]:
    """Read a single column from a file.

    If path is in headerless_files, col_name must be an integer (1-based position)
    and data is read directly by position without treating any row as a header.
    """
    if not path.exists():
        exit_error(f"file not found: {path}")

    raw_text = _read_raw_file(path.resolve())
    if comment:
        raw_text = "\n".join(
            line for line in raw_text.splitlines()
            if not line.strip().startswith(comment)
        )

    non_empty = [l.rstrip() for l in raw_text.splitlines() if l.strip()]
    remaining = "\n".join(non_empty[skip:])

    # Headerless mode: read by column position directly
    if headerless_files and path in headerless_files:
        try:
            col_index = int(col_name) - 1  # 1-based → 0-based
        except (ValueError, TypeError):
            exit_error(
                f"headerless file {path}: column reference must be an integer, got '{col_name}'"
            )

        lines = remaining.splitlines()
        result = []
        for line in lines:
            fields = line.split()
            if col_index < 0 or col_index >= len(fields):
                exit_error(
                    f"column index {col_name} out of range in {path} "
                    f"(line has {len(fields)} columns, indices are 1-based)"
                )
            result.append(fields[col_index])
        return result

    # Existing header-based reading logic (unchanged)
    if format == ExtractFormat.SIMPLE or (format == ExtractFormat.CSV and col_name is None):
        ...
```

### 2. Modify `_expand_bare_file_refs()` at line 603

For headerless files, convert integer refs to strings for use as NEF column names:

```python
def _expand_bare_file_refs(
    instructions: List[Tuple[str, str, Optional[str]]],
    skip: int = 0,
    comment: str = "",
    headerless_files: Optional[Set[Path]] = None,
) -> List[Tuple[str, str, Optional[str]]]:
    """Expand bare file-reference col specs into named col=@file:col instructions."""
    result = []
    for col_spec, keyword, anchor in instructions:
        col_name, value_spec = _split_col_spec(col_spec)
        if not col_name.startswith("@"):
            result.append((col_spec, keyword, anchor))
            continue

        file_part, _, csv_cols = col_name[1:].partition(":")
        path = Path(file_part)

        if headerless_files and path in headerless_files:
            # Headerless: use integer positions directly as NEF column names
            if csv_cols:
                raw_cols = [c.strip() for c in csv_cols.split(",") if c.strip()]
                for c in raw_cols:
                    # For headerless files, NEF column auto-named as "col_N"
                    nef_col = f"col_{c}"
                    result.append((f"{nef_col}=@{file_part}:{c}", keyword, anchor))
            else:
                exit_error(
                    f"bare @file reference requires header to determine column names; "
                    f"file {path} is headerless (all refs are integer indices)"
                )
        else:
            # Header mode: existing logic
            if csv_cols:
                raw_cols = [c.strip() for c in csv_cols.split(",") if c.strip()]
                headers = _csv_column_names(path, skip=skip, comment=comment)
                cols = [_resolve_file_col_name(c, headers, path) for c in raw_cols]
            else:
                cols = _csv_column_names(path, skip=skip, comment=comment)
            for c in cols:
                nef_col = _norm_col(c)
                result.append((f"{nef_col}=@{file_part}:{c}", keyword, anchor))
    return result
```

### 3. Thread through intermediate functions

- `pipe()` passes to `_expand_bare_file_refs()` at line 100
- `pipe()` passes to `_apply_instructions()` at line 114
- `_apply_instructions()` passes to `_resolve_values()` at line 728 and 778
- `_resolve_values()` passes to `_read_column_from_file()` at line 228

All follow the pattern: `..., skip=skip, comment=comment, headerless_files=headerless_files`

---

## Ambiguity Problem with the Heuristic

The "all-integer refs → headerless" heuristic has a fundamental ambiguity that makes it
**incompatible with the 1-based index selection feature already shipped this session**.

Earlier in this session, `_resolve_file_col_name()` was added to `columns_lib.py` so that
integer indices work on **headered** files:

```bash
source=@data.csv:1       # reads first column AFTER the header row "source"
uncertainty=@data.csv:2  # reads second column AFTER the header row "uncertainty"
```

Three tests cover this (`test_insert_file_ref_by_index_first_col`,
`test_insert_file_ref_by_index_second_col`, `test_insert_bare_file_ref_index_auto_names_from_header`)
and they pass today.

Under the proposed heuristic, those exact same commands would trigger headerless mode (all refs are
integers), consume the header row as data, and produce wrong results — silently, with no error.

The ambiguity cannot be resolved from the spec alone. `@data.csv:1` is syntactically identical
whether the file has a header or not. Rewriting those three tests to "add a name ref to force
header mode" masks the problem rather than fixing it: it would mean integer-only access on a
headered file is simply broken.

**Conclusion**: the heuristic approach needs to be replaced with an explicit mechanism (such as
a `--no-header` flag) that lets the user state their intent unambiguously. This is deferred
pending discussion.

---

## New Tests to Add

Add to `test_insert.py` after the existing index tests:

```python
EXPECTED_HEADERLESS_THREE_ROWS = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.seq
       _nef_chemical_shift.residue
       _nef_chemical_shift.atom
       _nef_chemical_shift.value_1

      A   2   GLN   N   123.22   1   G   C1p   91.38
      A   2   GLN   H   8.90     2   G   C2p   75.10
      .   .   .     .   .        3   G   C3p   74.98

    stop_
"""

EXPECTED_HEADERLESS_AUTO_NAMED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.col_4

      A   2   GLN   N   123.22   91.38
      A   2   GLN   H   8.90     75.10

    stop_
"""


def test_insert_headerless_file_by_index(tmp_path):
    """Headerless file: all integer refs infer no header, read all data rows."""
    data_path = tmp_path / "headerless.txt"
    data_path.write_text("1 G C1p 91.38\n2 G C2p 75.10\n3 G C3p 74.98\n")
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift",
         f"seq=@{data_path}:1", f"residue=@{data_path}:2",
         f"atom=@{data_path}:3", f"value_1=@{data_path}:4"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift")
    assert_lines_match(EXPECTED_HEADERLESS_THREE_ROWS, loop_text)


def test_insert_headerless_file_auto_named_column(tmp_path):
    """Bare @file:N on headerless file auto-names as col_N."""
    data_path = tmp_path / "headerless.txt"
    data_path.write_text("1 G C1p 91.38\n2 G C2p 75.10\n")
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift",
         f"@{data_path}:4"],  # Read 4th column with auto-naming
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift")
    assert_lines_match(EXPECTED_HEADERLESS_AUTO_NAMED, loop_text)


def test_insert_headerless_file_bare_ref_error(tmp_path):
    """Bare @file (no column spec) on headerless file errors - can't determine column names."""
    data_path = tmp_path / "headerless.txt"
    data_path.write_text("1 G C1p 91.38\n2 G C2p 75.10\n")
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift",
         f"@{data_path}"],  # No column spec
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    assert "headerless" in result.stdout.lower()
```

---

## Files to Change

| File | Changes |
|------|---------|
| `src/nef_pipelines/tools/columns/insert.py` | Add `_detect_headerless_files()` at top; call it in `insert()` after `_parse_interleaved()`; pass to `pipe()` |
| `src/nef_pipelines/tools/columns/columns_lib.py` | Add `headerless_files` param to 5 functions; add headerless branch in `_read_column_from_file()` that reads by position; update `_expand_bare_file_refs()` to handle headerless auto-naming |
| `src/nef_pipelines/tests/columns/test_insert.py` | Update 3 affected tests to force header mode; add 3 new headerless tests |

---

## Verification

1. **Run existing tests** (after updating the 3 affected ones):
   ```bash
   PYTHONPATH=src:/Users/garythompson/Dropbox/git/streamfitter/src \
     .venv312/bin/python -m pytest src/nef_pipelines/tests/columns/test_insert.py -v
   ```
   All 34 tests (31 existing + 3 new) should pass.

2. **Manual repro test**:
   ```bash
   # Create a 2-row loop
   echo 'data_test
   save_nef_chemical_shift_list_test
      _nef_chemical_shift_list.sf_category nef_chemical_shift_list
      _nef_chemical_shift_list.sf_framecode nef_chemical_shift_list_test
      loop_
         _nef_chemical_shift.index
         1
         2
      stop_
   save_' | \
   nef columns insert --selector test.chemical_shift \
     value=@/Users/garythompson/files_for_claude/repro_data.txt:4
   ```
   Expected: 4 values in output (not 3) — all data rows preserved, none lost as header.

3. **Regression check**: Run full columns test suite:
   ```bash
   PYTHONPATH=src:/Users/garythompson/Dropbox/git/streamfitter/src \
     .venv312/bin/python -m pytest src/nef_pipelines/tests/columns/ -q
   ```
   All 73 tests should pass (70 existing + 3 new).
