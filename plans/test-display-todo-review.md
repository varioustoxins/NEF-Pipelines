# Plan: Review and Resolve test_display.py TODO Comments

**STATUS: MOSTLY COMPLETE** ✅ - Cleanup needed

**Current state:**
- **17 of 19 TODOs marked "COMPLETED"** ✅
- Work WAS done, but TODO comments weren't removed
- Only **2 active TODOs** remain:
  - Line 533: "these outputs don't look right this should be the first 5 lines of the loop surely"
  - Line 1275: "logic a little flawed as the top levels are in the ccpn namespace"

**Completed work includes:**
- ✅ Hidden frame hints implemented
- ✅ Ellipsis positioning fixed (now at end)
- ✅ Default selector verified (`*` for all frames)
- ✅ Test structure verified and corrected

**Action needed:** Remove 17 COMPLETED TODO comments as cleanup.

---

## Context

The file `src/nef_pipelines/tests/frames/test_display.py` has been commented with 18 TODO comments. This plan reviews each comment to determine if it makes sense, then proposes how to address it. The display command allows selective viewing of NEF file contents using a selector syntax (frame.loop:tags) with various display modes (--head, --middle, --tail) and filtering options.

## TODO Comment Analysis and Proposed Actions

### Category 1: CONFIRMED BUGS - Must Fix

#### TODO Line 474-476: Ellipsis positioning with --head
**Comment:** "these outputs don't look right this should be the first 5 lines of the loop surely; also there shouldn't be a # more columns... as its all columns; ah i see the bug the ... 21 rows omitted ... should be at the end!"

**Assessment:** PARTIALLY CORRECT - Column selection is WORKING, but display annotations are buggy
- ✅ Correct: The ellipsis positioning IS wrong (appears in middle, should be at end)
- ✅ Correct: The "# more columns..." is inconsistent (appears when it shouldn't, or doesn't appear when it should)
p- ❌ Incorrect: Column selection is actually CORRECT - `value` wildcard matches both `value` AND `value_uncertainty`
- **Note:** `--exact` flag exists but is NOT implemented yet (TODO at line 131 in display.py) and has NO tests

**The Real Bugs:**
1. **Inconsistent "# more columns..." comment** - needs investigation of when/why it appears
2. **Wrong ellipsis positioning** - ellipsis should be at END after all displayed rows, not in middle

**Action:**
1. Investigate "# more columns..." logic - determine correct behavior and apply consistently
2. Fix ellipsis positioning (should appear at end after all displayed rows)
3. Fix test expectations to match correct behavior


**Files:** `src/nef_pipelines/tools/frames/display.py` (lines 565-614), test expectations lines 479-505

---

#### TODO Line 506: --middle ellipsis positioning
**Comment:** "... 11 rows omitted ... should be at the end!"

**Assessment:** CORRECT
Same root cause as line 474. The ellipsis placement logic needs fixing.

**Action:** Fix after resolving line 474 issue, update EXPECTED_MIDDLE_OUTPUT (lines 507-535)

---

#### TODO Line 536: --tail output correctness
**Comment:** "this one is correct!"

**Assessment:** CORRECT
EXPECTED_TAIL_OUTPUT appears to have correct structure. Keep as reference for correct behavior.

**Action:** None - remove TODO, it's just a note

---

### Category 2: TEST EXPECTATIONS NEEDING VERIFICATION

#### TODO Line 241: Default output vs file content
**Comment:** "shouldn't this just be the same as the contents of multi_frame_test.nef with the first two lines or so missing"

**Assessment:** REASONABLE QUESTION
The default selector should be `*` (all frames) not `*.*:*`. The output should match input file minus the NEF header.

**Action:**
1. Verify default selector is `*` (all complete frames)
2. Read `multi_frame_test.nef` test data file
3. Compare with EXPECTED_DEFAULT_OUTPUT (lines 242-294)
4. Update test to use no selector (defaults to `*`) and verify output matches file content

**Files:** `src/nef_pipelines/tests/frames/test_data/multi_frame_test.nef`, test expectations lines 242-294

---

#### TODO Lines 591, 761, 815, 1078: "I assume these will be broken"
**Comments:** "i presume these will be broken in the same way" (appears 4 times)

**Assessment:** NEEDS VERIFICATION
These tests likely inherit the same bugs. Need to verify after fixing the ellipsis positioning bugs.

