# Namespace Manipulation Utilities Plan

**STATUS: PARTIALLY IMPLEMENTED**

**What was built:**
- ✅ `nef namespace list` - implemented in `src/nef_pipelines/tools/namespace/list.py`
- ✅ `nef namespace catalog` - bonus command to list registered namespaces (not in original plan)

**What's in stash:**
- ⚠️ `nef namespace rename` - **IN STASH** `stash@{6}: prepare`
- ⚠️ `nef namespace delete` - **IN STASH** `stash@{6}: prepare`
- Helper functions in `cli_lib.py`: `parse_namespace_selectors()`, `parse_mapping_options()`

To recover: `git stash show stash@{6} -p | git apply`

---

## Overview

Create utilities for listing, renaming, and deleting namespaces in NEF files. These commands will help users understand and manipulate the namespace prefixes used in tag, loop, and frame names.

**Definition**: "Namespace" is the prefix between the first `_` and second `_` in a tag/loop/frame name.

**Examples:**
- `_nef_sequence` → namespace: `nef`
- `_nef_chemical_shift` → namespace: `nef`
- `_custom_sequence` → namespace: `custom`
- `_bmrb_data` → namespace: `bmrb`
- `_nef_peak.position` → namespace: `nef` (nested tag, same namespace)

## Command Structure

Namespace manipulation will be a **top-level command group** (like `frames`, `loops`, `chains`):

```
nef namespace list       # List namespaces
nef namespace rename     # Rename namespace prefix
nef namespace delete     # Delete by namespace
```

Located in: `src/nef_pipelines/tools/namespace/`

## Commands to Implement

### 0. Add an understanding of namespaces to the nef skill

### 1. `nef namespace list` - List Namespaces

List all unique namespace prefixes found in selected frames, with optional inclusion/exclusion filtering.

**Modes:**

- **Basic mode (default)**: Output ordered set of unique namespace prefixes
  ```
  nef
  custom
  bmrb
  ```

- **Verbose mode (`--verbose`)**: Table showing namespaces by frame and loop with level indicator, program, and use
  ```
  Namespace   Frame                          Loop Category              Level   Program           Use
  ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  nef         nef_molecular_system           _nef_sequence              loop    NEF Standard      Standard NEF categories
  nef         nef_chemical_shift_list_1      _nef_chemical_shift        loop    NEF Standard      Standard NEF categories
  nef         nef_nmr_spectrum_1             _nef_peak                  loop    NEF Standard      Standard NEF categories
  nef         nef_nmr_spectrum_1             _nef_peak                  tag     NEF Standard      Standard NEF categories
  nefpls      nefpls_data_frame              _nefpls_custom             loop    NEF Pipelines     Format transcoding
  custom      custom_data_frame              _custom_values             loop    [Unknown]         [Unknown]
  custom      custom_data_frame              -                          frame   [Unknown]         [Unknown]
  ```

  Note:
  - Level shows where namespace appears: `frame` (frame.category), `loop` (loop.category), or `tag` (tag names only)
  - Program and Use columns lookup from registered namespace table (shown as [Unknown] for unregistered namespaces)

**Arguments:**
- `namespace_selectors`: Optional namespace patterns for filtering (supports wildcards)
  - Prefix with `+` to explicitly include: `+nef +custom`
  - Prefix with `-` to exclude: `-nef` (excludes nef namespace)
  - No prefix: defaults to include
  - Escape: `++namespace` for literal `+namespace`, `--namespace` for literal `-namespace`
  - Can be comma-separated or repeated arguments
  - List separator: `,` (use `,,` to escape literal comma in names)

**Options:**
- `-f/--frames <FRAME-SELECTOR>`: Limit to specific frames (supports wildcards)
- `-s/--selector <TYPE>`: Selection type (name, category, any)
- `-v/--verbose`: Show detailed table format
- `-i/--in <NEF-FILE>`: Input NEF file (default: stdin)
- `--invert`: Invert namespace selection (exclude matched, include unmatched)
- `--exact`: Exact frame specification
- `--exclude`: List of frames to exclude
- `--use-separator-escapes`: Allow escape sequences in names (`,,` for `,`). If not set and separator found in names, error with suggestion to use this flag

