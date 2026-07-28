# File Instructions Refactoring

**Created:** 2026-07-27
**Part 1 — positional file settings:** ✅ implemented
**Part 2 — column headings:** ✅ implemented
**Test suite:** 1507 passed, 4 skipped

Supersedes `headerless-file-column-insert.md` (2026-07-06), whose automatic-detection design is
replaced by Part 2 here.

---

## Overview

One piece of work in two phases, sharing the same machinery.

| | scope | state |
|---|---|---|
| **Part 1** | `--comment` / `--skip` / `--skip-tail` / `--clear-comments` become positional | implemented |
| **Part 2** | whether a file's first row is headings — `--use-column-headings on\|off\|auto` | implemented |

Part 2 depends on Part 1's `FileSettings` stamping and is expressed as one more field on it.

---

# Part 1 — Positional file settings *(implemented)*

## Problem

`--skip` and `--comment` were global flags applying to every file reference in a command, so two
files with different comment prefixes or different numbers of leading rows could not be read in
one invocation.

## Design

Flags apply to _any_ `@file` references that **follow** them, in argv order, and may be repeated.
They are running state: once set, a flag affects every later column specification — across frame
and loop boundaries, and across different files — until a flag of the same kind changes it.

```bash
nef loops create \
  --comment '#'  'f.l:col1=@file1.csv:1' 'f.l:col2=@file1.csv:2' \
  --clear-comments --comment '!' --skip 5 \
                 'f.l:col3=@file2.csv:1'
```
- initial state no comments defined
- `--comment PREFIX` — add a comment prefix; repeatable and cumulative
- `--clear-comments` — remove **all** prefixes, returning to that initial state
- `--skip N` — rows to skip after comment removal
- `--skip-tail N` — trailing rows to skip

## How ordering works

The ordering problem is solved in one place: `_parse_ordered_col_instructions()` walks
`ctx.obj["sequence"]` (built by `track_order`) in argv order. This is the only point where argv
order and column-specification expansion are both visible — a single argv token expands to many
specifications, so command-line strings cannot be reconstructed and matched afterwards.

Two kinds of flag are interleaved with the specifications:

- **placement flags** (`--before`/`--after`/`--at`) bind the *pending* specifications and flush them
- **file-setting flags** (`--comment`/`--clear-comments`/`--skip`/`--skip-tail`) update running
  state and do **not** flush pending specifications

Every `ColumnPlacement` produced is stamped with a frozen `FileSettings(comment, skip, skip_tail)`
capturing the state in force where it appeared. That stamp travels through grouping, loop
resolution and bare-file expansion onto the resulting `InsertInstruction`.

## What was implemented

**Data structures** (`columns_structures.py`)
- `CommentInstruction(prefixes)`, `SkipInstruction(skip, skip_tail)`
- `FileSettings(comment, skip, skip_tail)` — frozen and hashable, used as a cache key
- `ResolvedFileValueSpecification(path, values)` — a file column already read into values,
  retaining its path so row-count diagnostics can still name the file
- removed `skip`, `comment`, `skip_tail` from `FileValueSpecification`
- `file_settings` on `ColumnPlacement` and `InsertInstruction`

**CLI parsing** (`insert.py`, `loops/create.py`, `columns/replace.py`)
- `--clear-comments` added; `--skip`, `--comment`, `--skip-tail` given `callback=track_order`
- `track_order` extended to record file-setting flags, including valueless boolean flags such as
  `--clear-comments`, which carry no value token for getopt to match
- `_placement_token_map()` generalised to `_tracked_token_map()` returning `(name, takes_value)`

**Instruction building** (`columns_cli_lib.py`)
- `_parse_ordered_col_instructions()` carries running settings and stamps each specification
- `_expand_bare_file_refs()` reads headings *using each specification's own settings*, so a bare
  `@file` preceded by `--comment`/`--skip` sees the same rows the later column read will see
- `_build_column_instructions()` propagates settings onto instructions

**Execution** (`columns_lib.py`)
- `apply_column_instructions()` walks the instruction stream maintaining comment/skip state,
  resolves file-backed columns through a two-level cache, then delegates to the existing
  `_group_instructions_by_loop()` + `_apply_instructions_by_loop()` machinery
- two-level caching: `raw_files` (path → raw text, read from disk once) and `filtered_files`
  ((path, settings) → text after comment removal and skipping)
- all placement, padding, column-clash and error handling stays in the single application path,
  so file columns, literals and ranges behave identically

## Breaking changes

- `--skip`/`--comment` apply from where they appear rather than globally
- a bare `@file` finds its column headings using the settings in force, so `--comment '#' @f.csv`
  takes headings from the first non-comment row rather than always row 1

