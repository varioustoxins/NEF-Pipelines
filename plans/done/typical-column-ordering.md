# Implementation Plan: TYPICAL Column Ordering for NMR/NEF Data

## Context

The `reorder` command currently supports CUSTOM (user-specified) and ALPHABETICAL ordering policies. However, NMR/NEF data has domain-specific column ordering conventions that improve readability and align with scientific practice. The TYPICAL ordering policy will automatically arrange columns in a scientifically conventional order commonly used in NMR spectroscopy.

**Why this is needed:**
- NMR data often has columns with numeric suffixes (e.g., `chain_code_1`, `chain_code_2`) representing multiple dimensions or assignments
- Standard ordering groups related columns together and follows measurement conventions
- Manual reordering is tedious and error-prone for large peak lists

**Ordering Groups**

The ordering should be in group as define below

# index                         index group
# combination_id                |
# serial                        |
# *_id                          |
# [                              chain_residue_atom group
#   chain_code_*.               |
#   sequence_code_*.            |
#   residue_name_*.             |
#   atom_name_*.                |
#   isotope_number_*.           |
# ] grouped by index            |
#   in numerical order          |
#  *value* *_uncertainty/error  measurement group
#  position                     |
#  volume                       |
#  height                       |
# *                             other group [anything not covered]
# *annotation*                  comment group
# *comment*                     |

These should be defined in structures in the tool at top level so they are easily refined

**Target behavior** (from GB1_T1_Relaxation_series_fitted.nef example):
```
# Fixed position columns
index, peak_id, serial, combination_id

# Measurements with uncertainties (paired)
volume, volume_uncertainty
height, height_uncertainty

# Dimensional groups (sorted by suffix number: _1, _2, _3...)
Within each suffix group, template order:
  position_{n}, position_uncertainty_{n}
  chain_code_{n}
  sequence_code_{n}
  residue_name_{n}
  atom_name_{n}
  isotope_number_{n}

# Remaining columns (preserve original order)
ccpn_figure_of_merit, ccpn_linked_integral, etc.

# Comments last
ccpn_comment, ccpn_annotation, any column with "comment" in name
```

## Algorithm

Add `_compute_typical_order(loop: Loop) -> List[str]` in reorder.py:

1. **Extract numeric suffix** from each column name:
   - Pattern: `^(.+?)_(\d+)$` (e.g., "chain_code_1" → base="chain_code", suffix=1)
   - Store mapping: `{col_name: (base, suffix_num)}` or `{col_name: (col_name, None)}`

2. **Categorize all columns** into buckets:
   - **fixed**: `index`, `serial`, `combination_id`, `peak_id` (exact matches, order preserved)
   - **measurements**: Column pairs matching `(base, f"{base}_uncertainty")` or `(base, f"{base}_error")`
     - Detect: if `col` exists and `col_uncertainty` OR `col_error` exists, pair them
     - Order: value first, then uncertainty/error
   - **dimensional_groups**: Columns with numeric suffixes, grouped by suffix
     - Group by suffix number, sort suffix numbers ascending
     - Within each suffix group, use template order:
       ```python
       TEMPLATE = [
           "position", "position_uncertainty",
           "chain_code", "sequence_code", "residue_name",
           "atom_name", "isotope_number"
       ]
       ```
     - For each suffix: place template columns that exist, then remaining columns in original order
   - **comments**: Any column containing "comment" (case-insensitive)
   - **remaining**: Everything else not categorized above

3. **Assemble final order**:
   ```python
   result = []
   result.extend(fixed)
   result.extend(flatten(measurement_pairs))  # [val1, unc1, val2, unc2, ...]
   for suffix_num in sorted(suffix_numbers):
       result.extend(dimensional_groups[suffix_num])
   result.extend(remaining)
   result.extend(comments)
   return result
   ```

## Implementation Details

### File: reorder.py

**Enable TYPICAL policy:**
```python
class ColumnOrderPolicy(LowercaseStrEnum):
    CUSTOM = auto()
    ALPHABETICAL = auto()
    TYPICAL = auto()  # Remove comment
```

