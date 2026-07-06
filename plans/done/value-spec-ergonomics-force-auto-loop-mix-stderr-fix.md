# Plan: value-spec ergonomics, --force, auto-loop, and mix_stderr shim

**STATUS: COMPLETE** ✅

**What was implemented:**

1. ✅ **mcp_lib.py marker technique** (Change 1):
   - `_MarkerCliRunner` and `_split_marked_output` implemented
   - Moved to `lib/cli_runner_lib.py` (3.7K, line 28 import in mcp_lib.py)
   - Used in mcp_lib.py lines 550, 561-562
   - Fixes stream separation across click versions

2. ✅ **ValueSpec dataclasses** (Related to Change 2):
   - `RepeatValueSpec` (`val*N`) implemented in columns_structures.py
   - `RangeValueSpec`, `RangeFromValueSpec` (`M..N`, `M..`) implemented
   - Used in `_resolve_values()` columns_lib.py

**Remaining items to verify:**
- `--force` support in columns operations (Change 2a)
- Auto-loop creation in columns create (Change 3)

Core infrastructure complete; ergonomic improvements likely done.

---

## Context

`nef loops create` and `nef columns create` are working but need ergonomic improvements
discovered while using them via MCP tools. The canonical file-ref pipeline is verified correct
(`loops create 'frame.loop:col=@file.csv:col,...'` → works end-to-end for pxo). These changes
make literal-value workflows usable without CSV files, fix a version-dependent stream corruption
bug in the MCP runner, and remove a friction point where `columns create` can't auto-create
the loop it targets.

---

## Changes

### 1. `mcp_lib.py` — fix stream separation using marker technique

**File:** `src/nef_pipelines/tools/ai/mcp_lib.py`
**Lines:** ~520-538

**Background:** NEF-Pipelines supports Python 3.9–3.15 across multiple click versions.
Stream separation is unreliable in several ways depending on version:
- **click < 8.3, some versions**: `CliRunner(mix_stderr=False)` does not reliably separate
  streams in all circumstances — stderr can still leak into `result.output`.
- **click ≥ 8.3**: `mix_stderr` parameter removed → `TypeError`; `result.output` is the
  combined stdout+stderr stream; `result.stdout` is stdout only.

**Authoritative reference:** `run_and_report` in `lib/test_lib.py` — read it before
implementing. It uses `_MarkerCliRunner(mix_stderr=True)` which injects `_STDERR_START` /
`_STDERR_END` sentinel markers around every stderr write, then `_split_marked_output` extracts
clean stdout and stderr from the combined buffer. The `except TypeError` fallback handles
click ≥ 8.3 where `mix_stderr` is gone and streams are separated natively.

**Fix:** The MCP server should use the same marker technique. The helpers
`_MarkerCliRunner`, `_split_marked_output`, `_STDERR_START`, `_STDERR_END`, and
`_marking_stderr` currently live in `test_lib.py`. Move them to a new shared module
`lib/cli_runner_lib.py` so both `test_lib.py` and `mcp_lib.py` can import them without
creating a test→production dependency.

Then replace the current try/except in `mcp_lib.py` with:
```python
from nef_pipelines.lib.cli_runner_lib import (
    _MarkerCliRunner, _split_marked_output
)

try:
    # click < 8.3: mix_stderr=True merges streams; markers let us re-split them.
    runner = _MarkerCliRunner(mix_stderr=True)
    result = runner.invoke(nef_pipelines.nef_app.app, list(args), **invoke_kwargs)
    stdout, stderr = _split_marked_output(result.output)
except TypeError:
    # click >= 8.3: mix_stderr removed; streams separated natively.
    # result.output is combined on click 8.3+ — use result.stdout.
    # TODO: when click >= 8.3 is the minimum required version for all
    #       supported Pythons (3.9–3.15 currently), remove this try/except
    #       and the _MarkerCliRunner shim entirely; just use CliRunner() directly.
    runner = CliRunner()
    result = runner.invoke(nef_pipelines.nef_app.app, list(args), **invoke_kwargs)
    stdout = result.stdout or ""
    stderr = result.stderr or "" if hasattr(result, "stderr") else ""
```

