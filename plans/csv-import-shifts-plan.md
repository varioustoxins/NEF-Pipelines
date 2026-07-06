# Plan: csv import shifts (composable 3-command design)

## Context

Adding `nef csv import shifts` to import chemical shifts from a CSV file into a NEF shift list
frame. The problem decomposes into two stages: (1) create the saveframe, (2) populate its loop
from CSV data. Rather than bundling those stages into one monolithic command, we build three
composable commands where `csv import shifts` calls the `pipe()` workers of the other two.

**Style rules for all new code:**
- Use **older-style** type annotations matching the existing codebase (`List[str]`, `Tuple[str, str]`,
  `Optional[str]` from `typing`) — do NOT use `Annotated[]` Typer style or Python 3.10+ `list[str]`
- Use `LowercaseStrEnum` with `auto()` for CLI enum options (from `strenum`)
- Use `create_nef_save_frame()` from `nef_lib.py` (not `Saveframe.from_scratch` directly) — it
  correctly sets `sf_category` and `sf_framecode` tags

---

## The Three Commands

possible we need a 4th loop create take pairs of davefames and loops and creates at loop ?

### 1. `nef frames create`
**New file:** `src/nef_pipelines/tools/frames/create.py`

Creates one or more empty NEF saveframes and adds them to the entry stream. If no entry is
present on stdin, creates a new empty one. Reusable standalone utility.

```
nef frames create nef_chemical_shift_list myshifts < in.nef
nef frames create nef_chemical_shift_list myshifts nef_rdc_restraint_list rdcs < in.nef
```

**CLI signature:**
```python
@frames_app.command()
def create(
    entry_name: str = typer.Option("new_entry"),
    input_path: Path = typer.Option(None, "--in", metavar="|PIPE|", ...),
    force: bool = typer.Option(False, "--force", help="overwrite existing frames"),
    name_categories: List[str] = typer.Argument(..., help="alternating category name pairs"),
):
```

**Notes:**
- `name_categories` is a flat list interpreted as alternating `category name` pairs;
  odd count is an error
- stdin used when `--in` is not supplied (standard pipe pattern)
- error (via `exit_error`) if a frame already exists, unless `--force` / global `--force`
- CLI validates overwrite conflicts before calling `pipe()`

**pipe() worker:**
```python
def pipe(
    entry: Entry,
    category_list: List[Tuple[str, str]],
    overwrite: bool = False,
) -> Entry:
    # For each (category, frame_id):
    #   frame = create_nef_save_frame(category, frame_id)  ← nef_lib.py:1076
    #   add_frames_to_entry(entry, [frame])
    return entry
```

**Key library function:** `create_nef_save_frame(frame_category, frame_id)` in
`src/nef_pipelines/lib/nef_lib.py:1076` — handles framecode construction and required tags.

---

### 2. `nef csv import loop`
**New file:** `src/nef_pipelines/transcoders/csv/importers/_loop_cli.py`

Reads one or more CSV files and adds each as a loop to its target saveframe in the entry stream.
CSV headers become loop tags; rows become loop data (passed through as strings).

```
nef csv import loop nef_chemical_shift_list myshifts shifts.csv
nef csv import loop --frame-policy filename nef_chemical_shift_list__myshifts.csv
nef csv import loop --frame-policy header annotated.csv
```

**FrameNamePolicy enum:**
```python
class FrameNamePolicy(LowercaseStrEnum):
    COMMAND_LINE = auto()   # triplets:  frame_name [category+idin loo] loop_catgory file  on the command line
    FILE_NAME    = auto()   # filename encodes: <category>__<frame-id>.csv
    HEADER       = auto()   # first line of file (may be #-commented): category,frame-id
```

**ChainPolicy enum:**
```python
class ChainPolicy(LowercaseStrEnum):
  COMMAND_LINE =  auto()  # once for all files or one per file [values in the file overrride and produce a single warnin g]
  FILE =  auto()          # read from the file if missing error
```

