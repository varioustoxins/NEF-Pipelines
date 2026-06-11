# SKILL: Writing Readable NEF-Pipelines Shell Scripts

## Purpose
When a user asks for a pipeline expressed as a bash script they can run
themselves, apply these conventions. The `nef://cli-idioms` resource provides
the command reference needed to construct the pipeline; this skill covers how to
format it as a readable, maintainable bash script. Apply all conventions unless
the user explicitly overrides one.

---

## Conventions

### 1. Single pipeline, no intermediate files
If possible write the entire conversion as one unbroken pipeline from `nef header` to
`nef sink`. Never write NEF content to a variable or intermediate file mid-pipeline.

### 2. Align the first command with the `|` stages
Indent the opening `nef header` command by 2 spaces to visually align it with
the `|` pipeline stages that follow:

```bash
  nef header "${STEM}"                                                        \
\
| nef frames create nef_molecular_system ""                                   \
```

### 3. Inline comments via a `comment()` function
Define this function at the top of every script:

```bash
# function which passes stdin through, ignoring arguments, to allow comments in a pipeline
comment() { cat; }
```

Use it as a pipeline stage to label each logical block. It passes stdin through
unchanged, so it does not break the pipeline:

```bash
| comment "populate the sequence loop with the single ligand residue"         \
| nef columns insert --selector "${SEQ_LOOP}"                                 \
```

Do NOT use shell `#` comments inside the pipeline — bash terminates the pipe
at the `#` character, so every subsequent stage is silently dropped.

### 4. Bare `\` lines as section separators
Place a bare `\` on its own line between sections. It is a valid bash line
continuation and renders as a visual blank line without breaking the pipe:

```bash
| nef loops   create "${SEQ_LOOP}"                                            \
\
| comment "populate the sequence loop with the single ligand residue"         \
```

### 5. Break dense command lines across multiple steps or lines
A long command with many arguments is hard to read. Apply one or more of these
strategies:

**Split across pipeline steps.** If a command is doing too much at once,
consider whether the work can be spread across multiple commands. For example,
rather than passing all column data to `nef loops create` in one dense spec,
create a placeholder loop and populate it with separate `nef columns insert`,
`nef columns rename`, and `nef columns delete` steps — each doing one thing:

```bash
| nef loops   create "${SHIFT_LOOP}"                                        \
| nef columns insert --selector "${SHIFT_LOOP}" --skip 1                    \
      "@${INPUT}:Name,Shift (ppm)"                                          \
| comment "spaces in CSV headers are auto-converted to _ on insert"         \
| nef columns rename --selector "${SHIFT_LOOP}"                             \
      Name=atom_name                                                        \
      "Shift_(ppm)=value"                                                   \
| nef columns delete "${SHIFT_LOOP}:place_holder"                           \
```

**Split comma-separated arguments across lines.** The comma/slash/space syntax
exists for interactive one-liners; in scripts always prefer the per-line form.
When a command takes a list of either space or comma-separated values, consider
whether the command supports passing them as separate arguments instead — one
per line:

```bash
| nef columns insert --selector "${SEQ_LOOP}"                                 \
       chain_code=A                                                           \
       sequence_code=1                                                        \
       residue_name="${RESIDUE}"                                              \
       linking=single                                                         \
       residue_variant=.                                                      \
```

**Extract repeated or long values into variables.** A long string that appears
multiple times, or that makes a command line hard to scan, belongs in a named
variable defined in the preamble:

```bash
SEQ_LOOP="nef_molecular_system.nef_sequence"
SHIFT_LOOP="nef_chemical_shift_list_${STEM}.nef_chemical_shift"
```

Apply all three strategies together where appropriate — the goal is that each
line in the pipeline is short enough to read at a glance.

### 6. Right-align `\` continuations
Pad each line with spaces so all `\` land at the same column (typically the
longest line in the block). The `\` MUST be the very last character — any
space after it breaks the continuation. Use a tool to calculate padding rather
than counting by hand. **Measure the positions of `\` line endings carefully —
AIs are bad at calculating their positions.** See the appendix for a Python
snippet to calculate correct padding.

### 7. Preamble style
Separate each preamble section with a blank line. Place a block comment above
each section. Use inline `#` comments on definition lines to explain
non-obvious derivations, and align all `#` comments to the same column within
the definitions block — determined by the longest line:

