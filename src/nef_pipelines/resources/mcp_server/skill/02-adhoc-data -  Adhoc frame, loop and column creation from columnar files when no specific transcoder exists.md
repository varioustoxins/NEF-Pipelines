# Building NEF Frames, Loops and Columns From Scratch

Use this skill when building NEF saveframes, loops, or columns from scratch using NEF-Pipelines
tools when no specific transcoder exists for the input file. Covers singleton vs named frames,
loops create, columns insert, and the complete workflow for constructing frames from columnar data.

## Why this skill exists

NEF transcoders (sparky, fasta, nmrview, etc.) create frames automatically from specific input file formats,
and should be used when a user provides an easily identified format. However, where no specific converter
exists a saveframe may need to be constructed by direct manipulation of frames, loops and columns using the
lower-level frame/loop/column toolkit described here.

This skill documents that toolkit, its gotchas, and the correct workflow order.

---

## The toolkit

| Command               | What it does                                                                                                                                           |
|:----------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------|
| `nef frames create`   | Create an empty saveframe                                                                                                                              |
| `nef loops create`    | Create a loop (with a placeholder column or optional columns and data filled in or from a file )                                                       |
| `nef loops delete`    | Remove entire loops from frames by pattern                                                                                                              |
| `nef columns insert`  | Add columns (with filler values or values froma file) to an existing loop; auto-creates the loop if absent |
| `nef columns rename`  | Rename one or more columns in a loop (`old=new` pairs)                                                                                                 |
| `nef columns delete`  | Remove one or more columns from a loop                                                                                                                 |

**Correct order:** `frames create` → `loops create` (or `columns insert` auto-creates it)

`loops create` requires a frame to already exist. `columns insert` will auto-create the loop
if it does not already exist, so a separate `loops create` step is optional when you are
populating all columns in one pipeline. `loops create` will creat a placeholder column if
no input columns are specified, th maybe be renamed, replaced or deleted later

---

## Syntax reference

### Selector grammar

All column and loop commands use a shared selector grammar built from three separators:

| Separator | Meaning | Example |
|:----------|:--------|:--------|
| `.` | Separates frame from loop | `myshifts.nef_chemical_shift` |
| `:` | Separates loop from column list | `myshifts.nef_chemical_shift:chain_code` |
| `,` | Separates columns in the list | `myshifts.nef_chemical_shift:chain_code,value` |

**Wildcards** are added automatically around frame and loop names, so partial names match:

```
myshifts          → matches nef_chemical_shift_list_myshifts
nef_chemical      → matches any frame whose name or category contains nef_chemical
```

---

### Value specs (`col=value_spec`)

In `loops create`, columns can carry a value spec using `=`:

| Form | Meaning | Rows produced |
|:-----|:--------|:--------------|
| `col` | No value — column declared empty | 0 (or padded with `.` to match other cols) |
| `col=A` | Single literal value | 1 |
| `col=A,B,C` | Comma-literal list — each value becomes one row | N values |
| `col=A*N` | Repeat `A` N times (e.g. `A*19`) | N |
| `col=A*` | Repeat `A` to fill the current row count (adapt-to-rows form) | n_rows |
| `col=M..N` | Integer range M to N inclusive (e.g. `1..19`; supports reverse `5..1`) | N−M+1 |
| `col=M..` | Integers from M filling the current row count (adapt-to-rows form) | n_rows |
| `col=@file.csv` | All non-empty lines after the header row, verbatim (whole line per row) | N from file |
| `col=@file.csv:colname` | Named column from CSV; NEF column name is `col` | N from file |
| `col=@/absolute/path/file.csv:colname` | Absolute path | N from file |

**Bare `@file` refs** — NEF column name is taken automatically from the CSV header (no `col=` prefix needed):

| Form | Meaning |
|:-----|:--------|
| `@path` | All columns in the CSV; each becomes a separate NEF column named from the header |
| `@path:colname` | One named CSV column; NEF column named from the CSV header |
| `@path:col1,col2` | Several columns from one file; each auto-named from the CSV header |
| `@path1:col1,@path2:col2` | Columns from multiple files — `,@` is the boundary between file refs |
| `@path1:c1,c2,@path2` | Mix: named cols from path1, all cols from path2 |

Bare refs require `--selector frame.loop` (or a fully-qualified `frame.loop:@path` prefix) so the
command knows which loop to target. They can be mixed freely with named `col=@path:col` specs.