**CLI signature:**
```python
@import_app.command()
def loop(
    input_path: Path = typer.Option(None, "--in", metavar="|PIPE|", ...),
    csv_format: CsvLikeFormats = typer.Option(CsvLikeFormats.AUTO, ...),
    skip: int = typer.Option(0, "--skip", help="extra header rows to skip after headers"),
    frame_policy: FrameNamePolicy = typer.Option(FrameNamePolicy.COMMAND_LINE, ...),
    chain_codes: List[str] = typer.Option(None, "-c", "--chains", ...),
    chain_policy: CgainPolicy =  typer.Option(ChainPolicy.FILE, '--chain-policy'),
    file_args: List[str] = typer.Argument(...),
):
```

**Notes on `file_args`:**
- `COMMAND_LINE` policy: flat list interpreted as triplets `category frame-id path`
- `FILE_NAME` policy: each arg is a path; category and frame-id parsed from filename
  (`<category>__<frame-id>`)
- `HEADER` policy: each arg is a path; first line of file provides `category,frame-id`
  (line may be `#`-prefixed; `skip` controls whether that line is consumed or left to the reader)
- CLI is responsible for building `List[Tuple[str, str, Path]]` before calling `pipe()`
- File contents cached after first read to avoid re-reading for header parsing + import


**pipe() worker:**
```python
def pipe(
    entry: Entry,
    category_id_path: List[Tuple[str, str, Path]],
    chains: List[str],
    csv_format: CsvLikeFormats,
    chain_policy: ChainPolicy=ChainPolicy.FILE,
    skip: int = 0,
) -> Entry:
    # For each (category, frame_id, csv_file):
    #   framecode = f"{category}_{frame_id}"
    #   frame = entry.get_saveframe_by_name(framecode)   ← error if not found
    #   rows, tags = _read_csv(csv_file, csv_format, skip)
    #   loop = Loop.from_scratch(category)
    #   loop.add_tag(tags); loop.add_data(rows)
    #   frame.add_loop(loop)
    return entry
```

---

### 3. `nef csv import shifts`
**New file:** `src/nef_pipelines/transcoders/csv/importers/_shifts_cli.py`

Convenience command. Internally calls `frames.create.pipe()` then `_loop_cli.pipe()` with
shift-specific defaults and column validation.

```
nef csv import shifts myshifts shifts.csv < in.nef
nef csv import shifts myshifts_A shifts_A.csv myshifts_B shifts_B.csv < in.nef
```

**Required CSV columns:** `value`
**Optional CSV columns:** `sequence_code`, `atom_name`, `chain_code` (defaults to `-c` option),
`residue_name`, `value_uncertainty`

**CLI signature:**
```python
@import_app.command()
def shifts(
    input_path: Path = typer.Option(None, "--in", metavar="|PIPE|", ...),
    chain_codes: List[str] = typer.Option(["A"], "-c", "--chains", ...),
    chain_policy: CgainPolicy =  typer.Option(ChainPolicy.FILE, '--chain-policy'),
    csv_format: CsvLikeFormats = typer.Option(CsvLikeFormats.AUTO, ...),
    name_file: List[str] = typer.Argument(..., help="alternating name file pairs"),
):
```

**Notes:**
- `name_file` is a flat list interpreted as alternating `name path` pairs; odd count is error
- `chain_codes` cycles across files (standard chain iterator pattern from other importers)

**pipe() worker:**
```python
def pipe(
    entry: Entry,
    name_file: List[Tuple[str, Path]],
    chain_codes: List[str],
    csv_format: CsvLikeFormats,
    chain_policy: ChainPolicy=ChainPolicy.FILE,
) -> Entry:
    CATEGORY = "nef_chemical_shift_list"
    LOOP_CATEGORY = "nef_chemical_shift"

    # Validate each CSV has required columns (exit_error if missing `value`)
    for name, csv_file in name_file:
        _validate_shift_headers(csv_file, csv_format)

    # Stage 1: create all frames
    category_list = [(CATEGORY, name) for name, _ in name_file]
    entry = frames_create_pipe(entry, category_list)

    # Stage 2: populate each loop
    category_id_path = [
        (LOOP_CATEGORY, name, csv_file) for name, csv_file in name_file
    ]
    entry = loop_pipe(entry, category_id_path, csv_format)

    return entry
```

