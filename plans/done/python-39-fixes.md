# Plan: Fix Remaining Test Failures on Python 3.9 and 3.10

## Context

After making the CI green on Python 3.10+ by unblocking typer/click `nargs=-1`
errors, click version shims, and Python 3.13/3.14 compatibility, two suites
still have failures:

- `nefl test`  (Python 3.10, click 8.3.x): **23 failures**
- `nefl39 test` (Python 3.9, click 8.1.x):  **48 failures**

The failures cluster into three categories. The fixes are independent and can
be done in any order, but doing Category 3 first makes the 3.9 run readable.

---

## Category 1 — `exit_error` debug-hint layout regression

### Symptom

Tests that assert against an error message see the debug hint inserted BETWEEN
the `ERROR [in: X]:` header and the message body, and see the continuation
lines indented with 2 spaces.

Actual output:

```
ERROR [in: project]:
... for full debug information run: nef --debug <sys.argv>
  the file name 5387 looks like a bmrb code but I couldn't read it
  from the bmrb website, is it correct, is you network up, is the bmrb up?
exiting...
```

Expected by tests:

```
ERROR [in: project]:
the file name 5387 looks like a bmrb code but I couldn't read it
from the bmrb website, is it correct, is you network up, is the bmrb up?
exiting...
```

### Fix

In `src/nef_pipelines/lib/util.py::exit_error`:

1. Move the `debug_clause` print to AFTER the full message block (just before
   `exiting...`) so the message is contiguous.
2. Drop the 2-space indent on continuation lines (`msg[1:]`).

Target layout produced by `exit_error`:

```
ERROR [in: X]: <msg[0]>
<msg[1]>
<msg[2]>
...
... for full debug information run: nef --debug <sys.argv>   # only if not --debug
exiting...
```

### Tests fixed (4)

- `nmrstar/test_import_project.py::test_failed_bmrb_web_fetch_fallback_to_nonexistent_file`
- `nmrstar/test_import_project.py::test_shortcut_ubiquitin_web_failure_fallback`
- `nmrstar/test_import_project.py::test_numeric_file_path_error_message`
- `entry/test_tree.py::test_tree_null_namespace_warning`

---

## Category 2 — `merge_stderr=True` duplicates output

### Symptom

Several commands (e.g. `sparky peaks`, `frames display`) write the SAME payload
to both stdout and stderr. `run_and_report` currently does
`self.stdout = stdout + stderr` when `merge_stderr=True` (the default), which
doubles the content in `result.stdout`.

Reproducer confirming both streams have identical content:

```python
runner = CliRunner()                         # new click, streams are separate
result = runner.invoke(peaks_app, ['--file-name-template', '-'], input=INPUT)
assert result.output == result.stderr        # true — same bytes in both
```

### Fix

In `src/nef_pipelines/lib/test_lib.py::run_and_report`:

1. Change default `merge_stderr=False`. `result.stdout` becomes pure stdout,
   `result.stderr` stays pure stderr — matching what the tests actually expect.
2. Any test that legitimately needs the merged view passes
   `merge_stderr=True` explicitly.

### Followup (out of scope for this pass)

`sparky peaks` (and likely `frames display`) write the same content to both
streams. That is probably a real bug in those commands, but it is not what the
current test failures are asking us to fix — leave it for a dedicated cleanup
once the suite is green.

### Tests fixed (~18)

- `sparky/test_export_peaks.py::test_ppm_out_short*`  — 12 tests
- `sparky/test_export_shifts.py::test_no_shift_frames_warning`
- `frames/test_display.py::test_default_behaviour_in_cli_runner`
- `frames/test_display.py::test_out_err_no_entry`
- plus most of the remaining `test_display.py` failures on 3.9 (same root cause)

---

## Category 3 — `Optional[List[str]]` lost under deferred annotations (3.9 only)

### Symptom

On typer 0.23.2 + Python 3.9, when a module has `from __future__ import
annotations`, a parameter annotated as
`Annotated[Optional[List[str]], typer.Argument(...)]` loses its variadic
nature. Invoking the command with positional arguments produces:

```
Error: Got unexpected extra arguments (- +nef +custom)
```

Minimal reproducer (fails on 3.9, passes on 3.10+):

```python
from __future__ import annotations
import typer
from typing import Annotated, List, Optional

app = typer.Typer()

@app.command()
def cmd(xs: Annotated[Optional[List[str]], typer.Argument()] = None):
    print(xs)

# `cmd a b` → 3.9: "Got unexpected extra arguments"; 3.10+: prints ['a', 'b']
```

Root cause: deferred annotations defeat typer's runtime introspection of the
`Optional[List[str]]` container on older typer/click on Python 3.9.

### Fix

Remove `from __future__ import annotations` from files that register typer
commands. Where a `X | Y` union relied on it, rewrite using `Optional[X]` /
`Union[X, Y]`.

| File | Action |
|---|---|
| `tools/namespace/list.py` | Remove `__future__` import. No `\|`-unions present. |
| `tools/frames/display.py` | Remove `__future__` import. Rewrite `str \| None` on line 792 as `Optional[str]` (add `Optional` to typing imports). Verify no other `\|`-unions remain. |
| `lib/cli_lib.py` | KEEP `__future__`. Pure library code, no typer commands. Has `str \| Any` on line 1639 that needs it. |
| `lib/test_lib.py` | KEEP `__future__`. Pure library code, no typer commands. Has `str \| bytes \| IO[AnyStr] \| None` on line 414 that needs it. |

### Tests fixed (11)

All failures in `namespace/test_list.py` on Python 3.9, plus any other 3.9
tests that exercised the namespace list command indirectly.

---

## Execution order

1. **Category 3 first** — mechanical edits to two files. Unblocks the 3.9
   namespace-list tests so the remaining 3.9 failures become readable.
2. **Category 2** — one-line default flip in `run_and_report`. Re-run full
   suite on 3.9 and 3.10 to confirm the expected ~18 sparky/display tests turn
   green and no new regressions surface.
3. **Category 1** — targeted edit to `exit_error`. Re-run; expect the 4
   message-format tests green.
4. Full-suite green on `nefl test` and `nefl39 test`. Then extend the run to
   `.venv311` / `.venv312` / `.venv313` / `.venv314` for completeness.
5. Commit, push, watch GitHub Actions for confirmation.

## Files modified

| File | Category | Change |
|---|---|---|
| `src/nef_pipelines/lib/util.py` | 1 | Reorder `exit_error` output; drop indent on continuation lines |
| `src/nef_pipelines/lib/test_lib.py` | 2 | `run_and_report(merge_stderr=True)` → `merge_stderr=False` |
| `src/nef_pipelines/tools/namespace/list.py` | 3 | Remove `from __future__ import annotations` |
| `src/nef_pipelines/tools/frames/display.py` | 3 | Remove `__future__` import; `str \| None` → `Optional[str]` |

## Verification

```sh
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines
.venv310/bin/python -m pytest src/nef_pipelines/tests/ -q
.venv39/bin/python  -m pytest src/nef_pipelines/tests/ -q
```

Both should report 0 failures.