**Remove TODO block** (lines 36-54) and replace with implementation.

**Add to `_compute_reorders()` function** (after line 156):
```python
elif policy == ColumnOrderPolicy.TYPICAL:
    new_order = _compute_typical_order(loop)
```

**New function** `_compute_typical_order(loop: Loop) -> List[str]`:
- Implement the algorithm above
- Use regex: `import re; re.match(r'^(.+?)_(\d+)$', col_name)`
- Fixed columns list: `["index", "serial", "combination_id", "peak_id"]`
- Template order list as shown above
- Preserve original relative order within each category

### Helper Functions

```python
def _extract_suffix(col_name: str) -> Tuple[str, Optional[int]]:
    """Extract base name and numeric suffix from column.

    Returns (base, suffix_num) or (col_name, None) if no suffix.
    Example: "chain_code_1" → ("chain_code", 1)
    """
    match = re.match(r'^(.+?)_(\d+)$', col_name)
    if match:
        return (match.group(1), int(match.group(2)))
    return (col_name, None)

def _find_measurement_pairs(columns: List[str]) -> Tuple[List[Tuple[str, str]], Set[str]]:
    """Find value/uncertainty pairs.

    Returns (pairs, used_cols) where pairs is [(val, unc), ...] and used_cols
    is a set of all columns consumed into pairs.
    """
    # Implementation

def _group_by_suffix(columns: List[str], exclude: Set[str]) -> Dict[int, List[str]]:
    """Group columns by numeric suffix, excluding already-categorized columns.

    Returns {suffix_num: [col1, col2, ...]}
    """
    # Implementation
```

## Integration Point

The function integrates into the existing pipeline at stage 2 (compute reorders) in the `_compute_reorders()` function. The CLI already handles validation, so `_compute_typical_order` can assume:
- Loop exists and has tags
- No further validation needed

## Test Strategy

### New test file: test_reorder_typical.py

**Test cases:**

1. **test_typical_fixed_columns_first**
   - Input loop with: peak_id, chain_code, index, volume
   - Expected: index, peak_id, chain_code, volume

2. **test_typical_measurement_pairs**
   - Input: volume, height, volume_uncertainty, height_uncertainty, index
   - Expected: index, volume, volume_uncertainty, height, height_uncertainty

3. **test_typical_dimensional_groups**
   - Input: chain_code_2, chain_code_1, sequence_code_1, sequence_code_2, index
   - Expected: index, chain_code_1, sequence_code_1, chain_code_2, sequence_code_2

4. **test_typical_template_order_within_suffix**
   - Input: atom_name_1, chain_code_1, position_1, residue_name_1, sequence_code_1
   - Expected: position_1, chain_code_1, sequence_code_1, residue_name_1, atom_name_1

5. **test_typical_comments_last**
   - Input: value, ccpn_comment, height, annotation
   - Expected: value, height, annotation, ccpn_comment

6. **test_typical_full_peak_loop** (integration test)
   - Use actual peak loop structure from GB1_T1_Relaxation_series_fitted.nef
   - Scramble column order
   - Verify TYPICAL produces expected NEF-standard order

7. **test_typical_with_selector**
   - Verify --policy typical works with frame.loop selectors
   - Multiple loops, only selected ones reordered

### Test data files needed:
- `typical_peak_loop_scrambled.nef` - Full peak loop with randomized column order
- Use existing chemical shift test data for simpler cases

### Manual verification:
```bash
# Apply to development file
nef columns reorder --policy typical \
  --selector "nef_nmr_spectrum_T1_1_8ms\`1\`.nef_peak" \
  --in development_data/GB1_T1_Relaxation_series_fitted.nef

# Verify column order in output matches expected pattern
```

## Files to Modify

1. `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/columns/reorder.py`
   - Enable TYPICAL in ColumnOrderPolicy enum
   - Remove TODO comment block
   - Add elif branch in _compute_reorders
   - Implement _compute_typical_order and helper functions
   - Add regex import

