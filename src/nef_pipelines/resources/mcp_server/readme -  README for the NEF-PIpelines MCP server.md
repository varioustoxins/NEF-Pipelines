# NEF-Pipelines: Reference for AI Assistants

NEF-Pipelines is a command-line toolkit for manipulating **NEF (NMR Exchange Format)** files and
converting NMR data between NEF and many third-party formats. You have it available via the MCP
tools in this session - you do not need to install anything.

**For deeper detail see:**
- `nef://cli-idioms`         - option / selector / escape syntax across commands
- `nef://nef-file-format`    - NEF STAR dialect (namespaces, saveframe categories, loop tags)
- `nef://nef-nmr-data-model` - molecular structure and atom-name model (4-string identifier, pseudoatoms)
- `nef://star-file-format`   - foundational STAR syntax
- `nef://skill`              - index of expert workflow skills; read before any non-trivial task
- `nef://readme`             - this document (overview, data model, command/transcoder catalogue)

---

## The NEF Data Model

A NEF file is a **STAR-format** text file (similar to NMR-STAR / mmCIF). For full syntax see
`nef://star-file-format`; for the NEF dialect on top of it see `nef://nef-file-format`.

```
data_<entry_name>                      ← top-level entry (one per file)

save_nef_molecular_system              ← save frame (named data container)
  _nef_molecular_system.sf_category   nef_molecular_system
  _nef_molecular_system.sf_framecode  nef_molecular_system
  _nef_molecular_system.ccpn_comment
;
this is a multi-line comment           ← multi-line strings open and close with ; in column 1
;

  loop_                                ← loop: tabular data (columns + rows)
    _nef_sequence.index
    _nef_sequence.chain_code
    _nef_sequence.sequence_code
    _nef_sequence.residue_name
    _nef_sequence.linking
    _nef_sequence.residue_variant
    _nef_sequence.cis_peptide

      1   A  1   HIS  start   .  .
      2   A  2   MET  middle  .  .
      3   A  3   GLY  end     .  .
  stop_                                ← loop terminator
save_

save_nef_chemical_shift_list_default
  _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
  _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_default

  loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value
    _nef_chemical_shift.value_uncertainty

    A  2  .  H   8.930837069  .
    A  2  .  N   131.3918342  .
    A  7  .  H  10.07446556   .
    A  7  .  N   127.7350966  .
  stop_
save_
```

**Key concepts:**

**Entry**: top-level container; the file begins with `data_<entry_name>`. Exactly one entry per
NEF file.

**Save frame**: named data block delimited by `save_<name>` … `save_`. Each frame has a
**category** (the *kind* of frame - e.g. `nef_chemical_shift_list`) and a **name** (a unique
identifier within the entry - e.g. `nef_chemical_shift_list_default`). Both are recorded inside
the frame as `_<category>.sf_category` and `_<category>.sf_framecode` tags.

**Loop**: tabular data within a frame, opened with `loop_` and closed with `stop_`. Column names
are `_<category>.<tag>`-prefixed; rows follow as whitespace-separated values. **Tag/column order
is arbitrary** - two semantically equivalent NEF files can list columns in different orders.
Always address columns by name, never by position.

**Tag**: scalar key/value pair within a frame, written as `_<category>.<tag>   value` outside any
loop.

**Sentinels:** `.` means unknown / not applicable / unused; `?` sometime means missing / not yet assigned.

**Common frame categories:**

| Frame category | Contains |
|---|---|
| `nef_molecular_system` | Sequence, chains, residues, cis-peptide flags |
| `nef_chemical_shift_list` | Chemical shift assignments |
| `nef_nmr_spectrum` | Peak lists with assignments |
| `nef_distance_restraint_list` | Distance restraints |
| `nef_dihedral_restraint_list` | Dihedral restraints |
| `nef_rdc_restraint_list` | RDC restraints |
| `nef_nmr_meta_data` | Entry metadata, history, UUID |

For the 4-string identifier (`chain_code`, `sequence_code`, `residue_name`, `atom_name`) that
links experimental data to the molecular system, see `nef://nef-nmr-data-model`.

---

## Command Architecture

Commands are hierarchical: `nef <group> [<subgroup>] <command> [OPTIONS] [ARGS]`. Group names
follow the object they operate on (`frames`, `chains`, `loops`, ...).

For the full set of selectors, option names, escape syntax, and multi-value argument forms see
`nef://cli-idioms`. The summary below is enough for command discovery.

**Discovery via MCP tools:**

```
nef_list_commands()                  - enumerate commands
nef_get_command_help("frames")       - help for a group or command
nef_get_command_help("*shift*")      - wildcard pattern
```

**Common options (most commands):**

| Option | Description |
|---|---|
| `-i / --in FILE` | Read NEF from FILE instead of stdin (`-` = stdin, the default) |
| `--out FILE` | Write output to FILE; `{entry}`, `{frame}`, `{loop}` placeholders expand |
| `-c / --chains` | Select chain(s); repeat or comma-separate (no spaces) |
| `-f / --force` | Overwrite existing output files |
| `-v / --verbose` | More detail on stderr; `-vv`, `-vvv` for more |

---

## Core Commands

