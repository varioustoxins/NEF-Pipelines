# columns_lib / insert TODO Cleanup

## Context

After the `_rewrite_loop_file_import` refactor, a pass over `columns_lib.py` and `insert.py` added TODO comments flagging code-quality issues. This plan converts each TODO into a concrete action so they can be addressed systematically.

---

## TODOs in `columns_lib.py`

### 1. Merge `RepeatValueSpec` and `FillValueSpec` (line 38)

**TODO:** `RepeatValueSpec` (fixed count) and `FillValueSpec` (fill-to-n-rows) are structurally identical except one has an `int` count and the other doesn't. Merge into one class with `count: Optional[int]` where `None` means "fill to row count."

**Change:** Replace both dataclasses with:
```python
@dataclass
class RepeatValueSpec:
    value: str
    count: Optional[int]  # None = fill to row count
```
Update `parse_value_spec` (which creates these), `_resolve_values` in `insert.py` (which consumes them), and any isinstance checks. All `FillValueSpec` sites become `RepeatValueSpec(value=..., count=None)`.

---

### 2. `_read_raw_file` — encoding, name, location (line 182)

**TODO:** Questions why it uses a module-level `_FILE_ENCODING` constant (`"utf-8-sig"`), whether the name is clear, and whether it belongs in `columns_lib`.

**Change:** Move to `nef_pipelines/lib/util.py` and rename to `read_utf8_file` (public, since it will be shared). The `utf-8-sig` encoding strips the BOM that Excel writes to CSV files — add a one-line comment saying so. Update the import in `columns_lib.py`.

---

### 3. `_detect_csv_dialect` — early returns and inline class (line 190)

**TODO:** Function has multiple early returns, an inline `class DetectedDialect(csv.Dialect)` definition mid-function, and no body-level exception catch.

**Change:** Extract `DetectedDialect` to module level. Replace the multiple early-return `if … return None` guards with a single guard at the top, then a straight-line success path. Wrap the whole body in a `try/except (clevercsv.exceptions.Error, csv.Error)` that returns `None`.

---

### 4. Move `_escape_spaces_with_underscore` to util (line 231)

**TODO:** One-liner that replaces spaces with underscores; flagged as belonging in a shared utilities module.

