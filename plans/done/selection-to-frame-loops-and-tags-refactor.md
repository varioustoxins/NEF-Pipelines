# Refactor `selection_to_frame_loops_and_tags`

**STATUS: SUPERSEDED** ✅ - Achieved via different approach

**What was implemented (differently than planned):**
- ✅ Typed accumulator: Uses `FrameLoopsAndTags` directly (not separate `_FrameMatch` class)
  - Plan's comment suggested this: "_FrameMatch is really FrameLoopsAndTags with an extra field"
- ✅ Phase extraction: Function split into helper functions:
  - `_init_frame_matches()` - creates `OrderedDict[str, FrameLoopsAndTags]`
  - `_merge_frame_tags()`
  - `_add_selected_loops()`
  - `_merge_loop_tags()`
  - `_drop_empty_matches()`
- ✅ `filter_frame_loops_and_tags_by_namespace()` moved to `namespace_lib.py`

**What was NOT done:**
- ❌ `_FrameMatch` separate class (not needed - used `FrameLoopsAndTags` instead)
- ❌ Tests for filter function not added to `test_namespace_lib.py`

**Current state**: The refactoring goals were achieved through the earlier `refactor-frame-loops-and-tags.md` plan (now in done/). This plan's approach was superseded by using `FrameLoopsAndTags` directly as the accumulator, eliminating the need for a separate `_FrameMatch` class.

---

## Context

The function mixes two distinct phases — accumulating per-frame state and resolving
patterns to actual tag names — in a single body. An untyped dict accumulator with
magic string keys (`"frame"`, `"loops"`, `"needs_frame_content"`, …) makes both
phases hard to read. Splitting along the natural fault line with a typed dataclass
makes each piece independently understandable.

## Changes (all in `src/nef_pipelines/lib/cli_lib.py` unless noted)

### 1. Add `_FrameMatch` dataclass

Replace the anonymous dict accumulator with a typed dataclass:

```python
@dataclass
class _FrameMatch:
    frame: Saveframe
    loops: List                        # ordered by frame position, deduplicated by identity
    frame_tags: List[str]
    loop_tags: Dict[str, List[str]]
    keep_without_loops: bool           # True → emit frame even when no loops matched
                                       # (replaces the opaque "needs_frame_content" flag)
```

**COMMENT** this is really FramsLoopsAndTags with an extra field, inheitt or track keep_without_loops ina dict using
the data class as key (you can mek it immutable if ypou want)


### 2. Extract `_collect_frame_matches` (Phase 1 — accumulate)

```python
def _collect_frame_matches(
    entry: Entry,
    selectors: List[FrameLoopAndTagSelectors],
    exact: bool = False,
) -> OrderedDict[str, _FrameMatch]:
```

Walks selectors → calls `select_frames` / `select_loops_by_category` → merges tag
lists via `_merge_tag_lists` → deduplicates loops by identity. Sets
`keep_without_loops=True` when `selector.loop_name is None or selector.frame_tags`.

### 3. Extract `_resolve_frame_match` (Phase 2 — resolve, per-frame)

```python
def _resolve_frame_match(match: _FrameMatch, exact: bool = False) -> Optional[FrameLoopsAndTags]:
```

Calls `_resolve_tag_projection` for frame_tags and each loop's loop_tags. Returns
`None` (skip) when there are no loops and `keep_without_loops` is False. Otherwise
returns a fully-resolved `FrameLoopsAndTags`.

### 4. Simplify `selection_to_frame_loops_and_tags`

```python
def selection_to_frame_loops_and_tags(entry, selectors, exact=False):
    """...
    Wildcard cascading is NOT done here — callers must pre-expand selectors
    with expand_frame_loop_and_tag_wildcards() before calling this function.
    Namespace filtering is a separate step — call filter_frame_loops_and_tags_by_namespace().
    """
    matches = _collect_frame_matches(entry, selectors, exact=exact)
    return [
        result
        for match in matches.values()
        if (result := _resolve_frame_match(match, exact=exact)) is not None
    ]
```

### 5. Move `filter_frame_loops_and_tags_by_namespace` to `namespace_lib`

It belongs with the other namespace helpers (`filter_namespaces`,
`collect_namespaces_from_frames`). It uses only `FrameLoopsAndTags` / `EntryPart`
from `structures` and `get_namespace` from `namespace_lib` — no CLI-only imports.

- Move function body to `src/nef_pipelines/lib/namespace_lib.py`
- Update imports in `cli_lib.py` and `display.py` to import from `namespace_lib`

### 6. Add tests for `filter_frame_loops_and_tags_by_namespace`

Currently untested. Add to `src/nef_pipelines/tests/lib/test_namespace_lib.py`:

- empty namespace set → returns `[]`
- namespace set matching one of two frames → only matching frame returned
- namespace set matching a subset of columns in a loop → only those columns in result

## Verification

```bash
nefl test src/nef_pipelines/tests/lib/test_cli_lib.py src/nef_pipelines/tests/lib/test_namespace_lib.py src/nef_pipelines/tests/frames/test_display.py src/nef_pipelines/tests/loops/test_delete.py -q
```

240+ tests must still pass with no behaviour change.