**Implementation notes:**
- Use `select_frames()` for frame selection (nef_lib.py:577-626)
- Iterate through selected frames and their loops
- Extract namespace from loop.category using pattern: `_<namespace>_<rest>`
- Also extract namespaces from sf_category and sf_framecode. note if they are incompatible [optional comments column]
- **Parse namespace selectors** with inclusion/exclusion logic:
  - Parse `namespace_selectors` using `parse_comma_separated_options()` with `,` separator
  - **Separator conflict handling**:
    - If `,` found in namespace names and `--use-separator-escapes` NOT set:
      - Exit with error: "Comma found in namespace names. Use --use-separator-escapes to enable escape sequences (`,,` for literal comma)"
    - If `--use-separator-escapes` set:
      - Process escape sequences: `,,` → `,` in namespace names
  - Process prefixes:
    - `+namespace` → explicitly include
    - `-namespace` → explicitly exclude
    - `++namespace` → escape to literal `+namespace`
    - `--namespace` → escape to literal `-namespace`
    - No prefix → defaults to include
  - Build inclusion and exclusion sets
  - Apply wildcard matching to namespace patterns
  - If `--invert`: swap inclusion/exclusion logic
  - Filter collected namespaces based on inclusion/exclusion rules
- For verbose mode, track namespace, frame.name, loop.category, **level type**, **program**, and **use**:
  - `frame`: namespace found in frame.category
  - `loop`: namespace found in loop.category
  - `tag`: namespace found only in tag names (not in loop.category)
  - `program`: Lookup from registered namespace mapping (or [Unknown])
  - `use`: Lookup from registered namespace mapping (or [Unknown])
- Create a namespace registry dict mapping namespace → (program, purpose)
- Skip duplicate/child namespace/level combinations within same frame/loop (as requested)
- Helper function: `extract_namespace(name: str) -> Optional[str]`
  - Parse `_<namespace>_...` pattern
  - Return namespace or None if pattern doesn't match
- Helper constant: `REGISTERED_NAMESPACES` dict with namespace → (program, purpose) mapping
- Output
  - Use `info()` for informational output (basic mode namespace list)
  - Use `warn()` for warnings (missing namespaces, orphaned frames, etc.)
  - both functions are in lib util? -  this should be in claude.md
  - when outputting tables use tabulate -  this should be in claude.md

### 2. `nef namespace rename` - Rename Namespace Prefix

Rename namespace prefixes across selected frames, updating all loop categories and tag names.

**Arguments:**
- `old_namespace`: Current namespace prefix (e.g., `nef`)
- `new_namespace`: New namespace prefix (e.g., `custom`)
- Alternative: `old_namespace:new_namespace` map format for batch renames
  - Can be repeated: `nef:mynef custom:mycustom`
  - Can be comma-separated: `nef:mynef,custom:mycustom`
  - List separator: `,` (use `,,` for literal comma)
  - Map separator: `:` (use `::` for literal colon)

**Options:**
- `-f/--frames <FRAME-SELECTOR>`: Limit to specific frames (supports wildcards)
- `-s/--selector <TYPE>`: Selection type (name, category, any)
- `-i/--in <NEF-FILE>`: Input NEF file
- `--use-separator-escapes`: Allow escape sequences (`,,` for `,`, `::` for `:`). If not set and separators found in names, error with suggestion
- `-v/--verbose`: Show detailed renaming report


**Implementation notes:**
- Parse namespace arguments using `parse_comma_separated_options()` from util.py
- Support both `:` separated mapping format and separate old/new arguments
- **Separator conflict handling**:
  - If `,` or `:` found in namespace names and `--use-separator-escapes` NOT set:
    - Exit with error: "Separator found in namespace names (`,` or `:`). Use --use-separator-escapes to enable escape sequences (`,,` for comma, `::` for colon)"
  - If `--use-separator-escapes` set:
    - Process escape sequences: `,,` → `,` and `::` → `:` in namespace names
- Find all selected saveframes with matching namespace
- Find all loops with categories matching `_<old_namespace>_*` pattern
- Rename loop.category: `_nef_sequence` → `_custom_sequence`
- Update all tag names in loop.tags list: `_nef_sequence.chain_code` → `_custom_sequence.chain_code`
- Also check and update frame.category if it matches pattern
- If new namespace already exists in different elements: silently merge namespaces (normal behavior)
- If old namespace doesn't exist: warn in verbose mode, continue (no-op)
- Validate new namespace follows naming conventions (alphanumeric + underscore)
- In verbose mode: Report number of loops/frames/tags renamed
- **Do not use regexes** - use simple string splitting with `_` delimiter

**Examples:**
```bash
# List all namespaces
cat input.nef | nef namespace list

# List only nef and custom namespaces
cat input.nef | nef namespace list +nef +custom

# List all except nef namespace
cat input.nef | nef namespace list -nef

# List with wildcards: all except nef* namespaces
cat input.nef | nef namespace list '-nef*'

# List in verbose mode with program/use info
cat input.nef | nef namespace list --verbose

# Inverted selection: list everything except what matches
cat input.nef | nef namespace list --invert nef custom

# With escape sequences for namespace containing comma
cat input.nef | nef namespace list --use-separator-escapes 'my,,namespace'
```

