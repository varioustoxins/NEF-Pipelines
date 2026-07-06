# Plan: Address TODOs in tree.py and tree_lib.py

**STATUS: PARTIALLY ADDRESSED** ⚠️

**Current TODO count:**
- `tree.py`: **10 TODOs** remain
- `tree_lib.py`: **1 TODO** remains

**Plan identified 7 TODOs** - unclear how many were resolved vs. new ones added.

**Unclear without detailed audit:**
- Which specific TODOs from this plan were completed?
- Were they replaced with new TODOs?
- Some may be marked "COMPLETED" like test_display.py

**Action needed:** Audit current TODOs in both files to determine which are from this plan and their status.

---

## Overview

This plan addresses 7 TODOs across tree.py and tree_lib.py to improve code organization, eliminate duplication, and follow best practices.

## TODOs to Address

### Priority 1 - Use Existing Library Functions

#### TODO 2: Replace _extract_namespace() with library function
**Location**: tree.py line 290
**Issue**: Duplicates functionality from namespace_lib.py
**Impact**: Medium - removes duplication, uses better-tested code

**Current code**:
```python
def _extract_namespace(frame_name: str) -> str:
    if "_" in frame_name:
        return frame_name.split("_", 1)[0]
    return frame_name
```

**Replacement**: Use `extract_namespace()` from namespace_lib.py
```python
from nef_pipelines.lib.namespace_lib import extract_namespace
```

**Changes needed**:
- Add import at top of tree.py
- Replace calls to `_extract_namespace()` with `extract_namespace()`
- Remove the old function
- Note: library version returns Optional[str], handle None case

#### TODO 7: Move find_matched_substring() to util.py
**Location**: tree_lib.py line 211
**Issue**: Tree-agnostic utility function is in tree_lib
**Impact**: Medium - improves organization

**Actions**:
1. Move function from tree_lib.py to lib/util.py
2. Update import in tree.py: `from nef_pipelines.lib.util import find_matched_substring`
3. Move existing tests from test_tree_lib.py to test_util.py (or create it)
4. Add comprehensive edge case tests:
   - Empty string/pattern
   - Pattern not found
   - Multiple wildcards: `*a*b*`
   - Only wildcards: `***`
   - Unicode/special characters

### Priority 2 - Code Organization

#### TODO 1: Refactor pipe() into high-level steps
**Location**: tree.py line 141
**Issue**: Monolithic 65-line function
**Impact**: High - improves readability and testability

**Current structure**: pipe() does everything in one function

**Refactor into**:
1. `_build_tree_from_entry(entry: Entry) -> Tree`
2. `_filter_tree_by_namespace(tree, selectors, invert) -> Tree`
3. `_filter_tree_by_node_selectors(tree, selectors) -> Tree`
4. `_expand_filtered_tree_with_children(full_tree, filtered_tree, first_selector) -> Tree`
5. `_render_filtered_tree(tree, colour_policy, highlight_patterns) -> str`

**New pipe() structure**:
```python
def pipe(...) -> str:
    full_tree = _build_tree_from_entry(entry)

    if namespace_selectors:
        full_tree = _filter_tree_by_namespace(full_tree, namespace_selectors, invert_namespace_selectors)

    if node_selectors:
        filtered_tree = _filter_tree_by_node_selectors(full_tree, node_selectors)

        if show_children and len(filtered_tree) > 0:
            filtered_tree = _expand_filtered_tree_with_children(full_tree, filtered_tree, node_selectors[0])
    else:
        filtered_tree = full_tree

    highlight_patterns = None if no_highlight else node_selectors
    return _render_filtered_tree(filtered_tree, colour_policy, highlight_patterns)
```

**Benefits**:
- Each function has single responsibility
- Easier to test individual steps
- Better names make flow clearer
- Can add docstrings to each step

#### TODO 4: Rename _merge_protected_descendants()

TODO: the real problem is its not clear what aprotected descendant
**Location**: tree.py line 498
**Issue**: Unclear name
**Impact**: Low - improves clarity

**Current name**: `_merge_protected_descendants()`
**Better name**: `_expand_tree_with_protected_nodes()` or `_add_descendants_to_filtered_tree()`

**Rationale**: The function doesn't "merge" trees, it expands the filtered tree to include protected nodes.

### Priority 3 - Code Quality Improvements