---

# Part 2 — Column headings *(implemented)*

## Problem

`@file:N` reads a column by index. Whether the first row is a heading or real data cannot be
recovered from the specification — `@data.csv:1` is identical in both cases. Put another way, the
value after the `:` is being asked to say both *which* column is wanted and *how* to find it — by
heading name or by column index — and it cannot carry both meanings at once.

`headed.csv` — the first row names the columns:

```
source,uncertainty
foo,0.1
bar,0.05
```

`headerless.txt` — the first row is already data:

```
1   G   C1'   91.38
2   G   C2'   75.10
3   G   C3'   74.98
```

`:1` asks for the first column of either, but the right answer differs: `foo, bar` for the first
file, and `1, 2, 3` for the second. Today the first row is always taken as headings, so the
headerless file silently loses `1  G  C1'  91.38`.

## Why no detection rule alone can settle it

Rules operate on the *specifications*; the fact needed is about the *file*. Both readings of
"numbered → by index; named → by name, using the non-name part" were checked:

| reading | `headed.csv:1` | `headerless.txt:1` |
|---|---|---|
| numbered chops the heading too | correct | still loses row 1 |
| only named chops the heading | changes behaviour (below) | correct |

Neither is right in both cases, because the cases differ in the data, not the command. So a
heuristic is still the right *default* — it keeps commands short and is usually correct — but it
speaks up when it looks likely to be wrong, and is always overridable.

## Detection rules — the default

Applied per batch, where a batch is a run of consecutive file references sharing the same
`(path, settings)`. Non-file instructions do not break a batch.

| rule | batch column references | inference | warns |
|---|---|---|-----|
| 1 | all by position (`:1`, `:4`) | no heading row; every row is data | rarely, see below |
| 2 | any by name (`:atom_name`) | first row is headings | no  |
| 3 | mixed position and name | first row is headings | **yes** |

Rule 1 is usually right and usually silent. Numeric column headings are common enough that
inferring a headerless file is not by itself worth reporting. It is reported only when the first
row is made **entirely of non-numeric text**, which is the tell that the file may really have
headings — data rows in such files almost always carry a number somewhere.

When it does report, it names the override:

```
WARNING: all column references to headed.csv are by number, so it is being read as
         having no heading row; use --use-column-headings on if the first row is headings
```

Rule 2 needs no warning — referring to a column by name is itself an unambiguous statement that
headings exist.

Under the disjoint semantics below, Rule 3's inference (`on`) turns each numeric reference into a
*name* lookup, which will usually fail with "no column headed '5'". That is an improvement: the
mixed case fails loudly, with the warning explaining what was inferred, instead of silently
returning shifted data.

## Evidence — what the advisory has to catch

The heuristic was implemented and measured. For

```bash
nef columns insert --in - --selector myshifts.chemical_shift 'source=@headed.csv:1'
```

| | `source` column |
|---|---|
| shipped behaviour | `foo`, `bar` |
| under Rule 1 | `source`, `foo`, `bar` |

The heading text leaks in as data, rows shift down, and the loop grows a padded row:

```
A   2   GLN   N   123.22   source     <- column NAME as data
A   2   GLN   H   8.90     foo
.   .   .     .   .        bar        <- spurious row
```

Two sibling cases behave differently and are diagnostic: `:uncertainty` (a name) hits Rule 2 and
is fine, and bare `@f.csv:2` is expanded to a *name* by `_expand_bare_file_refs` before detection
runs, so it never reaches Rule 1.

## `--use-column-headings on|off|auto` — the override

Positional, in the same sense as `--comment`/`--skip`: applies to the `@file` references that
follow it, and may be repeated to change mode mid-command.

| value | meaning | references are | warns |
|---|---|---|---|
| `on` | first row after comment removal and `--skip` names the columns | **names only** — `:1` is the column headed `1` | no |
| `off` | no heading row; every row is data | **indices only** — `:1` is position 1 | no |
| `auto` | let the detection rules decide (**the default**) | as inferred | yes, when inferred |

**`auto` is what makes the flag reversible.** Without it, setting `on` or `off` once would pin
every later reference in the command.

Setting `on` or `off` silences **both** the Rule 1 and Rule 3 warnings for the references it
covers — the user has stated the fact being inferred, so there is nothing to warn about. An
explicit `auto` still warns: asking for an inference is asking to be told what was inferred.

## `on` and `off` are disjoint

This is what removes the ambiguity for good:

- with **`on`** a reference is *always* a name; `:1` looks for a column headed `1` and errors if
  there is none. Positional access is not available.
- with **`off`** a reference is *always* an index. Name lookup is not available.

So `:N` never has two possible meanings — the mode alone decides.

