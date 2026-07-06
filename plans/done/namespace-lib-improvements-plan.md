# Plan: Refactor namespace_lib.py to Address TODOs

## Context

The `namespace_lib.py` file has TODOs requesting improvements to use dataclasses and EntryPart enum instead of tuples and string literals in `collect_namespaces_from_frames()`. Additionally, there's a question about whether the initial selection logic in `filter_namespaces()` can be simplified.

## Current Issues

**File:** `src/nef_pipelines/lib/namespace_lib.py`

1. **Line 161**: `collect_namespaces_from_frames()` returns complex tuples
   - Returns: `Dict[str, List[Tuple[str, str, Optional[str], str]]]`
   - Tuples are: `(frame_name, frame_category, loop_category, level_type)`
   - `level_type` uses string literals: "frame", "loop", "tag", "column-tag"
   - Hard to read, no type safety, error-prone

2. **Line 252**: `filter_namespaces()` already simplified (code fixed, tests may need updates)
   - Extra logic for determining initial state has been removed
   - Now correctly starts with `all_namespaces.copy()` and applies operations
   - `parse_selector_lists()` handles all logic - returns correct operations
   - Some tests may fail - need to verify and fix test expectations

## Investigation Findings

### Current Usage of collect_namespaces_from_frames()

**File**: `src/nef_pipelines/tools/namespace/list.py`

**Line 149**: `namespace_data = collect_namespaces_from_frames(frames)`

**Line 248**: Iterates over tuples:
```python
for frame_name, frame_category, loop_category, level_type in namespace_data[namespace]:
    if level_type == "loop":  # String comparison
        has_loops = True
```

### Level Type to EntryPart Mapping

Current string values → EntryPart enum values:
- `"frame"` → `EntryPart.Saveframe`
- `"loop"` → `EntryPart.Loop`
- `"tag"` → `EntryPart.FrameTag`
- `"column-tag"` → `EntryPart.LoopTag`

### parse_selector_lists() Behavior

From `cli_lib.py`:
- **Assumes "everything selected"** as the conceptual starting state
- Returns a list of operations to apply to that assumed state
- When `no_initial_selection=True`: Prepends `(EXCLUDE, ALL_NAMESPACES)` **as a marker**
- When `no_initial_selection=False`: No marker added
- **Does NOT enforce or determine the actual starting set** - just returns operations

### filter_namespaces() Logic Analysis

**Correct (simplified) behavior**:

`filter_namespaces()` should simply:
1. Start with `all_namespaces.copy()` (everything selected)
2. Apply operations from `parse_selector_lists()` in order
3. Return the result

**No extra logic needed** - `parse_selector_lists()` returns the correct operations assuming "everything selected" initial state. The operations themselves (including `EXCLUDE, ALL_NAMESPACES` when needed) handle all logic.

## Design Decisions

### Create NamespaceInformation Dataclass

Replace tuples with a frozen dataclass for immutability and type safety:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class NamespaceInformation:
    """\
    Information about a namespace occurrence in NEF data.

    Represents where a namespace is used (frame/loop/tag level).
    """
    frame_name: str
    frame_category: str
    loop_category: Optional[str]
    entry_part: EntryPart
```

Benefits:
- Type-safe field access
- IDE auto-completion
- Self-documenting code
- Immutable (frozen=True)
- Can add methods if needed later

### Keep filter_namespaces() Logic

The initial selection logic is correct and necessary - do NOT simplify it. Instead:
- Add clarifying comment explaining why it's needed
- Remove the misleading TODO comment

## Implementation Plan

### Task 1: Create NamespaceInformation Dataclass

**Location**: `namespace_lib.py` ~line 38 (after get_registered_namespaces, before EntryPart enum)

```python
@dataclass(frozen=True)
class NamespaceInformation:
    """\
    Information about a namespace occurrence in NEF data.

    Represents where a namespace is used within an entry at different levels
    (frame, loop, or tag).

    Attributes:
        frame_name: Saveframe name
        frame_category: Saveframe category
        loop_category: Loop category (None for frame-level items)
        entry_part: Level where namespace occurs (Saveframe, Loop, FrameTag, LoopTag)
    """
    frame_name: str
    frame_category: str
    loop_category: Optional[str]
    entry_part: EntryPart
