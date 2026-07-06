# Plan: `nef columns` command group

## Context

Adding a top-level `columns` group with 7 commands for inspecting and manipulating loop
columns in NEF saveframes. All commands use the `frame.loop:tag` selector syntax from
`parse_frame_loop_and_tags()` in `lib/cli_lib.py`. Each command follows the composable
pipe pattern (`pipe(entry, ...) -> Entry`).

The user also wants `extract` (write column data to file) and `replace` (read column data
from file), which can output/input CSV columns or simple one-value-per-line files.

---

## Verified facts (checked before writing this plan)

- **pynmrstar tag mutation**: `loop.clear_data()` clears data but keeps tags; `loop.tags[:] = new_order`
  (slice assignment) works; `loop.add_data(list_of_dicts)` matches dict keys to current tags.
  Confirmed approach for all column-reordering operations:
  ```python
  rows = list(loop_row_dict_iter(loop))
  loop.clear_data()
  loop.tags[:] = new_order   # slice-assign to mutate in place
  loop.add_data([{t: row.get(t, ".") for t in new_order} for row in rows])
  ```

- **`frames list` pipeline pattern**: `frames list` terminates the pipeline — it prints frame names
  to stdout and does NOT print the NEF entry. `columns list` uses the same pattern.
  It has `--write-error` to redirect output to stderr (allowing it to be chained if needed).

- **`select_frames` takes three args**: `select_frames(entry, patterns, selector_type)` —
  always pass `SelectionType.ANY` (or `NAME`) as the third argument.

---

## Commands

| Command | Pipeline | What it does |
|---|---|---|
| `nef columns list` | terminates | print column names in matching loops |
| `nef columns delete` | pass-through | remove one or more columns from matching loops |
| `nef columns rearrange` | pass-through | reorder columns; `*` = remaining in original order |
| `nef columns insert` | pass-through | add a new column at a specific position |
| `nef columns create` | pass-through | add a new column at the end (simple form of insert) |
| `nef columns extract` | pass-through | write column values to `--out` file (CSV or simple) |
| `nef columns replace` | pass-through | read column values from file and overwrite a column |

`create` vs `insert` distinction: `create` always appends (no position args), `insert` allows
`--at N`, `--before COL`, `--after COL`. They could be merged into one command in future.

---

## Selector syntax (all commands)

All commands accept selectors parsed via `parse_frame_loop_and_tags(spec)` (`lib/cli_lib.py:1448`):

```
myshifts.chemical_shift         # all columns in loop
myshifts.chemical_shift:value   # specific column
.chemical_shift:value           # matching loops in all frames
```

`parse_frame_loop_and_tags` returns `FrameLoopAndTagSelectors`:
- `frame_name` — pattern for saveframe name (default `"*"`)
- `loop_name` — pattern for loop category (None = frame-level only)
- `loop_tags` — list of column patterns (empty = all)

Resolve matching loops: `select_loops_by_category(frame.loops, [selector.loop_name])`
(`lib/nef_lib.py:719`).

---

## Module layout

```
src/nef_pipelines/tools/columns/
    __init__.py      ← registers columns_app; imports all 7 command submodules
    list_.py         ← "list" command (file suffix avoids shadowing list builtin)
    delete.py
    rearrange.py
    insert.py
    create.py
    extract.py
    replace.py

src/nef_pipelines/tests/columns/
    __init__.py
    test_list.py
    test_delete.py
    test_rearrange.py
    test_insert.py
    test_create.py
    test_extract.py
    test_replace.py
```

Add `"nef_pipelines.tools.columns"` to `_MODULES` in
`src/nef_pipelines/module_registry.py` (between `loops` and `namespace`).

---

## Step 1 — `tools/columns/__init__.py`

Pattern identical to `tools/loops/__init__.py`:

```python
import typer
from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

columns_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        columns_app,
        name="columns",
        help="- carry out operations on columns in nef loops [list, delete, rearrange, insert, create, extract, replace]",
        rich_help_panel="NEF manipulation",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    import nef_pipelines.tools.columns.list_      # noqa: F401
    import nef_pipelines.tools.columns.delete     # noqa: F401
    import nef_pipelines.tools.columns.rearrange  # noqa: F401
    import nef_pipelines.tools.columns.insert     # noqa: F401
    import nef_pipelines.tools.columns.create     # noqa: F401
    import nef_pipelines.tools.columns.extract    # noqa: F401
    import nef_pipelines.tools.columns.replace    # noqa: F401
```

