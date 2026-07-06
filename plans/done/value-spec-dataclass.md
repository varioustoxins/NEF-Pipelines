# Plan: `ValueSpec` — parsed representation for `value_spec: Optional[str]`

**STATUS: COMPLETE** ✅

**Implemented in:** `src/nef_pipelines/tools/columns/columns_structures.py`

**ValueSpec dataclasses created:**
- ✅ `DefaultValueSpecification` (line 40)
- ✅ `FileValueSpecification` (line 45)
- ✅ `RepeatValueSpec` (line 53)
- ✅ `RangeValueSpec` (line 59)
- ✅ `RangeFromValueSpec` (line 65)
- ✅ `LiteralsValueSpecification` (line 70)

**Used in:** `_resolve_values()` in `columns_lib.py` with `isinstance()` dispatch (line 446+)

**Design note**: Implemented as separate dataclasses (no enum discriminator), using `isinstance()` for dispatch as planned.

---

## Context

`ColumnSpec.value_spec` is currently `Optional[str]`, a raw string that encodes
one of several different value expressions. The actual parsing happens lazily in
`_resolve_values()` at call time. This mirrors the `col_spec: str` problem fixed
earlier: the type is a lie — it's really a discriminated union hiding in a string.
The goal is to parse `value_spec` eagerly at `ColumnSpec.from_str()` time and carry
a proper typed representation throughout because pipes are designed for programming
with structures not strings.

---

## value_spec mini-language (all forms)

| Form | Example | Meaning |
|------|---------|---------|
| `None` | — | fill with default |
| `@path` or `@path:col` | `@shifts.csv:value` | read from CSV file column |
| `val*N` | `A*19` | N copies of literal val |
| `val*` | `A*` | n_rows copies of val (adapts to row count) |
| `M..N` | `1..10` | integers M to N inclusive |
| `M..` | `1..` | n_rows integers from M (adapts to row count) |
| `v1,v2,...` | `ok,.,.` | comma-separated literals (fallback) |

---

## New types — all in `columns_lib.py`

### `ValueSpecKind` enum

```python
class ValueSpecKind(LowercaseStrEnum):
    DEFAULT    = auto()   # None → fill with default
    FILE       = auto()   # @path[:col]
    REPEAT     = auto()   # val*N
    FILL       = auto()   # val*
    RANGE      = auto()   # M..N
    RANGE_FROM = auto()   # M..
    LITERALS   = auto()   # v1,v2,...
```

### `ValueSpec` — one dataclass per variant, united by a type alias

Drop `ValueSpecKind` (the type itself IS the discriminator). Use separate
dataclasses so each carries only the fields it needs, and dispatch with
`isinstance()` for now — switch to `match/case` once Python 3.9 is retired.

```python
@dataclass
class DefaultValueSpec:
    pass

@dataclass
class FileValueSpec:
    path: Path
    col:  Optional[str]       # named col or 1-based index str; None → all cols

#TODO RepeatValueSpec and FillValueSpec could be merged with count as None or a sentinel representing infinity
#TODO could use inheritance debate!
@dataclass
class RepeatValueSpec:
    value: str
    count: int

@dataclass
class FillValueSpec:
    value: str

#TODO could use inheritance debate!
@dataclass
class RangeValueSpec:
    start: int
    end:   int

#TODO could use inheritance debate!
@dataclass
class RangeFromValueSpec:
    start: int

@dataclass
class LiteralsValueSpec:
    values: List[str]

ValueSpec = Union[
    DefaultValueSpec, FileValueSpec, RepeatValueSpec, FillValueSpec,
    RangeValueSpec, RangeFromValueSpec, LiteralsValueSpec,
]
```

### `parse_value_spec()` — standalone parser (not inside the dataclass)

Single `return result` at the bottom; `elif` chain for mutually-exclusive cases.
Note: the original fall-through (e.g. `*` present but count invalid → try `..`)
is preserved by checking validity before branching.

```python
def parse_value_spec(spec: Optional[str]) -> ValueSpec:
    if spec is None:
        result: ValueSpec = DefaultValueSpec()
    elif spec.startswith("@"):
        path, _, col = spec[1:].partition(":")
        result = FileValueSpec(path=Path(path), col=col or None)
    elif "*" in spec:
        val, _, count_str = spec.partition("*")
        if count_str == "":
            result = FillValueSpec(value=val)
        else:
            try:
                count = int(count_str)
                result = RepeatValueSpec(value=val, count=count) if count >= 0 else LiteralsValueSpec(values=spec.split(","))
            except ValueError:
                result = LiteralsValueSpec(values=spec.split(","))
    elif ".." in spec:
        start_str, _, end_str = spec.partition("..")
        try:
            start = int(start_str)
            result = RangeFromValueSpec(start=start) if end_str == "" else RangeValueSpec(start=start, end=int(end_str))
        except ValueError:
            result = LiteralsValueSpec(values=spec.split(","))
    else:
        result = LiteralsValueSpec(values=spec.split(","))
    return result
```

