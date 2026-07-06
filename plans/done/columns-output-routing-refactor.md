# Refactor Column Commands: Separate Output Generation from Output Routing

## Context

Column commands `list` and `extract` currently mix output generation with output routing decisions inside the `pipe()` function. The `pipe()` function decides whether to print to stdout or stderr based on `sys.stdout.isatty()` and directly prints output.

This violates the separation of concerns principle documented in `plans/design_docs/design_overview.md` (section "Handling Display Output: `print_output_or_exit_error`", lines 362-405), where:
- Display commands produce human-readable text (not NEF streams)
- `pipe()` generates and returns `(entry, output_dict)` where output_dict maps keys to display text
- CLI function handles routing using `print_output_or_exit_error(entry, out, output_dict, force)`
- The function routes based on `--out` option and TTY status

User clarification:
- `list` should follow this pattern (returns display text)
- `extract` should follow this pattern (file writing is output routing, not business logic)
- `delete` does NOT need changes (already returns just modified entry)

## Pattern to Follow

Based on `src/nef_pipelines/tools/frames/display.py`:

**CLI Function** (lines 206-212):
```python
entry, output_dict = pipe(entry, matched_items, display_options)
print_output_or_exit_error(entry, out, output_dict, force)
```

**pipe() Function** (lines 215-270):
- Returns `Tuple[Optional[Entry], Dict[str, str]]`
- Builds output as list of strings
- Returns `(entry, {"-": "\n".join(display_lines)})`
- Does NOT decide where to print

**Support Function** in `src/nef_pipelines/lib/cli_lib.py`:
- `print_output_or_exit_error(entry, out, output_dict, force)` handles routing based on `--out` option and TTY status

## Files to Modify

### 1. `src/nef_pipelines/tools/columns/list_.py`

**Current structure:**
- `list_()` CLI: reads entry, parses selectors, calls `pipe(entry, selections)`
- `pipe(entry, selections)`: decides output stream, prints directly, returns entry

**Changes needed:**
- `pipe()` signature: `pipe(entry: Entry, selections: List[FrameLoopsAndTags]) -> Tuple[Entry, Dict[str, str]]`
- Remove `piped = not sys.stdout.isatty()` and `out = sys.stderr if piped else sys.stdout`
- Build output as list of strings instead of printing
- Return `(entry, {"-": "\n".join(output_lines)})`
- CLI function: add `--out` parameter similar to `frames display` (see line 75-92 in display.py for the help text pattern)
- CLI function: call `print_output_or_exit_error(entry, out, output_dict, force=False)` instead of letting pipe print
- Add `from nef_pipelines.lib.cli_lib import print_output_or_exit_error`

### 2. `src/nef_pipelines/tools/columns/delete.py`

**No changes needed.** Delete is a filter pipe that modifies the entry and returns it. It doesn't produce display output. The `pipe()` function signature `pipe(entry, selections) -> Entry` is correct for filter pipes per `docs/design_overview.md`.

### 3. `src/nef_pipelines/tools/columns/extract.py`

**Current structure:**
- `extract()` CLI: reads entry, parses selectors, calls `pipe()`, prints entry
- `pipe()`: collects column data, writes to file directly, returns entry

**Changes needed:**
- Move file writing from `pipe()` to CLI function (output routing is not business logic)
- `pipe()` signature: `pipe(entry, selections, format) -> Tuple[Entry, Dict[str, str]]`
- `pipe()` should:
  - Collect column data into dict
  - Format data as CSV or simple text
  - Return `(entry, {"csv_data": formatted_string})` or similar key
- CLI function should:
  - Add `--out` parameter (same pattern as `list`)
  - Call `print_output_or_exit_error(entry, out, output_dict, force)`
  - Since extract always writes to a file (not display text), the output_dict should contain the formatted data
  - The `--out` value becomes the file path (not `@auto`, `@err`, etc. since extract is not display)

## Implementation Notes

1. **For list.py:**
   - Build complete output including table formatting before returning
   - Use same logic as current code but accumulate in list instead of printing
   - `--out` parameter options: `@auto` (default), `-` / `@out`, `@err`, `<filename>`
   - When `--out @auto`: if TTY → stdout (entry suppressed), if pipe → stderr (entry to stdout)
   - Copy the `--out` parameter definition and help text from `frames/display.py` lines 75-92

2. **For extract.py:**
   - There's already a TODO comment (line 90-91) saying pipe should return columns and CLI should write
   - Move `_write_columns_to_file()` into a new function that formats but doesn't write
   - `pipe()` returns `(entry, {"-": formatted_csv_or_text})`
   - CLI calls `print_output_or_exit_error()` with `out` set to the file path
   - Change `output: Path` parameter to `out: Optional[str]` to match display pattern
   - Default `--out` to `None` (error if not specified, unlike display commands)

3. **Reuse existing utilities:**
   - `print_output_or_exit_error()` from `src/nef_pipelines/lib/cli_lib.py`
   - `is_stdout_tty()` from `src/nef_pipelines/lib/util.py` (used by print_output_or_exit_error)
   - Pattern documented in `plans/design_docs/design_overview.md` section "Handling Display Output"

## Verification

```bash
# Test list command with various output modes
nefl test tests/columns/test_list.py

# Test that piped mode still works (entry to stdout, display to stderr)
echo "..." | nef columns list "*.chemical_shift:*" | nef frames list

# Test explicit output routing
nef columns list input.nef "*.chemical_shift:*" --out @err
nef columns list input.nef "*.chemical_shift:*" --out output.txt

# Test delete still works
nefl test tests/columns/test_delete.py

# Full column test suite
nefl test tests/columns/
```