---

## Step 2 — `columns list` (auto-detects pipe)

When stdout is a terminal: print column names to stdout (terminates pipeline).
When stdout is a pipe: automatically redirect column names to stderr; pass NEF entry through stdout.
Pattern matches `namespace list` — see `tools/namespace/list.py:488`.

```
# interactive: prints column names to stdout
nef columns list myshifts.chemical_shift

# in pipeline: column names go to stderr automatically, entry passes through
nef columns list myshifts.chemical_shift | nefl columns delete ...
```

```python
@columns_app.command("list")
def list_(
    input: Path = typer.Option(STDIN, "--in", ...),
    selectors: List[str] = typer.Argument(...),
) -> None:
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    piped = not sys.stdout.isatty()
    output = sys.stderr if piped else sys.stdout
    _print_columns(entry, selectors, output)
    if piped:
        print(entry)   # pass NEF through when piped
```

Output: one line per loop, format `frame_name.loop_category: col1, col2, ...`

**COMMENT** if the columns won't fit on the terminal tabulate them as other commands do if stdout is connected to a termianl

---

## Step 3 — `columns delete`

```
nef columns delete myshifts.chemical_shift:value_uncertainty
nef columns delete myshifts.chemical_shift:val1,val2
```

```python
def pipe(entry: Entry, selectors: List[str]) -> Entry:
    for spec in selectors:
        sel = parse_frame_loop_and_tags(spec)
        frames = select_frames(entry, [sel.frame_name], SelectionType.ANY)
        for frame in frames:
            loops = select_loops_by_category(frame.loops, [sel.loop_name] if sel.loop_name else [])
            for loop in loops:
                to_delete = _resolve_tags(loop, sel.loop_tags)  # error if unknown tag
                remaining = [t for t in loop.tags if t not in set(to_delete)]
                rows = list(loop_row_dict_iter(loop))
                loop.clear_data()
                loop.tags[:] = remaining
                if rows:
                    loop.add_data([{t: row[t] for t in remaining} for row in rows])
    return entry
```

---

## Step 4 — `columns rearrange`

Selector is a `--selector` **option** (not positional) to avoid argparse conflict with
the `column_order` list argument.

```
nef columns rearrange --selector myshifts.chemical_shift atom_name value *
nef columns rearrange --policy alphabetical --selector myshifts.chemical_shift
```

```python
class ColumnOrderPolicy(LowercaseStrEnum):
    CUSTOM       = auto()   # explicit list (with * for "the rest")
    ALPHABETICAL = auto()   # sort tags alphabetically

@columns_app.command()
def rearrange(
    input: Path = typer.Option(STDIN, "--in", ...),
    policy: ColumnOrderPolicy = typer.Option(ColumnOrderPolicy.CUSTOM, "--policy"),
    selector: str = typer.Option(..., "--selector", "-s"),
    column_order: List[str] = typer.Argument(None),  # may include "*"
) -> None:
    ...

def pipe(entry, selector, column_order, policy=ColumnOrderPolicy.CUSTOM) -> Entry:
    sel = parse_frame_loop_and_tags(selector)
    frames = select_frames(entry, [sel.frame_name], SelectionType.ANY)
    for frame in frames:
        loops = select_loops_by_category(frame.loops, [sel.loop_name] if sel.loop_name else [])
        for loop in loops:
            if policy == ColumnOrderPolicy.ALPHABETICAL:
                new_order = sorted(loop.tags)
            else:
                new_order = _expand_star(column_order, loop.tags)
            rows = list(loop_row_dict_iter(loop))
            loop.clear_data()
            loop.tags[:] = new_order
            if rows:
                loop.add_data([{t: row.get(t, ".") for t in new_order} for row in rows])
    return entry

def _expand_star(spec, current_tags):
    """Expand * to all tags not explicitly named, in their original relative order."""
    explicit = {c for c in spec if c != "*"}
    remaining = [t for t in current_tags if t not in explicit]
    result = []
    for col in spec:
        result.extend(remaining if col == "*" else [col])
    return result
```