```bash
# exit on error, undefined variable, or failed pipe
set -euo pipefail

# function which passes stdin through, ignoring arguments, to allow comments in a pipeline
comment() { cat; }

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input.txt>" >&2
    exit 1
fi

# definitions
INPUT="$1"
STEM="${INPUT%.*}"                                       # strip file extension
RESIDUE="$(echo "${STEM}" | tr '[:lower:]' '[:upper:]')" # uppercase for NEF residue name
OUTPUT="${STEM}.nef"
SEQ_LOOP="nef_molecular_system.nef_sequence"
SHIFT_LOOP="nef_chemical_shift_list_${STEM}.nef_chemical_shift"
```

### 8. Terminate with `nef sink`
Always end the pipeline with `nef sink`, making termination explicit and
symmetric with `nef header`:

```bash
| nef save --force "${OUTPUT}"                                                \
| nef sink
```

---

## Canonical example

Showing all conventions in context. See Appendix 2 for the complete working script.

```bash
#!/usr/bin/env bash
# exit on error, undefined variable, or failed pipe
set -euo pipefail

# function which passes stdin through, ignoring arguments, to allow comments in a pipeline
comment() { cat; }

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input.txt>" >&2
    exit 1
fi

# definitions
INPUT="$1"
STEM="${INPUT%.*}"                                       # strip file extension
RESIDUE="$(echo "${STEM}" | tr '[:lower:]' '[:upper:]')" # uppercase for NEF residue name
OUTPUT="${STEM}.nef"
SEQ_LOOP="nef_molecular_system.nef_sequence"
SHIFT_LOOP="nef_chemical_shift_list_${STEM}.nef_chemical_shift"

  nef header "${STEM}"                                              \
\
| comment "create the molecular system frame and sequence loop"     \
| nef frames  create nef_molecular_system ""                        \
| nef loops   create "${SEQ_LOOP}"                                  \
\
| comment "populate the sequence loop with the ligand residue"      \
| nef columns insert --selector "${SEQ_LOOP}"                       \
       chain_code=A                                                 \
       sequence_code=1                                              \
       residue_name="${RESIDUE}"                                    \
       linking=single                                               \
       residue_variant=.                                            \
| nef columns delete "${SEQ_LOOP}:place_holder"                     \
\
| comment "... further pipeline stages ..."                         \
| nef save --force "${OUTPUT}"                                      \
| nef sink
```

---

## Common mistakes to avoid

| Mistake                                    | Effect                            | Fix                                              |
|---                                         |---                                |---                                               |
| Space after `\`                            | Silent line continuation break    | `\` must be last character                       |
| `#` comment inside pipeline                | Terminates the pipe at that point | Use `comment()` instead                          |
| Blank line inside pipeline                 | Syntax error                      | Use bare `\` line instead                        |
| Dense single-step commands                 | Hard to read and maintain         | Split across steps, lines, or variables          |
| Repeating long strings inline              | Verbose and error-prone           | Extract into a named variable                    |
| `^^` or `,,` for case conversion           | Fails on macOS bash 3.2           | Use `tr '[:lower:]' '[:upper:]'`                 |
| No blank lines between preamble sections   | Dense, hard to scan               | Blank line between each section                  |
| Misaligned `\` or `#`                      | Hard to read; `\` may break pipe  | Use the padding snippet in the appendix          |

---

## Appendix 1: calculating correct padding for aligned `\` and `#`

AIs are unreliable at counting character positions by eye. Use this Python
snippet to calculate correct padding for a block of lines, then copy the
output into the script:

```python
# Align \ continuations or # comments to the column after the longest line.
# Edit `lines` to contain the raw content of each line (without trailing \ or #).
# Set `suffix` to '\' or '#' as needed.

lines = [
    'STEM="${INPUT%.*}"',
    'RESIDUE="$(echo "${STEM}" | tr \'[:lower:]\' \'[:upper:]\')"',
]
suffix = '#'
comments = [
    'strip file extension',
    'uppercase for NEF residue name',
]

target = max(len(l) for l in lines) + 1
for line, comment in zip(lines, comments):
    print(line + ' ' * (target - len(line)) + suffix + ' ' + comment)
```