**Rules:**
- If columns have different lengths, shorter columns are **padded with `.`** to match the longest.
- A lone literal (`col=A`) produces exactly one row. For example `col=.` produces one `.` but then
  other inputs may cause a column to be padded with `.`
- Multiple columns in one spec are separated by `,` — the parser detects a new column whenever
  it sees `,identifier=` (an identifier immediately followed by `=`). So `col1=A,B,col2=C,D`
  correctly produces two columns each with two values.
- Bare column names (no `=`) must come before any `col=value` specs in the same string, or use
  `col=.` as the sentinel-value form.
- Escape a literal `=` in a column name with `\=` (e.g. `weird\=tag`).
- Columns with names that contain spaces [e.g. in a TSV file] are supported, the spaces are translated to _.
- NEF headers support the full ascii character set so all the ods characters like *[]+=-~_ etc are supported

> Note: when building columns its often worth reading the data first and then filling empty or enumerated columns
>       so when reading a sequence you may read the amino acid column first, then fill the sequence_code column with
>       numbers and then set the chain_code column to a single chain such as `A`

```bash
# One row per column from literals:
'frame.loop:chain_code=A,sequence_code=1,residue_name=PXO'

# Three rows using comma-literal lists:
'frame.loop:chain_code=A,A,A,sequence_code=1,2,3,residue_name=PXO,PXO,PXO'

# N rows from a file (both columns from same CSV):
'frame.loop:chain_code=@seq.csv:chain_code,residue_name=@seq.csv:residue_name'

# N rows using repeat and range:
'frame.loop:chain_code=A*19,sequence_code=1..19'

# Mixed lengths — shorter column padded with '.':
'frame.loop:chain_code=A*2,value=1..3'
# → chain_code: A, A, .   value: 1, 2, 3
```

---

### Selector grammar for `loops create` and `columns insert`

Both commands share the same base syntax and `--selector` behaviour.

| `--selector` | Positional arg form | Example |
|:-------------|:--------------------|:--------|
| absent | `frame.loop:col=val` (fully qualified) | `myshifts.nef_chemical_shift:value=1.5` |
| `frame` | `loop:col=val` | `nef_chemical_shift:value=1.5` |
| `frame.loop` | `col=val` | `value=1.5` |

Multiple columns can appear in one positional arg using comma-literal lists or the
`col1=val,col2=val` form — the `identifier=` boundary is used to detect where one column spec
ends and the next begins.

```bash
# --selector sets the default frame.loop; col specs are bare:
nef columns insert --selector myshifts.nef_chemical_shift chain_code=A value=1.5,2.3

# No --selector; each arg is fully qualified:
nef columns insert myshifts.nef_chemical_shift:chain_code=A myshifts.nef_chemical_shift:value=1.5

# Multi-col in one quoted arg (both commands):
nef columns insert --selector myshifts.nef_chemical_shift 'chain_code=A,A,value=1.5,2.3'
nef loops create 'myshifts.nef_chemical_shift:chain_code=A,A,value=1.5,2.3'
```

`columns insert` also accepts `--force` to overwrite existing column values in place:
```bash
nef columns insert --selector frame.loop --force value=1.5,2.3
```

And auto-creates the loop if it does not yet exist:
```bash
# Even if nef_chemical_shift loop doesn't exist yet, this creates it:
nef columns insert --selector myshifts.nef_chemical_shift chain_code=A value=1.5
```

---

### File references (`@path`)

`@` marks a file path. The path follows directly after `@`:

```
@file.csv                        relative path — whole file (lines after header)
@/absolute/path/file.csv         absolute path
@../relative/path/file.csv       relative with traversal
@file.csv:colname                read named CSV column (NEF col name set by the lhs `col=`)
```

**Named form** (`col=@path:colname`) — you choose the NEF column name:
```bash
nef columns insert --selector frame.loop col=@data.csv:csv_col
```

**Bare form** (`@path…`) — NEF column name taken from the CSV header automatically:
```bash
# One column auto-named from header:
nef columns insert --selector frame.loop @data.csv:csv_col

# All columns in the file:
nef columns insert --selector frame.loop @data.csv

# Several columns from one file:
nef columns insert --selector frame.loop '@data.csv:col1,col2'

# Columns from two files in one argument (comma-@ splits file refs):
nef columns insert --selector frame.loop '@file1.csv:col1,@file2.csv:col2'

# Mix: two named cols from file1, all cols from file2:
nef columns insert --selector frame.loop '@file1.csv:col1,col2,@file2.csv'
```

Use `--skip N` to skip N leading metadata rows before the CSV header, and `--comment PREFIX`
to ignore comment lines (e.g. `--comment '#'`). Both apply to all `@file` references in the call.