**Numeric headings therefore stop being a problem.** Under `on` a heading of `1` is simply a name;
under `off` no names are synthesised at all, so nothing can collide. Earlier revisions treated
this as a hazard requiring special handling; it needs none.

**Indexing into a file that does have headings** remains expressible, by composing two orthogonal
flags rather than overloading one:

```bash
--use-column-headings off --skip 1 'src=@headed.csv:1'      # -> foo, bar
```

`--skip 1` discards the heading row, `off` treats what remains as positional data. Verified
against the current machinery: `extract_column_from_text(text, "1", skip=1, has_header=False)`
returns `['foo', 'bar']`, identical to today's result.

```bash
# default is auto - heuristic infers "no headings" from the all-numeric ref, and WARNS
nef columns insert 'f.l:src=@headed.csv:1'

# by name - the ordinary way to read a headed file
nef columns insert --use-column-headings on 'f.l:src=@headed.csv:source'   # -> foo, bar

# by position on a headed file - discard the heading row, then index
nef columns insert --use-column-headings off --skip 1 'f.l:src=@headed.csv:1'

# headerless file - state it, no warning
nef loops create --use-column-headings off \
    'shifts.nef_chemical_shift:value=@headerless.txt:4'          # -> every row, none lost

# three modes in one command, in argv order
nef columns insert --use-column-headings off  'a=@raw.txt:1' \
                   --use-column-headings on   'b=@headed.csv:name' \
                   --use-column-headings auto 'c=@other.csv:2'
```

Note what `on` does **not** do: `--use-column-headings on 'src=@headed.csv:1'` is an error,
because there is no column headed `1`. That is the point.

Carried on `FileSettings` beside `comment`/`skip`/`skip_tail`, so it reuses the existing
per-specification stamping and the `(path, settings)` cache key with no new machinery.

## Errors the modes imply

Both replace a silent wrong answer. Note they state only how the file was read - the option
names are added by the caller, per the warning architecture below:

```
# name lookup while off - there are no headings to match
ERROR: column 'atom' not found in raw.txt; available columns are indexed as 1..4
       [the file was read as having no column headings]

# numeric reference while on - it is a name, and no such heading exists
ERROR: column '1' not found in headed.csv; available columns are: source, uncertainty
       [the first row was read as column headings]

# and when the mode was a guess rather than stated
ERROR: column 'atom' not found in raw.txt; available columns are: 1, G, C1', 91.38
       [the first row was read as column headings (inferred)]
```

The second removed the silent positional fallback in `_resolve_file_col_name`, which resolved an
integer reference by position even when headings were in use.

---

# Shared — warning architecture

**The pipe is unconditionally silent, and phrases nothing.** It takes no `quiet` parameter. It
returns *typed findings*, and the caller renders them.

A pipe must not name command line options, because it knows nothing about a command line. That
rules out returning ready-made sentences: the wording, and the option named in it, belong to the
caller. Returning strings also loses the *kind* of finding at the boundary, which forces the
caller into generic advice and into attaching it to warnings it does not belong to.

So `PipeOutput` gained a typed list. `entry` stays a field of its own, so a pipe still visibly
returns an entry:

```python
# lib/structures.py
PipeItem                            # base for typed things returned alongside the entry
Advisory(PipeItem)                  # base for non-fatal findings
PipeOutput.items: List[PipeItem]    # additive; warnings/output untouched

# columns_structures.py - facts, no wording
HeadingsInferredAdvisory(Advisory): path, has_header, is_mixed

# columns_cli_lib.py - named so it is evident it mints user facing text
build_advisory_message(advisory) -> str
```

```python
# pipe - describes, never phrases
def pipe(entry, column_instructions) -> PipeOutput:
    ...
    return PipeOutput(entry=entry, items=advisories)

# CLI - decides, and is the only layer that names options
report_advisories(result.items, quiet)
print(result.entry)
```

**The naming rule:** a function that builds user facing text may live in a library, but must be
named so that is obvious — `build_*_message` — because such text may name command line options
and that has to be visible at the call site rather than buried. `pipe()` and everything it calls
does neither.

Errors follow the same split, using dataclass exceptions that already existed: the exception
carries the facts, and the CLI formats them. Pipe-side error text states only how the file was
read, for example `[the first row was read as column headings (inferred)]`.

`--quiet` is a CLI flag only, on `columns insert`, `loops create` and `columns replace`.

**Trialled here, to be retrofitted:** other pipes keep using `warnings: List[str]` untouched and
can move to `items` one at a time. `FileOutput` as a `PipeItem` is the obvious next one, deferred
until there is real file output to shape it against.

---

# What was built

