# Plan: Split frames rename into CLI + pipe

## Context

`frames rename` currently mixes I/O, argument parsing, frame selection, and rename logic in a single function. The goal is to extract a `pipe` function that is pure in-memory (no I/O), callable from other pipeline components, taking `(Saveframe, SaveframeNameParts)` pairs — the already-selected frame and a target name specification.

The CLI handles all selection and mode expansion, then builds the pairs and calls `pipe`. The pipe knows nothing about `--singleton`, `--replace`, `--set-category`, `--delete`, `--exact`, or `--category` — those are purely CLI concerns.

How each mode is encoded in the target `SaveframeNameParts`:
- **ID rename** (default / `--set-id`): `SaveframeNameParts(identity=new_id)` — category/namespace inherited from source
- **Category rename** (`--set-category`): `SaveframeNameParts(namespace=new_ns, category=new_cat)` — identity/counter inherited
- **Singleton** (`--singleton`): `SaveframeNameParts(identity=None, counter=None)` — category/namespace inherited
- **Replace** (`--replace`): `SaveframeNameParts(identity=old_identity.replace(old, new))` — others inherited
- **Delete** (`--delete --replace`): `SaveframeNameParts(identity=old_identity.replace(substr, ""))` — others inherited

## Existing utilities to reuse

`parse_frame_name()` (`src/nef_pipelines/lib/nef_lib.py:196`) and `SaveframeNameParts` (`src/nef_pipelines/lib/structures.py:149`) already do exactly this. No new helpers needed.

`SaveframeNameParts` currently has four required fields (`namespace`, `category`, `identity`, `counter`) plus `.is_singleton` and `.full_name` properties. `parse_frame_name()` accepts either a `Saveframe` or a `(full_name, category)` tuple.

**Required change to `structures.py`:** Make `category` (and `namespace`) optional with `None` meaning "carry over from the source frame". This lets the CLI build a minimal target spec like `SaveframeNameParts(identity="new_id")` without repeating the namespace/category it's already reading from the frame.

```python
@dataclass(frozen=True)
class SaveframeNameParts:
    namespace: Optional[str] = None
    category: Optional[str] = None   # None = keep source frame's category
    identity: Optional[str] = None
    counter: Optional[str] = None
```

The pipe resolves `None` fields by merging with `parse_frame_name(frame)` before computing `full_name`. The `.full_name` property must handle `category=None` gracefully (either raise or require resolution first).

Note: `structures.py:144` already has `# - src/nef_pipelines/tools/frames/rename.py (todo)` — this split is the intended migration. Implementing the plan clears that TODO.

The planned private helpers (`_frame_name_to_parts`, `_parts_to_frame_name`) are **not needed**. Use `parse_frame_name(target_frame)` and `parts.full_name` instead.

`parse_frame_name` is already imported in `nef_lib` — add `SaveframeNameParts` to imports from `nef_pipelines.lib.structures`.

## Changes — `src/nef_pipelines/tools/frames/rename.py`

### New `pipe` function

```python
def pipe(
    entry: Entry,
    renames: List[Tuple[Saveframe, SaveframeNameParts]],
    force: bool = False,
) -> Entry:
```

Each pair is `(frame_to_rename, target_parts)` — the frame object (already selected from entry) and a `SaveframeNameParts` describing exactly what the new name should be. The pipe's job is purely to apply the renames:

```python
for frame, target_parts in renames:
    # Resolve None fields from the source frame's current parts
    source = parse_frame_name(frame)
    resolved = SaveframeNameParts(
        namespace=target_parts.namespace if target_parts.namespace is not None else source.namespace,
        category=target_parts.category if target_parts.category is not None else source.category,
        identity=target_parts.identity,   # None is valid (singleton)
        counter=target_parts.counter if target_parts.counter is not None else source.counter,
    )
    new_full_name = resolved.full_name
    new_category = f"{resolved.namespace}_{resolved.category}" if resolved.namespace else resolved.category

    if new_full_name in entry.frame_dict and not force:
        existing = entry.get_saveframe_by_name(new_full_name)
        if existing is not frame:
            _exit_clashing_frame_name(new_full_name, entry)

    if new_full_name in entry.frame_dict and force:
        existing = entry.get_saveframe_by_name(new_full_name)
        if existing is not frame:
            entry.remove_saveframe(existing)

    frame.name = new_full_name
    if frame.category != new_category:
        frame.category = new_category

return entry
```

