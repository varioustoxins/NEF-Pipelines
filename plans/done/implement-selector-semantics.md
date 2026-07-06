# Implement Frame.Loop:Tag Selector Semantics per Design Document

## Context

Aligning the selector parser implementation in `cli_lib.py` with the canonical semantics
defined in `plans/design-selectors.md` and documented in `cli-idioms`.

**Key Semantic Principle:**

Projection lists (`frame_tags` and `loop_tags`) have three distinct states:

| Value         | Meaning                                                      |
|---------------|--------------------------------------------------------------|
| `[]`          | Not projected. Container is addressed; command decides what to render. |
| `['*']`       | Explicit wildcard. User asked for every member to be projected. |
| `[n1, n2]`    | Specific named projection.                                   |

**The distinction between `[]` and `['*']` is semantic and intentional:**
- `frame.loop` → loop_tags=`[]` — "show this loop" (command decides what columns)
- `frame.loop:*` → loop_tags=`['*']` — "show every column in this loop" (explicit)

Most commands treat these identically, but some don't — and those that don't are the
reason this distinction exists.

## Current vs Target Behavior

### Parsing Examples

| Selector       | Current                                    | Should Be                               |
|----------------|--------------------------------------------|-----------------------------------------|
| `frame`        | loop=None, ftags=[], ltags=[]              | ✓ **CORRECT**                          |
| `frame:tag`    | loop=None, ftags=['tag'], ltags=[]         | ✓ **CORRECT**                          |
| `frame:*`      | loop=None, ftags=['*'], ltags=[]           | ✓ **CORRECT**                          |
| `frame.loop`   | loop='loop', ftags=[], ltags=**`['*']`**   | **WRONG** → should be ltags=`[]`       |
| `frame.loop:*` | loop='loop', ftags=[], ltags=['*']         | ✓ **CORRECT**                          |
| `frame.*`      | loop='*', ftags=[], ltags=**`['*']`**      | **WRONG** → should be ltags=`[]`       |
| `frame.*:*`    | loop='*', ftags=[], ltags=['*']            | ✓ **CORRECT**                          |

### The Bug

In `_build_frame_loop_selectors()` around line 1666-1669, when a loop is specified WITHOUT
a tag separator (`:` colon), we currently default loop_tags to `["*"]`:

```python
elif has_loop_separator:
    # frame.loop → entire loop
    loop_name = result[LOOP_IDX]
    loop_tags = ["*"]  # ← WRONG
```

This should be `[]` (not projected, command decides), not `["*"]` (explicit wildcard).

## Canonical Truth Table (from design-selectors.md §3)

These are the target outputs the parser must produce:

| Selector              | Frame  | Loop  | FrameTags  | LoopTags  |
|-----------------------|--------|-------|------------|-----------|
| **Frame scope (no dot)** |     |       |            |           |
| `frame`               | name   | None  | `[]`       | `[]`      |
| `frame:tag`           | name   | None  | `[tag]`    | `[]`      |
| `frame:tag1,tag2`     | name   | None  | `[t1, t2]` | `[]`      |
| `frame:*`             | name   | None  | `['*']`    | `[]`      |
| `*:tag`               | `*`    | None  | `[tag]`    | `[]`      |
| `*`                   | `*`    | None  | `[]`       | `[]`      |
| `*:*`                 | `*`    | None  | `['*']`    | `[]`      |
| **Loop scope (has dot)** |     |       |            |           |
| `frame.loop`          | name   | loop  | `[]`       | `[]`      |
| `frame.loop:col`      | name   | loop  | `[]`       | `[col]`   |
| `frame.loop:col1,col2`| name   | loop  | `[]`       | `[c1, c2]`|
| `frame.loop:*`        | name   | loop  | `[]`       | `['*']`   |
| `frame.*`             | name   | `*`   | `[]`       | `[]`      |
| `frame.*:col`         | name   | `*`   | `[]`       | `[col]`   |
| `*.loop`              | `*`    | loop  | `[]`       | `[]`      |
| `*.loop:col`          | `*`    | loop  | `[]`       | `[col]`   |
| `*.*`                 | `*`    | `*`   | `[]`       | `[]`      |
| `*.*:col`             | `*`    | `*`   | `[]`       | `[col]`   |
| `*.*:*`               | `*`    | `*`   | `[]`       | `['*']`   |

**Governing rules:**
- **Dot governs loop scope.** No dot → Loop=None, LoopTags=[]. Dot present → Loop is set.
- **Colon governs projection.** No colon → projection list is `[]`. Colon present →
  projection list is `[name, ...]` or `['*']`.

## Implementation Changes

### 1. Fix Core Parsing Logic

**File:** `src/nef_pipelines/lib/cli_lib.py` (~line 1666-1669)

**Change:**
```python
elif has_loop_separator:
    # frame.loop → entire loop (command decides what to show)
    loop_name = result[LOOP_IDX]
    loop_tags = []  # CHANGED from ["*"]
```

**Explanation:** When no colon is present after the loop name, loop_tags should be empty `[]`,
meaning "the loop is addressed but no specific projection is requested — the command decides
what to render."