**Rename Examples:**
```bash
# Rename all nef namespace to custom
cat input.nef | nef namespace rename nef custom

# Result: _nef_sequence becomes _custom_sequence, etc.
```

### 3. `nef namespace delete` - Delete Loops/Frames/Tags by Namespace

Delete all loops/frames/tags matching specified namespace prefix(es) from selected frames.

**Arguments:**
- `namespaces`: One or more namespace prefixes (supports wildcards)
  - Can be repeated arguments: `nef custom test`
  - Or comma-separated: `nef,custom,test`
  - List separator: `,` (use `,,` for literal comma)

**Options:**
- `-f/--frames <FRAME-SELECTOR>`: Limit to specific frames (supports wildcards)
- `-s/--selector <TYPE>`: Selection type (name, category, any)
- `-i/--in <NEF-FILE>`: Input NEF file
- `--exact`: Disable wildcard matching (exact match only)
- `--level <LEVEL>`: Select what to delete - repeated or comma-separated
  - `frame`: Delete entire frames
  - `loop`: Delete loops (default)
  - `column-tag`: Delete loop tags (**WARNING: removes entire data columns from loops**)
  - `tag`: Delete straight tags (tags without associated loop data)
  - Can be comma-separated: `frame,loop,column-tag`
- `--use-separator-escapes`: Allow escape sequences (`,,` for `,`). If not set and separator found in names, error with suggestion
- `--remove-orphans`: Remove empty loops and frames after deletion
- `-v/--verbose`: Show detailed deletion report

**Implementation notes:**
- Parse namespace arguments using `parse_comma_separated_options()` from util.py
- Support both space-separated and comma-separated formats with `,` separator
- Parse level arguments (frame/loop/column-tag/tag) using same comma-separation logic
- **Separator conflict handling**:
  - If `,` found in namespace names and `--use-separator-escapes` NOT set:
    - Exit with error: "Comma found in namespace names. Use --use-separator-escapes to enable escape sequences (`,,` for literal comma)"
  - If `--use-separator-escapes` set:
    - Process escape sequences: `,,` → `,` in namespace names
- Extract namespace from frame.category, loop.category, and tag names using `extract_namespace()`
- Match against provided namespace pattern(s) with wildcard support
- Based on `--level` selection:
  - `frame`: Remove entire saveframes from entry
  - `loop`: Remove loops from saveframe.loops list (default)
  - `column-tag`: Remove tags from loop.tags (**deletes entire columns of data from loops**)
  - `tag`: Remove straight tags (standalone tags without loop data)
- Distinguish between:
  - **Column tags** (loop tags): Tags in `loop.tags` - part of loop structure with data columns
  - **Straight tags**: Standalone tags without associated loop data
- Track orphaned frames/loops:
  - Warn if deletion leaves frames with no loops
  - With `--remove-orphans`: automatically remove empty frames/loops
  - Without flag: leave empty but warn in verbose mode
- In verbose mode: Report detailed counts of deletions by type
- Support multiple namespace patterns with wildcards

**Example:**
```bash
# Delete loops with 'nef' namespace (default level)
cat input.nef | nef namespace delete nef

# Delete using repeated arguments
cat input.nef | nef namespace delete custom test

# Delete using comma-separated list
cat input.nef | nef namespace delete nef,custom,test

# Delete frames and loops
cat input.nef | nef namespace delete --level frame --level loop nef

# Delete frames, loops, column-tags (comma-separated levels)
cat input.nef | nef namespace delete --level frame,loop,column-tag nef

# Delete column-tags only (WARNING: removes data columns)
cat input.nef | nef namespace delete --level column-tag custom

# Delete straight tags only
cat input.nef | nef namespace delete --level tag custom

# With escape sequences for namespace containing comma
cat input.nef | nef namespace delete --use-separator-escapes 'my,,namespace'

# Remove orphaned frames after deletion
cat input.nef | nef namespace delete --remove-orphans --verbose nef
```

## File Locations

**New directories to create:**
- `src/nef_pipelines/tools/namespace/` - Namespace command group
- `src/nef_pipelines/tests/namespace/` - Namespace tests
- `src/nef_pipelines/tests/namespace/test_data/` - Test data