**COMMENT** rather than using selector we could do

save_frame.loop tag_1,tag_2,*,tag_3

we should also allow  --selector save_frame.loop and .loop [all loops of the same category across the file]
the position of --selector on the line would need to be tracked and could be used with the alphabetical option

Error if an explicit column name in `column_order` is not in the loop.

---

## Step 5 — `columns insert`

Insert one or more brand-new columns at specific positions with values set to `--default`.
Uses interleaved `sys.argv` parsing so multiple columns + positions can be expressed in
one command. Position flags use `count=True` so they don't consume a value from typer —
the anchor sits in `sys.argv` as a regular token right after the flag.

```
nef columns insert --selector myshifts.chemical_shift \
    col1 --before atom_name \
    col2 --after value \
    col3                      # no modifier → append at end
    col4 --at 2
```
**COMMENT** fully qualified column loop and tag names can be used and no --selector is then required
selectors need to be tracke through the command linem loops can be specified and defaults [again tracked]

```python
_SKIP_W_VALUE  = {"--in", "-i", "--selector", "-s", "--default"}
_POS_FLAGS     = {
    "--before": "before", "-b": "before",
    "--after":  "after",  "-a": "after",
    "--at":     "at",     "-@": "at",
}
_POS_SHORT_CHARS = {"b", "a", "@"}

def _parse_interleaved(argv: List[str]) -> List[Tuple[str, str, Optional[str]]]:
    """Return list of (column_name, keyword, anchor) from raw sys.argv[1:]."""
    instructions, pending = [], []
    it = iter(argv)
    for token in it:
        if token in _SKIP_W_VALUE:
            next(it, None)                              # skip flag + its value
        elif token in _POS_FLAGS:
            anchor = next(it, None)                     # count=True didn't consume this
            kw = _POS_FLAGS[token]
            for col in pending:
                instructions.append((col, kw, anchor))
            pending = []
        elif (token.startswith("-") and not token.startswith("--")
              and len(token) > 2
              and all(c in _POS_SHORT_CHARS for c in token[1:])):
            exit_error(f"combined short options not supported: use flags separately, not '{token}'")
        elif not token.startswith("-"):
            pending.append(token)                       # column name
    for col in pending:
        instructions.append((col, "append", None))
    return instructions

@columns_app.command()
def insert(
    input: Path = typer.Option(STDIN, "--in"),
    selector: str = typer.Option(..., "--selector", "-s"),
    default: str = typer.Option(".", "--default"),
    before: int = typer.Option(0, "--before", "-b", count=True,
                               help="insert preceding columns before this column"),
    after: int  = typer.Option(0, "--after",  "-a", count=True,
                               help="insert preceding columns after this column"),
    at: int     = typer.Option(0, "--at",     "-@", count=True,
                               help="insert preceding columns at this 0-based index"),
    columns: List[str] = typer.Argument(None),
) -> None:
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    instructions = _parse_interleaved(sys.argv[1:])   # ignore typer's before/after/at/columns
    entry = pipe(entry, selector, instructions, default)
    print(entry)

def pipe(
    entry: Entry,
    selector: str,
    instructions: List[Tuple[str, str, Optional[str]]],  # (col, keyword, anchor)
    default: str = ".",
) -> Entry:
    sel = parse_frame_loop_and_tags(selector)
    for frame in select_frames(entry, [sel.frame_name], SelectionType.ANY):
        for loop in select_loops_by_category(frame.loops, [sel.loop_name] if sel.loop_name else []):
            _apply_instructions(loop, instructions, default)
    return entry
```

`--at N` is 0-based. Columns without a position modifier are appended at end in order.
Error if a column name already exists in the loop.

### Value specification (insert and create)

Column tokens may carry an optional `=value_spec` suffix. The `=` separator is
unambiguous because NEF tag names never contain `=`.