**Action:**
1. After fixing bugs in Category 1, run these specific tests
2. Update expectations as needed
3. Remove TODO comments once verified

**Tests to check:**
- `test_count_option` (line 592)
- `test_additive_head_middle_tail` (line 763)
- `test_ellipsis_positioning_with_head_middle_tail` (line 816)
- `test_no_comments_with_head` (line 1079)

---

### Category 3: DESIGN DECISIONS NEEDED

#### TODO Line 216: Missing frame comments
**Comment:** "shouldn't EXPECTED_COMBINED_KEYS_VALUES have comments for missing frames"

**Assessment:** VALID DESIGN QUESTION
Currently the code adds `# loop category ...` comments for hidden loops but doesn't add similar comments for hidden frames.

**Action:**
1. Implement hidden frame placeholder comments like `# save_frame_name ...`
2. Create `_append_hidden_frame_hints()` function similar to `_append_hidden_loop_hints()`
3. Update test expectations to include frame placeholder comments

**Decision:** YES - Add frame hints for consistency with loop hints (this was in the original design plan)

**Files:** `src/nef_pipelines/tools/frames/display.py` (around line 499-504)

---

#### TODO Line 298: Missing saveframe comments in partial output
**Comment:** "TODO missing other saveframes as comments"

**Assessment:** SAME AS LINE 216
Same design question - should non-selected frames appear as commented placeholders?

**Action:** Resolve together with line 216

---

#### TODO Line 1194: Namespace test limitation
**Comment:** "logic a little flawed as the top levels are in the ccpn namespace; you would need a non ccpn frame or loop with ccpn tags etc for this test to work..."

**Assessment:** CORRECT OBSERVATION
The test for hierarchical namespace filtering is limited by test data structure. All ccpn frames only have ccpn children, so can't test mixed-namespace scenarios.

**Action:**
1. Create proper test data with cross-namespace hierarchies (e.g., nef frame with some ccpn tags, or ccpn frame with nef loop)
2. Update or add test to properly verify hierarchical namespace filtering
3. Update test expectations for comprehensive namespace coverage

**Decision:** Fix the test data and test properly - don't just document the limitation

**Files:** Test docstring at line 1183

---

### Category 4: --tags-only FLAG REVIEW

#### TODOs Lines 984, 1313, 1396: "is --tags-only still needed?"
**Comments:** "is --tags-only still needed? I think it was written before we had a comprehensive selection syntax..." / "see comment about tags-only"

**Assessment:** FLAG HAS DISTINCT BEHAVIOR, BUT REDUNDANT WITH SELECTOR SYNTAX

**Analysis:**
- Current selector syntax already supports tag-only selection:
  - `molecular_system:sf_category,sf_framecode` - select specific frame tags
  - `molecular_system:` - select ALL frame tags (equivalent to --tags-only for that frame)
  - `*:*` - select all frame tags from all frames
- The `--tags-only` flag provides a shorthand but doesn't enable anything new
- However, `--tags-only` with a loop selector produces `# loop not shown: _nef_sequence` which is different from explicit frame tag selection

**Recommendation:** REFACTOR OR REMOVE
1. **Option A (Remove):** Tests can be rewritten using selector syntax `molecular_system:` instead of `molecular_system:* --tags-only`
2. **Option B (Document):** Keep flag as convenient shorthand, document as syntactic sugar
3. **Option C (Deprecate):** Mark as deprecated, convert tests to use selector syntax

**Proposed Action:** **Remove `--tags-only` and `--loops-only` flags, KEEP tests using new selector syntax**
- Test `test_tags_only` (line 985): Rewrite to use `molecular_system:` selector (shows all frame tags)
- Test `test_tags_only_with_loop_selector` (line 1016): Rewrite to use appropriate selector
- Test `test_loops_only` (line 1038): Rewrite to use `molecular_system.` selector (shows all loops)
- Test `test_frame_tags_selector_consistent_with_tags_only` (line 1430): Keep but update to verify selector syntax equivalence
- Test `test_namespace_filter_tags` (line 1314): Update to use selector syntax without --tags-only
- Test `test_namespace_hierarchical_tags_only` (line 1397): Update to use selector syntax

**Decision:** Remove the flags but KEEP all tests - rewrite them to demonstrate the selector syntax can do the same thing

**Files:**
- `src/nef_pipelines/tools/frames/display.py` (remove --tags-only, --loops-only flags and related logic)
- Test file: rewrite tests at lines 985, 1016, 1038, 1314, 1397, 1430 to use selector syntax