**New files to create:**
- `src/nef_pipelines/lib/namespace_lib.py` - Core namespace extraction utilities
- `src/nef_pipelines/tools/namespace/__init__.py` - Register namespace_app with main
- `src/nef_pipelines/tools/namespace/list.py` - List command
- `src/nef_pipelines/tools/namespace/rename.py` - Rename command
- `src/nef_pipelines/tools/namespace/delete.py` - Delete command
- `src/nef_pipelines/tests/lib/test_namespace_lib.py` - Tests for namespace_lib
- `src/nef_pipelines/tests/namespace/test_list.py` - Tests for list
- `src/nef_pipelines/tests/namespace/test_rename.py` - Tests for rename
- `src/nef_pipelines/tests/namespace/test_delete.py` - Tests for delete
- `src/nef_pipelines/tests/namespace/test_data/namespace_test.nef` - Test data with multiple namespaces

**Files to modify:**
- `src/nef_pipelines/main.py` or plugin entry points - Register namespace tool module

## Implementation Pattern

Each command follows the standard NEF-Pipelines pattern:

```python
# Create namespace_app in __init__.py
from typer import Typer
namespace_app = Typer()

# Typer-decorated CLI function in each command file
@namespace_app.command()
def command_name(
    input: Path = typer.Option(Path("-"), "-i", "--in"),
    frame_selectors: List[str] = typer.Option(None, "-f", "--frames"),
    selector_type: SelectionType = typer.Option(SelectionType.ANY, "-s", "--selector"),
):
    """CLI docstring"""
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    result = pipe(entry, frame_selectors, selector_type, ...)
    print(result)

# Worker function with business logic
def pipe(
    entry: Entry,
    frame_selectors: List[str],
    selector_type: SelectionType,
    ...
) -> Entry:
    """Pure Python function that does the actual work"""
    frames = select_frames(entry, frame_selectors, selector_type)
    # Business logic here
    return entry
```

## Core Helper Functions

Create in `src/nef_pipelines/lib/namespace_lib.py`:

```python
# Registered namespace mapping from NEF specification
REGISTERED_NAMESPACES = {
    'nef': ('NEF Standard', 'Standard NEF categories'),
    'nefpls': ('NEF Pipelines', 'Format transcoding and NEF manipulation'),
    'amber': ('Amber', 'Structure modelling and refinement'),
    'aria': ('Aria', 'Structure calculation'),
    'ccpn': ('CcpNmr Analysis', 'NMR spectra processing and data analysis'),
    'csrosetta': ('CS-Rosetta', 'Structure calculation'),
    'cyana': ('Cyana', 'Structure calculation'),
    'meld': ('MELD', 'Structure modelling and refinement'),
    'NMRFx': ('NMRFx', 'Structure calculation'),
    'pdbstat': ('PDBStat', 'NMR data validation'),
    'unio': ('Unio NMR', 'Structure calculation'),
    'unres': ('Unres', 'Structure modelling and refinement'),
    'pdbx': ('wwPDB/BMRB', 'Database'),
    'XplorNIH': ('Xplor-NIH', 'Structure calculation and refinement'),
    'yasara': ('Yasara', 'Structure refinement'),
}


def extract_namespace(name: str) -> Optional[str]:
    """
    Extract namespace from a tag, loop, or frame name.

    Pattern: _<namespace>_<rest>

    Examples:
        _nef_sequence → nef
        _custom_data → custom
        _nef_peak.position → nef
        nef_molecular_system → None (no leading underscore)

    Args:
        name: Tag, loop category, or frame name

    Returns:
        Namespace string or None if pattern doesn't match
    """
    if not name.startswith('_'):
        return None

    parts = name[1:].split('_', 1)  # Split at first underscore after leading _
    if len(parts) >= 2:
        return parts[0]
    return None


def collect_namespaces_from_frames(
    frames: List[Saveframe]
) -> Dict[str, List[Tuple[str, str, str]]]:
    """
    Collect all namespaces from frames, loops, and tags.

    Args:
        frames: List of saveframes to process

    Returns:
        Dict mapping namespace → list of (frame_name, loop_category, level_type) tuples
        where level_type is 'frame', 'loop', or 'tag'
    """
    namespaces = {}
    seen = set()  # Track (namespace, frame, loop, level) to avoid duplicates

    for frame in frames:
        # Check frame.category for namespace
        frame_ns = extract_namespace(frame.category)
        if frame_ns:
            key = (frame_ns, frame.name, '-', 'frame')
            if key not in seen:
                namespaces.setdefault(frame_ns, []).append((frame.name, '-', 'frame'))
                seen.add(key)

        for loop in frame.loops:
            # Check loop.category for namespace
            loop_ns = extract_namespace(loop.category)
            if loop_ns:
                key = (loop_ns, frame.name, loop.category, 'loop')
                if key not in seen:
                    namespaces.setdefault(loop_ns, []).append((frame.name, loop.category, 'loop'))
                    seen.add(key)

            # Check tags for namespaces (tags that don't match loop namespace)
            for tag in loop.tags:
                tag_ns = extract_namespace(tag)
                if tag_ns and tag_ns != loop_ns:
                    key = (tag_ns, frame.name, loop.category, 'tag')
                    if key not in seen:
                        namespaces.setdefault(tag_ns, []).append((frame.name, loop.category, 'tag'))
                        seen.add(key)

    return namespaces


def parse_namespace_selectors(
    selectors: List[str],
    use_escapes: bool = False,
    invert: bool = False
) -> Tuple[Set[str], Set[str]]:
    """
    Parse namespace selectors with inclusion/exclusion prefixes and optional escape sequences.

    Args:
        selectors: List of namespace patterns (may include +/- prefixes)
        use_escapes: If True, process escape sequences (,, → ,)
        invert: If True, swap inclusion/exclusion logic

    Returns:
        Tuple of (include_set, exclude_set) with namespace patterns

    Examples:
        ['+nef', '-custom'] → ({'nef'}, {'custom'})
        ['-nef'] → (set(), {'nef'})
        ['nef', 'custom'] → ({'nef', 'custom'}, set())
        ['++nef'] → ({'+nef'}, set())  # escaped literal
        ['my,,ns'], use_escapes=True → ({'my,ns'}, set())  # comma escape
        invert=True, ['nef'] → (set(), {'nef'})
    """
    # Parse comma-separated options (always use ',' as separator)
    parsed = parse_comma_separated_options(selectors, separator=',')

    include = set()
    exclude = set()

    for selector in parsed:
        # Process separator escapes if enabled
        if use_escapes:
            selector = selector.replace(',,', ',')  # Unescape commas

        # Handle +/- prefix escapes first
        if selector.startswith('++'):
            # Escaped +
            namespace = selector[1:]  # Remove one +
            include.add(namespace)
        elif selector.startswith('--'):
            # Escaped -
            namespace = selector[1:]  # Remove one -
            include.add(namespace)
        elif selector.startswith('+'):
            # Explicit include
            namespace = selector[1:]
            include.add(namespace)
        elif selector.startswith('-'):
            # Explicit exclude
            namespace = selector[1:]
            exclude.add(namespace)
        else:
            # No prefix, default to include
            include.add(selector)

    # Apply inversion
    if invert:
        include, exclude = exclude, include

    return include, exclude


```