---

## Files to change

### `src/nef_pipelines/tools/columns/columns_lib.py`

1. Add the seven variant dataclasses, `ValueSpec` Union alias, and `parse_value_spec()` above `ColumnSpec`.
2. Change `ColumnSpec.value_spec: Optional[str]` → `value_spec: ValueSpec`.
3. Update `ColumnSpec.from_str()` to call `parse_value_spec(raw_spec)`.
4. Rewrite `_resolve_values` to accept `ValueSpec` and dispatch with `isinstance()`:

```python
def _resolve_values(
    value_spec: ValueSpec, n_rows: int, default: str,
    skip: int = 0, comment: str = "",
) -> List[str]:
    # TODO: replace isinstance chain with match/case once Python 3.9 is retired
    if isinstance(value_spec, DefaultValueSpec):
        result = [default] * n_rows
    elif isinstance(value_spec, FileValueSpec):
        result = _read_column_from_file(value_spec.path, value_spec.col, skip=skip, comment=comment)
    elif isinstance(value_spec, RepeatValueSpec):
        result = [value_spec.value] * value_spec.count
    elif isinstance(value_spec, FillValueSpec):
        result = [value_spec.value] * n_rows
    elif isinstance(value_spec, RangeValueSpec):
        s, e = value_spec.start, value_spec.end
        step = 1 if e >= s else -1
        result = [str(i) for i in range(s, e + step, step)]
    elif isinstance(value_spec, RangeFromValueSpec):
        result = [str(i) for i in range(value_spec.start, value_spec.start + n_rows)]
    else:  # LiteralsValueSpec
        result = list(value_spec.values)
    return result
```

No other call sites need changing — `_resolve_values` is only called from
`_apply_instructions`, which already gets `value_spec` via
`instr.column_spec.value_spec`.

---

## Verification

```bash
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines
nefl test src/nef_pipelines/tests/columns/test_insert.py -v
```

All 31 existing insert tests must pass without modification (they exercise the CLI
and go through the full parsing chain).

---

## Addendum: shared value spec across multiple column tags

### Motivation

`frame.loop:tag1,tag2,tag3=A*` should expand to three column specs each carrying `A*`.
Currently `_split_on_col_boundaries` finds `,tag3=` as the only boundary, producing
`['tag1,tag2', 'tag3=A*']` — the `tag1,tag2` segment has a literal comma and becomes
a malformed column name.

### How `_split_on_col_boundaries` currently works

- **Path 1** (`has_assignment = False`): no `=` anywhere → split on bare commas.
  `tag1,tag2,tag3` → `['tag1', 'tag2', 'tag3']` ✓
- **Path 2** (`has_assignment = True`): scan for `,identifier=` boundaries; split there.
  `tag1,tag2,tag3=A*` → boundary at `,tag3=` → `['tag1,tag2', 'tag3=A*']` ✗

### Fix

In `_split_on_col_boundaries` (`columns_lib.py`), after assembling `result` in path 2,
add a post-pass before `return` that expands bare-tag groups by inheriting the following
segment's value spec:

```python
    # Expand bare tag groups: ['tag1,tag2', 'tag3=spec'] → ['tag1=spec', 'tag2=spec', 'tag3=spec']
    expanded = []
    for i, seg in enumerate(result):
        if '=' not in seg and i + 1 < len(result) and '=' in result[i + 1]:
            _, _, spec = result[i + 1].partition('=')
            for bare_tag in seg.split(','):
                bare_tag = bare_tag.strip()
                if bare_tag:
                    expanded.append(f"{bare_tag}={spec}")
        else:
            expanded.append(seg)
    return [p for p in expanded if p]
```

**Resulting behaviour**:

| Input | Output |
|-------|--------|
| `tag1,tag2,tag3=A*` | `['tag1=A*', 'tag2=A*', 'tag3=A*']` |
| `tag1,tag2,tag3=A*,tag4=B*` | `['tag1=A*', 'tag2=A*', 'tag3=A*', 'tag4=B*']` |
| `tag1=v1,v2,tag2=v3` | `['tag1=v1,v2', 'tag2=v3']` (unchanged — segment has `=`) |
| `tag1,tag2` (no `=`) | `['tag1', 'tag2']` (path 1, unchanged) |

### Docstring update

Add a row to the Column Selectors section in `insert.py`:

```
frame.loop:tag1,tag2,tag3=SPEC   all three columns get the same value spec
```

### Tests to add

In `src/nef_pipelines/tests/columns/test_insert.py` (or a sibling unit-test file):

