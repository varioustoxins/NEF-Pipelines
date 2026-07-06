# Plan: `nef loops create`

## Context

Add a `nef loops create` command to create an empty loop (with no columns, no data rows)
inside an existing saveframe. Loops are addressed with the `frame.loop` selector syntax —
the same `parse_frame_loop_and_tags()` used across all column and frame commands.

**COMMENT** I think if there are no tags [columns] you can add a default column as a place holder
and issue a warning
---

## Command signature

```
nef loops create --selector myshifts chain_code sequence_code residue_name atom_name value
```

- `--frame` /  — `frame` selector for a frame if set this is the default frame to add loops to, it must exist!
- positional args — loop names and column names e.g. nef_chemical_shift,chain_code,sequence_code,residue_name,atom_name,value
  or for fully qualified names nef_chemical_shift_list_pxo_shifts.nef_chemical_shift,chain_code,sequence_code

---

## Implementation

### File: `src/nef_pipelines/tools/loops/create.py` (NEW)

```python
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry, Loop

from nef_pipelines.lib.cli_lib import parse_frame_loop_and_tags
from nef_pipelines.lib.nef_lib import (
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
    select_loops_by_category,
)
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.tools.loops import loops_app


@loops_app.command()
def create(
    input: Path = typer.Option(STDIN, "--in", metavar="|PIPE|",
                               help="read NEF data from a file or stdin"),
    selector: str = typer.Option(..., "--selector", "-s",
                                 help="frame.loop selector — loop part sets the new loop category"),
    columns: List[str] = typer.Argument(..., help="column names for the new loop"),
) -> None:
    """- create an empty loop in matching saveframes"""
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    entry = pipe(entry, selector, columns)
    print(entry)


def pipe(entry: Entry, selector: str, columns: List[str]) -> Entry:
    sel = parse_frame_loop_and_tags(selector)

    if not sel.loop_name:
        exit_error("selector must include a loop name, e.g. myshifts.nef_chemical_shift")

    frames = select_frames(entry, [sel.frame_name], SelectionType.ANY)
    if not frames:
        exit_error(f"no frames matched selector '{sel.frame_name}'")

    for frame in frames:
        existing = select_loops_by_category(frame.loops, [sel.loop_name])
        if existing:
            exit_error(
                f"loop matching '{sel.loop_name}' already exists in frame '{frame.name}'"
            )
        loop = Loop.from_scratch(sel.loop_name)
        for col in columns:
            loop.add_tag(col)
        frame.add_loop(loop)

    return entry
```

### File: `src/nef_pipelines/tools/loops/__init__.py` (MODIFY)

- Add `import nef_pipelines.tools.loops.create  # noqa: F401`
- Update help string to include `create` in the bracket list

---

## Test file: `src/nef_pipelines/tests/loops/test_create.py` (NEW)

Verify in `tests/loops/` — may need `__init__.py` if missing.

Tests to write (following CLAUDE.md mandatory guidelines):
- `test_create_empty_loop` — creates a loop with named columns, no data rows
- `test_create_loop_already_exists_errors` — errors if loop category already present
- `test_create_no_frame_match_errors` — errors if frame selector matches nothing
- `test_create_no_loop_in_selector_errors` — errors if selector is frame-only (no `.loop` part)

All use `EXPECTED_` constants + `assert_lines_match()` + `isolate_loop()`.

---

## Key library references

| Symbol | File | Purpose |
|---|---|---|
| `parse_frame_loop_and_tags(spec)` | `lib/cli_lib.py:1448` | Parse `frame.loop` selector |
| `select_frames(entry, pats, SelectionType.ANY)` | `lib/nef_lib.py` | Select saveframes |
| `select_loops_by_category(loops, patterns)` | `lib/nef_lib.py:719` | Check for existing loop |
| `Loop.from_scratch(category)` | pynmrstar | Create empty loop |
| `loop.add_tag(col)` | pynmrstar | Add a column to a loop |
| `frame.add_loop(loop)` | pynmrstar | Attach loop to saveframe |
| `read_entry_from_file_or_stdin_or_exit_error` | `lib/nef_lib.py` | Standard stdin/file read |
| `exit_error(msg)` | `lib/util.py` | Report error + exit 1 |

---

## Files to change

| Action | File |
|---|---|
| CREATE | `src/nef_pipelines/tools/loops/create.py` |
| MODIFY | `src/nef_pipelines/tools/loops/__init__.py` |
| CREATE | `src/nef_pipelines/tests/loops/test_create.py` |
| CREATE (if missing) | `src/nef_pipelines/tests/loops/__init__.py` |

---

## Verification

```bash
python -m pytest src/nef_pipelines/tests/loops/test_create.py -v
```
