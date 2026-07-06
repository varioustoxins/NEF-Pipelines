# Plan: Implement Opus doc-improvement suggestions

## Context

Opus reviewed the MCP server documentation and identified that the docs teach the wrong reflex: the canonical example uses a pre-cleaned CSV, so AIs learn to clean up user files before feeding them to the pipeline. The underlying capability — consuming messy files as-is via `--skip`, `--comment`, and header-name substitution — exists but is buried and not demonstrated. Additionally, `nef://skills` (plural) is referenced in two places but the actual resource URI is `nef://skill` (singular), causing 404s.

---

## Files to modify

### 1. `src/nef_pipelines/resources/mcp_server/skill - how to use the NEF-Pipelines commands in a pipeline.md`

This is the `nef://skill` (pipeline skill) document.

**a) Add Cardinal Rule section** — insert between "Core Concepts" and "Sandbox" (after line 21, before line 23):

```markdown
## Cardinal Rule: Consume Input As-Is

**Never rewrite, clean, normalise, or re-export the user's input file before
feeding it to a pipeline.** If the input is messy, the pipeline must absorb
the mess — that is what `--skip`, `--comment`, header-name references, and
literal value specs exist for.

**Symptoms you are about to violate this rule:**
- You are about to call `nef_upload_file` with content derived from another file.
- You are mentally renaming column headers before reaching the pipeline.
- You are about to drop a column from the source rather than just not referencing it.

**Instead:** call `nef_get_command_help("loops create")` and
`nef_get_command_help("columns insert")` and re-read the `@file` and value-spec
syntax. Every transformation you need is available as an option.
```

**b) Fix `nef://skills` → `nef://skill`** — line 186, the note at the bottom of the Columns section.

**c) Add pipeline-consumer warning** in the `nef_read_me_first` tool description (after "Show the `information` field to the user verbatim"):

Add one sentence: `Before building any pipeline that reads a user file, re-read the Cardinal Rule in the "Consume Input As-Is" section of this document.`

**d) Replace "Build a NEF file from scratch" example** (lines 263–281) with a messy-input example showing `--skip`, header-name substitution, and not referencing unwanted columns:

```markdown
### Build a NEF file from scratch (no transcoder available)

When no transcoder fits the input, construct frames and loops manually and
consume the input file **as it stands** — do not clean it up first.

**Example:** a ligand shift file `pxo.txt` with a pre-header row, spaces in the
column name, and an `Index` column we don't want:

    Shifts
    Index   Name    Shift (ppm)
    1       H23     4.700
    ...

nef_execute_pipeline([
    ["header", "pxo"],
    ["frames", "create",
     "nef_molecular_system", "",
     "nef_chemical_shift_list", "pxo"],
    ["loops", "create",
     "nef_molecular_system.nef_sequence:"
     "chain_code=A,sequence_code=1,residue_name=PXO,"
     "linking=single,residue_variant=."],
    ["loops", "create", "--skip", "1",
     "nef_chemical_shift_list_pxo.nef_chemical_shift:"
     "chain_code=A*,sequence_code=@pxo.txt:Index,"
     "residue_name=PXO*,"
     "atom_name=@pxo.txt:Name,value=@pxo.txt:Shift_(ppm)"],
    ["save", "pxo.nef"],
])

Notes:
- `--skip 1` discards the `Shifts` pre-header row so the parser sees
  `Index Name Shift (ppm)` as the column header.
- `Shift (ppm)` is referenced as `Shift_(ppm)` — spaces in CSV/TSV headings
  are substituted with underscores automatically.
- `Index` is not referenced and is silently ignored.
- `A*` and `PXO*` repeat to fill the row count established by the file references.
- Zero intermediate files are written.
```

---

### 2. `src/nef_pipelines/resources/mcp_server/readme -  README for the NEF-PIpelines MCP server.md`

**a) Fix `nef://skills` → `nef://skill`** — Core Commands table, `frames` row (line 139).

**b) Expand Anti-Patterns section** (lines 228–231) — replace the single-sentence paragraph with:

```markdown
## Anti-Patterns

When using the pipeline architecture you should **ALWAYS** strive to keep the
complete process as one pipeline. Specifically:

1. **No intermediate NEF files.** Don't `save` and then `stream` the same
   data back in. Chain commands instead.

2. **No intermediate data files derived from the user's input.** If the user
   provides `foo.txt`, do not upload a tidied `foo.csv` and then point the
   pipeline at that new file. Use `--skip`, `--comment`, header-name
   substitution, and `@file:col` references against the original. See
   the "Cardinal Rule: Consume Input As-Is" section in `nef://skill`.

3. **No shell text tools.** No `grep`/`awk`/`sed`/`cat` over NEF data. Use
   `frames tabulate`, `frames list`, `entry tree`.

Avoiding intermediate files keeps provenance intact and makes the shell-script
equivalent of the MCP pipeline portable and reproducible.
```

---

### 3. `src/nef_pipelines/resources/preamble.md`

**Add one sentence after "Start here - every session:":**

`Before building any pipeline that reads a user-supplied file: read nef://skill → "Cardinal Rule: Consume Input As-Is". Do not pre-process or rewrite the user's input file.`

---

### 4. `src/nef_pipelines/tools/loops/create.py` — fix docstring

Fix issues in the current command docstring:

- Remove the stray `do` line (line 64)
- Fix typo: `froma` → `from a` (line 59)
- Fix unclosed bracket: `[which start at the value of  --comment...` → add `]` and fix double space
- Add missing multi-file-ref bullet: `@path1:c1,@path2` (comma-@ splits file refs)
- Add `val*` and `M..` (adapt-to-rows forms) which were implemented but not listed in the docstring

---

## Verification

```bash
# Smoke test loops create help renders correctly
python -m nef_pipelines.main loops create --help

# All tests still pass
python -m pytest src/nef_pipelines/tests/columns/ src/nef_pipelines/tests/loops/ -q
```