```

**Required import**:
```python
from dataclasses import dataclass
```

### Task 2: Update collect_namespaces_from_frames() Signature

**Location**: `namespace_lib.py` line 162

**Change return type**:
```python
def collect_namespaces_from_frames(
    frames: List[Saveframe],
) -> Dict[str, List[NamespaceInformation]]:
```

**Remove TODO comment** at line 161

### Task 3: Update collect_namespaces_from_frames() Implementation

**Map string level_types to EntryPart enum**:

**Line 184-189** (frame collection):
```python
# Old:
namespaces.setdefault(frame_namespace, []).append(
    (frame.name, frame.category, None, "frame")
)

# New:
namespaces.setdefault(frame_namespace, []).append(
    NamespaceInformation(
        frame_name=frame.name,
        frame_category=frame.category,
        loop_category=None,
        entry_part=EntryPart.Saveframe,
    )
)
```

**Line 194-199** (frame tag collection):
```python
# Old:
namespaces.setdefault(tag_namespace, []).append(
    (frame.name, frame.category, None, "tag")
)

# New:
namespaces.setdefault(tag_namespace, []).append(
    NamespaceInformation(
        frame_name=frame.name,
        frame_category=frame.category,
        loop_category=None,
        entry_part=EntryPart.FrameTag,
    )
)
```

**Line 204-209** (loop collection):
```python
# Old:
namespaces.setdefault(loop_namespace, []).append(
    (frame.name, frame.category, loop.category, "loop")
)

# New:
namespaces.setdefault(loop_namespace, []).append(
    NamespaceInformation(
        frame_name=frame.name,
        frame_category=frame.category,
        loop_category=loop.category,
        entry_part=EntryPart.Loop,
    )
)
```

**Line 214-219** (loop tag collection):
```python
# Old:
namespaces.setdefault(tag_namespace, []).append(
    (frame.name, frame.category, loop.category, "column-tag")
)

# New:
namespaces.setdefault(tag_namespace, []).append(
    NamespaceInformation(
        frame_name=frame.name,
        frame_category=frame.category,
        loop_category=loop.category,
        entry_part=EntryPart.LoopTag,
    )
)
```

### Task 4: Update namespace/list.py to Use NamespaceInformation

**File**: `src/nef_pipelines/tools/namespace/list.py`

**Line 9** - Add import:
```python
from nef_pipelines.lib.namespace_lib import (
    REGISTERED_NAMESPACES,
    NamespaceInformation,  # NEW
    collect_namespaces_from_frames,
    filter_namespaces,
    if_separator_conflicts_get_message,
)
```

**Line 222** - Update docstring:
```python
def _generate_verbose_table(namespace_data: dict, namespaces_to_show: set) -> str:
    """
    Generate verbose table showing namespace details.

    Args:
        namespace_data: Dict mapping namespace → list of NamespaceInformation objects
        namespaces_to_show: Set of namespaces to include in table

    Returns:
        Formatted table string
    """
```

**Line 248** - Update iteration to use dataclass fields:
```python
# Old:
for frame_name, frame_category, loop_category, level_type in namespace_data[namespace]:
    if level_type == "loop":
        has_loops = True

# New:
for info in namespace_data[namespace]:
    if info.entry_part == EntryPart.Loop:
        has_loops = True

    # Access fields as properties
    frame_name = info.frame_name
    frame_category = info.frame_category
    loop_category = info.loop_category
    level_type = info.entry_part.name.lower()  # For display: "saveframe" → need mapping
