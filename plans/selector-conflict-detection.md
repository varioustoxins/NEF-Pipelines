# Selector Conflict Detection Function Plan

**STATUS: PARTIALLY IMPLEMENTED** ⚠️

**What was implemented:**
- ✅ `if_separator_conflicts_get_message()` exists in `namespace_lib.py`
  - Lower-level helper: takes list of names + separators
  - Returns tuple of (conflicting_names, found_separators, escape_sequences)
- ✅ Used in `namespace/list.py` for namespace conflict detection

**What was NOT implemented:**
- ❌ High-level `check_selector_conflicts()` wrapper not created
  - Would take Entry + EntryPart locations and auto-collect names
  - Would simplify caller code
- ❌ Not integrated into `tree.py` or `display.py` as planned
- ❌ EntryPart extensions for fine-grained distinctions not added
- ❌ General utility integration across all selector-using commands

**Current state**: Lower-level conflict detection helper exists and works, but the comprehensive wrapper function to make it easy to use throughout the codebase was never built. Each caller must manually collect names before checking.

---

## Overview
Add a general-purpose function to `cli_lib.py` to detect when NEF data names contain separator characters that could conflict with selector syntax.

## Problem
Selectors use special characters as separators (e.g., `.`, `:`, `,`, `-`, `+`, `!`). When NEF data (frame names, loop categories, tags, namespaces) contains these characters, selector parsing can fail or behave unexpectedly.

## Existing Functions to Mine
`cli_lib.py` already contains selector conflict detection in specific contexts:
- Line ~1705: `_check_for_selector_conflicts_in_names()` - Checks frame and loop category conflicts
- Line ~1785: `_if_separator_conflicts_get_message()` - General conflict checking pattern

These functions should be generalized and made reusable.

## Required Function

*TODO* EntryPart components may not be fine grained enough to distinguish between frame names, loop categories, tag names,
etc. We may need to add more specific EntryPart values or use additional parameters to specify what types of names to
check.

A save frame has a namespace, a category, and id and an iterator
A saveframe tag has a namespace, and an id
A loop has a namespace, and a category
A loop tag has a namespace, and an id

suggest extensions to EntryPart to capture these distinctions if needed.

### Function Signature
```python
def check_selector_conflicts(
    entry: Entry,
    separators: List[str],
    check_locations: List[EntryPart],
) -> Optional[Tuple[List[str], List[str], List[Tuple[str, str]]]]:
    """
    Check if any NEF data names contain separator characters.

    Args:
        entry: NEF entry to check
        separators: List of separator characters to check for (e.g., ['-', '+', '!'])
        check_locations: Where to look for conflicts (e.g., [EntryPart.Saveframe, EntryPart.Loop])

    Returns:
        None if no conflicts or escapes enabled
        Tuple of (conflicting_names, found_separators, escape_sequences) if conflicts found:
        - conflicting_names: List of names containing separators (up to 5, with count if more)
        - found_separators: List of separator characters that were found
        - escape_sequences: List of (separator, escape) tuples for building help message
    """
```

*TODO* the return type is too complicated just return a list of entry parts and list of conflicting values or an empty
list

- `EntryPart.Saveframe` - Check saveframe names
- `EntryPart.Loop` - Check loop categories
- `EntryPart.FrameTag` - Check saveframe tag names
- `EntryPart.LoopTag` - Check loop tag names
- Additional: Check namespaces, frame categories, loop categories separately

### Usage Locations
This should be used in:
1. **tree.py** (line ~191-197) - Check for `-`, `+`, `!` in namespaces and selectors
2. **display.py** - Check namespace conflicts
3. Other commands using namespace or selector filtering

its a general utility function that should be called wherever selector parsing is used to ensure users are warned about
potential conflicts and asked to enablle --use-escapes.

## Implementation Steps

### 1. Extract Name Collections from Entry
Use existing library functions:
- `collect_namespaces_from_frames()` from `namespace_lib` - Get all namespaces
- `get_namespace()` from `namespace_lib` - Extract namespace from names
- Loop through entry frames, loops, and tags to collect names

### 2. Reuse Existing Conflict Detection Logic
Base implementation on `_if_separator_conflicts_get_message()` pattern:
- Iterate through collected names
- Check each separator against each name
- Track conflicts (name, separator) tuples
- Return formatted results matching existing pattern

### 3. Format Conflict Messages
Follow existing pattern:
- Show up to 5 conflicting names (with count if more)
- List found separators
- Provide escape sequences for each separator (e.g., `--` to escape `-`)

### 4. Integration Points
Commands should call this function early in their execution:
```python
# In tree.py, display.py, etc.
from nef_pipelines.lib.cli_lib import check_selector_conflicts
from nef_pipelines.lib.namespace_lib import EntryPart

conflicts = check_selector_conflicts(
    entry,
    separators=['-', '+', '!'],
    check_locations=[EntryPart.Saveframe, EntryPart.Loop],
    use_escapes=use_escapes
)

if conflicts:
    conflicting_names, found_seps, escape_seqs = conflicts
    # Generate warning or error message
```

## Testing Requirements

### Test Cases
1. **No conflicts** - Entry with clean names, should return None
2. **Frame name conflicts** - Frame containing `-` or `+`
3. **Loop category conflicts** - Loop category containing separators
4. **Tag name conflicts** - Tag names with separators
5. **Namespace conflicts** - Namespace containing separators
6. **Multiple conflict types** - Conflicts across different locations
7. **Escapes enabled** - Should return None when `use_escapes=True`
8. **Partial location check** - Only check specified EntryPart locations

### Test Data
Create minimal NEF files with:
- Frame named `nef-molecular-system` (contains `-`)
- Loop category `_nef+sequence` (contains `+`)
- Tag name `chain!code` (contains `!`)
- Namespace `nef-pls_frame` (contains `-`)

## Missing Functions Check
If any of these are missing from existing libraries, they need to be identified:
- ✓ `collect_namespaces_from_frames()` - EXISTS in namespace_lib
- ✓ `get_namespace()` - EXISTS in namespace_lib
- ✓ Frame/loop/tag iteration - EXISTS via pynmrstar Entry/Saveframe/Loop
- ? Name decomposition functions - CHECK if additional helpers needed

## Future Enhancements
- Integrate with existing `_check_for_selector_conflicts_in_names()` to avoid duplication

## References
- `cli_lib.py` lines ~1705, ~1785 for existing patterns
- `namespace_lib.py` for `collect_namespaces_from_frames()`, `get_namespace()`, `EntryPart`
- `tree.py` lines 191-197 for usage context
