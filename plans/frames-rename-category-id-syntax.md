# Plan: Enhance `frames rename` to support category and ID changes

## Context

The `frames rename` command currently can rename the ID part of a frame name (the part after the category prefix) or change the category (via `--rename-category`), but cannot change both in a single operation or make a frame into a singleton (empty ID).

This enhancement adds a new syntax that supports changing category and/or ID in a single operation using a `category.id` format:

- `selection new_category.new_id` - change both
- `selection category.*` - change category only, keep existing ID
- `selection *.id` - keep category, change ID only
- `selection *.` - keep category, make singleton (empty ID)
- `selection .*` - **illegal** (empty category not allowed)

Pairs can be separated by spaces, `=`, or commas. Escape special chars (`.`, `=`, `,`) with `\`, and use `\\` for literal backslash.

**Keep backward compatibility:** The existing simple rename syntax `old new` (without `.`) continues to work as before, changing only the ID part.

## Files to modify

### 1. `src/nef_pipelines/tools/frames/rename.py`

**a) Add escape/unescape functions** (after imports, before command):

```python
def _unescape_rename_arg(arg: str) -> str:
    """Unescape \., \=, \,, and \\ in rename arguments."""
    result = []
    i = 0
    while i < len(arg):
        if arg[i] == '\\' and i + 1 < len(arg):
            next_char = arg[i + 1]
            if next_char in '.=,\\':
                result.append(next_char)
                i += 2
                continue
        result.append(arg[i])
        i += 1
    return ''.join(result)

def _split_rename_pairs(args: List[str]) -> List[tuple[str, str]]:
    """
    Split arguments into (old, new) pairs, handling =, comma, and space separators.
    Examples:
      ['old1', 'new1', 'old2', 'new2'] → [('old1', 'new1'), ('old2', 'new2')]
      ['old1=new1', 'old2=new2'] → [('old1', 'new1'), ('old2', 'new2')]
      ['old1,new1,old2,new2'] → [('old1', 'new1'), ('old2', 'new2')]
    """
    # First expand comma-separated args
    expanded = parse_comma_separated_options(args)

    # Then check for = separator in each arg
    pairs = []
    i = 0
    while i < len(expanded):
        arg = expanded[i]
        if '=' in arg and '\\=' not in arg:  # Has unescaped =
            # Split on first unescaped =
            parts = arg.split('=', 1)
            if len(parts) == 2:
                pairs.append((_unescape_rename_arg(parts[0]), _unescape_rename_arg(parts[1])))
                i += 1
                continue

        # No =, treat as space-separated pair
        if i + 1 >= len(expanded):
            # Odd number of args - error will be caught later
            return [(expanded[i], '')]

        pairs.append((_unescape_rename_arg(expanded[i]), _unescape_rename_arg(expanded[i + 1])))
        i += 2

    return pairs
```

**b) Add category.id parsing** (after escape functions):

```python
def _parse_category_id_spec(spec: str, current_category: str, current_id: str) -> tuple[str, str]:
    """
    Parse a category.id specification.
    Returns (new_category, new_id).

    Formats:
      'category.id' → ('category', 'id')
      'category.*' → ('category', current_id)
      '*.id' → (current_category, 'id')
      '*.' → (current_category, '')  # singleton
      '.*' → ERROR (empty category illegal)
      'simple' → (current_category, 'simple')  # backward compat
    """
    # Check for illegal pattern first
    if spec.startswith('.'):
        exit_error(f"illegal rename pattern '{spec}': category cannot be empty (pattern .* or .name)")

    # No dot = simple rename (backward compat)
    if '.' not in spec:
        return (current_category, spec)

    # Split on first unescaped dot
    parts = spec.split('.', 1)
    if len(parts) != 2:
        exit_error(f"invalid category.id spec: '{spec}'")

    category_part, id_part = parts

    # Resolve wildcards
    new_category = current_category if category_part == '*' else category_part
    new_id = current_id if id_part == '*' else id_part

    # Validate
    if not new_category:
        exit_error(f"category cannot be empty in spec '{spec}'")

    # Empty id_part (e.g., "category.") makes a singleton
    # id_part == '' is valid (singleton)

    return (new_category, new_id)
```

**c) Update `rename()` command function**:

Replace lines 58-66 (argument parsing) with:

```python
    pairs = _split_rename_pairs(old_new_names)

    # Validate pairs
    if any(new == '' for _, new in pairs):
        # Check if it's actually an odd number of args error
        all_args = parse_comma_separated_options(old_new_names)
        if len(all_args) % 2 != 0:
            _exit_renames_not_pairs(all_args)
```

Replace lines 105-141 (the renaming logic inside the loop) with:

```python
            if len(new_name.split()) > 1:
                _exit_spaces_in_new_name(new_name)

            # Parse the new name as category.id spec
            current_id = target_frame.name[len(target_frame.category):].lstrip('_')
            new_category, new_id = _parse_category_id_spec(
                new_name,
                target_frame.category,
                current_id
            )

            # Special case: --rename-category overrides (backward compat)
            if rename_category:
                # Old behavior: new_name is treated as category only
                new_category = new_name
                new_id = current_id

            # Build full name
            if new_id:
                new_full_name = f"{new_category}_{new_id}"
            else:
                # Singleton (empty ID)
                new_full_name = new_category

            # Check for clashes
            if new_full_name in entry.frame_dict.keys() and not force:
                existing_frame = entry.get_saveframe_by_name(new_full_name)
                if existing_frame is target_frame:
                    continue  # Renaming to itself - no-op
                _exit_clashing_frame_name(new_full_name, entry)

            if new_full_name in entry.frame_dict.keys() and force:
                frame_to_remove = entry.get_saveframe_by_name(new_full_name)
                entry.remove_saveframe(frame_to_remove)

            # Apply rename
            target_frame.category = new_category
            target_frame.name = new_full_name