---

### Category 5: ORGANIZATIONAL IMPROVEMENTS

#### TODO Line 331: Expected output organization
**Comment:** "be consistent about where these go either all global or all in their functions; most probably above function of first use is best and if all tests with the same expected group together that's even better; or is there some other logical order in the file"

**Assessment:** VALID ORGANIZATIONAL CONCERN

**Current State:** Mix of global expected outputs (top of file) and inline (near tests)

**Recommendation:** ALL EXPECTED OUTPUTS GLOBAL BEFORE FIRST USE
- All EXPECTED_* constants should be defined at module level (top of file)
- Organize them in order of first use in the test file
- Group related expectations together

**Action:**
1. Move ALL expected outputs to top section of file (after imports, before tests)
2. Order them by first use in the test suite
3. Group related expectations together with blank lines for readability
4. Mark TODO as completed

---

#### TODO Line 677: Test name clarity
**Comment:** "this is the wrong name running in cli_runner is the artifact that does it!"

**Assessment:** CORRECT - NAME IS MISLEADING

**Current:** `test_default_behaviour_in_cli_runner()`
**Problem:** "in_cli_runner" describes the test harness, not the behavior being tested

**Recommendation:** Rename to `test_pipe_mode_output_routing()` or `test_non_tty_output_streams()`

**Action:** Rename test function and update docstring (line 678-685)

---

### Category 6: FEATURE REQUESTS

#### TODO Line 636: Show column count in "# more columns..." comment
**Comment:** "it would be nice to say n more columns and possibly even xxxx...yyyy"

**Assessment:** REASONABLE ENHANCEMENT

**Current:** `# more columns...`
**Proposed:** `# ... 5 more columns ...` or `# more 5 columns (atom_id through merit) ...`

**Action:**
1. Modify `_insert_more_columns_comment()` to calculate omitted column count
2. Optionally show first and last omitted column names
3. Update all test expectations

**Recommendation:** Implement count only first, add column names as future enhancement

**Files:** `src/nef_pipelines/tools/frames/display.py` (line 617)

---

#### TODO Line 762: Index range syntax for AI-friendly selection
**Comment:** "add todo we should be able to specify indices as well 1...30,20..25 etc maybe useful for AIs"

**Assessment:** INTERESTING FEATURE FOR AI INTERACTION

**Proposed Enhancement:** Support explicit row index selection like:
- `--rows 1-5,10-15` to show specific row ranges
- `--rows 0,5,10,15` to show specific indices

**Action:**
1. Add TODO comment at top of `display.py` documenting this feature request
2. Include proposed syntax examples in the TODO
3. Mark test TODO as completed, referencing the display.py TODO

**Decision:** Add as TODO comment in display.py (not GitHub issue) for future implementation

**TODO Text for display.py:**
```python
# TODO: Add support for explicit row index selection for AI-friendly interaction
#   Proposed syntax:
#     --rows 1-5,10-15    # show specific row ranges
#     --rows 0,5,10,15    # show specific indices
#   This would allow AI agents to request precise row selections without
#   relying on --head/--middle/--tail semantics
```

---

### Category 7: DISCOVERED ISSUES (Not in original TODOs)

#### --exact Flag: IMPLEMENTED and NOW TESTED ✓
**Location:** display.py line 49-53, TODO at line 131

**Status:** The `--exact` flag IS fully implemented and working correctly!
- The TODO comment `# TODO [Future] exact!` at line 131 is **misleading** - the flag works
- Had ZERO tests initially - **NOW HAS TEST** (`test_exact_flag_disables_wildcards`)
- Disables wildcard matching for BOTH loop names AND tag names

**How it works:**
- **Without `--exact`**: `value` → `*value*` → matches `value`, `value_uncertainty`, etc.
- **With `--exact`**: `value` → `value` → matches ONLY `value` exactly
- **Loop names**: Must use full category name with `--exact` (e.g., `nef_chemical_shift` not `chemical_shift`)

**Action:**
1. ✅ Added comprehensive test for --exact behavior
2. **Remove misleading TODO comment** at line 131 in display.py
3. Mark this discovery as completed in plan

**Discovery:** The flag was already working - it just lacked tests and had a misleading TODO!

---

### Category 8: MINOR COMMENTS/NOTES