| Group | Subcommands | What it does |
|---|---|---|
| `frames` | `create`, `list`, `delete`, `tabulate`, `display`, `filter`, `insert`, `rename`, `unassign` | Inspect and edit save frames. **Use `tabulate` to read loop data - never grep/awk**. `create` builds a new empty frame (see `nef://skill/adhoc-data` for ad-hoc construction) |
| `chains` | `list`, `clone`, `rename`, `renumber`, `align`, `validate` | Manage molecular chains |
| `loops` | `create`, `trim` | Loop-level operations. `create` adds a loop with columns and optional data to an existing frame |
| `columns` | `insert`, `delete`, `list`, `rename`, `reorder`, `replace`, `extract` | Manipulate loop columns: add, remove, reorder, rename, or bulk-replace values |
| `entry` | `rename`, `tree` | Rename the entry; show its hierarchical structure |
| `header` | (no subcommand) | Add a NEF header (UUID + history) to the stream |
| `save` | (no subcommand) | Write the stream to file(s); `save -` writes to stdout (pass-through) |
| `stream` | (no subcommand) | Open a NEF file into the pipeline |
| `sink` | (no subcommand) | Read and discard the stream (terminate without output) |
| `globals` | (no subcommand) | Set pipeline-wide options (`--verbose`, `--force`) |
| `namespace` | `list`, `catalog` | List namespaces in a file; show registered NEF namespaces |
| `peaks` | `match` | Match one peak list against another (α) |
| `shifts` | `average`, `correlation` | Average shifts from peaks (α); correlate two shift frames (α) |
| `series` | `build` | Build a data series |
| `simulate` | (various) | Simulate data |
| `fit` | (various) | Fitting operations (α) |
| `help` | `commands`, `about` | Show command help; show installation info |
| `test` | (no subcommand) | Run the test suite |
| `version` | (no subcommand) | Print version |
| `ai` | (various) | AI / MCP server tools |

α = alpha quality (limited test coverage; check `--help` and verify output).

---

## Transcoders (Import / Export)

R = import to NEF, W = export from NEF, α = alpha quality.

| Program | Direction | Data types |
|---|---|---|
| `xplor` | R | dihedrals, distances, sequence |
| `xplor` | W | rdcs |
| `csv` | R | peaks, rdcs |
| `deep` | R α | peaks |
| `nmrpipe` | R | peaks, sequence, shifts |
| `nmrview` | RW | peaks, shifts |
| `nmrview` | R | sequence |
| `nmrview` | W | sequences |
| `fasta` | RW | sequence |
| `echidna` | R | peaks |
| `sparky` | R | sequence, shifts, peaks |
| `sparky` | W | shifts, peaks |
| `mars` | R | peaks, sequence, shifts |
| `mars` | W | fixed assignments, fragments, input file, sequence, shifts |
| `modelfree` | W α | data |
| `pales` | RW | rdcs |
| `pales` | W | template |
| `rcsb` | R | sequence (from PDB / mmCIF by accession or file) |
| `rpf` | W α | shifts |
| `shifty` | W | predicted shifts |
| `shiftx2` | R α | predicted shifts |
| `nmrstar` | R α | project, rdcs, sequence, shifts (BMRB / NMR-STAR) |
| `talos` | R | order parameters, restraints, secondary structure, sequence |
| `talos` | W α | shifts |
| `ucbshift` | R | shifts, sequence |
| `xcamshift` | W | shifts |
| `xeasy` | R | peaks, sequence, shifts |

---

## Pipeline Architecture

Commands read NEF from stdin and write NEF to stdout. In a shell they chain with `|`; via MCP each
step is an array passed to `nef_execute_pipeline` (see `nef://cli-idioms` for the mapping).

```bash
# Create a NEF file from scratch (shell view)
nef header \
| nef fasta import sequence protein.fasta \
| nef sparky import shifts shifts.list \
| nef save output.nef

# Import from BMRB then export shifts to Sparky format
nef nmrstar import project 5387 \
| nef sparky export shifts -o shifts.txt

# Filter frames then pass through
nef stream input.nef \
| nef frames delete '*peak*' \
| nef save filtered.nef

# Clone chain A to make B and C
nef fasta import sequence --chains A protein.fasta \
| nef chains clone A 2 --chains B,C \
| nef save output.nef
```

## Anti-Patterns
When using the pipeline architecture you should **ALWAYS** strive to keep the complete process as one pipeline wihtout
intermediate files. This avoids creating extraneous files and makes a shell script version of the MCP command
pipeline more portable.
---

## Inspecting NEF Data

**Always use `nef frames tabulate`** to read NEF content - never grep, awk, or cat. NEF tag/column
order is arbitrary, frames are nested, and multi-line strings span lines, so single-line text
tools will give wrong answers. The MCP server's in-process executor does not have shell text tools
available anyway.

```
nef frames list -i file.nef                                  # all frames
nef frames tabulate nef_molecular_system -i file.nef         # sequence
nef frames tabulate nef_chemical_shift_list_default -i file.nef
nef frames tabulate nef_molecular_system.nef_sequence -i file.nef   # one loop
nef entry tree -i file.nef                                   # hierarchical view
```

`tabulate` correctly handles all NEF data types, sentinel values, and multi-loop frames. See
`nef://cli-idioms` for the full `frame.loop:tag` selector syntax and column-selection idioms.