```
col_name                       # use --default for all rows
col_name=0.1,0.05,0.1,0.05    # comma-separated inline values
col_name=@errors.csv           # read from first/only column of file
col_name=@errors.csv:uncertainty  # read named column from file
```

```python
def _split_col_spec(token: str) -> Tuple[str, Optional[str]]:
    """Split 'col_name=value_spec' → (col_name, value_spec_or_None)."""
    parts = token.split("=", 1)
    return parts[0], parts[1] if len(parts) == 2 else None

def _resolve_values(value_spec: Optional[str], n_rows: int, default: str) -> List[str]:
    if value_spec is None:
        return [default] * n_rows
    if value_spec.startswith("@"):
        path, _, col = value_spec[1:].partition(":")
        return _read_column_from_file(Path(path), col or None)
    return value_spec.split(",")
```

`@file` uses the same CSV/simple file logic as `extract`/`replace`. Error if
resolved value count ≠ loop row count.

---

## Step 6 — `columns create`

Simplified form: always appends at end. No position args. Accepts the same
`col=value_spec` token format as `insert` (inline values or `@file:col`).

```
nef columns create --default . --selector myshifts.chemical_shift new_col
nef columns create --selector myshifts.chemical_shift \
    uncertainty=0.1,0.05,0.1,0.05 \
    label=@labels.csv:name
```

**COMMENT** before at==fter and at may be specified
```python
@columns_app.command()
def create(
    input: Path = typer.Option(STDIN, "--in"),
    selector: str = typer.Option(..., "--selector", "-s"),
    default: str = typer.Option(".", "--default"),
    columns: List[str] = typer.Argument(...),  # col or col=value_spec
) -> None:
    ...

def pipe(entry, selector, col_specs: List[str], default=".") -> Entry:
    sel = parse_frame_loop_and_tags(selector)
    for frame in select_frames(entry, [sel.frame_name], SelectionType.ANY):
        for loop in select_loops_by_category(frame.loops, [sel.loop_name] if sel.loop_name else []):
            for token in col_specs:
                col_name, value_spec = _split_col_spec(token)
                if col_name in loop.tags:
                    exit_error(f"column {col_name} already exists in {loop.category}")
                loop.add_tag(col_name)
                values = _resolve_values(value_spec, len(loop.data), default)
                set_column(loop, col_name, values)
    return entry
```

---

## Step 7 — `columns extract`

Write column values to `--out` file; NEF entry passes through stdout unchanged.
`--out` is required (cannot write both NEF and column data to same stdout stream).

```
nef columns extract --out values.csv myshifts.chemical_shift:value
nef columns extract --format simple --out values.txt myshifts.chemical_shift:atom_name
```

```python
class ExtractFormat(LowercaseStrEnum):
    CSV    = auto()   # header row + values (default)
    SIMPLE = auto()   # one value per line, no header

@columns_app.command()
def extract(
    input: Path = typer.Option(STDIN, "--in", ...),
    output: Path = typer.Option(..., "-o", "--out"),  # required
    format: ExtractFormat = typer.Option(ExtractFormat.CSV, "--format"),
    selectors: List[str] = typer.Argument(...),
) -> None:
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    pipe(entry, selectors, output, format)
    print(entry)   # NEF entry passes through

def pipe(entry, selectors, output, format=ExtractFormat.CSV) -> Entry:
    # collect (tag_name, [values]) for all selected columns across all matching loops
    # write to output file in requested format
    # CSV: first row = tag names, subsequent rows = values
    # SIMPLE: one value per line (only valid for a single column selection)
    ...
    return entry
```

---

## Step 8 — `columns replace`

Read column values from file; overwrite the column in matching loops.

```
nef columns replace --selector myshifts.chemical_shift:value values.csv
nef columns replace --format simple --selector myshifts.chemical_shift:atom_name values.txt
```

**COMMENT** this can just take lists of selectors and values or files, files are @filename.csv or @filename.csv:col_1,col_2
selectors shouldn't need --selector as its an argument not an option

full file paths should be /x/y/@z.csv [@ goes on the filename]