### 2. Update extract_tags_from_result Documentation

**File:** `src/nef_pipelines/lib/cli_lib.py` (~line 1644-1650)

**Current comment is misleading:**
```python
def extract_tags_from_result(result: ParseResults, start_index: int) -> List[str]:
    """Extract and strip tags from parse results, defaulting to ["*"] if no tags present."""
```

**Should say:**
```python
def extract_tags_from_result(result: ParseResults, start_index: int) -> List[str]:
    """Extract tags from parse results. If colon present but nothing after it, returns ['*']."""
```

**Note:** This function is ONLY called when `has_tag_separator` is True (colon present),
so the `["*"]` default is correct for cases like `frame:` or `frame.loop:` where the colon
exists but the tag list is empty. This represents an explicit wildcard request.

### 3. Update Docstring Examples

**File:** `src/nef_pipelines/lib/cli_lib.py` (~line 1478)

Update the docstring in `parse_frame_loop_and_tags()` to reflect the canonical forms:

```python
"""
Parse a frame/loop/tag selector specification.

Selector format:
    frame.loop:tags

Where:
- frame: frame name or '*' (all frames)
- loop: loop name or '*' (all loops) — optional, requires '.'
- tags: tag/column names or '*' — optional, requires ':'

Projection semantics:
- [] (empty list) = not projected, command decides what to show
- ['*'] = explicit wildcard, show all members
- [name, ...] = specific named projection

Examples:
    frame               → (frame, None, [], [])      # frame metadata only
    frame:tag           → (frame, None, [tag], [])   # specific frame tag
    frame:*             → (frame, None, ['*'], [])   # all frame tags (explicit)
    frame.loop          → (frame, loop, [], [])      # one loop, command decides columns
    frame.loop:col      → (frame, loop, [], [col])   # specific column
    frame.loop:*        → (frame, loop, [], ['*'])   # all columns (explicit)
    frame.*             → (frame, '*', [], [])       # all loops in frame
    frame.*:col         → (frame, '*', [], [col])    # one column across all loops
    *.*                 → ('*', '*', [], [])         # all loops in all frames

Shorthand expansion (empty parts default to '*'):
    .loop   → *.loop    (empty before dot)
    frame.  → frame.*   (empty after dot)
    :tag    → *:tag     (empty before colon)
    frame:  → frame:*   (empty after colon - explicit wildcard)

Returns:
    FrameLoopAndTagSelectors with (frame_name, loop_name, frame_tags, loop_tags)
"""
```

### 4. Add/Update Tests

**File:** `src/nef_pipelines/tests/lib/test_cli_lib.py`

**Add test for `frame.loop` returning `[]` not `['*']`:**

```python
def test_parse_frame_loop_and_tags_loop_without_colon():
    """Test that 'frame.loop' (no colon) returns loop_tags=[] not ['*']."""
    result = parse_frame_loop_and_tags("myframe.myloop")

    assert result.frame_name == "myframe"
    assert result.loop_name == "myloop"
    assert result.frame_tags == []
    assert result.loop_tags == []  # Not ['*']!

def test_parse_frame_loop_and_tags_loop_with_explicit_wildcard():
    """Test that 'frame.loop:*' returns loop_tags=['*']."""
    result = parse_frame_loop_and_tags("myframe.myloop:*")

    assert result.frame_name == "myframe"
    assert result.loop_name == "myloop"
    assert result.frame_tags == []
    assert result.loop_tags == ['*']  # Explicit wildcard

def test_parse_frame_loop_and_tags_wildcard_loop_without_colon():
    """Test that 'frame.*' returns loop_tags=[] not ['*']."""
    result = parse_frame_loop_and_tags("myframe.*")

    assert result.frame_name == "myframe"
    assert result.loop_name == "*"
    assert result.frame_tags == []
    assert result.loop_tags == []  # Not ['*']!

def test_parse_frame_loop_and_tags_wildcard_loop_with_explicit_wildcard():
    """Test that 'frame.*:*' returns loop_tags=['*']."""
    result = parse_frame_loop_and_tags("myframe.*:*")

    assert result.frame_name == "myframe"
    assert result.loop_name == "*"
    assert result.frame_tags == []
    assert result.loop_tags == ['*']  # Explicit wildcard

def test_parse_frame_loop_and_tags_frame_tags_explicit_wildcard():
    """Test that 'frame:*' returns frame_tags=['*']."""
    result = parse_frame_loop_and_tags("myframe:*")

    assert result.frame_name == "myframe"
    assert result.loop_name is None
    assert result.frame_tags == ['*']  # Explicit wildcard
    assert result.loop_tags == []

def test_parse_frame_loop_and_tags_bare_frame():
    """Test that bare 'frame' returns empty projections."""
    result = parse_frame_loop_and_tags("myframe")

    assert result.frame_name == "myframe"
    assert result.loop_name is None
    assert result.frame_tags == []  # Not projected
    assert result.loop_tags == []
```

**Update existing test if needed:**