All of the below is done; the suite is at 1505 passed / 4 skipped.

1. ✅ `insert.pipe` / `apply_column_instructions` return `PipeOutput`; `quiet` dropped
2. ✅ `--quiet` on the three CLI commands, rendering returned findings
3. ✅ Rule 1 advisory, with the CLI naming the option that would settle it
4. ✅ `use_column_headings` (`on`/`off`/`auto`, default `auto`) on `FileSettings`, positional via
   `track_order`; overrides the inference and silences its advisory. The positional fallback in
   `_resolve_file_col_name` is gone, so with headings in use `:1` is the column *headed* `1`
5. ✅ the two by-index tests rewritten as `--use-column-headings off --skip 1`
6. ✅ 18 tests added, including the first coverage of `--skip-tail`, `--clear-comments` and
   `loops create`'s separate `ctx` path

Beyond the original plan:

- the `PipeItem` / `Advisory` typed-return trial described above, adopted after it became clear
  that returning sentences forced the pipe to name options
- `has_header` threaded through `parse_csv_text` → `parse_csv_as_dicts` →
  `extract_column_from_text` in both the `tabular_data_lib` and `columns_lib` layers

## Advisories are not reported alongside an error

When a command exits on an error the advisories are discarded rather than printed first. This is
deliberate: an error is already the actionable message, and advice about how a file was read
would only compete with it for attention. The error carries how the file was read anyway, for
example `[the first row was read as column headings (inferred)]`, so nothing diagnostic is lost.

# Files to change

| File | Changes |
|---|---|
| `tools/columns/columns_lib.py` | `apply_column_instructions` returns warnings, loses `quiet`; Rule 1 warning; honour the flag over the inference |
| `tools/columns/columns_structures.py` | `use_column_headings` on `FileSettings` |
| `tools/columns/columns_cli_lib.py` | register the flag in `_FILE_SETTING_FLAG_NAMES`; stamp it in `_parse_ordered_col_instructions` |
| `tools/columns/insert.py` | `pipe` returns `PipeOutput`; add `--use-column-headings`, `--quiet`; print warnings; update the help table, which still documents `col=@path:N` as positional |
| `tools/loops/create.py` | same flags; print warnings |
| `tools/columns/replace.py` | same flags; print warnings |
| `lib/tabular_data_lib.py` | `_resolve_file_col_name` must not fall back to positional when headings are in use |
| `tests/columns/test_insert.py` | update 2 by-index tests; add the tests below |
| `tests/loops/test_create.py` | positional-settings coverage |

# Tests

Column headings:

- Rule 1 fires — headerless file, all-numeric refs → row count equals file row count, first row
  present, **and** the warning is emitted naming the flag
- `--use-column-headings on` — headed file, name reference → heading consumed, **no** warning
- `--use-column-headings on` with a numeric reference → errors naming the available headings
- `--use-column-headings off` on a headerless file → all rows, no warning
- `--use-column-headings off` with a name reference → errors naming the column
- `--use-column-headings off --skip 1` on a headed file → matches the old by-index behaviour
- mode changed mid-command, including back to `auto`
- `--quiet` suppresses the warnings but not the behaviour
- pipe called directly returns warnings and prints nothing

Positional file settings — currently almost untested; one parametrised test with two cases covers
only the old global-flag path:

- two files with different `--comment` prefixes in one command
- `--clear-comments` alone, with no replacement prefix
- `--skip-tail`, which has no coverage at all today
- bare `@file` under no settings / `--skip 1` / `--comment '#'`, parametrised
- `loops create` with positional settings — its `ctx` path is distinct and was silently broken
  until `_parse_colum_specifications_or_exit_error` was fixed to take `ctx`

Per CLAUDE.md: `EXPECTED_` constants, `assert_lines_match`, `isolate_loop`, `run_and_report`,
`path_in_test_data`, IDs as the first element of each parametrised tuple. Test the pipe rather
than the Typer function, except for the positional-ordering tests, where the CLI *is* the thing
under test.

**Test data**: reuse `tests/columns/test_data/` where possible — `headed.csv`,
`values_with_comments.csv`, `values_with_skip.csv` already exist. A headerless all-numeric fixture
will be needed; ask before creating it.

---

# Decisions on record

- The flag is named after **the shape of the file, not the selection method**. An inverted name
  such as `--indexed-columns` would re-conflate "how you select a column" with "does the file have
  headings" — the confusion that caused this bug. `@headed.csv:1` is an indexed selection on
  a file that *does* have headings, and both must stay expressible.
- Advisories are discarded when a command exits on an error; an error is the actionable
  message and advice alongside it would only compete with it.
- Follow-up, not in scope here: numeric column ambiguity detection beyond the above.
