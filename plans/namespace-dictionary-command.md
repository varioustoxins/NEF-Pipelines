# Plan: `nef namespace dictionary` command

**STATUS: NOT IMPLEMENTED**

**Note**: `nef namespace catalog` exists but is NOT this command. Catalog simply lists the hardcoded registered namespaces (program + use), while this plan proposed auto-generating full mmCIF DDL2 dictionaries by analyzing actual NEF files and inferring data types.

---

## Context

NEF files use namespaces (e.g. `nef`, `ccpn`, `amber`) to prefix categories and tags. Some namespaces (like `ccpn`, and the relaxation format) have no formal mmCIF dictionary documenting their schema. This tool will analyse NEF files and auto-generate a formal mmCIF DDL2-style dictionary for a specified namespace, making it possible to document and validate custom namespace extensions.

## What the tool does

Given one or more NEF files and a target namespace, it:
1. Scans all saveframes, loops, and tags
2. Identifies everything belonging to the target namespace
3. Infers data types from actual values
4. Outputs a formal mmCIF dictionary to stdout

## Output format

Matches the structure of `mmcif_nmr-star.dic` (138K-line real dictionary at `src/nef_pipelines/data/mmcif_nmr-star.dic`):

- `data_` block header with `_datablock`, `_dictionary` tags
- `save_<Category>` blocks for each category (with `_category.description`, `_category.id`, `_category.mandatory_code`, `_category_key.name`)
- `save__<Category>.<tag>` blocks for each item (with `_item_description.description`, `_item.name`, `_item.category_id`, `_item.mandatory_code`, `_item_type.code`, `_item_examples.case`)

## Two kinds of namespace presence

1. **Owned categories** - the namespace owns the category (e.g. `ccpn_substance`, `ccpn_spectrum_dimension`). These get full category + item definitions.
2. **Extension tags** - namespace-prefixed tags on another namespace's category (e.g. `_nef_peak.ccpn_figure_of_merit`). These get item definitions only, with a comment noting they extend another category.

## Files to create/modify

### New files
| File | Purpose |
|------|---------|
| `src/nef_pipelines/lib/dictionary_lib.py` | Core logic: data collection, type inference, formatting |
| `src/nef_pipelines/tools/namespace/dictionary.py` | CLI command with `pipe()` separation |
| `src/nef_pipelines/tests/namespace/test_dictionary.py` | Tests |
| `src/nef_pipelines/tests/namespace/test_data/dictionary_test.nef` | Test NEF data |

### Modified files
| File | Change |
|------|--------|
| `src/nef_pipelines/tools/namespace/__init__.py` | Add `from nef_pipelines.tools.namespace import dictionary` import |

## Reusable functions (with paths)

- `read_entry_from_file_or_stdin_or_exit_error(file: Path) -> Entry` - `lib/nef_lib.py:778`
- `get_namespace(value, node_type, parent_namespace, known_namespaces)` - `lib/namespace_lib.py:79`
- `collect_namespaces_from_frames(frames)` - `lib/namespace_lib.py:201`
- `EntryPart` enum (Saveframe, Loop, FrameTag, LoopTag) - `lib/namespace_lib.py:67`
- `is_int(value)`, `is_float(value)` - `lib/util.py:517,537`
- `exit_error()` - `lib/util.py`
- `read_test_data()`, `run_and_report()`, `assert_lines_match()` - `lib/test_lib.py`

## Implementation details

### CLI signature
```
nef namespace dictionary <NAMESPACE> [NEF-FILES...] [-i FILE] [--version 1.0.0] [--description TEXT] [--max-examples 5] [--name DICT_NAME]
```

### Type inference algorithm
1. Filter out null values (`.` and `''`)
2. All `true`/`false` -> `yes_no`
3. All pass `is_int()` -> `int`
4. All pass `is_float()` -> `float`
5. Contains whitespace/newlines -> `text`
6. Otherwise -> `code`

### Mandatory detection
- Tag never has `.` across all files -> `mandatory_code yes`
- Otherwise -> `mandatory_code no`

### Category key heuristic
Priority: column named `index` > `ordinal` > `id` > first column

### Namespace detection for unregistered namespaces
`get_namespace()` accepts a `known_namespaces` parameter. We'll pass a dict that includes the target namespace alongside `REGISTERED_NAMESPACES` so that unregistered namespaces are correctly detected.

## Implementation order

1. `dictionary_lib.py` - data structures (`TagInfo`, `CategoryInfo`, `StarType`)
2. `dictionary_lib.py` - `collect_dictionary_data()` scanning logic
3. `dictionary_lib.py` - type inference functions
4. `dictionary_lib.py` - `format_dictionary()` STAR output formatter
5. `dictionary.py` - CLI command
6. `__init__.py` - register import
7. Test data file and tests

## Open items (user feedback)

1. **Multiple input NEF files** - supported via positional args, all tags merged across files
2. **Reuse definitions from existing dictionaries** - the tool should accept existing mmCIF dictionaries (e.g. the core NEF dictionary) via a `--dictionary` option. Items already defined in a loaded dictionary should be skipped (not re-emitted). Type definitions can be inherited. Assumes pynmrstar has been extended to read dictionaries.
3. **Dictionary parser** - assume pynmrstar can parse .dic files. Need to explore the API.

## Verification

1. Run against `namespace_test.nef` for `custom` namespace: `nef namespace dictionary custom -i src/nef_pipelines/tests/namespace/test_data/namespace_test.nef`
2. Run against `Sec5Part4.nef` for `ccpn` namespace: `nef namespace dictionary ccpn /Users/garythompson/Sec5Part4.nef`
3. Run against multiple large files to test merging
4. Verify output parses as valid STAR (feed back into pynmrstar)
5. Run existing tests to check no regressions: `cd nef_pipelines && python -m pytest src/nef_pipelines/tests/namespace/`
6. Run new tests