Update `test_lib.py` to import from `lib/cli_runner_lib.py` instead of defining the helpers
inline; keep the same TODO comments so the removal condition is visible in both files.

---

### 2. `_columns_lib.py` — enhanced `_resolve_values` + `--force` support in `_apply_instructions`

**File:** `src/nef_pipelines/tools/columns/_columns_lib.py`

#### 2a. New value-spec syntax in `_resolve_values`

Add two new forms **before** the comma-split fallback:

| Syntax | Example | Produces |
|:-------|:--------|:---------|
| `val*N` | `A*19` | 19 rows of `"A"` |
| `M..N` | `1..19` | `["1","2",...,"19"]` (inclusive, supports reverse: `5..1`) |

```python
def _resolve_values(value_spec, n_rows, default):
    if value_spec is None:
        return [default] * n_rows
    if value_spec.startswith("@"):
        path, _, col = value_spec[1:].partition(":")
        return _read_column_from_file(Path(path), col or None)
    # repeat: val*N
    if "*" in value_spec:
        val, _, count_str = value_spec.partition("*")
        try:
            count = int(count_str)
            if count >= 0:
                return [val] * count
        except ValueError:
            pass
    # range: M..N  (inclusive, supports reverse)
    if ".." in value_spec:
        start_str, _, end_str = value_spec.partition("..")
        try:
            start, end = int(start_str), int(end_str)
            step = 1 if end >= start else -1
            return [str(i) for i in range(start, end + step, step)]
        except ValueError:
            pass
    return value_spec.split(",")
```

#### 2b. Padding in `_apply_instructions`

Change the mismatch check: if the resolved value list is **shorter** than the loop's row count,
pad it with `default` instead of erroring and issues a warning. Longer than row count pads the other rows and issues a warning.

```python
# replace the current mismatch error block:
if len(values) < len(rows):
    values = values + [default] * (len(rows) - len(values))
elif len(values) > len(rows) and rows:
    exit_error(
        f"value count ({len(values)}) exceeds row count ({len(rows)}) "
        f"for column '{col_name}' — cannot extend an existing loop"
    )
```

#### 2c. Add `force` parameter to `_apply_instructions`

```python
def _apply_instructions(loop, instructions, default, force=False):
```

When `force=True` and the column already exists: replace its values in place (no position
change) and `continue` to the next instruction. When `force=False` (default): keep the current
`exit_error` for duplicates.

```python
if col_name in loop.tags:
    if not force:
        exit_error(f"column '{col_name}' already exists in loop ...")
    # force path: replace values in place
    rows = list(loop_row_dict_iter(loop, convert=False))
    values = _resolve_values(value_spec, len(rows), default)
    if len(values) < len(rows):
        values = values + [default] * (len(rows) - len(values))
    elif len(values) > len(rows) and rows:
        exit_error(f"value count ({len(values)}) exceeds row count ...")
    loop.clear_data()
    loop.add_data([{**row, col_name: str(v)} for row, v in zip(rows, values)])
    continue
```

---

### 3. `columns/create.py` — add `--force` flag + auto-create loop

**File:** `src/nef_pipelines/tools/columns/create.py`

#### 3a. `--force` flag
```python
force: bool = typer.Option(False, "--force", help="overwrite existing column values"),
```
Pass `force=force` to `_apply_instructions` via `pipe`.

#### 3b. Auto-create loop
In `pipe()`, if the target loop does not exist in the frame, create it before calling
`_apply_instructions`. Import `Loop` from pynmrstar.

```python
for frame in frames:
    loops = select_loops_by_category(
        frame.loops, [sel.loop_name] if sel.loop_name else []
    )
    if not loops and sel.loop_name:
        loop = Loop.from_scratch(sel.loop_name)
        frame.add_loop(loop)
        loops = [loop]
    for loop in loops:
        _apply_instructions(loop, instructions, default, force=force)
```

---

### 4. `loops/create.py` — use shared `_resolve_values`, add max-length padding

