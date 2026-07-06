# expand_frame_loop_and_tag_wildcards — Generalisation Plan

## Context

`expand_frame_loop_and_tag_wildcards` exists in `cli_lib.py` (~line 2188) but is currently
unused (no callers, no tests). It was written as an all-or-nothing expander. Different
commands need different expansion depths, so the function needs to say precisely which parts
of the selector hierarchy to fill in.

The hierarchy has two independent rivers:

```
Saveframe → FrameTag       (frame_tags:  [] → ['*'])
Saveframe → Loop → LoopTag  (loop_name: None → '*', loop_tags: [] → ['*'])
```

---

## Design

Use the existing `EntryPart` enum (`structures.py`) as a `Set[EntryPart]` argument — no
new enum needed. The caller passes the set of endpoints they want expanded.

Relevant values:
- `EntryPart.FrameTag` — expand `frame_tags: [] → ['*']`
- `EntryPart.Loop`     — expand `loop_name: None → '*'`
- `EntryPart.LoopTag`  — expand `loop_tags: [] → ['*']`  _(implies Loop should also be in the set)_

### Signature

```python
_ALL_EXPANDABLE = frozenset({EntryPart.FrameTag, EntryPart.Loop, EntryPart.LoopTag})

def expand_frame_loop_and_tag_wildcards(
    selector: FrameLoopAndTagSelectors,
    expand_to: Set[EntryPart] = _ALL_EXPANDABLE,
) -> FrameLoopAndTagSelectors:
    """Expand unset selector fields to wildcard for the specified entry parts.

    Two independent rivers can be expanded:
      FrameTag          → frame_tags: [] → ['*']
      Loop              → loop_name: None → '*'
      Loop + LoopTag    → loop_name: None → '*' AND loop_tags: [] → ['*']

    Parts already set (non-empty / non-None) are never overwritten.

    Example usages:
        expand_frame_loop_and_tag_wildcards(sel)
            # expand everything (default)
        expand_frame_loop_and_tag_wildcards(sel, {EntryPart.FrameTag})
            # expand frame tags only, leave loops alone
        expand_frame_loop_and_tag_wildcards(sel, {EntryPart.Loop, EntryPart.LoopTag})
            # expand into loops and their columns, leave frame tags alone
        expand_frame_loop_and_tag_wildcards(sel, set())
            # no expansion
    """
```

### Implementation

```python
    frame_name = selector.frame_name
    loop_name  = selector.loop_name
    frame_tags = selector.frame_tags
    loop_tags  = selector.loop_tags

    if EntryPart.FrameTag in expand_to and not frame_tags:
        frame_tags = ["*"]

    if EntryPart.Loop in expand_to and loop_name is None:
        loop_name = "*"

    if EntryPart.LoopTag in expand_to and not loop_tags:
        loop_tags = ["*"]

    return FrameLoopAndTagSelectors(frame_name, loop_name, frame_tags, loop_tags)
```

---

## Truth table

| Selector       | expand_to                         | loop_name | frame_tags | loop_tags   |
|----------------|-----------------------------------|-----------|------------|-------------|
| `frame`        | `{FrameTag, Loop, LoopTag}`       | `*`       | `['*']`    | `['*']`     |
| `frame`        | `{Loop, LoopTag}`                 | `*`       | `[]`       | `['*']`     |
| `frame`        | `{Loop}`                          | `*`       | `[]`       | `[]`        |
| `frame`        | `{FrameTag}`                      | `None`    | `['*']`    | `[]`        |
| `frame`        | `set()`                           | `None`    | `[]`       | `[]`        |
| `frame.loop`   | `{FrameTag, Loop, LoopTag}`       | `loop`    | `['*']`    | `['*']`     |
| `frame.loop`   | `{Loop, LoopTag}`                 | `loop`    | `[]`       | `['*']`     |
| `frame.loop:*` | `{FrameTag, Loop, LoopTag}`       | `loop`    | `['*']`    | `['*']` (unchanged) |

---

## Files to change

- `src/nef_pipelines/lib/cli_lib.py` — rewrite `expand_frame_loop_and_tag_wildcards`,
  add `_ALL_EXPANDABLE` constant, add `Set` to imports
- `src/nef_pipelines/tests/lib/test_cli_lib.py` — add parametrised tests covering the
  truth table above; import `EntryPart` from `structures`

No new enum needed. `EntryPart` is already imported in `cli_lib.py` (line 70).