For `columns replace`, the file token is a **separate positional argument** (not embedded in the selector):
```
nef columns replace myshifts.nef_chemical_shift:value @data.csv
nef columns replace myshifts.nef_chemical_shift:value @data.csv:value_col
```

---

## frames create — singleton vs named frames

`frames create` takes **alternating category/name pairs**.

### Named frame (has a suffix after the category)
```
nef frames create nef_chemical_shift_list my_shifts
```
Produces: `save_nef_chemical_shift_list_my_shifts`

### Singleton frame (framecode == category, no suffix)
Pass `""` as the name:
```
nef header | nef frames create nef_molecular_system ""
```
Produces:
```star
save_nef_molecular_system
   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system
save_
```

**Critical:** `nef_molecular_system` and `nef_nmr_meta_data` are singletons — their framecode
must equal their category exactly. Passing any non-empty name will produce a non-singleton
framecode (e.g. `nef_molecular_system_molecular_system`) which strict validators will reject.

### frames create --force
Add `--force` to overwrite an existing frame with the same framecode:
```
nef frames create --force nef_molecular_system ""
```

---

## loops create

Creates a loop inside an existing frame. The selector syntax is `frame.loop` or
`frame.loop:col1,col2=val,col3=@file`. The loop category determines the column tag prefix
(e.g. `nef_sequence` → columns will be `_nef_sequence.chain_code` etc.).

### Empty loop (columns only, no data rows)
```
nef loops create 'nef_molecular_system.nef_sequence:chain_code,sequence_code,residue_name,linking,residue_variant'
```
Creates the loop structure with those columns and no data rows.

### Loop with data — literal values (single row)
```
nef loops create 'nef_molecular_system.nef_sequence:chain_code=A,sequence_code=1,residue_name=Ala,linking=single,residue_variant=.'
```

### Loop with data — repeat and range
```
# 5 rows, chain_code all A, sequence_code 1-5, all Gly residues:
nef loops create 'nef_molecular_system.nef_sequence:chain_code=A*5,sequence_code=1..5,residue_name=Gly*5'
```

### Loop with data — from a CSV file (recommended for many rows)
```
nef loops create 'nef_chemical_shift_list_default.nef_chemical_shift:chain_code=@shifts.csv:chain_code,sequence_code=@shifts.csv:sequence_code,residue_name=@shifts.csv:residue_name,atom_name=@shifts.csv:atom_name,value=@shifts.csv:value'
```
Columns without `=` or with fewer rows than the longest column are padded with `.`.

### No columns specified
If no `:col` part is given, a `place_holder` column is added with a WARNING:
```
nef loops create nef_molecular_system.nef_sequence
# WARNING: no columns specified ... adding placeholder column 'place_holder'
```

### Multiple loops in one call
Pass multiple selectors to create several loops at once:
```
nef loops create 'frame1.loop1:col1,col2' 'frame2.loop2:col3'
```

---

## loops delete

Remove entire loops from frames using `frame.loop` selectors. Wildcards are automatically added
around patterns (substring matching), so partial loop category names work.

### Delete a single loop
```bash
nef loops delete myshifts.chemical_shift
```

### Delete loops by wildcard pattern
```bash
# Delete all loops containing "peak" in their category:
nef loops delete myshifts.peak

# Delete from all frames (leading . = wildcard frame):
nef loops delete .chemical_shift
```

### Delete multiple loops
Pass multiple selectors as separate arguments:
```bash
nef loops delete myshifts.chemical_shift myshifts.peak_restraint
```

Or use slash-separated selectors in a single argument:
```bash
nef loops delete "myshifts.chemical_shift/myshifts.peak_restraint"
```

### Substring matching
Patterns are wrapped with `*` automatically, so `chemical_shift` matches both
`nef_chemical_shift` and `nef_chemical_shift_error`. Use more specific patterns to target
individual loops:
```bash
# Matches both loops due to substring matching:
nef loops delete myshifts.nef

# More specific — only matches nef_chemical_shift:
nef loops delete myshifts.chemical_shift
```

**Common use case:** Remove temporary or intermediate loops after data processing:
```bash
# After merging loops, delete the originals:
nef loops delete frame.temp_loop1 frame.temp_loop2
```

---

## Complete example: protein molecular system from scratch

Given a simple sequence file `sequence.txt`:

```
# A random sequence
>SEQUENCE
(CHAIN NAME)  AA
A Gly
A Ala
A Arg
A Tyr
A Thr
```

