# NEF-Pipelines CLI — Common Idioms and Patterns

This document covers the recurring patterns, option names, and argument conventions found across
NEF-Pipelines commands. Read it alongside the `skill` resource, which covers workflow guidance and
option discovery. This document covers *how* the CLI is structured, not *what to do with it*.

Command group names always reflect the primary object they operate on (`frames`, `chains`, `loops`,
`namespace`, `shifts`, `peaks`, ...). Knowing the object lets you guess the group.

> Note many commands take the things they act on as arugments, so `frames delete` would take a list of
> frame names; this also allows you to make intelligent guesses.

---

## CLI vs MCP — how the same idioms map

Examples in this document are written as shell pipelines for clarity. When using the MCP server you
do **not** type shell commands — you call `nef_execute_pipeline` with each pipeline step as a list
of arguments.

| Shell pipeline | MCP equivalent |
|---|---|
| `nef stream my.nef` | `['stream', 'my.nef']` |
| `nef frames delete ccpn_*` | `['frames', 'delete', 'ccpn_*']` |
| `nef save result.nef` | `['save', 'result.nef']` |

So the full pipeline:

```
nef stream my.nef | nef frames delete ccpn_* | nef save result.nef
```

is sent as:

```python
nef_execute_pipeline([
    ['stream', 'my.nef'],
    ['frames', 'delete', 'ccpn_*'],
    ['save', 'result.nef'],
])
```

Each step is a list of arguments only — no `nef`, no `|`, no shell quoting. File input and output
is currently relative to the MCP server's working directory; this is expected to move to a managed
file registry in future.

Use `nef_execute_pipeline(steps=[...])` for all commands — single steps and multi-step pipelines alike.

---

## Pipeline Architecture (shell view)

Every manipulation command reads NEF from stdin (`-`) and writes to stdout. `stream` opens a file
into the pipeline; `save` closes it to disk.

```
nef stream my.nef | nef frames delete ccpn_* | nef save result.nef
```

**`save -`** writes to stdout with entry delimiters — useful to inspect mid-pipeline or as the last
command when passing through without writing a file.

**`sink`** reads and discards the stream — terminates a pipeline without producing output.

**`globals`** at the head of a pipeline sets `--verbose` / `--force` for all downstream commands:

```
nef globals --force | nef stream my.nef | ... | nef save
```

---

## Input / Output Options

| Option | Short | Meaning |
|---|---|---|
| `--in FILE` | `-i` | Read NEF from file instead of stdin (`-` = stdin, the default) |
| `--out FILE` | | Write output to file; `{entry}`, `{frame}`, `{loop}` placeholders expand |
| `--force` | `-f` | Overwrite existing output files |
| `--verbose` | `-v` | More detail; many commands accept `-v` as a counter (`-vvv` = maximum) |

---

## Frame Selectors

NEF-Pipelines has two kinds of frame selector. Most commands take the simple form; a few
inspection commands (`frames tabulate`, `frames display`, `entry tree`) take the composite form.

### Simple Frame Selectors

A simple frame selector is a name pattern using `fnmatch`-style wildcards (`*`, `?`):

- Without `--exact`: the pattern is auto-wrapped (`*pattern*`) — `shift` matches `*shift*`
- With `--exact`: the pattern must match the whole string

By default the pattern is matched against the **frame name first, then the frame category** if no
name matches. Override with `--selector-type` (alias `-t` or `-s`):

```
--selector-type name       # match name only
--selector-type category   # match category only
--selector-type any        # name first, category as fallback (default)
```

### Frame.Loop:Tag Selectors

Composite selectors locate a specific loop or tag inside a frame. Used by `frames tabulate`,
`frames display`, and `entry tree`:

| Pattern | Selects |
|---|---|
| `frame` | entire saveframe (all tags + all loops) |
| `frame.loop` | one loop in one frame |
| `frame.1` | first loop in a frame by index |
| `frame:tag` | frame-level tag only (no loops) |
| `frame.loop:tag1,tag2` | specific columns in a loop |
| `.loop` | that loop in all frames |
| `:tag` | that frame-level tag in all frames |
| `*.*:*` | everything |

The `frame` part follows the same wildcard / `--exact` rules as simple selectors.

