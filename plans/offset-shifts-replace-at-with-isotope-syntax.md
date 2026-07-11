# Plan: Tidy Up Shifts Offset - Replace @ Syntax with Isotope Library

## Context

The `nef shifts offset` command currently uses `@` prefix syntax to distinguish between exact atom matching and element-type matching. This is being replaced with a more intuitive isotope-based syntax that leverages the existing isotope library (`lib/isotope_lib.py`).

**Current behavior:**
- `@CA=+0.07` → exact match for atom named "CA"
- `C=+0.07` → element-type match for all carbon atoms (CA, CB, CG, etc.)

**New behavior:**
- `13C=+0.07` → isotope-specific match for 13C atoms only
- `C=+0.07` → element-type match for all carbon atoms (any isotope)
- `15N=-0.44` → isotope-specific match for 15N atoms only

This change makes the syntax more intuitive and consistent with NMR conventions, where isotope codes (`13C`, `15N`, `1H`) are the standard way to specify nucleus types.

**Why:** The `@` prefix was confusing and non-standard. Using isotope codes aligns with established NMR notation and makes the command more self-documenting. The isotope library already exists and provides robust parsing for both standard (`13C`) and alternate (`C13`) formats.

**How to apply:** Update the offset command implementation to use isotope library for parsing, match against NEF `element` and `isotope_number` columns, and add comprehensive tests to ensure correct behavior.

## Critical Files to Modify

1. **`/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/shifts/offset.py`**
   - Update `_parse_specs()` to use isotope library instead of `@` prefix
   - Update `_matches()` to check isotope_number when isotope code is provided
   - Add isotope_number index extraction from loop data
   - Import and use `isotope_lib.convert_isotopes()` and related utilities

2. **`/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/shifts/test_offset.py`** (NEW FILE)
   - Create comprehensive test suite for offset command
   - Test element-type matching (bare C, N, H)
   - Test isotope-specific matching (13C, 15N, 1H)
   - Test mixed specs with override behavior
   - Test both formats (13C and C13) supported by isotope library
   - Test wildcard patterns
   - Test error cases (invalid specs, missing values, etc.)

3. **`/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/shifts/test_data/`** (NEW DIRECTORY)
   - Create test NEF files with chemical shifts for various atom types and isotopes
   - Include edge cases: missing values, different isotopes, wildcard matches

## Implementation Plan

### Step 1: Update offset.py Implementation

**Import isotope library:**
```python
from nef_pipelines.lib.isotope_lib import convert_isotopes, ATOM_TO_ISOTOPE
```

**Update `_parse_specs()` function:**
- Remove `@` prefix logic (lines 55-58)
- Add isotope code detection using `convert_isotopes()`
- For isotope codes (e.g., `13C`, `15N`):
  - Extract element symbol and isotope number
  - Return triple: `(element, isotope_number, value)`
- For bare element names (e.g., `C`, `N`, `H`):
  - Return triple: `(element, None, value)` where `None` means any isotope
- Return type changes from `List[Tuple[str, bool, float]]` to `List[Tuple[str, Optional[int], float]]`

**Update `_matches()` function signature and logic:**
- Change from `_matches(atom, pattern, exact)` to `_matches(atom, element, isotope_num, element_col, isotope_col)`
- Match on element first (fnmatch pattern for bare names, exact for isotopes)
- If isotope_num is provided (not None), also verify isotope_number column matches
- Return True only if both element and isotope (when specified) match

**Update `offset()` command function:**
- Extract `element_idx` and `isotope_idx` from loop tags (lines 109-110)
- Update matching logic (lines 116-126) to pass element and isotope columns to `_matches()`
- Preserve override behavior: isotope-specific specs override element-type specs

**Update help text:**
- Already updated to mention isotope codes
- Fix typo: "hte correct ayom type" → "the correct atom type"

### Step 2: Create Test Infrastructure