**Note on validate_separator:**
The `validate_separator()` function exists in `cli_lib` (currently in stash). When implementing, use the existing function from cli_lib instead of creating a duplicate in namespace_lib. The function checks if a separator character appears in any frame/loop/tag names and exits with an error if conflicts are found.

## Key Utilities to Use

From `nef_lib.py`:
- `select_frames(entry, predicate, selector_type)` - Frame selection
- `loop_row_dict_iter(loop)` - Iterate loop rows
- `read_entry_from_file_or_stdin_or_exit_error(input)` - File input
- `SelectionType` enum - NAME, CATEGORY, ANY

From `util.py`:
- `parse_comma_separated_options(options, separator=',')` - Parse repeated/comma-separated arguments
- Helper for handling both `['nef', 'custom']` and `['nef,custom']` formats

From `namespace_lib.py` (to be created):
- `REGISTERED_NAMESPACES` - Dict mapping namespace → (program, purpose) for registered NEF software
- `extract_namespace(name)` - Extract namespace from tag/loop/frame name
- `collect_namespaces_from_frames(frames)` - Collect all namespaces with (frame, loop, level) metadata
- `parse_namespace_selectors(selectors, separator, invert)` - Parse +/- prefixed namespace patterns, return (include_set, exclude_set)

## Testing Strategy

**Test coverage for each command:**

1. **list command tests (test_list.py):**
   - Basic mode: Single frame, multiple frames, empty frame
   - Verbose mode: Multiple frames showing frame/loop/tag levels with program/use columns
   - Registered namespaces: Verify correct program/use lookup (e.g., nef, nefpls, ccpn)
   - Unregistered namespaces: Verify [Unknown] shown for custom namespaces
   - Frame selection: By name, by category, with wildcards
   - **Inclusion/exclusion filtering:**
     - Include specific namespaces: `+nef +custom`
     - Exclude specific namespaces: `-nef`
     - Mixed include/exclude: `+nef -custom`
     - Wildcard patterns: `+nef* -custom*`
     - Escaped literals: `++namespace` → `+namespace`
     - No selectors: List all namespaces (default)
     - Inverted selection: `--invert nef` (list all except nef)
     - Comma-separated: `+nef,+custom,-test`
     - Separator escape: `--use-separator-escapes 'my,,namespace'` → `my,namespace`
     - Separator conflict: Error when `,` in names without `--use-separator-escapes`
   - Edge cases: No loops, no matching frames, mixed namespaces, all namespaces excluded
   - Output format: Verify info() used for basic mode, tabulate for verbose table