**Embedding separators in names.** When `--use-escapes` is active, doubled separators become
literals: `::` → `:`, `..` → `.`, `,,` → `,`. Some commands additionally accept a backslash escape
(`\:`, `\.`, `\,`); others only support the doubled form. Check each command's `--help` before
relying on `\`-style escapes.

---

## Chain / Residue Selectors

Chain codes are passed to `--chain` / `-c` as a comma-separated list or by repeating the flag:

```
--chain A,B           # comma list — no spaces
--chain A --chain B   # repeated flag — equivalent
```

Residue ranges follow `CHAIN:START..END` syntax:

| Form | Meaning |
|---|---|
| `A` | entire chain A |
| `A:10` | residue 10 in chain A |
| `A:10..20` | residues 10–20 in chain A |
| `A:10..` | residue 10 to end of chain A |
| `A:..20` | start of chain A to residue 20 |
| `A+B:10..20` | same range in chains A and B |
| `:10..20` | residues 10–20 in all chains |
| `10..20` | same, bare numbers (implied all chains) |

Ranges are merged automatically unless `--no-combine` is given.

**Chain offset syntax** for `chains clone`: `A:10..20+5` copies residues 10–20 with offset +5;
`A:+3` offsets the whole chain by 3.

---

## Multi-Value Arguments

Many commands accept values as repeated flags or comma-separated lists — both are equivalent:

```
--chain A,B,C       ≡   --chain A --chain B --chain C
--starts 1,10,20    ≡   --starts 1 --starts 10 --starts 20
```

**Old→new pairs** (for `frames rename`, `chains rename`): positional args alternate old/new.
Pairs can be space-separated or comma-joined:

```
nef chains rename A B C D      # A→B, C→D
nef chains rename A,B C,D      # same
```

---

## Include / Exclude Selectors (`+` / `-` / `!`)

Used for namespace filtering (`namespace list`), column selection
(`frames tabulate --select-columns`), and similar. The `parse_selector_lists` function in
`cli_lib.py` implements this pattern:

| Prefix | Action |
|---|---|
| `name` (bare) | include `name` |
| `+name` | include `name` (explicit) |
| `-name` or `!name` | exclude `name` |
| `+` (alone) | include all |
| `-` or `!` (alone) | exclude all |

**`!` is the shell-safe alias for `-`** — use `!nef` instead of `-nef` to avoid the shell
treating it as a flag.

Use `--` before the argument list to separate arguments from options when they start with `-`:

```
nef namespace list -- -ccpn     # exclude ccpn
nef namespace list !ccpn        # same, no -- needed
```

`--no-initial-selection` starts the selection empty rather than all-selected; subsequent `+`
selectors then add into the empty set.

---

## `frames tabulate` Column Selection

`--select-columns` (default `+*`) uses the same `+`/`-` selector idiom:

```
--select-columns chain_code,sequence_code   # include only these two columns
--select-columns -residue_name              # all columns except residue_name
--select-columns +*,-height                 # all columns except height
```

Prefix a column name with `--` to escape a leading `-` in the column name itself.

---

## Transcoder Structure

All transcoders follow the same multi-level hierarchy:

```
nef <program> import|export <datatype> [options] [files]
```

Examples:

```
nef fasta import sequence myprotein.fasta
nef sparky export peaks -i my.nef
nef talos export shifts
nef xplor import distances restraints.tbl
```

---

## Common Option Names (cross-command reference)

| Option | Meaning |
|---|---|
| `--chains` / `-c` | chain codes (comma-separated list or repeated flag) |
| `--starts` | first residue number(s) per chain |
| `--molecule-type` | `protein`, `dna`, `rna`, `carbohydrate` |
| `--entry-name` | override the NEF entry name |
| `--exact` / `-e` | disable wildcard wrapping on selectors |
| `--force` / `-f` | overwrite files |
| `--frame` / `-f` | limit to named frame(s) (singular form) |
| `--frames` / `-f` | limit to named frame(s) (plural form, same intent) |
| `--use-escapes` | enable `,,` `::` `..` escape sequences in selectors |
| `--no-initial-selection` | start include/exclude set empty instead of all-selected |
| `--selector-type` / `-t` or `-s` | `name\|category\|any` frame match mode |
| `--format` | output format: `plain`, `csv`, `markdown`, `psql`, etc. |
| `--abbreviate` | shorten column headings (needed for csv/tsv formats) |

---

## Naming of Outputs with Format-String Templates

Many output options have default destinations (often the current working directory), especially
export transcoders. The `--out` option (or a command-specific `--template`) accepts a string with
format placeholders that expand from the current entry, frame, loop, or chain:

```
--out "{entry}_{frame}.xpk"
```

Setting an explicit entry name (via `nef globals --entry-name <name>` or
`nef entry rename <name>`) gives consistent output filenames.

Notes:

1. `--out -` writes to stdout; if multiple files would be produced, header lines are emitted to
   delimit them. Useful for inspecting mid-pipeline output.
2. If `--out` points to a single file but multiple files would be produced, header lines are
   inserted in the same way.
3. Some commands accept `@err` (stderr) and `@out` (stdout) as symmetric pseudo-paths.
4. Some commands write to stdout when connected to a terminal but switch to stderr when stdout is
   a pipe — this avoids contaminating the NEF data stream with diagnostic output.

---

## Discovery Commands

```
nef help commands                                        # tree of all commands
nef help commands --display=table --format=markdown      # AI-friendly flat table
nef help commands "*sparky*"                             # filter by pattern
nef frames list -i my.nef                                # list frames in a file
nef frames list -i my.nef -vvv                           # with loop/tag detail
nef entry tree -i my.nef                                 # hierarchical tree view
nef namespace list -i my.nef                             # namespaces in a file
nef namespace catalog --format=ai                        # registered namespaces
```

Many commands also expose extended help with worked examples — check `nef <cmd> --help` before
guessing option names or default behaviour.