```

**Note**: Need to create display name mapping for EntryPart:
```python
ENTRY_PART_DISPLAY = {
    EntryPart.Saveframe: "frame",
    EntryPart.Loop: "loop",
    EntryPart.FrameTag: "tag",
    EntryPart.LoopTag: "column-tag",
}
```

Add this constant in `list.py` around line 28, then use:
```python
level_type = ENTRY_PART_DISPLAY[info.entry_part]
```

### Task 5: Verify and Fix Tests for Simplified filter_namespaces()

**Note**: The code has already been simplified to:
```python
filtered_namespaces = all_namespaces.copy()  # Start with everything
# Apply operations from parse_selector_lists in order
```

This is **correct** - `parse_selector_lists()` handles all logic and returns the right operations.

**Action needed**: Some tests may be failing because they expect the old behavior. Need to:

1. Run tests: `nefl test src/nef_pipelines/tests/lib/test_namespace_lib.py`
2. Identify which tests fail
3. Update test expectations to match the correct behavior:
   - `parse_selector_lists()` assumes "everything selected"
   - Operations are applied in order to that initial state
   - No special logic in `filter_namespaces()` needed

**Files to check**:
- `src/nef_pipelines/tests/lib/test_namespace_lib.py`
- Any other tests calling `filter_namespaces()`

### Task 6: Add EntryPart Import to namespace/list.py

**File**: `src/nef_pipelines/tools/namespace/list.py`

**Line 9** - Update imports:
```python
from nef_pipelines.lib.namespace_lib import (
    REGISTERED_NAMESPACES,
    EntryPart,  # NEW
    NamespaceInformation,
    collect_namespaces_from_frames,
    filter_namespaces,
    if_separator_conflicts_get_message,
)
```

## Implementation Sequence

**Phase 1: Create Dataclass**
1. Add dataclass import to namespace_lib.py
2. Create NamespaceInformation dataclass
3. Run tests: `nefl test src/nef_pipelines/tests/lib/test_namespace_lib.py` (should still pass)

**Phase 2: Update collect_namespaces_from_frames()**
4. Update function signature and docstring
5. Replace all tuple creations with NamespaceInformation instances
6. Remove TODO comment
7. Run tests

**Phase 3: Update namespace/list.py**
8. Add NamespaceInformation and EntryPart imports
9. Add ENTRY_PART_DISPLAY mapping constant
10. Update _generate_verbose_table() to use dataclass fields
11. Update iteration to access fields as properties
12. Run tests: `nefl test src/nef_pipelines/tests/namespace/test_list.py`

**Phase 4: Clarify Comments**
13. Replace TODO in filter_namespaces() with clarifying comment
14. Run full test suite

## Critical Files

- `src/nef_pipelines/lib/namespace_lib.py` - Main refactoring target
- `src/nef_pipelines/tools/namespace/list.py` - Update caller
- `src/nef_pipelines/tests/lib/test_namespace_lib.py` - Verify no breakage
- `src/nef_pipelines/tests/namespace/test_list.py` - Test namespace list command

## Verification

### Tests to Pass
```bash
# Run namespace lib tests
nefl test src/nef_pipelines/tests/lib/test_namespace_lib.py

# Run namespace list tests
nefl test src/nef_pipelines/tests/namespace/test_list.py

# Run full test suite
nefl test
```

### Verification Checklist
- [ ] All existing tests pass without modification
- [ ] No changes to output format (verbose table looks the same)
- [ ] NamespaceInformation is immutable (frozen=True)
- [ ] Type hints work correctly in IDEs
- [ ] EntryPart enum used instead of string literals
- [ ] Comments clarified in filter_namespaces()
- [ ] Code follows British spelling

### Expected Impact
- **Type Safety**: Dataclass fields instead of tuple indices
- **Code Clarity**: `info.frame_name` instead of `tuple[0]`
- **IDE Support**: Auto-completion for NamespaceInformation fields
- **Maintainability**: Easier to add fields or methods to dataclass
- **Documentation**: Self-documenting field names

## Benefits of This Refactoring

1. **Type Safety**: Dataclass with typed fields prevents index errors
2. **Readability**: `info.frame_name` is clearer than `tuple[0]`
3. **IDE Support**: Auto-completion and type checking
4. **Immutability**: frozen=True prevents accidental modification
5. **Consistency**: Uses EntryPart enum like tree.py
6. **Extensibility**: Easy to add fields or methods to dataclass later