2. **rename command tests (test_rename.py):**
   - Single namespace rename in one frame
   - Rename across multiple frames
   - Update loop categories and all tag names
   - Update frame categories if they match
   - Namespace doesn't exist: Warn in verbose, continue (no-op)
   - New namespace already exists: Silently merge (normal behavior, test merge result)
   - Mapping format: `old:new` syntax
   - Separator conflicts:
     - Error when `:` appears in namespace names without `--use-separator-escapes`
     - Error when `,` appears in namespace names without `--use-separator-escapes`
   - Escape sequences with `--use-separator-escapes`:
     - `::` → `:` in namespace names
     - `,,` → `,` in namespace names
   - Comma-separated arguments: `old1:new1,old2:new2`
   - Repeated arguments: `old1:new1 old2:new2`
   - Verbose mode reporting with counts

3. **delete command tests (test_delete.py):**
   - Delete single namespace (loops only - default level)
   - Delete multiple namespaces with wildcards
   - Delete with single level: `--level frame`
   - Delete with multiple levels (repeated): `--level frame --level loop`
   - Delete with multiple levels (comma-separated): `--level frame,loop,column-tag`
   - Delete column-tags: Verify entire data columns removed from loops
   - Delete straight tags: Verify only standalone tags removed (no column data)
   - Distinguish between column-tags (loop tags with data) vs straight tags
   - Frame selection filtering
   - Comma-separated namespaces: `nef,custom,test`
   - Repeated namespaces: `nef custom test`
   - Mixed format: `nef,custom test`
   - Separator conflict: Error when `,` in names without `--use-separator-escapes`
   - Escape sequences with `--use-separator-escapes`: `,,` → `,` in namespace names
   - Namespace doesn't exist: Warn in verbose, continue (no-op)
   - Deleting last loop: Warn about orphaned frame
   - `--remove-orphans`: Auto-remove empty frames
   - Verbose mode reporting with counts by level type

**Test data structure (`namespace_test.nef`):**
```
Entry
├── nef_molecular_system (namespace: nef in frame category)
│   └── _nef_sequence (namespace: nef loop, column-tags: chain_code, sequence_code, residue_name)
├── nef_chemical_shift_list_1 (namespace: nef in frame category)
│   └── _nef_chemical_shift (namespace: nef loop, column-tags: chain_code, value)
├── nef_nmr_spectrum_1 (namespace: nef in frame category)
│   ├── _nef_spectrum_dimension (namespace: nef loop)
│   └── _nef_peak (namespace: nef loop, has _nef_peak.position nested tags - column-tags at level 2)
├── custom_data_frame (namespace: custom in frame category)
│   ├── _custom_values (namespace: custom loop, column-tags: _custom_values.data)
│   └── Includes _custom_tag straight tags (namespace: custom, not in any loop)
└── test_experiment (namespace: test in frame category)
    ├── _test_measurements (namespace: test loop, column-tags: _test_measurements.value)
    └── Includes _test_note straight tags (namespace: test, not in any loop)

Extracted namespaces: nef, custom, test

Key test elements:
- nef namespace: Standard NEF loops with column-tags
- custom namespace: Mix of loop with column-tags AND straight tags
- test namespace: Loop with column-tags AND straight tags
- Enables testing deletion of column-tags (removes data columns) vs straight tags (no column data)
```

## Implementation Order