---

## Shared Utilities Refactor

**New file:** `src/nef_pipelines/transcoders/csv/importers/_csv_lib.py`

Extract five functions currently duplicated identically between `_peaks_cli.py` and
`_rdcs_cli.py`:

| Function | Notes |
|---|---|
| `get_csv_reader_for_format(csv_format, fp, encoding)` | Identical in both |
| `exit_error_if_value_not_type(value, type, msg, row, row_number, file)` | Identical |
| `exit_bad_sequence(...)` | Identical |
| `lookup_residue_name_or_exit(...)` | Identical |
| `tabulate_sequence(...)` | Identical |

Update `_peaks_cli.py` and `_rdcs_cli.py` to import from `_csv_lib.py` and delete local copies.

---

## Registration

**Modify:** `src/nef_pipelines/transcoders/csv/__init__.py`
- Add imports for `_loop_cli` and `_shifts_cli`

**Modify:** `src/nef_pipelines/tools/frames/__init__.py`
- Add import for `create`

---

## Files to Create / Modify

| Action | File |
|---|---|
| CREATE | `src/nef_pipelines/transcoders/csv/importers/_csv_lib.py` |
| CREATE | `src/nef_pipelines/transcoders/csv/importers/_loop_cli.py` |
| CREATE | `src/nef_pipelines/transcoders/csv/importers/_shifts_cli.py` |
| CREATE | `src/nef_pipelines/tools/frames/create.py` |
| CREATE | `src/nef_pipelines/tests/csv/test_import_loop.py` |
| CREATE | `src/nef_pipelines/tests/csv/test_import_shifts.py` |
| CREATE | `src/nef_pipelines/tests/frames/test_create.py` |
| MODIFY | `src/nef_pipelines/transcoders/csv/__init__.py` |
| MODIFY | `src/nef_pipelines/tools/frames/__init__.py` |
| MODIFY | `src/nef_pipelines/transcoders/csv/importers/_peaks_cli.py` |
| MODIFY | `src/nef_pipelines/transcoders/csv/importers/_rdcs_cli.py` |

---

## Key Library References

| Symbol | File | Purpose |
|---|---|---|
| `create_nef_save_frame(category, frame_id)` | `lib/nef_lib.py:1076` | Create properly tagged saveframe |
| `add_frames_to_entry(entry, frames)` | `lib/nef_lib.py:939` | Add frames to entry |
| `read_entry_from_file_or_stdin_or_exit_error(path)` | `lib/nef_lib.py` | Standard stdin/file entry read |
| `is_save_frame_name_in_entry(entry, name)` | `lib/nef_lib.py:994` | Check frame existence |
| `CsvLikeFormats` | `transcoders/csv/importers/_peaks_cli.py` | CSV format enum (move to `_csv_lib.py`) |
| `LowercaseStrEnum` | `strenum` | Enum base for CLI options |

---

## Verification

```bash
# frames create
echo "" | nefl frames create nef_chemical_shift_list myshifts
echo "" | nefl frames create nef_chemical_shift_list myshifts | nefl frames list

# csv import loop (create frame first, then populate loop)
echo "" | nefl frames create nef_chemical_shift_list myshifts \
        | nefl csv import loop myshifts shifts.csv

# csv import loop with file-name policy
echo "" | nefl frames create nef_chemical_shift_list myshifts \
        | nefl csv import loop --frame-policy filename nef_chemical_shift_list__myshifts.csv

# csv import shifts (convenience command)
echo "" | nefl csv import shifts myshifts shifts.csv

# tests
nefl test src/nef_pipelines/tests/frames/test_create.py
nefl test src/nef_pipelines/tests/csv/test_import_loop.py
nefl test src/nef_pipelines/tests/csv/test_import_shifts.py
```