**Change:** Move to `nef_pipelines/lib/util.py` (or a new `string_util.py` if one doesn't exist). Update the import in `columns_lib.py`. Check for other callers that could use it.

---

### 5. `_read_column_from_file` — exit_error vs raise (line 272)

**TODO:** Library function calls `exit_error()` directly, which is the CLI layer's job. Should raise an exception instead.

**Change:** Define a new exception class in `columns_lib.py` (or `structures.py` alongside sibling exceptions):
```python
class NEFColumnsException(NEFPipelinesException):
    pass
```
`NEFPipelinesException` is the project base at `nef_pipelines/lib/structures.py:67`. Replace all `exit_error(...)` calls inside `_read_column_from_file` (and `_csv_column_names`) with `raise NEFColumnsException(...)`. The CLI boundary in `_expand_bare_file_refs` / `_resolve_values` catches `NEFColumnsException` and calls `exit_error(str(e))`.

---

### 6. `_read_column_from_file` — too long + caching danger (line 274)

**TODO:** Function is too long. Also, the `lru_cache` on `_read_raw_file` is dangerous in tests (stale cached content between test runs).

**Changes:**
- Remove the `@functools.lru_cache` decorator from `_read_raw_file` entirely. File reads are fast enough; the cache is more trouble than it's worth in tests.
- Extract sub-functions: `_apply_skip_and_comment(lines, skip, comment)`, `_parse_ragged_whitespace(lines)`, `_parse_csv_rows(lines, dialect)`.

---

### 7. `_split_on_column_specification_on_assignment_boundaries` — too long (line 365)

**TODO:** Function is too long and hard to follow.

**Change:** Extract three helpers:
- `_has_assignment(s)` — fast check for unescaped `=`
- `_find_assignment_boundaries(s)` — returns list of comma positions that precede `identifier=`
- `_split_bare_tags(s)` — handles the no-assignment branch (including `@`-ref comma logic)

The main function becomes a short dispatcher calling these three.

---

## TODOs in `insert.py`

### 8. `_unique_col_name` — delete (line 247)

**TODO:** Could be a shared utility with a user-supplied format string instead of hardcoding `{base}_{i}`.

**Change:** Delete. Its only caller was the (buggy) clone-on-default branch in `_resolve_column_and_values`, which is removed in TODO 12. If a genuine use for unique-name generation appears elsewhere in future, add it to `lib/util.py` then.

---

### 9. `_resolve_col_spec_selector` — too long (line 263)

**TODO:** ~60-line function needs decomposition.

**Change:** Extract:
- `_split_frame_loop_prefix(col_spec)` — returns `(frame_loop_or_none, bare_spec)`
- `_merge_selector_and_prefix(selector, frame_loop, bare_spec)` — applies the selector when no explicit prefix is present

Main function becomes: call split, call merge, validate result, return.

---

### 10. `_resolve_values` — type checking clarity (line 324)

**TODO:** Questions whether isinstance dispatch is the right pattern and whether validation should happen earlier.

**What the function does:** `_resolve_values` converts a `ValueSpec` into a concrete `List[str]` of cell values. Each branch handles one subtype:
- `DefaultValueSpec` → `n_rows` copies of `default` (the NEF unused sentinel `'.'`)
- `FileValueSpec` → reads a column from a CSV file (length determined by file content, not `n_rows`)
- `RepeatValueSpec` (count not None) → `count` copies of the value
- `FillValueSpec` / `RepeatValueSpec(count=None)` → `n_rows` copies (fill to loop length)
- `RangeValueSpec` → integer sequence `start..end` inclusive, step ±1
- `RangeFromValueSpec` → `n_rows` integers starting at `start`
- `LiteralsValueSpec` → the literal list as-is (currently the implicit `else` branch)

**The TODO question:** "does this check types are correct?" — No. It trusts that `parse_value_spec` only produces valid subtypes. The `else` branch silently assumes `.values` exists (duck-typing `LiteralsValueSpec`). If a new `ValueSpec` subtype is added and forgotten here, it fails with an `AttributeError` instead of a clear message.

**Change:**
1. Make `LiteralsValueSpec` an explicit `elif isinstance(value_spec, LiteralsValueSpec)` branch.
2. Add a final `else: raise NEFColumnsException(f"unhandled ValueSpec type: {type(value_spec).__name__}")` so new subtypes fail loudly.
3. After TODO 1 (merging `FillValueSpec` into `RepeatValueSpec`): the `FillValueSpec` branch disappears; the `RepeatValueSpec` branch checks `count is None` to decide between fixed-count and fill-to-rows.

---

### 11. `_expand_bare_file_refs` — file error handling (line 344)

**TODO:** No handling for files that don't exist or can't be opened; unclear how errors reach the CLI.

**Change:** The functions it calls (`_csv_column_names`, `_read_column_from_file`) should raise after TODO 5 is done. Add a `try/except (FileNotFoundError, ValueError) as e: exit_error(str(e))` wrapper at the call site in `_expand_bare_file_refs`, making the error boundary explicit. Add a docstring note about what exceptions propagate.

---

### 12. `_resolve_column_and_values` — why does this exist? (line 485)

**TODO:** Purpose unclear; possibly redundant.

**What it does:** It is the non-`--force` path in `_apply_instructions`, handling the case where the requested column name already exists in the loop. Currently has three branches, but the first is wrong:

1. **Column exists + `DefaultValueSpec`** — **(bug)** silently clones the existing column under a generated unique name. This should not happen.
2. **Column exists + any other spec** — `exit_error`.
3. **Column does not exist** — normal path: call `_resolve_values`.

**Intended semantics:** a column name either doesn't clash (use it) or clashes (error), full stop. `--force` is the only escape hatch, and it is handled by `_force_replace_column` before this function is ever called. There is no "silent rename on default" case.

**Changes:**

*Fix the bug:*
- Remove branch 1 entirely. `_resolve_column_and_values` collapses to: clash → `raise NEFColumnsException`; else → `return col_name, _resolve_values(...)`.
- Delete `_unique_col_name` — it will have no remaining callers. (Supersedes TODO 8.)

*Add CLI preflight in `insert`:*
- Before calling `pipe`, walk all resolved `InsertInstruction` objects and check every `col_name` against its target loop's tags. Collect all clashes and `exit_error` with the full list. This ensures no loop is partially mutated when a multi-column spec has a clash partway through.
- Preflight only runs in the CLI `insert` function, not in `pipe`.

*Document `pipe` contract:*
- `pipe` is the programmatic API. It does **no** name-clash checking. Callers are responsible for ensuring column names do not already exist in the target loop (or for passing `force=True` if overwrite is intended). Add this explicitly to the `pipe` docstring.

---

## Additional bugs found (need review)

### A. `_force_replace_column` — should grow the loop, not error (lines 450–453)

`_force_replace_column` errors when the supplied values exceed the current row count. Growing the loop when values outnumber rows is a general rule — "unfilled cells are filled with the NEF unused value `.`" — that applies regardless of `--force`.

**Change:** Remove the error branch in `_force_replace_column`. When `len(values) > len(rows)`, extend the loop with new rows (all other columns filled with `default`), matching the behaviour already in `_apply_instructions` lines 530–533.

---

### B. `_resolve_insert_index` — `AT` must not remove columns (lines 479–482)

`_resolve_insert_index` physically removes the existing column from `loop.tags` and `loop.data` as a side effect of resolving an index. Index resolution should be a pure query; column removal is an instruction-application concern.

**Change:** Remove the column-deletion side effect from `_resolve_insert_index` entirely — it returns only an `int`. Move the removal into `_apply_instructions`: after resolving the index for `AT`, explicitly delete the old column from the loop before inserting the new one.

---

### C. `_read_column_from_file` — ragged-whitespace rows with missing fields (columns_lib.py line 331)

```python
if len(fields) == len(headers):
    rows.append(...)
```

Rows with fewer fields than headers are currently silently dropped.

**Change:** Fill short rows with the NEF unknown value (`.`) for each missing field, consistent with how the rest of the pipeline handles missing values. Do not error.

---

### D. `pipe` — remove `force` parameter (consistency with all other pipes)

No other `pipe` function in the codebase has a `force` parameter (the two exceptions — `fasta/exporters/sequence.py` and `mars/exporters/fragments.py` — use `force` to mean "overwrite the output file on disk", which is unrelated). The `force` concept in `columns/insert.py:pipe` is unique and inconsistent.

**Change:**
- Remove `force` from `pipe` and from `_apply_instructions_by_loop` / `_apply_instructions`.
- `_apply_instructions` always silently overwrites: `if col_name in loop.tags` → `_force_replace_column`; else → normal insert path.
- `_resolve_column_and_values` becomes redundant (the only non-trivial branch was the now-removed clone-on-default; its remaining body is just `_resolve_values`) — delete it, inline `_resolve_values` call directly.
- The CLI `insert` function decides whether to run the preflight (no `--force`) or skip it (`--force`), then calls `pipe(entry, column_instructions)` unconditionally.
- Fix `loops/create.py`: currently calls `insert_pipe` with the old keyword-argument API (`selector=`, `instructions=`, `grow=`). Update to use the current pipeline: convert its `(col_spec_str, "append", None)` tuples to `InsertPlacement.APPEND`, call `_group_column_specifications_by_frame_and_loop` → `_resolve_frame_loop_strings_to_loops` → `_build_column_instructions` → `pipe`.

---

## Ordering / dependencies

Do these in dependency order to avoid rework:

1. **TODO 5** (raise instead of exit_error in `_read_column_from_file`) — unblocks TODO 11
2. **TODO 1** (merge RepeatValueSpec/FillValueSpec) — affects TODOs 6, 10
3. **TODO 6** (decompose `_read_column_from_file`) — safe after TODO 5
4. **TODO 7** (decompose `_split_on_column_specification_on_assignment_boundaries`) — independent
5. **TODO 3** (clean up `_detect_csv_dialect`) — independent
6. **TODO 2** (rename `_read_raw_file`) — independent, tiny
7. **TODO 4** (move `_escape_spaces_with_underscore`) — independent
8. **TODO 8** (move `_unique_col_name`) — independent
9. **TODO 9** (decompose `_resolve_col_spec_selector`) — independent
10. **TODO 10** (add else-raise in `_resolve_values`) — tiny, independent
11. **TODO 11** (error handling in `_expand_bare_file_refs`) — after TODO 5
12. **TODO 12** (investigate `_resolve_column_and_values`) — last, after reading call sites

---

## Verification

After each group of changes:
```
pytest src/nef_pipelines/tests/columns/ -v
```
Full suite after all changes:
```
pytest src/nef_pipelines/tests/ -v
```