1. **Phase 0: namespace_lib foundation**
   - Create `namespace_lib.py` with core helper functions
   - Add `REGISTERED_NAMESPACES` constant with all registered NEF software namespaces
   - Implement `extract_namespace()` with comprehensive tests:
     - Test with `_nef_sequence` → `nef`
     - Test with `_custom_data` → `custom`
     - Test with `_nef_peak.position` → `nef` (nested tags)
     - Test with `nef_molecular_system` → `None` (no leading underscore)
     - Test with `_sequence` → `None` (only one underscore)
   - Implement `collect_namespaces_from_frames()` with tests:
     - Returns dict mapping namespace → list of (frame_name, loop_category, level_type) tuples
     - level_type is 'frame', 'loop', or 'tag'
     - Correctly identifies namespaces from frame.category, loop.category, and tag names
   - Implement `parse_namespace_selectors()` with tests:
     - Parse +/- prefixed namespace patterns
     - Handle prefix escapes: `++namespace`, `--namespace`
     - Handle separator escapes when `use_escapes=True`: `,,` → `,`
     - Return (include_set, exclude_set) tuples
     - Test invert flag
     - Test comma-separated and repeated arguments
     - Test escape sequence processing
   - Implement separator conflict detection:
     - Check if `,` appears in namespace names
     - If found and `--use-separator-escapes` not set: error with helpful message
     - For rename: also check `:` in namespace names
   - This establishes the shared utilities all commands will use

2. **Phase 1: list command**
   - Create `tools/namespace/` directory and `__init__.py`
   - Implement basic mode first (simpler, establishes CLI patterns)
   - Add verbose mode using `collect_namespaces_from_frames()`
   - Add frame selection support
   - Write comprehensive integration tests
   - Register namespace_app in main.py

3. **Phase 2: delete command**
   - Implement core deletion logic using `extract_namespace()`
   - Add wildcard matching for namespace patterns
   - Add `--delete-frames` flag to also delete frames
   - Add safety warnings (empty frames)
   - Write tests

4. **Phase 3: rename command**
   - Implement rename logic (most complex due to tag prefix updates)
   - Use regex for robust prefix replacement: `^_old_` → `^_new_`
   - Update loop.category, frame.category, and all tags in loop.tags
   - Add validation (namespace exists, no conflicts)
   - Add dry-run mode
   - Write tests

## Verification Steps

After implementation, verify functionality end-to-end:

### 1. Test namespace_lib utilities
```bash
# Run unit tests for core utilities
pytest src/nef_pipelines/tests/lib/test_namespace_lib.py -xvs
```

### 2. Test list command
```bash
# List namespaces in basic mode (all)
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | nef namespace list

# Expected output:
# nef
# custom
# test

# List only specific namespaces
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | nef namespace list +nef +custom

# Expected output:
# nef
# custom

# List excluding specific namespaces
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | nef namespace list -nef

# Expected output:
# custom
# test

# List with inverted selection
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | nef namespace list --invert custom

# Expected output:
# nef
# test

# List in verbose mode
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | nef namespace list --verbose

# Should show table with namespace, frame, loop, level, program, and use columns
# Registered namespaces (nef) show program name, unregistered (custom, test) show [Unknown]
```

### 3. Test rename command
```bash
# Rename nef to mynef
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | \
  nef namespace rename nef mynef | \
  nef namespace list

# Expected output should show 'mynef' instead of 'nef'

# Verify tags were updated too
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | \
  nef namespace rename nef mynef | \
  grep "_mynef_sequence"

# Should find _mynef_sequence instead of _nef_sequence
```

### 4. Test delete command
```bash
# Delete custom namespace
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | \
  nef namespace delete custom | \
  nef namespace list

# Expected output: nef, test (custom removed)

# Delete with dry-run
cat src/nef_pipelines/tests/namespace/test_data/namespace_test.nef | \
  nef namespace delete --dry-run nef

# Should show what would be deleted without actually deleting
```

### 5. Run all tests
```bash
# Run all namespace-related tests
pytest src/nef_pipelines/tests/namespace/test_list.py -xvs
pytest src/nef_pipelines/tests/namespace/test_rename.py -xvs
pytest src/nef_pipelines/tests/namespace/test_delete.py -xvs

# Run full test suite to ensure no regressions
pytest src/nef_pipelines/tests/ -x
```

### 6. Integration with other commands
```bash
# Pipeline: rename namespace, then list frames
cat input.nef | \
  nef namespace rename nef custom | \
  nef frames list

# Pipeline: delete namespace, then check what remains
cat input.nef | \
  nef namespace delete test | \
  nef namespace list --verbose
```

## Success Criteria

- All commands follow NEF-Pipelines patterns (CLI + worker function)
- Frame selection works consistently across all commands
- Wildcard matching works for delete and frame selection
- Verbose output is properly formatted and readable
- All error cases handled gracefully with clear messages
- Test coverage >90% for each command
- Documentation includes usage examples
- Commands can be piped together with other NEF tools
- All verification steps pass

## Edge Cases and Considerations