### Step 1: Create the molecular system with sequence from the file with the first residue as sequenc_code 5

```bash
  nefl header my_protein                                                                                    \
| nefl frames create nef_molecular_system ""                                                                \
| nefl loops create --skip 1 nef_molecular_system.nef_sequence:residue_name=@sequence.txt:AA                \
| nefl columns insert  --skip 1 'nef_molecular_system.nef_sequence:chain_code=@sequence.txt::(CHAIN NAME)'  \
| nefl columns insert nef_molecular_system.nef_sequence:sequence_code=5..                                   \
| nefl columns insert nef_molecular_system.nef_sequence:linking=start,middle,middle,middle,end              \
| nefl columns insert 'nef_molecular_system.nef_sequence:residue_variant=.*'                                \
| nefl columns reorder nef_molecular_system.nef_sequence:chain_code,sequence_code,residue_name              \
| nef save my_protein.nef
```

**Key points:**
- rather than doing a single shot this builds up columns individually `frames create` → `loops create` → `columns insert`
- reading AA using `@sequence.txt:AA` fills the residue_names and ensures the frame has the right number of rows
- `@sequence.txt:CHAIN` reads the CHAIN column from the file
- `1..` generates sequence codes 1, 2, 3, 4, 5
- `linking=start,middle,middle,middle,end` specifies residue positions in the chain
- `residue_variant=.*` repeats `.` (no variant) 5 times
- for shell users note the use of ' s to hide * from the shell
- **AVOID using literal values** and read values directly from files unless this fails or is not possible as
  it's much more portable
- The column header `(CHAIN NAME)` is supported even though it has unusual characters and spaces as it can be
  distinguished as the file is tab delimited.
- Note the use of quotes for the shell which are not required in the MCP server

### Step 2: Verify the molecular system

```bash
nef frames tabulate nef_molecular_system --in my_protein.nef
```

Should show:
```
chain_code  sequence_code  residue_name  linking  residue_variant
A           1              Gly           start    .
A           2              Ala           middle   .
A           3              Arg           middle   .
A           4              Tyr           middle   .
A           5              Thr           end      .
```

####  result

```nef
save_nef_nmr_meta_data
   _nef_nmr_meta_data.sf_category      nef_nmr_meta_data
   _nef_nmr_meta_data.sf_framecode     nef_nmr_meta_data
   _nef_nmr_meta_data.format_name      nmr_exchange_format
   _nef_nmr_meta_data.format_version   1.1
   _nef_nmr_meta_data.program_name     NEFPipelines
   _nef_nmr_meta_data.script_name      nef/frames/create.py
   _nef_nmr_meta_data.program_version  0.1.125
   _nef_nmr_meta_data.creation_date    2026-05-26T11:15:25.203327
   _nef_nmr_meta_data.uuid             NEFPipelines-2026-05-26T11:15:25.203327-0974325884

   loop_
      _nef_run_history.run_number
      _nef_run_history.program_name
      _nef_run_history.program_version
      _nef_run_history.script_name

     1   NEFPipelines   0.1.125   nef/header.py

   stop_

save_

save_nef_molecular_system
   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system

   loop_
      _nef_sequence.chain_code
      _nef_sequence.sequence_code
      _nef_sequence.residue_name
      _nef_sequence.linking
      _nef_sequence.residue_variant

     A   1   GLY   start    .
     A   2   ALA   middle   .
     A   3   ARG   middle   .
     A   4   TYR   middle   .
     A   5   THR   end      .

   stop_

save_
```

> note you could also do
>  ```nef
>  nef header my_protein                                                                                             \
>| nef frames create nef_molecular_system ""                                                                         \
>| nef loops create --comment '#' --skip 1 nef_molecular_system.nef_sequence:residue_name=@sequence.txt:AA           \
>                                          'nef_molecular_system.nef_sequence:chain_code=@sequence.txt:(CHAIN NAME)' \
>                                          nef_molecular_system.nef_sequence:sequence_code=1..                       \
>                                          nef_molecular_system.nef_sequence:linking=start,middle,middle,middle,end  \
>                                          'nef_molecular_system.nef_sequence:residue_variant=.*'                    \
> | nef columns reorder nef_molecular_system.nef_sequence:chain_code,sequence_code,residue_name                      \
> | nef save my_protein.nef
```

### Step 3: Add chemical shifts (if available)

If you have a shifts file `shifts.csv`:
```
chain_code,sequence_code,residue_name,atom_name,value
A,2,Ala,H,8.24
A,2,Ala,N,122.5
A,3,Arg,H,8.41
```ad h