Output:
```
STEM="${INPUT%.*}"                                       # strip file extension
RESIDUE="$(echo "${STEM}" | tr '[:lower:]' '[:upper:]')" # uppercase for NEF residue name
```

## Appendix 2: `convert_ligand_shifts.sh`

```bash
#!/usr/bin/env bash
# Convert ligand chemical shifts from a tab-separated text file to NEF format.
#
# Input format (tab-separated):
#   Row 1: title (e.g. "Shifts")
#   Row 2: headers: Index  Name  "Shift (ppm)"
#   Rows 3+: data
#
# Usage:  ./convert_ligand_shifts.sh <input.txt>
# Output: <input.nef>  (residue name taken from the input filename stem, uppercased)

# exit on error, undefined variable, or failed pipe
set -euo pipefail

# function which passes stdin through, ignoring arguments, to allow comments in a pipeline
comment() { cat; }

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <input.txt>" >&2
    exit 1
fi

# definitions
INPUT="$1"
STEM="${INPUT%.*}"                                       # strip file extension
RESIDUE="$(echo "${STEM}" | tr '[:lower:]' '[:upper:]')" # uppercase for NEF residue name
OUTPUT="${STEM}.nef"
SEQ_LOOP="nef_molecular_system.nef_sequence"
SHIFT_LOOP="nef_chemical_shift_list_${STEM}.nef_chemical_shift"

  nef header "${STEM}"                                                                       \
\
| comment "create the molecular system frame with a placeholder sequence loop"               \
| nef frames  create nef_molecular_system ""                                                 \
| nef loops   create "${SEQ_LOOP}"                                                           \
\
| comment "populate the sequence loop with the single ligand residue"                        \
| nef columns insert --selector "${SEQ_LOOP}"                                                \
       chain_code=A                                                                          \
       sequence_code=1                                                                       \
       residue_name="${RESIDUE}"                                                             \
       linking=single                                                                        \
       residue_variant=.                                                                     \
| nef columns delete "${SEQ_LOOP}:place_holder"                                              \
\
| comment "create an empty chemical shift list frame with a placeholder loop"                \
| nef frames  create nef_chemical_shift_list "${STEM}"                                       \
| nef loops   create "${SHIFT_LOOP}"                                                         \
\
| comment "read atom names and shift values from the input file, skipping the title row"     \
| nef columns insert --selector "${SHIFT_LOOP}" --skip 1                                     \
      "@${INPUT}:Name,Shift (ppm)"                                                           \
\
| comment "rename columns: spaces in CSV headers auto-convert to _ on insert"                \
| nef columns rename --selector "${SHIFT_LOOP}"                                              \
      Name=atom_name                                                                         \
      "Shift_(ppm)=value"                                                                    \
\
| comment "add constant columns for chain, sequence position, and residue name"              \
| nef columns insert --selector "${SHIFT_LOOP}"                                              \
       chain_code=A*                                                                         \
       sequence_code=1*                                                                      \
       residue_name="${RESIDUE}*"                                                            \
| nef columns delete "${SHIFT_LOOP}:place_holder"                                            \
\
| comment "put the columns in standard NEF order and save"                                   \
| nef columns reorder "${SHIFT_LOOP}:chain_code,sequence_code,residue_name,atom_name,value"  \
| nef save --force "${OUTPUT}"                                                               \
| nef sink

echo "Written: ${OUTPUT}"
```


## Appendix 3: The example input file `PXO.txt` `for convert_ligand_shifts.sh` generated by `Claude`

```txt
Shifts
Index	Name	Shift (ppm)
1	H23	4.700
4	H21	2.643
5	H22	2.713
7	H19	4.292
8	H20	3.062
14	H16	2.901
15	H17	2.114
17	H14	3.698
18	H15	3.406
24	H11	3.216
26	H12	4.700
29	H5	0.922
30	H6	0.922
31	H7	0.922
33	H8	1.098
34	H9	1.098
35	H10	1.098
37	H3	2.671
38	H4	3.836
```
