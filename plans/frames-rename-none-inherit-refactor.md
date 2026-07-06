# Plan: frames rename refactor — phased

## Sentinel design (shared across all phases)

| value   | meaning                              |
|---------|--------------------------------------|
| `None`  | inherit this field from source frame |
| `""`    | explicitly absent                    |
| `"val"` | use this exact value                 |

Currently `identity=None` and `index=None` mean "absent", not "inherit from source". After
Phase 1 all four fields follow the same rule: `None` = inherit, `""` = explicitly absent.

---

## Phase 1 — None=inherit / ""=absent sentinels ← IMPLEMENT NOW

No CLI changes. Pure internal consistency fix.

### `src/nef_pipelines/lib/structures.py`

**`full_name` property** — treat `""` same as `None` for identity:
```python
# was: if self.identity is None:
if not self.identity:      # None or "" → absent
    base = category_with_namespace
else:
    base = f"{category_with_namespace}_{self.identity}"
# index: `if self.index:` already correct — no change
```

**`is_singleton` property:**
```python
# was: return self.identity is None and self.index is None
return not self.identity and not self.index
```

Update docstring to document None=inherit / ""=absent sentinels.

### `src/nef_pipelines/tools/frames/rename.py`

**`_resolve_frame_name_parts`** — extend inheritance to identity and index:
```python
return SaveframeNameParts(
    namespace=target.namespace if target.namespace is not None else source.namespace,
    category=target.category if target.category is not None else source.category,
    identity=target.identity if target.identity is not None else source.identity,
    index=target.index if target.index is not None else source.index,
)
```

**`_build_rename_pairs` — default case** (was `SaveframeNameParts(identity=new_name or None)`):
```python
target = SaveframeNameParts(identity=new_name or "", index="")
```
`index=""` is now explicit rather than relying on absence — same observable CLI behaviour.

**`_build_rename_pairs` — `--set-category` case** — remove explicit identity/index copying:
```python
if set_category:
    new_cat_parts = parse_frame_name((new_name, new_name))
    explicit_ns = new_cat_parts.namespace if new_cat_parts.namespace is not None else ""
    target = SaveframeNameParts(
        namespace=explicit_ns,
        category=new_cat_parts.category,
        # identity=None, index=None → inherit via _resolve_frame_name_parts
    )
```

### `src/nef_pipelines/tests/frames/test_rename.py`

Add `test_rename_pipe_inherits_index`:
```python
def test_rename_pipe_inherits_index():
    OLD_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_FRAME_ID = "nef_nmr_spectrum_new_id`1`"    # index=1 inherited
    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    entry = Entry.from_file(str(path))
    frame = entry.get_saveframe_by_name(OLD_FRAME_ID)
    target = SaveframeNameParts(identity="new_id")  # index=None → inherit
    result = rename_pipe(entry, [(frame, target)])
    assert NEW_FRAME_ID in result.frame_dict
    assert OLD_FRAME_ID not in result.frame_dict
```

### Verification

```
nefl test frames/test_rename
```
All 23 existing tests must pass unchanged. New test brings total to 24.

---

## Phase 2 — `--target identity|category|namespace` replaces `--set-category`/`--set-id`

Replace two mutually-exclusive bool flags with a single enum option. Scales to namespace; removes
proliferating booleans.

```python
class RenameTarget(str, Enum):
    identity = "identity"
    category = "category"
    namespace = "namespace"

target: Optional[RenameTarget] = typer.Option(
    None, '--target',
    help="field to set: identity (default), category, or namespace"
)
```

Positional pairs become `(old_selector, new_value)` where `new_value` sets the chosen field.
`--target category` reuses the existing `parse_frame_name((new_name, new_name))` logic (namespace
prefix parsing from the value). `--target namespace` sets namespace only; identity/index inherit.
`singleton` stays orthogonal — check `if singleton and target: exit_error(...)`.

### Concrete examples

```
frames rename --target category k_ubi_hnco`1` new_category
  → new_category_k_ubi_hnco`1`   (identity/index inherited)

frames rename --target namespace k_ubi_hnco`1` ccpn
  → ccpn_nmr_spectrum_k_ubi_hnco`1`  (all others inherited)
```

---

## Phase 3 — `--replace OLD NEW` / `--delete SUBSTR` as typed options

Convert from bool flags to proper typed options; positional args become frame selectors.
`--replace` and `--delete` are mutually exclusive. They always operate on identity regardless of
`--target`.

```python
replace: Optional[Tuple[str, str]] = typer.Option(
    None, '--replace', nargs=2, metavar='OLD NEW',
    help="replace OLD with NEW in the frame identity (positional args = selectors)"
)
delete: Optional[str] = typer.Option(
    None, '--delete', metavar='SUBSTR',
    help="delete SUBSTR from the frame identity (positional args = selectors)"
)
```

Default selector when no positional args given: `[old_str]` for `--replace`, `[delete]` for
`--delete`. Empty-identity guard: if replace/delete produces `identity == ""`, error with hint to
use `--singleton`.

### Concrete examples

```
frames rename --replace k_ubi k_ubiquitin *hnco* *hncaco*
  → identity substring replaced, index inherited

frames rename --delete k_ubi          # selector defaults to "k_ubi"
frames rename --delete k_ubi *hnco*   # explicit selectors
```

---

## Phase 4 — `category.id` selector syntax ← DROPPED

`category.id` would collide with the existing `frame.loop` selector grammar — `.` is already
taken. `--category` stays as-is. No further work needed here.

---

## Phase 5 — `--index N|+N|-N` index arithmetic (DEFERRED)

Set or shift the index field. See addendum in `plans/frames-rename-cli-pipe-split.md`.
Orthogonal to all phases above.
