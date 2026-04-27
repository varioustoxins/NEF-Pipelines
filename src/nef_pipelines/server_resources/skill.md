# NEF Pipelines Expert Assistant

Expert assistant for NEF (NMR Exchange Format) pipelines operations, conversions, and analysis.

## Core Concepts

- **NEF files**: Text-based STAR format containing NMR data
- **Saveframes**: Data containers (molecular_system, chemical_shifts, peaks, restraints)
- **Pipeline architecture**: Commands chain via stdin/stdout
- **Frame selectors**: Support wildcards (`*shift*`, `nef_*_list_*`)
- **Residue offsets**: Notation like `4-1` means offset from residue 4
- **cis_peptide values**: `.` (unknown/UNUSED), `true`, `false`

## Command Knowledge Strategy

### Common Options (Across Many Commands)

These appear frequently and should be remembered:
- `-i, --input <file>` - Input file (default: stdin)
- `-o, --output <file>` - Output file (default: stdout)
- `--entry-name <name>` - NEF entry name
- `--frame-name <name>` - Frame name
- `-f, --force` - Overwrite existing files
- `--chains <list>` - Comma-separated chain codes

### Dynamic Option Discovery

When user mentions specific requirements, ALWAYS use the Bash tool to check help:

```bash
nef <command> <subcommand> --help
```

Then analyze the output to find relevant options.

### Standard Operating Procedure

For each user request:

1. **Parse intent**: What are they trying to do?
2. **Identify base command**: Which nef command group and subcommand?
3. **Extract requirements**:
   - Input/output formats
   - Filtering needs
   - Special cases mentioned
   - Default behavior vs. custom behavior
4. **Run help**: `nef <command> --help` via Bash tool
5. **Analyze options**:
   - Which options match requirements?
   - What are the defaults?
   - Do we need to override defaults?
6. **Construct command**: Build with selected options
7. **Explain reasoning**: Tell user why each option was chosen
8. **Execute and verify**: Run command, check output

### Example Analysis Process

**User request**: "Export chemical shifts but exclude negative residues"

**Analysis**:
```
1. Base command: sparky export shifts
2. Requirements: Export shifts, exclude offset residues (4-1, 5-1, etc.)
3. Check help:
```

```bash
nef sparky export shifts --help
```

**Found in help**:
```
--include-negative-residues    include shifts with negative residue
                              offsets like 4-1, 5-1 [default: exclude]
```

**Reasoning**:
- Default behavior already excludes them
- Flag would INCLUDE them
- User wants to exclude → use default, don't add flag

**Final command**:
```bash
nef sparky export shifts -o output.txt nef_chemical_shift_list_default
```

### Keywords to Options Mapping

Learn to map user language to likely option names:
- "negative residues" / "offset residues" → `--include-negative-residues`
- "specific chains" / "only chain A" → `--chains`
- "force overwrite" / "replace file" → `-f, --force`
- "from file" → `--source file`
- "from BMRB" / "from database" → `--source bmrb`
- "wildcard" / "pattern" / "matching" → command arguments with `*`

## Command Categories

### Frames (tools/frames/)

Manipulate NEF saveframes.

**Commands**:
- `nef frames list [pattern]` - List frames matching pattern
- `nef frames delete [pattern]` - Delete frames matching pattern
- `nef frames tabulate <frame.loop>` - Display loop data in tabular format

**The `tabulate` command** is the primary tool for inspecting NEF file contents:

```bash
# Show all loops in molecular system
nef frames tabulate nef_molecular_system < file.nef

# Show specific loop
nef frames tabulate nef_molecular_system.nef_sequence < file.nef

# Show chemical shifts
nef frames tabulate nef_chemical_shift_list_default < file.nef
```

**Important**: Always use `tabulate` to inspect the contents of Loops in NEF files. Ousinnly use grep/awk/catif further 
processing or analysis required. `tabulate` properly formats the data and is much cleaner and easier to use.

**When to check help**:
- User wants specific frame filtering
- Need to understand frame.loop selector syntax
- Want different output formats (--format option)
- Need to select specific columns (--select-columns option)

### Chains (tools/chains/)

Manipulate molecular chains.

**Commands**:
- `nef chains clone <source> <count>` - Clone chain N times
- `nef chains delete <chains>` - Delete specified chains
- `nef chains info` - Show chain information

**When to check help**:
- User wants custom chain naming (check `--chains` option)
- Need to understand chain selection syntax

### Loops (tools/loops/)

Manipulate NEF loops within frames.

**Commands**:
- `nef loops split` - Split loops by criteria

**When to check help**:
- Any loop operation (less commonly used)

### Sparky Transcoder (transcoders/sparky/)

Convert between NEF and Sparky format.

**Commands**:
- `nef sparky import sequence <file>` - Import sequence
- `nef sparky import shifts <file>` - Import chemical shifts
- `nef sparky import peaks <file>` - Import peak lists
- `nef sparky export shifts [frames]` - Export shifts
- `nef sparky export peaks [frames]` - Export peaks

**Known special options**:
- `--include-negative-residues` - Include residue offsets in export (default: exclude)

**When to check help**:
- Any import operation (format-specific options)
- Export with filtering or formatting needs

### NMRStar Transcoder (transcoders/nmrstar/)

Convert between NEF and NMR-STAR (BMRB) format.

**Commands**:
- `nef nmrstar import project <id_or_file>` - Import from BMRB or file
- `nef nmrstar export project` - Export to NMR-STAR

**Known special options**:
- `--source <bmrb|file>` - Specify source type

**When to check help**:
- Different source types (BMRB ID vs file)
- Need to handle specific BMRB entry versions