#### TODO Line 456: Formatting note
**Comment:** "no spaces before the final \"\"\""

**Assessment:** STYLE NOTE
This is just a formatting reminder for multiline strings.

**Action:** Mark TODO as completed, this is covered by code style guidelines

---

## Implementation Plan

### Phase 1: Fix Critical Bugs (Priority 1)

**Files to modify:**
- `src/nef_pipelines/tools/frames/display.py`
- `src/nef_pipelines/tests/frames/test_display.py`

**Steps:**
1. **Investigate and fix "# more columns..." inconsistency**
   - Determine when this comment should/shouldn't appear
   - The comment appears inconsistently across tests
   - Check `_is_partial_loop_columns()` and `_insert_more_columns_comment()` logic
   - Consider: wildcard matching means more columns may appear than explicitly requested
   - Apply consistent logic and update test expectations

2. **Fix ellipsis positioning for --head, --middle, --tail**
   - Ellipsis should appear at END of displayed rows, not in middle
   - Review `_calculate_display_indices()` (lines 550-562)
   - Verify indices are correctly calculated
   - Check `_insert_ellipsis_comments()` (lines 654-724) for insertion logic
   - Fix insertion logic to place ellipsis at correct positions
   - Update test expectations for correct behavior

3. **Update affected test expectations**
   - EXPECTED_HEAD_OUTPUT (lines 479-505)
   - EXPECTED_MIDDLE_OUTPUT (lines 507-535)
   - EXPECTED_COUNT_OUTPUT (lines 609-632)
   - Any other expectations affected by bug fixes

### Phase 2: Verify Assumptions (Priority 2)

**Steps:**
1. Run tests marked "I assume these will be broken"
   - `test_count_option`
   - `test_additive_head_middle_tail`
   - `test_ellipsis_positioning_with_head_middle_tail`
   - `test_no_comments_with_head`

2. Update expectations as needed

3. Mark assumption TODO comments as completed (lines 591, 761, 815, 1078)

### Phase 3: Design Decisions (Priority 3)

**Steps:**
1. **Implement hidden frame placeholder comments** (TODOs line 216, 298)
   - Create `_append_hidden_frame_hints()` function
   - Add `# save_frame_name ...` comments for non-selected frames
   - Update test expectations to include frame hints
   - Mark TODOs as completed

2. **Verify and fix default selector behavior** (TODO line 241)
   - Ensure default selector is `*` (all complete frames)
   - Read multi_frame_test.nef and compare with EXPECTED_DEFAULT_OUTPUT
   - Update test to use default selector and verify output matches input
   - Mark TODO as completed

3. **Fix namespace test data and test properly** (TODO line 1194)
   - Create test data with cross-namespace hierarchies
   - Update or add tests for comprehensive namespace filtering
   - Don't just document limitation - actually fix it
   - Mark TODO as completed

### Phase 4: Refactor --tags-only Flag (Priority 4)

**Steps:**
1. **Remove --tags-only and --loops-only flags**
   - Remove from `display()` CLI function parameters
   - Remove from `pipe()` worker function parameters
   - Remove all related logic for these flags
   - Update command help text

2. **Rewrite ALL affected tests to use selector syntax:**
   - `test_tags_only` (line 985): Rewrite to use `molecular_system:` selector
   - `test_tags_only_with_loop_selector` (line 1016): Rewrite with selector equivalent
   - `test_loops_only` (line 1038): Rewrite to use `molecular_system.` selector
   - `test_frame_tags_selector_consistent_with_tags_only` (line 1430): Update test name and verify selector equivalence
   - `test_namespace_filter_tags` (line 1314): Update to use selector syntax
   - `test_namespace_hierarchical_tags_only` (line 1397): Update to use selector syntax
   - Update all test docstrings to explain they're testing selector syntax capabilities

3. **Mark all related TODOs as completed** (lines 984, 1313, 1396)

### Phase 5: Organizational Improvements (Priority 5)

**Steps:**
1. **Reorganize ALL expected outputs to top of file** (TODO line 331)
   - Move ALL EXPECTED_* constants to module level (after imports)
   - Order them by first use in the test file
   - Group related expectations with blank lines
   - Mark TODO as completed

2. **Rename misleading test** (TODO line 677)
   - Rename `test_default_behaviour_in_cli_runner` to `test_pipe_mode_output_routing`
   - Update docstring to clarify what's being tested (pipe mode behavior, not test harness)
   - Mark TODO as completed