```

**d) Update docstring** (line 53):

```python
    """- rename frames (change category and/or ID)

    Syntax: <selection> <new_spec> [<selection> <new_spec> ...]

    <new_spec> formats:
      category.id   - change both category and ID
      category.*    - change category, keep current ID
      *.id          - keep category, change ID
      *.            - keep category, make singleton (empty ID)
      simple        - keep category, change ID (backward compat)

    Pairs can be separated by spaces, =, or commas:
      old new                   (space)
      old=new                   (equals)
      old1,new1,old2,new2       (comma)

    Escape special chars with \\:
      \\. \\= \\, \\\\
    """
```

### 2. `src/nef_pipelines/tests/frames/test_rename.py`

Add new test cases:

```python
def test_rename_category_and_id():
    """Test changing both category and ID with category.id syntax"""
    OLD_FRAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_SPEC = "nef_test.my_spectrum"
    NEW_FRAME = "nef_test_my_spectrum"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, OLD_FRAME, NEW_SPEC])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    assert NEW_FRAME in frame_names
    assert OLD_FRAME not in frame_names
    assert entry.frame_dict[NEW_FRAME].category == "nef_test"


def test_rename_category_wildcard():
    """Test changing only category with category.* syntax"""
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_SPEC = "nef_test.*"
    OLD_FRAME = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME = f"nef_test_{SEARCHED_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, SEARCHED_NAME, NEW_SPEC])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    assert NEW_FRAME in frame_names
    assert OLD_FRAME not in frame_names


def test_rename_id_wildcard():
    """Test changing only ID with *.id syntax"""
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_SPEC = "*.new_id"
    OLD_FRAME = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME = f"{CATEGORY}_new_id"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, SEARCHED_NAME, NEW_SPEC])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    assert NEW_FRAME in frame_names
    assert OLD_FRAME not in frame_names


def test_rename_to_singleton():
    """Test making a singleton with *. syntax"""
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_SPEC = "*."
    OLD_FRAME = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME = CATEGORY  # No ID = singleton

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, SEARCHED_NAME, NEW_SPEC])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    assert NEW_FRAME in frame_names
    assert OLD_FRAME not in frame_names


def test_rename_illegal_empty_category():
    """Test that .* pattern is rejected"""
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_SPEC = ".*"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, SEARCHED_NAME, NEW_SPEC], expected_exit_code=EXIT_ERROR
    )

    assert "category cannot be empty" in result.stdout


def test_rename_equals_separator():
    """Test using = as separator"""
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_NAME = "test_id"
    OLD_FRAME = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, f"{SEARCHED_NAME}={NEW_NAME}"])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    assert NEW_FRAME in frame_names
    assert OLD_FRAME not in frame_names


def test_rename_escaped_dot():
    """Test escaping . in names"""
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_NAME = "my\\.id"  # Escaped dot
    OLD_FRAME = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME = f"{CATEGORY}_my.id"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, SEARCHED_NAME, NEW_NAME])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    assert NEW_FRAME in frame_names
    assert OLD_FRAME not in frame_names
```

### 3. Update help text

The existing `--rename-category` flag should be marked as **deprecated but maintained** for backward compatibility. Update its help text:

```python
rename_category: bool = typer.Option(
    False,
    help="[DEPRECATED] change the category (use 'category.*' syntax instead)"
)
```

## Verification

```bash
# Run existing tests (should all still pass - backward compat)
python -m pytest src/nef_pipelines/tests/frames/test_rename.py -v

# Run new tests
python -m pytest src/nef_pipelines/tests/frames/test_rename.py::test_rename_category_and_id -v
python -m pytest src/nef_pipelines/tests/frames/test_rename.py::test_rename_category_wildcard -v
python -m pytest src/nef_pipelines/tests/frames/test_rename.py::test_rename_id_wildcard -v
python -m pytest src/nef_pipelines/tests/frames/test_rename.py::test_rename_to_singleton -v
python -m pytest src/nef_pipelines/tests/frames/test_rename.py::test_rename_illegal_empty_category -v
python -m pytest src/nef_pipelines/tests/frames/test_rename.py::test_rename_equals_separator -v
python -m pytest src/nef_pipelines/tests/frames/test_rename.py::test_rename_escaped_dot -v

# Manual testing
echo "data_test save_nef_chemical_shift_list_a ... save_" | \
  nef frames rename "shift_list_a" "nef_shifts.my_list"
# Should produce: save_nef_shifts_my_list

echo "data_test save_nef_chemical_shift_list_a ... save_" | \
  nef frames rename "shift_list_a" "nef_shifts.*"
# Should produce: save_nef_shifts_a (category changed, ID kept)

echo "data_test save_nef_chemical_shift_list_a ... save_" | \
  nef frames rename "shift_list_a" "nef_shifts."
# Should produce: save_nef_shifts (singleton)
```

## Edge cases handled

1. **Backward compatibility**: Simple `old new` syntax still works (no dot = ID-only rename)
2. **Escaping**: `\.` `\=` `\,` `\\` work correctly
3. **Illegal patterns**: `.*` and `.name` rejected with clear error
4. **Separators**: space, `=`, comma all work
5. **Wildcards**: `*` in category or ID position means "keep current"
6. **Singletons**: Empty ID (`*.` or `category.`) creates singleton frame
7. **--rename-category**: Still works for backward compat (overrides dot syntax)
8. **--replace flag**: Remains unchanged (operates on ID part only)