#TODO: [not possible this is an illegal star file]
1. **Names without underscores**: `nef_molecular_system` (frame name) has no leading `_`, so no namespace is extracted from frame.name. Only frame.category and loop.category are checked.
#TODO: [this is an illegal nef file warn and continue]
2**Single underscore prefix**: `_sequence` would extract empty string as namespace - validate and reject.
#[TODO there is no such thing as a nested namespace a namespace is _ delimited and doesn't contain .'s either]
3. **Nested namespaces**: Nested tags like `_nef_peak.position.x` still have namespace `nef` (determined by prefix before second `_`).

4. **Mixed namespaces in one frame**: A frame can contain loops with different namespaces - this is valid.

5. **Empty frames after deletion**: Warn user if deletion would leave a frame with no loops. Use `--remove-orphans` to auto-remove empty frames.

6. **Rename namespace merging**: Renaming `nef` → `custom` when `custom` namespace already exists **silently merges** namespaces (normal behavior, not an error or warning).

7. **Separator conflicts** (CRITICAL):
   - Fixed separators: `,` for lists, `:` for maps (rename command)
   - If separator found in names without `--use-separator-escapes`:
     - Exit with error: "Separator found in names (`,` or `:`). Use --use-separator-escapes to enable escape sequences"
     - Error message lists conflicting names
   - If `--use-separator-escapes` set:
     - User must escape separators: `,,` for `,`, `::` for `:`
     - Example: namespace `my,ns` → `my,,ns` in arguments
   - Example: Frame name is `nef_shift,list_1`:
     - Without flag: ERROR with suggestion to use `--use-separator-escapes`
     - With flag: User provides `nef_shift,,list_1` in arguments

8. **Column-tag deletion removes columns** (CRITICAL):
   - Deleting column-tags from `loop.tags` removes entire data columns from loops
   - Distinguish between:
     - **Column-tags** (loop tags): Tags in `loop.tags` (part of loop structure, have data columns)
     - **Straight tags**: Standalone tags found at the top of a saveframe
   - When using `--level column-tag`: just delete no warning
   - When using `--level tag`: Only removes straight tags (no column data affected)
   - In verbose mode: Show which column-tags (columns) vs straight tags will be removed

9. **Comma-separated vs repeated arguments**:
   - Fixed separator: `,` for lists (no custom separators)
   - Support both formats: `nef custom test` and `nef,custom,test`
   - Mix is allowed: `nef,custom test` → parsed as `['nef', 'custom', 'test']`
   - Use `parse_comma_separated_options()` for consistent handling
   - Escape sequences: `,,` represents literal comma when `--use-separator-escapes` set

10. **Namespace doesn't exist**: When renaming/deleting non-existent namespace, **warn in verbose mode**, continue (no-op). No error.

11. **Missing namespaces**: If a namespace listed in delete or rename isn't used, produce a warning in verbose mode

12. **Escape sequences and --use-separator-escapes** (CRITICAL):
   - By default, separators (`,` and `:`) in namespace names cause an error
   - Error message: "Separator found in namespace names. Use --use-separator-escapes to enable escape sequences"
   - When `--use-separator-escapes` is set:
     - User must escape separators: `my,ns` → `my,,ns`, `my:ns` → `my::ns`
     - Processing unescapes: `,,` → `,`, `::` → `:`
   - This prevents accidental splits while allowing explicit handling of special characters
   - Example workflow:
     1. User runs: `nef namespace list my,namespace`
     2. Error: "Comma found in namespace 'my,namespace'. Use --use-separator-escapes..."
     3. User runs: `nef namespace list --use-separator-escapes 'my,,namespace'`
     4. Success: namespace `my,namespace` is processed correctly

## Common Namespaces in NEF Files

Based on the NEF specification, registered software namespaces include:

| Namespace | Program | Purpose |
|-----------|---------|---------|
| `nef` | NEF Standard | Standard NEF categories |
| `nefpls` | NEF Pipelines | Format transcoding and NEF manipulation |
| `amber` | Amber | Structure modelling and refinement |
| `aria` | Aria | Structure calculation |
| `ccpn` | CcpNmr Analysis | NMR spectra processing and data analysis |
| `csrosetta` | CS-Rosetta | Structure calculation |
| `cyana` | Cyana | Structure calculation |
| `meld` | MELD | Structure modelling and refinement |
| `NMRFx` | NMRFx | Structure calculation |
| `pdbstat` | PDBStat | NMR data validation |
| `unio` | Unio NMR | Structure calculation |
| `unres` | Unres | Structure modelling and refinement |
| `pdbx` | wwPDB/BMRB | Database |
| `XplorNIH` | Xplor-NIH | Structure calculation and refinement |
| `yasara` | Yasara | Structure refinement |

The list/rename/delete commands help users manage these namespace prefixes consistently.
