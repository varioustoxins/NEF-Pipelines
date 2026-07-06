# Refactor cli_lib Escape System: Double-Character to Backslash Escapes

## Context

The cli_lib.py module currently uses a double-character escape system (`::`→`:`, `..`→`.`, `,,`→`,`) for literal separators in frame.loop:tag selectors. This system:
- Is **not used in production** (only appears in test code)
- Uses complex null-byte placeholder preprocessing
- Is less intuitive than standard backslash escapes

This refactoring will:
- Remove the unused double-character escape system entirely
- Replace it with backslash escapes (`\:`, `\.`, `\,`, `\*`, `\?`, `\\`)
- Reuse existing proven utilities: `find_first_unescaped()` and `unescape_backslashes()` from util.py
- Support wildcard escaping for literal `*` and `?` characters

The backslash utilities are already implemented, tested (37 test cases), and successfully used in frames/create.py.

## Implementation Plan

### 1. Add Backslash-Aware Parsing Function

**File:** `src/nef_pipelines/lib/cli_lib.py`

Add new parsing function `_parse_with_backslash_escapes()` after `parse_frame_loop_and_tags()` (around line 1553):

```python
def _parse_with_backslash_escapes(frame_spec: str) -> FrameLoopAndTagSelectors:
    """Parse frame.loop:tag1,tag2 with backslash escape support.

    Supports: \: \. \, \* \? \\
    """
    # Import utilities
    from nef_pipelines.lib.util import find_first_unescaped, unescape_backslashes

    # Step 1: Split on unescaped : (frame.loop | tags)
    colon_pos = find_first_unescaped(frame_spec, FRAME_TAG_SEPARATOR)
    if colon_pos is not None:
        frame_loop_part = frame_spec[:colon_pos]
        tags_part = frame_spec[colon_pos + 1:]
        tags = _split_on_unescaped_char(tags_part, TAG_LIST_SEPARATOR)
        tags = [unescape_backslashes(t.strip()) for t in tags]
    else:
        frame_loop_part = frame_spec
        tags = []

    # Step 2: Split on unescaped . (frame | loop)
    dot_pos = find_first_unescaped(frame_loop_part, FRAME_LOOP_SEPARATOR)
    if dot_pos is not None:
        frame_name = unescape_backslashes(frame_loop_part[:dot_pos]) or "*"
        loop_name = unescape_backslashes(frame_loop_part[dot_pos + 1:]) or "*"
        # Loop-level selector
        return FrameLoopAndTagSelectors(frame_name, loop_name, [], tags or ["*"])
    else:
        frame_name = unescape_backslashes(frame_loop_part) or "*"
        if tags:
            # Frame-level tags
            return FrameLoopAndTagSelectors(frame_name, None, tags, [])
        else:
            # Entire frame
            return FrameLoopAndTagSelectors(frame_name, "*", ["*"], ["*"])
```

Add helper function `_split_on_unescaped_char()`:

```python
def _split_on_unescaped_char(s: str, char: str) -> List[str]:
    """Split string on unescaped occurrences of char."""
    parts = []
    current = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            current.append(s[i:i+2])
            i += 2
        elif s[i] == char:
            parts.append(''.join(current))
            current = []
            i += 1
        else:
            current.append(s[i])
            i += 1
    parts.append(''.join(current))
    return parts
```

### 2. Update parse_frame_loop_and_tags to Use New Parser

**File:** `src/nef_pipelines/lib/cli_lib.py` (line ~1469)

Modify the main function to route to backslash parser when `use_escapes=True`:

```python
def parse_frame_loop_and_tags(
    frame_spec: str,
    use_escapes: bool = False,
) -> FrameLoopAndTagSelectors:
    """..."""
    original_spec = frame_spec

    if use_escapes:
        # New: backslash escape parsing
        try:
            return _parse_with_backslash_escapes(frame_spec)
        except Exception as e:
            raise BadFrameLoopTagSyntaxException(original_spec, f"invalid syntax: {str(e)}")
    else:
        # Legacy: pyparsing grammar (no escapes)
        grammar = _build_frame_loop_tag_grammar(use_escapes=False)
        parser_result = _parse_spec_with_grammar(frame_spec, grammar, original_spec, use_escapes=False)
        return _build_frame_loop_selectors(frame_spec, parser_result)
```

### 3. Remove Double-Character Escape System

**File:** `src/nef_pipelines/lib/cli_lib.py`

