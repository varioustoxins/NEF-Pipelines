# Plan: fix `run_and_report` stdout/stderr separation and duplication

## Context

After fixing Category 1 (exit_error layout) and Category 3 (typer variadic args on
3.9), Category 2 remains: tests fail on 3.9 (33) and 3.10/3.14 (20) because the
test harness `run_and_report` in `src/nef_pipelines/lib/test_lib.py` mis-attributes
stdout/stderr content, producing either missing stdout or duplicated output.

### Evidence gathered

Two root causes, both in `run_and_report` / `_MarkerCliRunner`:

**Cause A — wrong field on click 8.3 (Python 3.10+)**

`_MarkerCliRunner(mix_stderr=True)` raises `TypeError` on click 8.3 (the parameter
was removed), so we fall back to plain `CliRunner()`. Then:

```python
captured_stdout = result.output   # BUG: result.output is combined stdout+stderr
captured_stderr = result.stderr   # pure stderr
```

On click 8.3, `result.output` = stdout + stderr interleaved. `result.stdout` is
the pure stdout we wanted. So `captured_stdout` wrongly contains stderr content
too. Then with `merge_stderr=True` (default):

```python
self.stdout = captured_stdout + captured_stderr   # = stdout + stderr + stderr
```

stderr content appears twice in `result.stdout` (the sparky peaks duplication).

**Cause B — marker splitter can't handle stderr-then-stdout interleaving (Python 3.9)**

`_MarkedWriter` prefixes stderr writes with `_STDERR_MARKER` (start marker only).
`_split_marked_output` treats the first chunk as stdout and *all* remaining chunks
as stderr. If stderr is written before stdout (e.g. `frames display` writes
display-to-stderr then entry-to-stdout), the buffer is:

```
MARKER + display + MARKER + "\n" + entry + "\n"
```

After `split(MARKER)`: `["", "display", "\nentry\n"]`. The splitter emits
`stdout=""`, `stderr="display\nentry\n"` — entry content wrongly classified as
stderr. 29 display tests fail this way on 3.9.

Verified both causes with direct probes:
- `.venv310/bin/python` + sparky peaks `--file-name-template -`: command writes
  only to stderr (stdout=0, stderr=388); test asserts `result.stdout` has one
  copy, gets two.
- `.venv39/bin/python` + minimal typer app writing stderr-before-stdout: current
  splitter returns `stdout=""`, `stderr="<display>+<entry>"`.

## Fix

Two surgical changes in `src/nef_pipelines/lib/test_lib.py`. No other files change.

### 1. Bracket stderr writes with START/END markers

Replace single `_STDERR_MARKER` with a pair:

```python
_STDERR_START = "\x00STDERR_START\x00"
_STDERR_END   = "\x00STDERR_END\x00"
```

In `_MarkedWriter.write`:

```python
original.write(_STDERR_START + s + _STDERR_END)
```

Rewrite `_split_marked_output` to scan linearly: text between START/END → stderr,
text outside → stdout. Handles any interleaving correctly.

### 2. Use marker approach on all click versions; use clean stdout

In `run_and_report`:

- Always use `_MarkerCliRunner` (fall back to `_MarkerCliRunner()` without
  `mix_stderr` on click 8.3 — still wraps stderr; works because click 8.3 merges
  native stdout/stderr into `result.output` in order).
- Always derive `(captured_stdout, captured_stderr)` from
  `_split_marked_output(result.output)`. Drop the click-version branch.
- `NormalisedResult.stderr` = `captured_stderr` (always pure stderr).
- `NormalisedResult.stdout` = `captured_stdout + captured_stderr` if
  `merge_stderr` else `captured_stdout`. No duplication because `captured_stdout`
  is now pure.

`merge_stderr=True` stays as the default — preserves behaviour of existing tests
that rely on stderr content showing up in `result.stdout` (they just stop getting
it twice).

## Files modified

| File | Change |
|------|--------|
| `src/nef_pipelines/lib/test_lib.py` | `_STDERR_MARKER` → `_STDERR_START`/`_STDERR_END`; rewrite `_MarkedWriter.write`; rewrite `_split_marked_output` to linear scan; in `run_and_report` always use marker runner and split from `result.output` |

No test files need to change — the fix restores the behaviour the tests were
written against.

## Verification

```bash
cd nef_pipelines
.venv39/bin/pytest  src/nef_pipelines/tests -q
.venv310/bin/pytest src/nef_pipelines/tests -q
.venv311/bin/pytest src/nef_pipelines/tests -q
.venv312/bin/pytest src/nef_pipelines/tests -q
.venv313/bin/pytest src/nef_pipelines/tests -q
.venv314/bin/pytest src/nef_pipelines/tests -q
```

Target: 0 failures on all six. Current baseline: 33 failures on 3.9, 20 on
3.10/3.14 (display + sparky + one tree + one sparky-shifts warning test).

Spot-check the two most-indicative cases after the fix:

```bash
.venv310/bin/pytest src/nef_pipelines/tests/sparky/test_export_peaks.py::test_ppm_out_short -v
.venv39/bin/pytest  src/nef_pipelines/tests/frames/test_display.py::test_basic_selector -v
```