**Create test data directory:**
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/shifts/test_data/`
- Create minimal NEF file with diverse shifts: different atoms (C, CA, CB, N, H), different isotopes (13C, 15N, 1H)
- Reuse pattern from `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/test_data/ubiquitin_short_sequence_and_shifts.nef`

**Test file structure:**
Create `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/shifts/test_offset.py` with test cases:

1. **`test_offset_element_type_matching()`**
   - Input: shifts with CA=50.0, CB=40.0, N=120.0
   - Spec: `C=+1.0`
   - Expected: CA=51.0, CB=41.0, N=120.0 (only carbons affected)

2. **`test_offset_isotope_specific_matching()`**
   - Input: shifts with 13C atoms and 15N atoms
   - Spec: `13C=+0.5`
   - Expected: only 13C atoms offset, 15N unchanged

3. **`test_offset_override_behavior()`**
   - Input: shifts with C=174.0, CA=55.0, CB=42.0
   - Spec: `C=+1.0,13C=+2.0` (latter overrides for 13C specifically)
   - Expected: all carbons get base +1.0, but if 13C column shows isotope 13, apply +2.0 instead

4. **`test_offset_alternate_isotope_format()`**
   - Test both `13C` and `C13` formats work (isotope library supports both)

5. **`test_offset_multiple_specs_comma_separated()`**
   - Spec: `C=+0.07,15N=-0.44`
   - Verify both applied correctly

6. **`test_offset_multiple_specs_space_separated()`**
   - Specs as separate args: `['C=+0.07', '15N=-0.44']`

7. **`test_offset_with_frame_selector()`**
   - Multiple shift frames, use `--frame` to select specific one

8. **`test_offset_wildcard_patterns()`**
   - Pattern: `C*=+1.0` should match CA, CB, CG, etc.

9. **`test_offset_error_cases()`**
   - Missing `=` in spec → exit_error
   - Non-numeric value → exit_error
   - Empty pattern → exit_error

10. **`test_offset_skips_unused_values()`**
    - Rows with value=UNUSED, ".", or "" should not be modified

Use testing patterns from codebase:
```python
from nef_pipelines.lib.test_lib import (
    run_and_report,
    assert_lines_match,
    read_test_data,
    EXPECTED_EXIT_ERROR,
)
from nef_pipelines.tools.shifts import shifts_app
```

### Step 3: Handle Edge Cases

**Consider:**
- Mixed isotope atoms in same offset spec
- Empty/missing isotope_number column (older NEF files)
- Invalid isotope codes (non-existent isotopes)
- Case sensitivity for element symbols
- Wildcards in isotope codes (should not be supported)

**Reuse existing utilities:**
- `ATOM_TO_ISOTOPE` dictionary maps element → default isotope
- `convert_isotopes()` handles both `13C` and `C13` formats
- `UNUSED` constant for checking unused shift values

## Verification

**End-to-end testing:**

1. **Create test NEF file with sample shifts:**
   ```bash
   # Use existing test data or create minimal example
   cat > /tmp/test_shifts.nef <<EOF
   # [NEF header and molecular system]
   # Chemical shifts with various atoms and isotopes
   EOF
   ```

2. **Run offset command with element-type matching:**
   ```bash
   nef shifts offset 'C=+1.0' < /tmp/test_shifts.nef
   # Verify: all carbon atoms (CA, CB, CG, C) offset by +1.0
   ```

3. **Run offset command with isotope-specific matching:**
   ```bash
   nef shifts offset '13C=+0.5,15N=-0.3' < /tmp/test_shifts.nef
   # Verify: only 13C atoms offset by +0.5, only 15N atoms offset by -0.3
   ```

4. **Run offset command with override behavior:**
   ```bash
   nef shifts offset 'C=+1.0,13C=+2.0' < /tmp/test_shifts.nef
   # Verify: 13C atoms get +2.0 (override), other carbons get +1.0
   ```

5. **Run test suite:**
   ```bash
   nefl test src/nef_pipelines/tests/shifts/test_offset.py
   # Verify: all tests pass
   ```

6. **Run with real data:**
   ```bash
   nef shifts offset 'C=+0.07,13C=+0.05,15N=-0.44' < real_data.nef
   # Verify: realistic offsets applied correctly to production data
   ```

## Dependencies

**Existing code to reuse:**
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/lib/isotope_lib.py` - `convert_isotopes()`, `ATOM_TO_ISOTOPE`, `Isotope` enum
- Test utilities in `lib/test_lib.py` - `run_and_report()`, `assert_lines_match()`, `EXPECTED_EXIT_ERROR`
- Test data pattern from `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/test_data/ubiquitin_short_sequence_and_shifts.nef`

## Migration Notes

**Breaking change:** The `@` prefix syntax will no longer work. Users must update to isotope codes.

**Old syntax → New syntax:**
- `@CA=+0.07` → `13C=+0.07` (if matching carbonyl specifically) or use wildcard pattern
- `C=+1.0` → unchanged (element-type matching still works the same way)

**Note:** The help text already documents the new syntax, suggesting this change is intentional and planned.