The test `test_parse_frame_loop_selectors_explicit_wildcard_works` may need updating
depending on what it currently expects. Check that it's testing `frame.` or `frame.*`
and verify the expected loop_tags.

### 5. Display Logic Considerations

**File:** `src/nef_pipelines/tools/frames/display.py`

The display command interprets `[]` as "show everything in this scope". This is correct
per the design document (§2: "Selectors Address, Commands Interpret").

**Current behavior should be:**
- When `loop=None` and `frame_tags=[]` → show all frame tags (command decides)
- When `loop='specific'` and `loop_tags=[]` → show all columns in that loop (command decides)
- When `loop='*'` and `loop_tags=[]` → show all columns in all loops (command decides)

**DO NOT change display.py logic** — it already interprets `[]` as wildcard for display
purposes, which is correct. The fix is ONLY in the parser.

## Verification

### 1. Unit Tests

```bash
# Test the core parsing changes
pytest src/nef_pipelines/tests/lib/test_cli_lib.py::test_parse_frame_loop_and_tags_loop_without_colon -xvs
pytest src/nef_pipelines/tests/lib/test_cli_lib.py::test_parse_frame_loop_and_tags_loop_with_explicit_wildcard -xvs
pytest src/nef_pipelines/tests/lib/test_cli_lib.py::test_parse_frame_loop_and_tags_wildcard_loop_without_colon -xvs
pytest src/nef_pipelines/tests/lib/test_cli_lib.py::test_parse_frame_loop_and_tags_wildcard_loop_with_explicit_wildcard -xvs
pytest src/nef_pipelines/tests/lib/test_cli_lib.py::test_parse_frame_loop_and_tags_frame_tags_explicit_wildcard -xvs
pytest src/nef_pipelines/tests/lib/test_cli_lib.py::test_parse_frame_loop_and_tags_bare_frame -xvs
```

### 2. Integration Tests

```bash
# All cli_lib tests should pass
pytest src/nef_pipelines/tests/lib/test_cli_lib.py -v

# All display tests should pass (display logic unchanged)
pytest src/nef_pipelines/tests/frames/test_display.py -v

# Loop deletion tests should pass
pytest src/nef_pipelines/tests/loops/test_delete.py -v
```

### 3. Manual Verification

```python
from nef_pipelines.lib.cli_lib import parse_frame_loop_and_tags

# Bare frame = no projections
result = parse_frame_loop_and_tags("myframe")
assert result.loop_name is None
assert result.frame_tags == []
assert result.loop_tags == []

# Frame with explicit tag wildcard
result = parse_frame_loop_and_tags("myframe:*")
assert result.loop_name is None
assert result.frame_tags == ['*']
assert result.loop_tags == []

# Frame.loop = loop addressed, no projection
result = parse_frame_loop_and_tags("myframe.myloop")
assert result.loop_name == "myloop"
assert result.frame_tags == []
assert result.loop_tags == []  # NOT ['*']

# Frame.loop:* = loop addressed, explicit wildcard projection
result = parse_frame_loop_and_tags("myframe.myloop:*")
assert result.loop_name == "myloop"
assert result.frame_tags == []
assert result.loop_tags == ['*']

# Frame.* = all loops addressed, no projection
result = parse_frame_loop_and_tags("myframe.*")
assert result.loop_name == "*"
assert result.frame_tags == []
assert result.loop_tags == []  # NOT ['*']

# Frame.*:* = all loops addressed, explicit wildcard projection
result = parse_frame_loop_and_tags("myframe.*:*")
assert result.loop_name == "*"
assert result.frame_tags == []
assert result.loop_tags == ['*']
```

## Files to Modify

**Core implementation:**
- `src/nef_pipelines/lib/cli_lib.py` - Fix line 1669 + update docstrings

**Tests:**
- `src/nef_pipelines/tests/lib/test_cli_lib.py` - Add new tests for `[]` vs `['*']` semantics

**No changes needed:**
- `src/nef_pipelines/tools/frames/display.py` - Already interprets `[]` correctly as "show all"
- `src/nef_pipelines/tests/frames/test_display.py` - Should pass once parser is fixed
- `src/nef_pipelines/tests/loops/test_delete.py` - Should pass once parser is fixed

## Risk Assessment

**Low Risk** - Highly localized change:
- ✓ One-line fix in parser (line 1669)
- ✓ No behavioral change for commands (they already interpret `[]` as "show all")
- ✓ Maintains backward compatibility at command level (users see same output)
- ✓ Aligns implementation with design document
- ⚠ **Semantic change**: Selector data model now distinguishes `[]` from `['*']`
- ✓ **Non-breaking**: Commands that don't care about the distinction work identically

**Migration:**
- No user-facing changes required
- Internal APIs that inspect `loop_tags` or `frame_tags` need to understand `[]` vs `['*']`
- Most commands already treat both identically (via "if not tags" logic)

## References

- Design document: `plans/design-selectors.md`
- User documentation: `cli-idioms` → *Frame.Loop:Tag Selectors*
- Related: `plans/selector-syntax-reference.md` (older reference, may be outdated)
