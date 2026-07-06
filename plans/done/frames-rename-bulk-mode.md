# Plan: frames rename --bulk mode

## Context

`frames rename` currently applies a single OLD→NEW (or replace/delete/singleton) operation across
selected frames. Users who need to rename multiple frames with different old/new pairs must invoke
the command repeatedly. `--bulk` addresses this by accepting a list of independent
`SELECTOR=/OLD/NEW/` triples in one invocation — the mmv-like multi-rename use case referenced in
the existing TODO comment at the top of `rename.py`.

---

## Triple syntax

```
SELECTOR=/OLD/NEW/
```

`=` separates the frame selector from the sed-style `/OLD/NEW/` replacement expression.
Trailing `/` is accepted but not required.

- `=` terminates the selector (unambiguous — `=` never appears in NEF frame names)
- `/OLD/NEW/` follows sed convention; the two `/` delimit OLD and NEW
- `\=` escapes a literal `=` inside the selector (rare)
- `\/` escapes a literal `/` inside OLD or NEW
- Selector supports the same wildcards as the existing frame selectors (`*`, `?`)
- `OLD` and `NEW` are substring values (same semantics as default `find_and_replace` mode)
- `--target` composes freely: if `--target namespace`, OLD/NEW apply to the namespace component

### Multi-triple forms

Multiple triples can be provided in any of these equivalent forms:

```bash
# space-separated positional args (shell-level)
frames rename --bulk "S1=/OLD1/NEW1/" "S2=/OLD2/NEW2/"

# comma-separated in a single arg
frames rename --bulk "S1=/OLD1/NEW1/,S2=/OLD2/NEW2/"

# trailing-slash concatenated (trailing '/' of one triple flows into the next)
frames rename --bulk "S1=/OLD1/NEW1/S2=/OLD2/NEW2/"
```

Parsing rule (applied to each positional arg independently):
1. Split on unescaped `,` to get chunks.
2. For each chunk, parse triples in a loop:
   - Find first unescaped `=` → SELECTOR; consume `=`
   - Consume leading `/`
   - Find first unescaped `/` → OLD; consume it
   - Find first unescaped `/` → NEW (if found) and advance past it; otherwise NEW = rest, done
   - Remaining non-empty string → loop to parse next triple
3. Concatenated form requires the trailing `/`; without it the boundary is ambiguous.

### Examples

```bash
# rename two specific frames, different old→new each (single quotes: no escaping needed)
frames rename --bulk 'k_ubi_hnco`1`=/k_ubi/k_ubiquitin/' 'k_ubi_hncaco`1`=/k_ubi/k_ubiquitin/'

# same, comma-separated in one arg
frames rename --bulk 'k_ubi_hnco`1`=/k_ubi/k_ubiquitin/,k_ubi_hncaco`1`=/k_ubi/k_ubiquitin/'

# same, concatenated (trailing-slash form)
frames rename --bulk 'k_ubi_hnco`1`=/k_ubi/k_ubiquitin/k_ubi_hncaco`1`=/k_ubi/k_ubiquitin/'

# wildcard selector, replace substring in identity
frames rename --bulk '*hnco*=/k_ubi/k_ubiquitin/' '*hncaco*=/k_ubi/k_ubiquitin/'

# --target namespace: OLD/NEW apply only to the namespace component
frames rename --target namespace --bulk '*hnco*=/k_ubi/k_ubiquitin/' '*hncaco*=/k_ubi/k_ubiquitin/'

# delete (empty NEW)
frames rename --bulk '*hnco*=/k_ubi//'
```

---

## Implementation

### 1. Add `Mode.bulk` to the enum

```python
class Mode(str, Enum):
    find_and_replace = "find_and_replace"
    singleton        = "singleton"
    replace          = "replace"
    delete           = "delete"
    bulk             = "bulk"
```

### 2. Add `--bulk` bool flag (same idiom as `--replace`, `--delete`, `--singleton`)

```python
bulk: bool = typer.Option(
    False, '--bulk',
    help="apply multiple independent SELECTOR=/OLD/NEW/ triples; positional args are the triples"
)
```

### 3. Update `_mode_from_flags_or_exit_error`

Add `bulk` parameter. It is mutually exclusive with `--replace`, `--delete`, `--singleton`.
`--bulk` with `--target` is allowed (operates on the targeted component).
`--bulk` with `--singleton` is an error.

### 4. Add `_parse_bulk_triples_or_exit_error`  (in `rename.py`)

Reuse `find_index_of_first_unescaped` and `unescape_backslashes` from
`src/nef_pipelines/lib/util.py`. `DEFAULT_ESCAPES` (util.py:1439) = `{".", "*", "?", ":", ",", "\\"}`
is the existing base — the bulk sets swap `:` for the relevant separator:

```python
_BULK_SELECTOR_ESCAPES = ('.', '*', '?', '=', '\\')   # DEFAULT_ESCAPES with = instead of :
_BULK_VALUE_ESCAPES    = ('.', '*', '?', '/', '\\')   # DEFAULT_ESCAPES with / instead of :

def _parse_bulk_triples_or_exit_error(chunk: str) -> List[Tuple[str, str, str]]:
    results = []
    remainder = chunk
    while remainder:
        eq_idx = find_index_of_first_unescaped(remainder, "=")
        if eq_idx is None:
            exit_error(f"bulk expression {chunk!r}: missing '=' separator (SELECTOR=/OLD/NEW/)")
        selector  = unescape_backslashes(remainder[:eq_idx], escapes=_BULK_SELECTOR_ESCAPES)
        remainder = remainder[eq_idx + 1:]

        if not remainder.startswith("/"):
            exit_error(f"bulk expression {chunk!r}: replacement must start with '/' after '=' (SELECTOR=/OLD/NEW/)")
        remainder = remainder[1:]  # consume leading /

        slash_idx = find_index_of_first_unescaped(remainder, "/")
        if slash_idx is None:
            exit_error(f"bulk expression {chunk!r}: missing '/' between OLD and NEW (SELECTOR=/OLD/NEW/)")
        old_val   = unescape_backslashes(remainder[:slash_idx], escapes=_BULK_VALUE_ESCAPES)
        remainder = remainder[slash_idx + 1:]

        slash_idx2 = find_index_of_first_unescaped(remainder, "/")
        if slash_idx2 is None:
            new_val   = unescape_backslashes(remainder, escapes=_BULK_VALUE_ESCAPES)
            remainder = ""
        else:
            new_val   = unescape_backslashes(remainder[:slash_idx2], escapes=_BULK_VALUE_ESCAPES)
            remainder = remainder[slash_idx2 + 1:]  # "" or next triple's selector

        results.append((selector, old_val, new_val))
    return results
```

Comma-splitting uses `find_index_of_first_unescaped(arg, ",")` in a short inline loop — no named
helper needed. `parse_comma_separated_options` in `util.py` does a plain `str.split(",")` and
cannot be reused here.

### 5. Update `rename()` body — bulk branch

`pipe()` already accepts `List[Tuple[Saveframe, SaveframeNameParts]]`, so bulk mode just
accumulates all pairs from all triples and calls `pipe()` once. The existing `--force` flag and
`NEFFrameAlreadyExistsException` handler are unchanged — they apply to the merged batch.
Note: all pairs are applied atomically; a conflict in triple N stops the whole batch, not just
that triple.

```python
if mode == Mode.bulk:
    renames = []
    for arg in args:
        chunks = []
        start = 0
        while True:
            idx = find_index_of_first_unescaped(arg[start:], ",")
            if idx is None:
                chunks.append(arg[start:])
                break
            chunks.append(arg[start:start + idx])
            start += idx + 1
        for chunk in chunks:
            for selector, old_val, new_val in _parse_bulk_triples_or_exit_error(chunk):
                selected = _select_frames_or_exit_error(entry, [selector], category_filter, exact)
                pairs = _build_rename_pairs_or_exit_error(
                    selected, [old_val, new_val], target, Mode.find_and_replace
                )
                renames.extend(pairs)
else:
    operation_args, selectors = _extract_args_and_selectors_or_exit_error(args, mode)
    frames = _select_frames_or_exit_error(entry, selectors, category_filter, exact)
    renames = _build_rename_pairs_or_exit_error(frames, operation_args, target, mode)

try:
    entry = pipe(entry, renames, force=force)
except NEFFrameAlreadyExistsException as e:
    ...  # existing handler unchanged
```

`_extract_args_and_selectors_or_exit_error` is never called in the bulk branch so needs no change.

### 6. Update docstring examples

Add a `--bulk` section to the existing `rename()` docstring example block.

---

## Files to change

| File | Change |
|------|--------|
| `src/nef_pipelines/tools/frames/rename.py` | Mode.bulk, --bulk flag, `_parse_bulk_triples_or_exit_error`, `_split_on_unescaped_comma`, rename() bulk branch, docstring |
| `src/nef_pipelines/tests/frames/test_rename.py` | New tests for bulk mode (happy path, escaping, error cases) |

`util.py` and `structures.py` — **no changes needed** (reuse existing functions as-is).

---

## Tests to add

- `test_rename_bulk_basic` — two triples, different selectors and old/new values, verify both frames renamed
- `test_rename_bulk_wildcard_selector` — selector with `*` matches multiple frames
- `test_rename_bulk_escaped_slash` — OLD value containing `\/`, verify unescaping
- `test_rename_bulk_trailing_slash` — triple with trailing `/` parses identically to without
- `test_rename_bulk_comma_separated` — two triples in one arg: `S1=/A/B/,S2=/C/D/`
- `test_rename_bulk_concatenated` — two triples joined via trailing slash: `S1=/A/B/S2=/C/D/`
- `test_rename_bulk_with_target` — `--bulk --target namespace` operates on namespace component
- `test_rename_bulk_missing_equals_error` — chunk without `=` → exit error
- `test_rename_bulk_missing_slash_separator_error` — `SELECTOR=/OLD` (no closing `/`) → exit error
- `test_rename_bulk_bad_replacement_start_error` — `SELECTOR=OLD/NEW` (no leading `/`) → exit error
- `test_rename_bulk_no_frames_error` — selector matches nothing → exit error (reuses existing path)

---

## Verification

```bash
# run rename tests
nefl test frames/test_rename    # all existing 31 + new bulk tests pass

# smoke test
echo "..." | nef frames rename --bulk "*hnco*=/k_ubi/k_ubiquitin/"
```