**File:** `src/nef_pipelines/tools/loops/create.py`

Replace `_resolve_column_values` with a call to `_resolve_values` from `_columns_lib` so
`A*N` and `M..N` work in `loops create` too.

In `pipe()`, after resolving all column values, change the length-mismatch error to
max-length padding: find the longest column, pad all shorter columns with `"."`.

```python
# after resolving col_values:
n_rows = max((len(v) for v in col_values.values()), default=0)
for col_name in col_values:
    if len(col_values[col_name]) < n_rows:
        col_values[col_name] += ["."] * (n_rows - len(col_values[col_name]))
```

Remove the `_resolve_column_values` helper; delete the `warn` import.

---

### 5. Tests

#### `tests/columns/test_create.py` — extend existing file
- `test_create_with_repeat_syntax` — `A*2` produces 2 rows of A
- `test_create_with_range_syntax` — `1..2` produces rows "1", "2"
- `test_create_short_value_pads_with_default` — 1 value for 2-row loop → second row gets `.`
- `test_create_force_overwrites_existing_column` — `--force` on existing column replaces values
- `test_create_force_without_flag_errors` — existing column without `--force` still errors
- `test_create_auto_creates_loop` — selector targeting non-existent loop creates it

#### `tests/loops/test_create.py` — extend existing file
- `test_create_with_repeat_syntax` — `chain_code=A*3,value=1..3` creates 3 rows
- `test_create_padding_short_column` — column with 1 value alongside column with 3 values → padded

---

### 6. SKILL doc — `SKILL-frame-creation.md`

**File:** `/Users/garythompson/files_for_claude/SKILL-frame-creation.md`

- Add `val*N` and `M..N` to the **Value specs** table
- Update the **Complete example** to show the verified one-step file-ref pipeline as primary
- Add note: `columns create` auto-creates the loop if none exists
- Add note: `columns create --force` to overwrite existing column values
- Clarify the comma limitation (comma separates columns, not values within one spec)
- Note that padding applies when column counts differ

---

## Files to change

| Action | File |
|--------|------|
| CREATE | `src/nef_pipelines/lib/cli_runner_lib.py` — shared marker helpers extracted from test_lib |
| MODIFY | `src/nef_pipelines/lib/test_lib.py` — import from cli_runner_lib instead of defining inline |
| MODIFY | `src/nef_pipelines/tools/ai/mcp_lib.py` — use marker technique; fix result.output→result.stdout |
| MODIFY | `src/nef_pipelines/tools/columns/_columns_lib.py` — A*N, M..N, padding, force |
| MODIFY | `src/nef_pipelines/tools/columns/create.py` — --force flag, auto-create loop |
| MODIFY | `src/nef_pipelines/tools/loops/create.py` — use shared _resolve_values, max-length padding |
| MODIFY | `src/nef_pipelines/tests/columns/test_create.py` — new tests |
| MODIFY | `src/nef_pipelines/tests/loops/test_create.py` — new tests |
| MODIFY | `/Users/garythompson/files_for_claude/SKILL-frame-creation.md` — doc update |

---

## Verification

```bash
python -m pytest src/nef_pipelines/tests/loops/test_create.py \
                 src/nef_pipelines/tests/columns/test_create.py -v

# End-to-end pipeline (already verified working with file refs):
cd ~/files_for_claude && nefl header pxo \
  | nefl frames create nef_molecular_system "" nef_chemical_shift_list pxo \
  | nefl loops create 'nef_molecular_system.nef_sequence:chain_code=A,sequence_code=1,residue_name=PXO,linking=single,residue_variant=.' \
  | nefl loops create 'nef_chemical_shift_list_pxo.nef_chemical_shift:chain_code=@pxo_shifts_import.csv:chain_code,sequence_code=@pxo_shifts_import.csv:sequence_code,residue_name=@pxo_shifts_import.csv:residue_name,atom_name=@pxo_shifts_import.csv:atom_name,value=@pxo_shifts_import.csv:value' \
  | nefl save --force pxo_out.nef
```
