# Integrate qsv commands into `nef loops` via CSV stdin/stdout

## Context

`qsv` (https://github.com/dathere/qsv) is a fast CSV processing tool with 63 subcommands
covering filtering, sorting, column selection, deduplication and more. NMR scientists
working with NEF loops need these operations but building them all from scratch is
unnecessary. The goal is to wrap the NMR-relevant subset as `nef loops qsv-*` commands
that transparently convert a loop to CSV, pipe it through qsv, and parse the result
back into the loop — all within the normal NEF pipeline.

A code generator script (`scripts/generate_qsv_wrapper.py`) parses qsv's help output
to produce typer command stubs, making it easy to add further wrappers in future.

---

## Minimal initial command set

Five commands — four transforms (loop in → modified loop out) plus one diagnostic:

| nef command        | qsv command | type       | primary use for NMR data                  |
|--------------------|-------------|------------|-------------------------------------------|
| `loops qsv-search` | `search`    | transform  | filter rows by regex (e.g. only CA atoms) |
| `loops qsv-sort`   | `sort`      | transform  | sort by sequence number or value          |
| `loops qsv-slice`  | `slice`     | transform  | take a row range (first N, last N, etc.)  |
| `loops qsv-dedup`  | `dedup`     | transform  | remove duplicate rows                     |
| `loops qsv-stats`  | `stats`     | diagnostic | print summary statistics to stderr        |

`select` dropped: column picking is already handled by the NEF loop selector syntax
(`frame.loop:col1,col2`). qsv column names in other commands work directly because
`loop_to_csv` strips the category prefix (`_nef_chemical_shift.value` → `value`).

`rename` dropped: not commonly needed for NMR data; can be added later via the generator.

`stats` semantics: prints the qsv stats table to **stderr** and passes the NEF entry
unchanged to **stdout** — stays pipeline-safe, useful as an inline diagnostic.

Explicitly excluded from initial set: geographic tools, web fetching, Excel/JSON import,
compression, interactive viewer, LLM tools, file-indexed operations, output-splitting.

---

## Build order

1. **`lib/qsv_lib.py`** with tests (`tests/lib/test_qsv_lib.py`) — the substrate
2. **One command first** (`qsv-sort`) with full test coverage — validates the pattern
3. **Remaining four commands** — follow the same pattern, tests per command
4. **`scripts/generate_qsv_wrapper.py`** — code generator, built last once pattern is stable

---

## New files

### `src/nef_pipelines/lib/qsv_lib.py`
Shared substrate — three functions:

```python
def loop_to_csv(loop: Loop) -> str:
    """Serialise loop to CSV. Short tag names as headers (strip _category. prefix)."""

def csv_to_loop(csv_text: str, category: str) -> Loop:
    """Rebuild a Loop from CSV text, restoring the _category. prefix on all tags."""

def run_qsv(subcommand: str, args: list[str], csv_input: str) -> str:
    """Run qsv <subcommand> [args] with csv_input on stdin; return stdout.
    Calls exit_error on non-zero returncode, forwarding qsv stderr."""
```

NEF's UNUSED `.` value is passed through as-is. `run_qsv` checks that `qsv` is on
PATH and calls `exit_error` with a friendly message if not found.

### `src/nef_pipelines/tests/lib/test_qsv_lib.py`
Unit tests for `loop_to_csv`, `csv_to_loop` round-trip, and `run_qsv` (using
`qsv count` as a trivial smoke-test so tests don't require mocking subprocess).

### `src/nef_pipelines/tools/loops/qsv_commands.py`
Five `@loops_app.command(name="qsv-<cmd>")` functions sharing this pattern:

```python
@loops_app.command(name="qsv-sort")
def qsv_sort(
    selector: str = typer.Argument(..., help="frame.loop selector"),
    input: Path = typer.Option(STDIN, "--in", metavar="|PIPE|", ...),
    select: Optional[str] = typer.Option(None, "--select", help="columns to sort by"),
    numeric: bool = typer.Option(False, "--numeric", "-N", help="numeric sort"),
    reverse: bool = typer.Option(False, "--reverse", "-R", help="reverse order"),
    # ... remaining qsv-sort-specific options ...
) -> None:
    """- sort loop rows using qsv"""
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    entry = _pipe(entry, selector, _build_qsv_args("sort", select=select, ...))
    print(entry)
```

Shared private `_pipe(entry, selector, qsv_args)`:
1. Resolve selector → matched loops via `parse_frame_loop_selectors_and_get_errors`
2. For each loop: `loop_to_csv` → `run_qsv` → `csv_to_loop` → replace loop in frame
3. Return modified entry

`stats` variant: calls `run_qsv("stats", ..., csv)` then pipes result through
`qsv table` for readable formatting, writes to stderr, prints entry unchanged to stdout.

qsv "Common options" (`--output`, `--no-headers`, `--delimiter`, `--help`,
`--progressbar`) are **never** exposed.

### `src/nef_pipelines/tests/loops/test_qsv_commands.py`
One test file covering all five commands against a small fixed NEF entry.
Use `pytest.importorskip` or `@pytest.mark.skipif` to skip if `qsv` is not on PATH.

### `scripts/generate_qsv_wrapper.py`
Development-time code generator (built after the pattern is stable). Invoked as:
```
python scripts/generate_qsv_wrapper.py sort
```
Produces a typer command stub on stdout.

Parser reads `qsv <cmd> --help` and extracts:
- **Description**: lines before `Usage:`
- **Positional args**: usage line between `[options]` and `[<input>]`
- **Command-specific options**: section `<cmd> options:` up to `Common options:`
- **Option format** (regex): `^\s+(-\w,\s+)?--([\w-]+)(\s+<\w+>)?\s{2,}(.+)`
  - Has `<arg>` → `Optional[str] = typer.Option(None, ...)`
  - No `<arg>` → `bool = typer.Option(False, ...)`
- Converts `--ignore-case` → Python name `ignore_case`

---

## Modified files

- **`src/nef_pipelines/tools/loops/__init__.py`** — add
  `import nef_pipelines.tools.loops.qsv_commands  # noqa: F401  # deferred`

---

## Usage examples

```bash
# Filter to backbone heavy atoms only
nef ... | nef loops qsv-search nef_chemical_shift_list_1.nef_chemical_shift '^(CA|CB|C|N)$' --select atom_name

# Sort by sequence number (numeric)
nef ... | nef loops qsv-sort nef_chemical_shift_list_1.nef_chemical_shift --select sequence_code --numeric

# Inspect statistics inline without breaking the pipeline
nef ... | nef loops qsv-stats nef_chemical_shift_list_1.nef_chemical_shift | nef ...
```

---

## Verification

```bash
nefl test src/nef_pipelines/tests/lib/test_qsv_lib.py src/nef_pipelines/tests/loops/test_qsv_commands.py -q
```

Manual smoke-test each command against a real NEF file. Tests skip automatically if
`qsv` is not on PATH.