#### TODO 5: Consolidate or clarify two highlight functions
**Location**: tree.py line 522
**Issue**: Two similar functions with unclear distinction
**Impact**: Low - reduces confusion

**Current functions**:
1. `_apply_highlight(text, match_span)` - highlights match only, no base colour
2. `_apply_highlight_with_colour(text, match_span, base_colour)` - highlights match + preserves base colour

**Decision**: Keep both but rename for clarity
- `_highlight_match_only(text, match_span)` - for already-coloured contexts (frames/loops)
- `_highlight_match_preserve_base(text, match_span, base_colour)` - for leaf tags

**Alternative**: Consolidate into single function with optional base_colour parameter:
```python
def _apply_highlight_to_match(
    text: str,
    match_span: Tuple[int, int],
    base_colour: Optional[str] = None
) -> str:
    """Apply bold red highlight to matched portion.

    If base_colour provided, applies it to non-matched portions.
    """
    start, end = match_span
    before = text[:start]
    matched = text[start:end]
    after = text[end:]

    result = ""
    if base_colour and before:
        result += f"[{base_colour}]{before}[/{base_colour}]"
    else:
        result += before

    result += f"[bold red]{matched}[/bold red]"

    if base_colour and after:
        result += f"[{base_colour}]{after}[/{base_colour}]"
    else:
        result += after

    return result
```

**Recommendation**: Use consolidated version - simpler API, easier to maintain
REPLY: yes do the consolidation

#### TODO 6: Extract hard-coded colours to constants
**Location**: tree.py line 570
**Issue**: Colours hard-coded in _colour_nef_node()
**Impact**: Low - improves maintainability

**Current hard-coded colours**:
- Entry: `"bold cyan"`
- Frame: `"yellow"`
- Loop: `"blue"`
- Tag (leaf): `"green"`
- Matched: `"bold red"`
- Metadata: `"dim"`

**Solution**: Create colour scheme dataclass in tree_lib.py

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TreeColourScheme:
    """Colour scheme for NEF tree rendering."""
    entry: str = "bold cyan"
    frame: str = "yellow"
    loop: str = "blue"
    tag: str = "green"
    matched: str = "bold red"
    metadata: str = "dim"

# Default scheme
DEFAULT_TREE_COLOURS = TreeColourScheme()
```

**Usage in _colour_nef_node()**:
```python
def _colour_nef_node(
    node: Node,
    filter_patterns: Optional[List[str]],
    colours: TreeColourScheme = DEFAULT_TREE_COLOURS
) -> str:
    # Use colours.frame, colours.loop, etc.
```

**Benefits**:
- Easy to customize colour schemes
- Can create themes (dark mode, high contrast, etc.)
- Better testability
- Single source of truth

### Priority 4 - Review and Document

#### TODO 3: Review _if_is_nef_file_load_as_entry()
**Location**: tree.py line 397
**Issue**: May duplicate nef_lib functionality
**Impact**: Low - potential duplication

**Current implementation**:
```python
def _if_is_nef_file_load_as_entry(file_path: str) -> Optional[Entry]:
    try:
        result = Entry.from_file(file_path)
    except Exception:
        result = None
    return result
```

**Library alternatives** in nef_lib.py:
- `read_entry_from_file_or_raise(file)` - raises on error
- `read_entry_from_file_or_exit_error(file)` - calls exit_error()
- `read_entry_from_file_or_stdin_or_raise(file)` - handles stdin

**Key difference**: Current function silently returns None on ANY error (catches all exceptions)

**Decision needed**:
- **Option A**: Keep current implementation if silent failure is required for polymorphic file argument detection
- **Option B**: Use library function with try/except wrapper
- **Option C**: Add new function to nef_lib: `try_load_entry_from_file(path) -> Optional[Entry]`

REPLY: use read_entry_from_file_or_exit_error(file) - not finding the file should be an error

**Recommendation**: Keep current implementation but add detailed docstring explaining why it differs from library functions:
```python
def _if_is_nef_file_load_as_entry(file_path: str) -> Optional[Entry]:
    """
    Try to load file as NEF entry, returning None on any error.

    This function intentionally returns None on any error (unlike library functions
    that raise exceptions) to support polymorphic argument detection where the first
    positional argument might be either a file path or a filter pattern.

    Args:
        file_path: Path to potential NEF file

    Returns:
        Entry if valid NEF file, None otherwise (on any error)
    """
    try:
        return Entry.from_file(file_path)
    except Exception:
        return None