Delete these functions entirely:
- `_insert_frame_loop_tag_placeholders()` (~line 1714)
- `_remove_frame_loop_tag_place_holders()` (~line 1610)

Delete these constants (~lines 162-172):
- `_FRAME_LOOP_AND_TAG_PLACEHOLDERS`
- `_REVERSED_FRAME_LOOP_AND_TAG_PLACEHOLDERS`

### 4. Update _build_frame_loop_selectors

**File:** `src/nef_pipelines/lib/cli_lib.py` (lines ~1649-1650)

Change from naive string checks to escape-aware checks:

```python
# BEFORE:
has_tag_separator = FRAME_TAG_SEPARATOR in frame_spec
has_loop_separator = FRAME_LOOP_SEPARATOR in frame_spec

# AFTER:
from nef_pipelines.lib.util import find_first_unescaped
has_tag_separator = find_first_unescaped(frame_spec, FRAME_TAG_SEPARATOR) is not None
has_loop_separator = find_first_unescaped(frame_spec, FRAME_LOOP_SEPARATOR) is not None
```

### 5. Update _detect_escape_sequences

**File:** `src/nef_pipelines/lib/cli_lib.py` (~line 1678)

Replace double-character detection with backslash detection:

```python
def _detect_escape_sequences(spec: str) -> str:
    """Detect backslash escape sequences."""
    backslash_escapes = []
    i = 0
    while i < len(spec):
        if spec[i] == '\\' and i + 1 < len(spec):
            next_char = spec[i + 1]
            if next_char in ':.,*?\\':
                backslash_escapes.append(f'\\{next_char}')
            i += 2
        else:
            i += 1

    if backslash_escapes:
        unique = sorted(set(backslash_escapes))
        return f"I found {', '.join(unique)} which look like backslash escapes. Use --use-escapes to enable."
    return ""
```

### 6. Update Documentation

**File:** `src/nef_pipelines/lib/cli_lib.py`

Update the TODO comment (line ~3):
```python
*COMPLETED* Backslash escape support added using find_first_unescaped() and unescape_backslashes()
```

Update docstring for `parse_frame_loop_and_tags()` (lines ~1512-1527):
```python
Escape Sequences (use_escapes=True):
    Backslash escapes for special characters:
    - \: → literal : (in frame/loop/tag names)
    - \. → literal . (in frame/loop names)
    - \, → literal , (in tag names)
    - \* → literal * (not wildcard)
    - \? → literal ? (not wildcard)
    - \\ → literal backslash

    Examples:
        parse_frame_loop_and_tags(r"frame\.v2:tag", use_escapes=True)
        → frame_name="frame.v2", frame_tags=["tag"]
```

### 7. Update Tool Help Text

**File:** `src/nef_pipelines/tools/chains/rename.py` (lines ~31, 61)

Change from `,,` to `\,`:
```python
# Line ~31:
help="...use --use-escapes and escape commas with backslash: \\, (e.g. \"A\\,1,B\"..."

# Line ~61:
help="enable escape sequences for chain codes containing commas (use \\, for literal comma)"
```

### 8. Update Tests

**File:** `src/nef_pipelines/tests/lib/test_cli_lib.py`

Update `test_parse_frame_loop_and_tags_with_escapes` (~line 2187) to use backslash escapes:

```python
@pytest.mark.parametrize(
    "input_str,expected",
    [
        (r"frame\:name:tag", FrameLoopAndTagSelectors("frame:name", None, ["tag"], [])),
        (r"frame\.name.loop:tag", FrameLoopAndTagSelectors("frame.name", "loop", [], ["tag"])),
        (r"frame:tag1\,2,tag3", FrameLoopAndTagSelectors("frame", None, ["tag1,2", "tag3"], [])),
        (r"frame.loop\.name:tag", FrameLoopAndTagSelectors("frame", "loop.name", [], ["tag"])),
        (r"frame\*.loop:tag", FrameLoopAndTagSelectors("frame*", "loop", [], ["tag"])),
        (r"frame\?.loop:tag", FrameLoopAndTagSelectors("frame?", "loop", [], ["tag"])),
        (r"frame\\.loop:tag", FrameLoopAndTagSelectors(r"frame\", "loop", [], ["tag"])),
    ],
)
def test_parse_frame_loop_and_tags_with_escapes(input_str, expected):
    """Test backslash escape sequences."""
    result = parse_frame_loop_and_tags(input_str, use_escapes=True)
    assert result == expected
```