- `_split_on_col_boundaries("tag1,tag2,tag3=A*")` → `['tag1=A*', 'tag2=A*', 'tag3=A*']`
- `_split_on_col_boundaries("tag1,tag2,tag3=A*,tag4=B*")` → `['tag1=A*', 'tag2=A*', 'tag3=A*', 'tag4=B*']`
- `_split_on_col_boundaries("tag1=v1,v2,tag2=v3")` → `['tag1=v1,v2', 'tag2=v3']`
- Integration test: CLI token `shifts.nef_chemical_shift:index,flag=1..` inserts two columns

### Verification

```bash
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines
nefl test src/nef_pipelines/tests/columns/ -q
```

---

## Addendum: `--at` replace semantics and name-or-index anchor

### Motivation

`--at N` currently only accepts an integer and inserts at that position without removing
anything — making it identical to `--before N`. For `--at` to be semantically distinct
it should **replace**: remove the column at the anchor position and insert the new column
there. Accepting names as well as indices makes it consistent with `--before`/`--after`.

### Agreed design

| Flag | Anchor | Behaviour |
|------|--------|-----------|
| `--before ANCHOR` | name or index | insert before ANCHOR, nothing removed |
| `--after  ANCHOR` | name or index | insert after ANCHOR, nothing removed |
| `--at     ANCHOR` | name or index | remove column at ANCHOR, insert new column at that slot |

`--force` remains orthogonal — it handles the case where the *new* column's name already
exists elsewhere in the loop (not at the anchor slot).

### Changes

**`src/nef_pipelines/tools/columns/columns_lib.py`** — `_apply_instructions`:

Replace the `InsertPlacement.AT` block:

```python
# before
elif keyword == InsertPlacement.AT:
    if not isinstance(position_anchor, int):
        exit_error(f"--at requires an integer index, got '{position_anchor}'")
    idx = position_anchor - 1

# after
elif keyword == InsertPlacement.AT:
    resolved_anchor = _resolve_tag(position_anchor, loop.tags)
    if resolved_anchor not in loop.tags:
        exit_error(
            f"anchor column '{position_anchor}' not found in loop {loop.category.lstrip('_')}"
        )
    idx = loop.tags.index(resolved_anchor)
    loop.tags.pop(idx)
    for row in loop.data:
        row.pop(idx)
```

`_resolve_tag` already handles int→tag-name conversion (1-based) and string pass-through
(`columns_lib.py` line 284).  `_parse_position_anchor` already returns `Union[int, str]`
so no change needed there.

**`src/nef_pipelines/tools/columns/insert.py`** — docstring:

Update the `--at` bullet:
```
* **`--at, -@ <anchor>`**: replace the column at `<anchor>` (name or 1-based index).
```

### Tests to add

In `src/nef_pipelines/tests/columns/test_insert.py`:

- `--at chain_code` replaces `chain_code` with a new column of the same name (with `--force`)
- `--at chain_code` replaces `chain_code` with a column of a different name
- `--at 1` replaces the first column by index
- `--at` with a missing anchor errors cleanly

### Verification

```bash
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines
nefl test src/nef_pipelines/tests/columns/ -q
```

---

## TODO: Bare loop-level file import

### Idea

Allow `<frame>.<loop>=@file` as a top-level token (no `:col-spec`) to bulk-import all
columns from a CSV file into a loop, using the CSV headers as NEF column names. This is
the loop-level analogue of the existing bare `@path` column-level form.

Example:
```
nef columns insert --selector myframe  nef_chemical_shift=@shifts.csv
```

would create/populate the `nef_chemical_shift` loop with all columns from `shifts.csv`,
naming each NEF tag from the CSV header row.

### Open questions

- How does this interact with `--selector`? If selector is `frame`, then `loop=@file`
  is the token; if selector is `frame.loop`, there's no column spec at all.

  the selector and the loop spec have to match otherwise its an error

- Should it merge into an existing loop or error if one exists?

  yes as long as columsn don't match otherwise requires --force

- Is the syntax unambiguous with the existing `loop:col=@file` form?

  depends what the selector has selected...!

  **Resolution**: two unambiguous forms:
  - `frame.loop=@file` — fully qualified; the `.` before `=` (and no `:`) makes it
    unambiguously a loop-level import, not a column spec.
  - `loop:=@file` — with `--selector frame`; the `:=` sigil (colon immediately before `=`)
    signals "all columns into this loop" rather than a named column.

  `_peel_selector_prefix` already looks for `.` before `:` to detect a frame.loop prefix;
  the `frame.loop=@file` form (dot present, no colon) can be detected similarly.
  The `loop:=@file` form is a new token shape that the interleaved parser can recognise
  before passing to `_split_on_col_boundaries`.

### Status

Not yet designed or implemented — captured here for future planning.