```

## Implementation Order

1. **TODO 7**: Move find_matched_substring() to util.py and add tests (foundational)
2. **TODO 6**: Extract colour constants (independent change)
3. **TODO 2**: Replace _extract_namespace() with library function (simple substitution)
4. **TODO 4**: Rename _merge_protected_descendants() (simple rename)
5. **TODO 5**: Consolidate highlight functions (affects TODO 6)
6. **TODO 3**: Document _if_is_nef_file_load_as_entry() (documentation only)
7. **TODO 1**: Refactor pipe() into steps (depends on understanding from above changes)

## Files to Modify

### Primary Changes

**src/nef_pipelines/lib/tree_lib.py**:
- Remove find_matched_substring() (moving to util.py)
- Add TreeColourScheme dataclass
- Export DEFAULT_TREE_COLOURS

**src/nef_pipelines/lib/util.py**:
- Add find_matched_substring() (moved from tree_lib.py)

**src/nef_pipelines/tools/entry/tree.py**:
- Replace _extract_namespace() with import from namespace_lib
- Refactor pipe() into helper functions
- Rename _merge_protected_descendants() → _expand_tree_with_protected_nodes()
- Consolidate _apply_highlight() and _apply_highlight_with_colour()
- Update _colour_nef_node() to use TreeColourScheme
- Add comprehensive docstring to _if_is_nef_file_load_as_entry()

### Test Files

**src/nef_pipelines/tests/lib/test_util.py** (create if doesn't exist):
- Add comprehensive tests for find_matched_substring()

**src/nef_pipelines/tests/lib/test_tree_lib.py**:
- Remove find_matched_substring() tests (moved to test_util.py)
- Add tests for TreeColourScheme

**src/nef_pipelines/tests/entry/test_tree.py**:
- Update imports if needed
- Tests should continue to pass (no breaking changes)

## Testing Strategy

### Unit Tests

1. **test_util.py - find_matched_substring()**:
   ```python
   def test_find_matched_substring_empty_string()
   def test_find_matched_substring_empty_pattern()
   def test_find_matched_substring_not_found()
   def test_find_matched_substring_multiple_wildcards()
   def test_find_matched_substring_only_wildcards()
   def test_find_matched_substring_unicode()
   ```

2. **test_tree_lib.py - TreeColourScheme**:
   ```python
   def test_tree_colour_scheme_defaults()
   def test_tree_colour_scheme_custom()
   def test_tree_colour_scheme_frozen()  # dataclass immutability
   ```

### Integration Tests

3. **test_tree.py**:
   - Run all existing tests to ensure no regressions
   - All 16 tests should continue to pass

### Manual Verification

```bash
# Test tree command still works
nef entry tree src/nef_pipelines/tests/test_data/multi_shift_frames.nef

# Test with filters
nef entry tree src/nef_pipelines/tests/test_data/multi_shift_frames.nef chain_code

# Test with namespace filtering
nef entry tree src/nef_pipelines/tests/test_data/namespace_test.nef --namespace -,+nef

# Test colour modes
nef entry tree file.nef --colour-policy plain
nef entry tree file.nef --colour-policy color
```

## Success Criteria

✅ All 7 TODOs addressed or documented
✅ find_matched_substring() moved to util.py with comprehensive tests
✅ Colours extracted to TreeColourScheme dataclass
✅ extract_namespace() imported from namespace_lib
✅ _merge_protected_descendants() renamed to clearer name
✅ Highlight functions consolidated or clearly documented
✅ _if_is_nef_file_load_as_entry() has comprehensive docstring
✅ pipe() refactored into well-named helper functions
✅ All existing tests pass (16 entry tests, 18 tree_lib tests)
✅ New tests added for edge cases
✅ No breaking changes to public API

## Non-Breaking Changes

All changes are internal refactoring:
- No CLI interface changes
- No public API changes
- All test expectations remain the same
- Behaviour identical to current implementation

## Notes

- TODO about escape sequences in tree_lib.py (line 125) is NOT included per user request
- Changes prioritized by impact and dependencies
- Refactoring improves code quality without changing behaviour
- Comprehensive tests ensure nothing breaks