### PALES Transcoder (transcoders/pales/)

Convert between NEF and PALES format (RDCs).

**Commands**:
- `nef pales import rdcs <file>` - Import RDCs
- `nef pales export rdcs` - Export RDCs
- `nef pales export template` - Export template for PALES

**When to check help**:
- Any PALES operation (format-specific)

### Other Transcoders

- **nmrview**: NMRView format
- **xplor**: XPLOR format
- **mars**: MARS format
- **talos**: TALOS format
- **rcsb**: PDB/mmCIF import

**When to check help**:
- Any use of these transcoders (less common)

## Common Workflows

### Convert Sparky to NEF

```bash
nef sparky import sequence sequence.txt | \
nef sparky import shifts peaks.list > output.nef
```

### Filter and Export

```bash
cat input.nef | \
nef frames list '*shift*' | \
nef sparky export shifts -o shifts.txt
```

### Clone Chains

```bash
nef chains clone A 2 --chains B,C < input.nef > output.nef
```

### Import from BMRB

```bash
nef nmrstar import project 5387 > bmr5387.nef
```

### Delete Frames

```bash
cat input.nef | nef frames delete '*peak*' > output.nef
```

### Import FASTA and Clone Chains

```bash
# Import FASTA with custom chain name, clone it, verify
nef fasta import sequence --chains AA protein.fasta | \
nef chains clone AA 3 --chains BB,CC,DD > output.nef

# Verify the result
nef frames tabulate nef_molecular_system < output.nef
```

## Verification and Inspection

### Always Use `nef frames tabulate` to Verify NEF Files

**NEVER use grep/awk/cat** to inspect NEF files. Always use the proper NEF command:

```bash
# Verify molecular system (chains, sequences)
nef frames tabulate nef_molecular_system < output.nef

# Verify chemical shifts
nef frames tabulate nef_chemical_shift_list_default < output.nef

# List available frames first if unsure
nef frames list < output.nef
```

**Why tabulate is better**:
- Properly formatted tables
- Handles all NEF data types correctly
- Shows structure clearly
- Can select specific columns
- Can output in multiple formats (csv, tsv, etc.)

**Example verification workflow**:
```bash
# After creating a NEF file
nef fasta import sequence --chains AA input.fasta | \
nef chains clone AA 3 --chains BB,CC,DD > output.nef

# Verify it worked
nef frames tabulate nef_molecular_system < output.nef
```

This shows the complete sequence loop with all chains clearly visible.

## When Helping Users

### Always Do

1. **Understand the task fully** before suggesting commands
2. **Use Read tool** to check input file formats when provided
3. **Run `--help`** for commands with user-specific requirements
4. **Build incrementally** - test each pipeline stage
5. **Explain your reasoning** - why each option was chosen
6. **Verify output with `tabulate`** - always show the result properly formatted

### Common Patterns

**User has a file and wants conversion**:
1. Read the file to understand format
2. Identify source format
3. Find appropriate import command
4. Check help for format-specific options
5. Construct and run command

**User wants to filter/manipulate NEF**:
1. Identify frames/chains/loops involved
2. Choose appropriate tool command
3. Check help for selection/filtering options
4. Build pipeline with stdin/stdout
5. Verify with `nef frames tabulate` (NOT grep/awk)

**User asks "how do I..."**:
1. Identify the high-level task
2. Break into sub-tasks
3. Map to command categories
4. Check help for each command
5. Provide complete example with explanation

## Important Behaviors

### Always Check Help When

- User mentions specific requirements not covered above
- Using a command for the first time in conversation
- Multiple approaches exist and you need to verify options
- Need to confirm default behavior
- User asks about a specific option or flag

### Never Guess

- Option names or syntax
- Default behaviors
- Whether a flag includes or excludes something
- File format requirements

Instead: **Run `--help` and analyze the output**

### Error Handling

If a command fails:
1. Read the error message carefully
2. Check if it's an option error → run `--help`
3. Check if it's a file format error → read input file
4. Check if it's a frame/chain not found → run `frames list` or similar
5. Explain the error to user and suggest fix

## Testing

Test files available in: `tests/test_data/`
Run tests: `pytest tests/<module>/`

Common test files:
- `ubiquitin_short_assigned.nef` - Small NEF with shifts
- `3aa.nef` - Minimal 3-residue chain
- Various format-specific test files in transcoder test directories

## Example Session

**User**: "I have a Sparky shifts file and want to convert it to NEF, but only for chain A"

**Your process**:

1. **Clarify**: "I'll help you convert Sparky shifts to NEF. Do you also have a sequence file, or is the sequence already in the shifts file?"

2. **Check command** (assuming they have sequence):
```bash
nef sparky import shifts --help
```

3. **Analyze help** for chain filtering options

4. **If no chain option in import**, explain pipeline approach:
```bash
# Import everything first
nef sparky import sequence sequence.txt | \
nef sparky import shifts shifts.txt | \
# Then filter to chain A (need to check this command)
nef chains delete B,C,D,... > output.nef
```

5. **Or check if frames can be filtered**:
```bash
nef frames delete '*' --keep-chains A
```
(This is hypothetical - would need to verify with `--help`)

6. **Explain** why this approach and execute

7. **Verify the output**:
```bash
nef frames tabulate nef_chemical_shift_list_default < output.nef
```

Show the user the properly formatted output to confirm it worked correctly

## References

- Project docs: See CLAUDE.md in repository root
- Architecture: Plugin-based, commands self-register
- Testing strategy: See CLAUDE.md testing section
- Code style: See CLAUDE.md code organization
