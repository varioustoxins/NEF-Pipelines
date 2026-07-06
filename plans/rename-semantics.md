# Improving frames rename

**STATUS: PARTIALLY IMPLEMENTED** ⚠️

**What was implemented:**
- ✅ `RenameTarget.type` added to enum (namespace, category, identity, type)
- ✅ `--target` flag exists and works
- ✅ `--singleton` flag exists
- ✅ `--delete` flag exists

**What was NOT implemented (breaking changes):**
- ❌ Default behavior not changed to substring replace
- ❌ `--replace` flag not removed (plan wanted this deleted as redundant)
- ❌ Semantic swap not completed (default and --replace meanings still swapped from plan)
- ❌ Arg order not changed (still `SELECTOR NEW` instead of `NEW SELECTOR...`)

**Current state**: The infrastructure exists (--target with type support), but the proposed breaking CLI change to swap default/--replace semantics was not implemented. The command works but with the "awkward" semantics the plan identified.

---

The semantics of frames rename don't work clearly or well.

## Framecode components (canonical EBNF vocabulary)

```
framecode  ::= category ["_" identity] [qualifier]
category   ::= namespace "_" type
qualifier  ::= index | suffix
```

Independently settable components: **namespace**, **type**, **category** (= namespace + type), **identity**.
Future: **index**, **suffix**, complete **framecode**.

---

## Current vs proposed semantics

| | Default (no flag) | `--replace` flag |
|---|---|---|
| **Plan (intended)** | substring replace in identity | set a whole component |
| **Code (current)** | set whole identity (pair mode) | substring replace |

The meanings are **swapped**. The plan's design is better:
- Substring-default composes cleanly across multiple frames (each frame gets a unique result).
- Whole-identity-default clashes when a selector matches multiple frames of the same type
  (see `test_error_multiple_frames_matched` — documented but awkward).

**Decision: adopt plan's semantics.** This is a breaking CLI change; justified because the
command is still in development.

---

## Proposed syntax

### Default — substring replace in identity

```
frames rename OLD NEW [SELECTOR...]
```

Replace OLD with NEW in the identity of every matched frame.
If no selectors given, default selector is `*` (all frames); frames whose identity doesn't
contain OLD are unaffected.

```
frames rename k_ubi k_ubiquitin                    # selector = * (all frames)
frames rename k_ubi k_ubiquitin *hnco* *hnca*      # explicit selectors
```

This subsumes the current `--replace` flag (which can be removed).

### `--target COMPONENT` — set a whole component

```
frames rename --target identity  NEW [SELECTOR...]   # set identity
frames rename --target type      NEW [SELECTOR...]   # set type (non-namespace part of category)
frames rename --target category  NEW [SELECTOR...]   # set namespace + type together
frames rename --target namespace NEW [SELECTOR...]   # set namespace only
```

`--target type` and `--target namespace` are complementary: type changes the data kind while
keeping the namespace; namespace changes ownership while keeping the data kind.

Sets the named component to NEW; other components are inherited.

```
# nef_nmr_spectrum_hsqc`1` → ccpn_nmr_spectrum_hsqc`1`
frames rename --target category ccpn_nmr_spectrum nef_nmr_spectrum_hsqc`1`

# nef_nmr_spectrum_hsqc → nef_relaxation_hsqc  (type only)
frames rename --target type relaxation nef_nmr_spectrum_hsqc

# nef_nmr_spectrum_hsqc → ccpn_nmr_spectrum_hsqc  (namespace only)
frames rename --target namespace ccpn nef_nmr_spectrum_hsqc
```

Note: arg order is `NEW SELECTOR...` (NEW first), not `SELECTOR NEW` as currently.

### `--delete` — delete substring from identity

```
frames rename --delete SUBSTR [SELECTOR...]
```

Unchanged from current behaviour. Default selector is `*` (consistent with default mode).

### `--singleton` — strip identity

```
frames rename --singleton [SELECTOR...]
```

Removes identity from matched frames. Incompatible with `--target category/namespace`.

---

## Changes required to implement

`pipe()` is **unchanged** — it takes `List[Tuple[Saveframe, SaveframeNameParts]]` and remains
a clean programmatic API. All changes are in the CLI layer.

1. **Remove `--replace` flag** — default becomes substring replace; `--replace` is redundant.
2. **Add `RenameTarget.type`** to the enum alongside identity/category/namespace.
3. **Change positional arg parsing** in `_build_rename_pairs`:
   - Default (substring): first two positionals are OLD/NEW, remaining are selectors; no selectors → `*`.
   - `--target`: first positional is NEW, remaining are selectors; no selectors → `*`.
   - `--delete`: unchanged (SUBSTR is first positional, remaining are selectors; no selectors → `*`).
4. **Update `--target type` branch** in `_build_rename_pairs`:
   `SaveframeNameParts(type=new_value)` — namespace=None (inherit), identity=None (inherit).
5. **Update `--target` arg order**: currently `SELECTOR NEW`; new form `NEW SELECTOR...`.
6. **Default selector `*`** replaces OLD-as-selector in current `--replace` mode and SUBSTR-as-selector in `--delete`.
7. **Update help text and docstring examples**.
8. **Update tests**: `test_rename_pattern_match`, `test_rename_replace*`, `test_rename_delete*`,
   `test_rename_multiple_matched`.

---

## Known selector constraints (from prior work)

- `.` is taken by `frame.loop:tag` syntax — can't use `category.identity` selector form (Phase 4 dropped).
- Commas are ambiguous with `frame.loop:tag` — use `/` or space-separated selectors.
- `--category` and `--exact` filters compose with all modes.

---

## Future (not in scope now)

- `--index N|+N|-N` arithmetic (Phase 5 in `frames-rename-none-inherit-refactor.md`).
- `--target suffix` / `--target index` for qualifier components.
- `--target framecode` for complete framecode replacement.