Update error detection test (~line 2243):
```python
@pytest.mark.parametrize(
    "input_str,escape_seq",
    [
        (r"frame\:name:tag", r"\:"),
        (r"frame\.name.loop", r"\."),
        (r"frame:tag1\,2", r"\,"),
    ],
)
def test_parse_frame_loop_and_tags_escape_sequences_without_flag(input_str, escape_seq):
    """Test helpful errors when backslash escapes used without flag."""
    with pytest.raises(BadFrameLoopTagSyntaxException) as exc_info:
        parse_frame_loop_and_tags(input_str)
    assert "Did you forget --use-escapes?" in str(exc_info.value)
```

**File:** `src/nef_pipelines/tests/chains/test_rename.py` (~line 304)

Update integration test:
```python
# BEFORE:
result = run_and_report(app, ["--use-escapes", "B", "D,,1"], input=INPUT)

# AFTER:
result = run_and_report(app, ["--use-escapes", "B", r"D\,1"], input=INPUT)
```

### 9. Update Error Messages

**File:** `src/nef_pipelines/lib/cli_lib.py` (~line 1737)

Change error guidance:
```python
# BEFORE:
msg = f". To use a literal '{FRAME_TAG_SEPARATOR}', escape it as '{FRAME_TAG_SEPARATOR * 2}'"

# AFTER:
msg = f". To use a literal '{FRAME_TAG_SEPARATOR}', escape it with backslash: \\{FRAME_TAG_SEPARATOR}"
```

## Files to Modify

**Core implementation:**
- `src/nef_pipelines/lib/cli_lib.py` - Main parsing logic changes

**Tests:**
- `src/nef_pipelines/tests/lib/test_cli_lib.py` - Update test cases to backslash syntax
- `src/nef_pipelines/tests/chains/test_rename.py` - Update integration test

**Documentation/Help:**
- `src/nef_pipelines/tools/chains/rename.py` - Update help text

**Utilities (already exist, no changes needed):**
- `src/nef_pipelines/lib/util.py` - Contains find_first_unescaped() and unescape_backslashes()
- `src/nef_pipelines/tests/lib/test_util.py` - Already has 37 tests for escape utilities

## Verification

1. **Run escape utility tests:**
   ```bash
   pytest src/nef_pipelines/tests/lib/test_util.py::test_find_first_unescaped -v
   pytest src/nef_pipelines/tests/lib/test_util.py::test_unescape_backslashes -v
   ```

2. **Run updated cli_lib tests:**
   ```bash
   pytest src/nef_pipelines/tests/lib/test_cli_lib.py::test_parse_frame_loop_and_tags_with_escapes -v
   pytest src/nef_pipelines/tests/lib/test_cli_lib.py::test_parse_frame_loop_and_tags_escape_sequences_without_flag -v
   ```

3. **Run integration tests:**
   ```bash
   pytest src/nef_pipelines/tests/chains/test_rename.py -k "escape" -v
   ```

4. **Run full test suite:**
   ```bash
   pytest src/nef_pipelines/tests/lib/test_cli_lib.py -v
   ```

5. **Manual verification:**
   ```python
   from nef_pipelines.lib.cli_lib import parse_frame_loop_and_tags

   # Test basic escapes
   r1 = parse_frame_loop_and_tags(r"frame\.v2:tag", use_escapes=True)
   assert r1.frame_name == "frame.v2"

   # Test comma in tags
   r2 = parse_frame_loop_and_tags(r"frame:tag\,1,tag2", use_escapes=True)
   assert r2.frame_tags == ["tag,1", "tag2"]

   # Test wildcard escaping
   r3 = parse_frame_loop_and_tags(r"frame\*.loop:tag", use_escapes=True)
   assert r3.frame_name == "frame*"  # Literal asterisk, not wildcard
   ```

## Risk Assessment

**Low Risk** - The double-character escape system is unused in production:
- Only appears in test code
- No real NEF files use it
- Backslash utilities already proven in frames/create.py
- Maintains backward compatibility via `use_escapes` flag

## Next Steps

After implementation is stable, consider:
1. Making backslash escapes always active (remove `use_escapes` flag)
2. Removing the pyparsing grammar entirely (use manual parsing for all cases)
3. Adding escape support to other parts of the codebase that need it