3. **Mark style note TODO as completed** (TODO line 456)
   - This is covered by code style guidelines
   - Change TODO to "TODO: COMPLETED - no spaces before final triple quotes (style guideline)"

### Phase 6: Feature Enhancements (Priority 6 - Optional)

**Steps:**
1. **Implement column count in "# more columns..." comment** (TODO line 636)
   - Modify `_insert_more_columns_comment()` to calculate and show omitted column count
   - Change from `# more columns...` to `# ... N more columns ...`
   - Update all affected test expectations
   - Mark TODO as completed
   - Future enhancement: add first/last column names

2. **Add TODO comment in display.py for index range syntax** (TODO line 762)
   - Add detailed TODO at top of display.py documenting proposed feature
   - Include syntax examples (--rows 1-5,10-15 and --rows 0,5,10,15)
   - Note AI interaction use case
   - Mark test TODO as completed with reference to display.py TODO

## Verification

After implementation:

1. **Run full test suite:** `nefl test src/nef_pipelines/tests/frames/test_display.py`
2. **Verify no regressions** in other frame-related tests
3. **Manual testing** with various selector combinations
4. **Check test coverage** remains comprehensive

## Summary of TODO Comment Assessment

| Line | Comment | Assessment | Action |
|------|---------|------------|--------|
| Line | Comment | Assessment | Action |
|------|---------|------------|--------|
| 216 | Missing frame comments | Valid - implement | Implement `_append_hidden_frame_hints()`, mark TODO completed |
| 241 | Default output vs file | Correct - fix | Fix default selector to `*`, verify output, mark TODO completed |
| 298 | Missing saveframes | Same as 216 | Same as 216, mark TODO completed |
| 331 | Output organization | Valid - reorganize | Move ALL expected outputs to top before first use, mark TODO completed |
| 456 | No spaces before """ | Style note | Mark TODO as completed (covered by style guide) |
| 474-476 | Ellipsis positioning + inconsistent "# more columns..." | **BUG - Partially correct** | Fix ellipsis positioning + "# more columns..." logic, mark TODO completed |
| 506 | Ellipsis at end | **BUG - Correct** | Fix implementation + expectations, mark TODO completed |
| 536 | This one is correct | Correct observation | Mark TODO as completed (reference example) |
| 591 | Assume broken | Needs verification | Verify after fixes, update expectations, mark TODO completed |
| 636 | Column count feature | Implement now | Add column count to "# more columns...", mark TODO completed |
| 677 | Wrong test name | Correct | Rename test function, mark TODO completed |
| 761 | Assume broken | Needs verification | Verify after fixes, update expectations, mark TODO completed |
| 762 | Index range syntax | Add TODO to display.py | Add TODO at top of display.py, mark test TODO completed |
| 815 | Assume broken | Needs verification | Verify after fixes, update expectations, mark TODO completed |
| 984 | --tags-only needed? | **Flag is redundant** | Remove flag, rewrite test with selectors, mark TODO completed |
| 1078 | Assume broken | Needs verification | Verify after fixes, update expectations, mark TODO completed |
| 1194 | Namespace test flaw | Correct - fix test data | Create proper test data, update tests, mark TODO completed |
| 1313 | See tags-only comment | Same as 984 | Update test to use selectors, mark TODO completed |
| 1396 | See tags-only comment | Same as 984 | Update test to use selectors, mark TODO completed |

## Critical Files

- `src/nef_pipelines/tools/frames/display.py` - Implementation to fix
- `src/nef_pipelines/tests/frames/test_display.py` - Tests to update
- `src/nef_pipelines/tests/frames/test_data/multi_frame_test.nef` - Test data for verification
- `src/nef_pipelines/tests/frames/test_data/ubiquitin_short_unassign.nef` - Test data for bug reproduction

## TODO Completion Strategy

**IMPORTANT:** When completing work, mark TODOs as completed rather than removing them:

Format for completed TODOs:
```python
#TODO: COMPLETED - <brief description of what was done>
# Original: <original TODO text>
```

Examples:
```python
#TODO: COMPLETED - Ellipsis now positioned at end of displayed rows
# Original: ... 21 rows omitted ... should be at the end!

#TODO: COMPLETED - Using molecular_system: selector syntax instead of --tags-only
# Original: is --tags-only still needed?
```

This allows verification before final cleanup. After verification, all "COMPLETED" TODOs will be stripped.