```python
@columns_app.command()
def replace(
    input: Path = typer.Option(STDIN, "--in", ...),
    format: ExtractFormat = typer.Option(ExtractFormat.CSV, "--format"),
    selector: str = typer.Option(..., "--selector", "-s"),
    file: Path = typer.Argument(...),
) -> None:
    ...

def pipe(entry, selector, file, format=ExtractFormat.CSV) -> Entry:
    # CSV: use header row to identify column name; SIMPLE: column name from selector
    # Use set_column(loop, col, values) from lib/nef_lib.py:1010
    # Error if row count in file ≠ row count in loop
    ...
```

---

## Key library references

| Symbol | File | Purpose |
|---|---|---|
| `parse_frame_loop_and_tags(spec)` | `lib/cli_lib.py:1448` | Parse frame.loop:tag selector |
| `select_frames(entry, pats, SelectionType.ANY)` | `lib/nef_lib.py` | Select saveframes by pattern |
| `select_loops_by_category(loops, patterns)` | `lib/nef_lib.py:719` | Select loops by category |
| `loop_row_dict_iter(loop)` | `lib/nef_lib.py:599` | Iterate rows as `{tag: value}` dicts |
| `set_column(loop, col, values)` | `lib/nef_lib.py:1010` | Set a column's values from a list |
| `set_column_to_value(loop, col, value)` | `lib/nef_lib.py:1044` | Fill a column with a single value |
| `read_entry_from_file_or_stdin_or_exit_error(path)` | `lib/nef_lib.py` | Standard stdin/file entry read |
| `LowercaseStrEnum` / `auto()` | `strenum` | Enum base for CLI options |
| `exit_error(msg)` | `lib/util.py` | Report error + exit 1 |
| `fnmatchcase` | `fnmatch` | Platform-consistent glob matching |
| `STDIN` | `lib/util.py` | Sentinel for stdin path |

---

## File changes

| Action | File |
|---|---|
| CREATE | `src/nef_pipelines/tools/columns/__init__.py` |
| CREATE | `src/nef_pipelines/tools/columns/list_.py` |
| CREATE | `src/nef_pipelines/tools/columns/delete.py` |
| CREATE | `src/nef_pipelines/tools/columns/rearrange.py` |
| CREATE | `src/nef_pipelines/tools/columns/insert.py` |
| CREATE | `src/nef_pipelines/tools/columns/create.py` |
| CREATE | `src/nef_pipelines/tools/columns/extract.py` |
| CREATE | `src/nef_pipelines/tools/columns/replace.py` |
| CREATE | `src/nef_pipelines/tests/columns/__init__.py` |
| CREATE | `src/nef_pipelines/tests/columns/test_list.py` |
| CREATE | `src/nef_pipelines/tests/columns/test_delete.py` |
| CREATE | `src/nef_pipelines/tests/columns/test_rearrange.py` |
| CREATE | `src/nef_pipelines/tests/columns/test_insert.py` |
| CREATE | `src/nef_pipelines/tests/columns/test_create.py` |
| CREATE | `src/nef_pipelines/tests/columns/test_extract.py` |
| CREATE | `src/nef_pipelines/tests/columns/test_replace.py` |
| MODIFY | `src/nef_pipelines/module_registry.py` (add `"nef_pipelines.tools.columns"`) |

---

## Verification

```bash
# list columns (terminates pipeline)
echo "" | nefl frames create nef_chemical_shift_list myshifts \
        | nefl csv import loop nef_chemical_shift_list_myshifts nef_chemical_shift shifts.csv \
        | nefl columns list myshifts.chemical_shift

# delete a column
... | nefl columns delete myshifts.chemical_shift:value_uncertainty

# rearrange columns (selector as --selector option)
... | nefl columns rearrange --selector myshifts.chemical_shift atom_name value '*'

# insert at position
... | nefl columns insert --before atom_name --default . --selector myshifts.chemical_shift my_col

# create (append at end)
... | nefl columns create --default 0.0 --selector myshifts.chemical_shift my_col

# extract to file, replace from file
... | nefl columns extract --out /tmp/vals.csv myshifts.chemical_shift:value
... | nefl columns replace --selector myshifts.chemical_shift:value /tmp/vals.csv

# run tests
nefl test src/nef_pipelines/tests/columns/
```