Add a shift list frame and populate it:
```bash
nef stream my_protein.nef                                                                       \
  | nef frames create nef_chemical_shift_list default                                           \
  | nef loops create                                                                            \
      nef_chemical_shift_list_default.nef_chemical_shift:chain_code=@shifts.csv:chain_code      \
      sequence_code=@shifts.csv:sequence_code,residue_name=@shifts.csv:residue_name             \
      atom_name=@shifts.csv:atom_name,value=@shifts.csv:value                                   \
  | nef save my_protein.nef
```

---

## Alternative: Importing from a complete TSV/CSV file with columns insert

When the source data already includes all required columns (chain_code, sequence_code,
residue_name, linking, residue_variant), use `frames create` followed by `columns insert`
reading directly from the file — no intermediate file creation needed.

Given `full_sequence.tsv`:
```
chain_code  sequence_code  residue_name  linking  residue_variant
A           1              Gly           start    .
A           2              Ala           middle   .
A           3              Arg           middle   .
A           4              Tyr           middle   .
A           5              Thr           end      .
```

Build the molecular system directly:
```bash
nef header my_protein                                               \
  | nef frames create nef_molecular_system ""                       \
  | nef loops create nef_molecular_system.nef_sequence              \
  | nef columns insert --selector nef_molecular_system.nef_sequence \
      chain_code=@full_sequence.tsv:chain_code                      \
      sequence_code=@full_sequence.tsv:sequence_code                \
      residue_name=@full_sequence.tsv:residue_name                  \
      linking=@full_sequence.tsv:linking                            \
      residue_variant=@full_sequence.tsv:residue_variant            \
  | nef save my_protein.nef
```

### Handling non-standard column names

If the file uses different column names, pipe through `columns rename` afterwards:

```bash
  | nef columns rename --selector nef_molecular_system.nef_sequence \
      res_name=residue_name seq_no=sequence_code \
```

If the file contains extra columns you don't want in the loop, drop them with `columns delete`:

```bash
  | nef columns delete --selector nef_molecular_system.nef_sequence:extra_col \
```

---

## Using `columns rename`

Rename one or more columns in a loop. Pass `--selector` to identify the frame/loop and then
one or more `old_name=new_name` positional arguments.

```bash
# Rename a single column:
nef columns rename --selector myshifts.nef_chemical_shift value=chemical_shift_value

# Rename multiple columns in one call:
nef columns rename --selector myshifts.nef_chemical_shift \
    sequence_code=seq_code value=shift_value

# Swap two columns atomically (safe — rename_map is built first, then applied):
nef columns rename --selector myshifts.nef_chemical_shift \
    chain_code=sequence_code sequence_code=chain_code
```

**Rules:**
- `old_name` must exist in the loop; errors if not found.
- The resulting tag list must not contain duplicates; errors if a rename would collide with
  an existing column name.
- Pairs are applied atomically — a `a→b, b→a` swap works correctly.

---

## Using `frames rename` to make a singleton

`frames rename --set-id` allows the id part of a frame name to be set.

---

## linking values for nef_sequence

| Molecule type | First residue | Middle residues | Last residue | Single residue |
|:--------------|:--------------|:----------------|:-------------|:---------------|
| Polymer (protein/DNA/RNA) | `start` | `middle` | `end` | `single` |
| Small molecule / ligand   | `single` | — | — | `single` |
| Unknown                   | `.` | `.` | `.` | `.` |

For small molecules and ligands, every residue uses `linking=single`.

---

## Common mistakes

- **Forgetting `""` for singletons** — produces `nef_molecular_system_molecular_system`
  instead of `nef_molecular_system`. Strict validators will reject this.
- **Trailing bare tag name after a value spec** — in `col1=A,B,bare_tag`, the parser sees no
  `bare_tag=` boundary so `bare_tag` is treated as a value for `col1`. Write `bare_tag=.` instead.
- **Forgetting shell quotes around the selector** — the shell interprets `:` and `,` in
  `frame.loop:col1,col2` as special characters in some contexts. Always quote: `'frame.loop:col1,col2'`.
- **Using `columns insert` on a pre-declared column without `--force`** — `columns insert` errors if a
  column already exists. Either use `--force` to overwrite, or declare and populate the column
  in the same `loops create` call using `=value_spec`.
- **Forgetting `--force` on `nef save`** when overwriting an existing file.
- **Using a transcoder** (fasta, sparky, nmrview) for ligands — none support
  `molecule_type=ligand`; use this manual workflow instead.