All selection, mode logic, and pair-building lives in the CLI:
- **Default ID rename**: `SaveframeNameParts(identity=new_name or None)`
- **`--set-category`**: `SaveframeNameParts(namespace=new_ns, category=new_cat)` — CLI strips namespace from `new_name` if present
- **`--singleton`**: `SaveframeNameParts(identity=None, counter=None)`
- **`--replace`**: `SaveframeNameParts(identity=source.identity.replace(old_name, new_name))`

Add `Tuple` to `typing` imports. Add `SaveframeNameParts` to imports from `nef_pipelines.lib.structures`.

### Updated CLI `rename` function

Keeps all current validation (`--delete` requires `--replace`, `--singleton` mutual exclusion, `_exit_renames_not_pairs`). After reading the entry, the CLI builds the `(Saveframe, SaveframeNameParts)` pairs by:

1. Iterating `chunks(old_new_names, 2)` to get `(old_name, new_name)` string pairs
2. For each pair, calling `select_frames_by_name` / category filter to find matching frames
3. For each matching frame, calling `parse_frame_name(frame)` to get source parts
4. Building target `SaveframeNameParts` based on active mode (see Context section)
5. Appending `(frame, target_parts)` to the rename list
6. Calling `_exit_error_mutiple_frames_selected` / `_exit_no_frames_selected` as before for selection errors

Then:

```python
entry = read_entry_from_file_or_stdin_or_exit_error(input)
renames = _build_rename_pairs(entry, old_new_names, category, exact, set_category, replace)
entry = pipe(entry, renames, force=force)
print(entry)
```

The selection + pair-building logic can live in a private `_build_rename_pairs(...)` helper to keep `rename()` readable.

## Tests — `src/nef_pipelines/tests/frames/test_rename.py`

Add one direct pipe test (no CLI runner) to confirm the pipe is callable in-memory:

```python
def test_rename_basic_pipe():
    from nef_pipelines.lib.structures import SaveframeNameParts
    from nef_pipelines.tools.frames.rename import pipe as rename_pipe

    OLD_ID = "k_ubi_hnco`1`"
    NEW_ID = "k_ubi_hnco_1"
    OLD_FRAME = f"nef_nmr_spectrum_{OLD_ID}"
    NEW_FRAME = f"nef_nmr_spectrum_{NEW_ID}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    entry = Entry.from_file(str(path))

    frame = entry.get_saveframe_by_name(OLD_FRAME)
    target = SaveframeNameParts(identity=NEW_ID)
    result = rename_pipe(entry, [(frame, target)])

    frame_names = list(result.frame_dict.keys())
    assert NEW_FRAME in frame_names
    assert OLD_FRAME not in frame_names
```

`Entry.from_file` is confirmed present in pynmrstar (`nef_lib.py:814` uses it).

## Verification

```
pytest src/nef_pipelines/tests/frames/test_rename.py
nefl test frames/test_rename.py
```

All 22 existing tests must still pass plus the new pipe test.

## Addendum: Higher-level refactoring of pipe (decision: not warranted)

The implemented `pipe()` has three logical phases — resolve parts, check clash, apply rename — but they flow naturally in a single 20-line loop. `_build_rename_pairs()` has three blocks — select frames, filter by category, build target per mode — but each is only a few lines deep and they share local state (`source`, `target_frames`). Extracting either into further helpers would produce one-liner or two-liner functions with no reuse value, violating the rule (3+ non-trivial, coherent, meaningful functions). No further refactoring is warranted.