2. `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/columns/test_reorder_typical.py` (new file)
   - Implement 7 test cases listed above
   - Follow CLAUDE.md testing guidelines (EXPECTED_ constants, assert_lines_match, path_in_test_data)

3. Test data (new files in test_data/columns/):
   - `typical_peak_loop_scrambled.nef`
   - May reuse existing test data for simpler cases

## Verification Steps

1. **Run tests**: `nefl test tests/columns/test_reorder_typical.py`
2. **Manual verification** with development file as shown above
3. **Edge cases**:
   - Empty loop (should return empty list)
   - Loop with no matches (all columns → remaining category)
   - Mixed suffixes (_1, _3, _5 - verify sorted correctly)
   - Columns with suffix but not in template (verify original order preserved within suffix group)

## Open Questions / Design Decisions

1. **Measurement pairing priority**: If a column could be either a measurement or part of a dimensional group (e.g., `position_1` pairs with `position_uncertainty_1`), should the pair take priority?
   - **Decision**: Pair within dimensional groups - `position_1` and `position_uncertainty_1` stay in the `_1` group and follow template order
**COMMENT** yes these stay together
   -
2. **Comment detection**: Case-sensitive or case-insensitive for "comment" in column name?
   - **Decision**: Case-insensitive (`"comment" in col_name.lower()`)
**COMMENT** generaly everying is lower snake case so dont worry keep it case sensitive

3. **Unknown fixed columns**: What if new fixed columns appear (e.g., `series_id`)?
   - **Decision**: Only the 4 listed fixed columns get special treatment; unknown columns fall through to remaining category
-**COMMENT** just go with the ones we have in constants i can add extras laif ter if needed

4. **Uncertainty vs Error**: Both `_uncertainty` and `_error` suffixes should pair?
   - **Decision**: Yes, check for both patterns
**COMMENT** yes

## Implementation Questions (Wildcards and Patterns)

Based on the updated specification with wildcards, need clarification on:

1. **Index group wildcard `*_id`** (line 18):
   - Should ANY column ending in `_id` be in the index group (e.g., `series_id`, `experiment_id`, `spectrum_id`)?
   - Or should we stick to the explicit list: `index`, `serial`, `combination_id`, `peak_id`?
   - Current implementation: Uses explicit list only
**COMMENT** yes anything that matches the wild card?

2. **Measurement group wildcard `*value*`** (line 27):
   - Should ANY column containing "value" be in the measurement group (e.g., `r_value`, `fitted_value`, `initial_value`)?
   - Or should we stick to the explicit list: `value`, `position`, `volume`, `height`?
   - Current implementation: Uses explicit list only
**COMMENT** Yes anything that matches the wild card.

3. **Comment group wildcards `*annotation*` and `*comment*`** (lines 32-33):
   - Current implementation only checks for "comment" (case-insensitive)
   - Should we also match columns containing "annotation"?
   - Should these be case-sensitive or case-insensitive?
   - Examples: `ccpn_annotation`, `user_comment`, `ANNOTATION_TEXT`
**COMMENT** Yes anything that matches the wild card.
   -
4. **Pairing wildcards `*_uncertainty/error`**:
   - Current implementation pairs ONLY columns in TYPICAL_MEASUREMENT_GROUP with their _uncertainty/_error
   - Should we pair ANY column that has a matching _uncertainty or _error suffix?
   - Example: If we have `r_value` and `r_value_uncertainty`, should they be paired even though `r_value` isn't in TYPICAL_MEASUREMENT_GROUP?
**COMMENT** Yes if the *_value was matched, so  `r_value` and `r_value_uncertainty` would go at the end of the
            measurement group together

5. **Ordering within groups**:
   - For wildcard-matched columns (not in the explicit lists), what order should they appear?
   - Alphabetical? Original order? Order they're discovered?
   - Example: If `series_id`, `spectrum_id`, `peak_id` are all matched by `*_id`, what order?

**COMMENT**  the order they are found in the file the user can always do a double-sort, first on alphabetical and then
             on typical, if they wanted them sorted alphabetically within the group.
