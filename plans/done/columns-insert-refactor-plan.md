# Plan: Refactor `columns insert` — typed instructions

## Context

The `pipe` function and internal helpers pass instructions around as raw strings and
bare tuples `(col_spec: str, keyword: str, anchor: Optional[str])`. This makes the
code hard to follow and the types untrustworthy. The goal is to replace the stringly-
typed representation with proper structs and an enum, and to narrow `pipe`'s scope so
it operates on a single `Saveframe` with fully-resolved `InsertInstruction` objects
that each carry their target `Loop` instance.

---

## What the current parameters mean

| Param | Default | Meaning |
|-------|---------|---------|
| `default` | `"."` | Fill value for new column cells when the value list is shorter than the row count (or no value spec is given) |
| `force` | `False` | Overwrite existing column values instead of erroring when the column already exists |
| `skip` | `0` | Skip N non-empty lines before the header row when reading `@file` refs (for files with metadata rows above the column header) |
| `comment` | `""` | Strip lines starting with this prefix before parsing `@file` refs (e.g. `#` for comment lines) |
| `grow` | `False` | Allow the loop to grow extra rows when the value list has more values than existing rows (pads existing rows with `default`); not currently exposed in the CLI |

---

## Files to modify

- `nef_pipelines/src/nef_pipelines/tools/columns/columns_lib.py`
- `nef_pipelines/src/nef_pipelines/tools/columns/insert.py`

Tests (`tests/columns/test_insert.py`) use the CLI via `run_and_report` so the refactor
should be invisible to them — they should pass without modification.

---

## Steps

### 1. Add `InsertKeyword` enum to `columns_lib.py`

```python
class InsertKeyword(LowercaseStrEnum):
    BEFORE = auto()
    AFTER = auto()
    AT = auto()
    APPEND = auto()
```

Update `_POS_FLAGS` → rename to `POSITION_FLAGS`, mapping to enum values:
```python
POSITION_FLAGS = {
    "--before": InsertKeyword.BEFORE, "-b": InsertKeyword.BEFORE,
    "--after":  InsertKeyword.AFTER,  "-a": InsertKeyword.AFTER,
    "--at":     InsertKeyword.AT,     "-@": InsertKeyword.AT,
}
```

### 2. Add `ColumnSpec` dataclass to `columns_lib.py`

```python
@dataclass
class ColumnSpec:
    col_name: str
    value_spec: Optional[str]   # None → clone existing col or fill with default
```

Add a helper `ColumnSpec.from_str(token: str) -> ColumnSpec` that wraps `_split_col_spec`.

### 3. Add `InsertInstruction` dataclass to `columns_lib.py`

`InsertInstruction` is the fully-resolved form — it carries the actual `Loop` object so
`pipe` needs no separate loop-lookup step:

```python
@dataclass
class InsertInstruction:
    column_spec: ColumnSpec
    keyword: InsertKeyword
    anchor: Optional[str]   # None when keyword is APPEND; column name or index otherwise
    loop: Loop
```

### 4. Update `_parse_interleaved` → returns raw `(str, InsertKeyword, str)` tuples

`_parse_interleaved` cannot produce `InsertInstruction` because loops are not yet known
at parse time. It returns a lightweight list of `(col_spec_str, keyword, anchor)` tuples
(where `col_spec_str` may still carry a `frame.loop:` prefix).

- Replace `_POS_FLAGS` references with `POSITION_FLAGS`
- Map flag strings to `InsertKeyword` enum values
- Pending tokens at end-of-stream get `InsertKeyword.APPEND` and `anchor=None`

### 5. Update `insert` command in `insert.py` — resolve loops, build `InsertInstruction`

The `insert` command resolves selectors, selects frames, finds or creates loops, expands
bare file refs, and builds fully-resolved `InsertInstruction` objects before calling `pipe`:

```python
def insert(...):
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    raw = _parse_interleaved(ctx.args)   # List[(col_spec_str, InsertKeyword, str)]

    # Group by resolved frame.loop target
    groups: Dict[str, List[Tuple[str, InsertKeyword, str]]] = {}
    for col_spec_str, kw, anchor in raw:
        frame_loop, bare_col = _resolve_col_spec_selector(selector, col_spec_str)
        groups.setdefault(frame_loop, []).append((bare_col, kw, anchor))

    for frame_loop_str, group in groups.items():
        sel = parse_frame_loop_and_tags(frame_loop_str)
        for frame in select_frames(entry, [sel.frame_name], SelectionType.ANY):
            # Find or create the target loop
            loops = select_loops_by_category(frame.loops, [sel.loop_name] if sel.loop_name else [])
            if not loops and sel.loop_name:
                new_loop = Loop.from_scratch(sel.loop_name)
                frame.add_loop(new_loop)
                loops = [new_loop]
            for loop in loops:
                # Expand bare @file refs, then build InsertInstruction with resolved loop
                expanded = _expand_bare_file_refs(
                    [(col, kw, anc) for col, kw, anc in group],
                    skip=skip, comment=comment,
                )
                instructions = [
                    InsertInstruction(ColumnSpec.from_str(col), kw, anc, loop)
                    for col, kw, anc in expanded
                ]
                pipe(frame, instructions, default, force=force, skip=skip,
                     comment=comment, grow=grow)

    print(entry)
```

### 6. Update `_expand_bare_file_refs` — stays on raw tuples

`_expand_bare_file_refs` operates before loop resolution and continues to work on
`(col_spec_str, InsertKeyword, str)` tuples. No signature change needed beyond the
`keyword` type becoming `InsertKeyword`.

### 7. Update `_apply_instructions` → uses `InsertInstruction`

- Signature: `(frame, loop, instructions: List[InsertInstruction], default, force, skip, comment, grow)`
- Replace tuple unpacking with attribute access:
  - `instr.column_spec.col_name`, `instr.column_spec.value_spec`
  - `instr.keyword == InsertKeyword.BEFORE` etc.
  - `instr.anchor`

### 8. Refactor `pipe` — takes `Saveframe` + resolved `List[InsertInstruction]`

`pipe` is now a complete, testable API: given a frame and a list of fully-resolved
instructions (each carrying its target loop), it groups by loop and applies:

```python
def pipe(
    frame: Saveframe,
    instructions: List[InsertInstruction],
    default: str = ".",
    force: bool = False,
    skip: int = 0,
    comment: str = "",
    grow: bool = False,
) -> Saveframe:
    by_loop: Dict[int, Tuple[Loop, List[InsertInstruction]]] = {}
    for instr in instructions:
        key = id(instr.loop)
        if key not in by_loop:
            by_loop[key] = (instr.loop, [])
        by_loop[key][1].append(instr)
    for loop, group in by_loop.values():
        _apply_instructions(frame, loop, group, default,
                            force=force, skip=skip, comment=comment, grow=grow)
    return frame
```

---

## Future ideas (not in scope)

- A bare `frame.loop:` token (no col name) in the CLI arg stream could shift the default
  context for subsequent bare col specs — a "context setter" distinct from `--selector`.
- A `--with saveframe.loop` option as an alternative to `--selector`.

---

## Verification

```bash
cd nef_pipelines
nefl pytest src/nef_pipelines/tests/columns/test_insert.py -v
```

All existing tests should pass without modification.
Smoke-test the CLI manually:
```bash
echo <nef_data> | nefl columns insert --selector "frame.loop" col=val
```
