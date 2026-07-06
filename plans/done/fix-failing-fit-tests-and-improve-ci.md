# Fix Failing Fit Tests and Improve CI

## Problem Summary

### Failing Tests
6 tests in `src/nef_pipelines/tests/tools/fit/` are currently failing:
1. `test_exponential.py::test_exponential_r1_data_single` - looking for wrong frame name
2. `test_exponential.py::test_t1noe_with_r1noe_data_single_mc10_n0_1` - duplicate frame error
3. `test_fit.py::test_exponential_single` - looking for wrong frame name
4. `test_mean.py::test_mean_data_single` - case mismatch (mean vs MEAN)
5. `test_t1noe.py::test_t1noe_with_r1noe_data_single` - duplicate frame error
6. `test_t1noe.py::test_t1noe_with_r1noe_data_single_mc10_n0_1` - duplicate frame error

### Why GHA Missed These Failures
**Critical Issue:** The `nef test` command in `src/nef_pipelines/tools/test.py:51` calls `pytest.main(command)` but doesn't check or propagate the exit code. This means:
- GHA runs `nef test` which always exits with 0 (success)
- pytest reports 8 failures but the workflow continues successfully
- Tests have been failing since August 2025 without being caught

### Missing Test Data
Two test data files are untracked:
- `src/nef_pipelines/tests/tools/fit/test_data/test_1_exponential.nef`
- `src/nef_pipelines/tests/tools/fit/test_data/test_1_r1noe.nef`

## Current Uncommitted Changes

### Category 1: Sparky Block Parser Implementation (Recent Session Work)
**New Files to Add:**
- `src/nef_pipelines/lib/tabular_parser.py` - whitespace-based tabular parser
- `src/nef_pipelines/tests/test_tabular_parser.py` - tests for tabular parser (16 tests, all passing)
- `src/nef_pipelines/transcoders/sparky/sparky_block_lib.py` - block structure utilities
- `src/nef_pipelines/transcoders/sparky/sparky_block_parser.py` - block file parser
- `src/nef_pipelines/transcoders/sparky/sparky_parser_lib.py` - parser functions
- `src/nef_pipelines/transcoders/sparky/sparky_structures.py` - data structures
- `src/nef_pipelines/transcoders/sparky/importers/project_shifts.py` - import shifts from .proj
- `src/nef_pipelines/transcoders/sparky/importers/save.py` - import from .save files
- `src/nef_pipelines/tests/sparky/test_sparky_block_lib.py` - block lib tests (67 tests)
- `src/nef_pipelines/tests/sparky/test_sparky_parser_lib.py` - parser tests
- `src/nef_pipelines/tests/sparky/test_import_project_shifts.py` - importer tests
- `src/nef_pipelines/tests/sparky/test_import_save.py` - save importer tests
- `src/nef_pipelines/tests/sparky/test_data/minimal_example.proj` - test data
- `src/nef_pipelines/tests/sparky/test_data/minimal_example.save` - test data
- `src/nef_pipelines/tests/sparky/test_data/minimal_poky.save` - test data

**Modified Files:**
- `src/nef_pipelines/transcoders/sparky/__init__.py` - register new importers
- `src/nef_pipelines/transcoders/sparky/sparky_lib.py` - integration with new parser
- `src/nef_pipelines/transcoders/sparky/importers/sequence.py` - use new parser
- `src/nef_pipelines/tests/sparky/test_sparky_lib.py` - updated for new parser
- `src/nef_pipelines/tests/sparky/test_sparky_parser.py` - updated imports

**Backup File (Don't Commit):**
- `src/nef_pipelines/transcoders/sparky/sparky_parser_lib.py.backup_before_tabular_integration`

### Category 2: Other Previously Modified Work
Many other modified files from earlier work (loops, pales, frames, etc.) - these should be reviewed separately and are NOT part of this plan.

## Implementation Plan

### Phase 1: Fix Test Failures

#### 1.1 Fix Frame Name Mismatches
**File:** `src/nef_pipelines/tests/tools/fit/test_exponential.py`
- Line 69: Change `"nefpls_relaxation_list_r1"` → `"nefpls_relaxation_list_T2"`
- Reason: Test runs T2 fitting but looks for r1 frame

**File:** `src/nef_pipelines/tests/tools/fit/test_fit.py`
- Line 48: Change `"nefpls_relaxation_list_r1"` → `"nefpls_relaxation_list_T2"`
- Reason: Same as above

**File:** `src/nef_pipelines/tests/tools/fit/test_mean.py`
- Line 48: Change `"nefpls_relaxation_list_mean"` → `"nefpls_relaxation_list_MEAN"`
- Reason: Output uses uppercase MEAN

#### 1.2 Fix Duplicate Frame Addition in t1noe
**Root Cause Analysis:**

Test data has 2 series frames: `nefpls_series_list_T1_NOE_pos` and `nefpls_series_list_T1_NOE_neg`.
Each series references two relaxation list IDs: "r1" and "noe".

The code in `t1noe.py` lines 257-274 loops to create frames for each output:
```python
fit_ids = ["time_constant", "offset"]
for fit_name, output in zip(fit_ids, outputs):
    frame = _fit_results_as_frame(...)
    entry.add_saveframe(frame)  # Duplicate name collision!
```

**Problem:** Frame naming in `fit_lib.py` doesn't incorporate the `output` parameter, so all frames get the same name (e.g., `nefpls_relaxation_list_T1_NOE_pos`), causing duplicates when processing multiple outputs.

**Fix Required:**
Modify frame naming to incorporate the `output` parameter to create distinct frames like:
- `nefpls_relaxation_list_r1` (for r1 output)
- `nefpls_relaxation_list_noe` (for noe output)

This requires changes to `_fit_results_as_frame()` in fit_lib.py or the calling code in t1noe.py to pass the output name to the frame creation logic.

### Phase 2: Fix CI to Catch Test Failures

#### 2.1 Fix `nef test` Command Exit Code
**File:** `src/nef_pipelines/tools/test.py`
- Line 51: Change from `main(command)` to `exit_code = main(command); sys.exit(exit_code)`
- This ensures pytest's exit code is propagated to the shell
- GHA will now fail when tests fail

#### 2.2 Streamfitter Dependency Decision

Since streamfitter is a child project that needs testing with nef-pipelines, we need to decide how to handle the dependency.

**Option A: Add as Optional Dependency**
```toml
[project.optional-dependencies]
fitting = ["streamfitter"]
```
**Pros:**
- Clearly documents the relationship
- Users can install with `pip install nef-pipelines[fitting]`
- Keeps core package lightweight for users who don't need fitting
- CI can explicitly install with the extra

**Cons:**
- Adds complexity to installation instructions
- Users might not discover fitting features
- Requires maintaining extra dependency specifications

**Option B: Add as Required Dependency**
```toml
dependencies = [
    ...,
    "streamfitter",
]
```
**Pros:**
- Simple installation - fitting always works
- Tests always pass (no missing dependency issues)
- Better user experience - all features available out of the box

**Cons:**
- Forces all users to install streamfitter even if they don't use fitting
- Couples nef-pipelines release cycle to streamfitter
- Since streamfitter is a child project, this creates circular dev dependency

**Option C: Keep External, Document in CI**
Current state - streamfitter installed separately.

**Pros:**
- Maximum flexibility - projects remain independent
- Users who don't need fitting don't install it
- Dev workflow stays decoupled

**Cons:**
- Tests fail by default unless streamfitter is manually installed
- Harder to discover fitting features
- Requires documenting in multiple places (README, CI, tests)

**Recommendation:** Option A (Optional Dependency)
- Best balance of discoverability and flexibility
- Makes the relationship explicit without forcing it
- CI can install with `--with fitting` or `[fitting]`
- Tests can be marked with `@pytest.mark.skipif` when streamfitter not installed

### Phase 3: Commit Organization

Based on user request to "include everything", here's a comprehensive organization of all uncommitted changes:

#### Commit 1: Core Library Enhancements
**Message:** "Add core library functions and improve error handling"

**Files:**
- `src/nef_pipelines/lib/nef_lib.py` - NEF library improvements
- `src/nef_pipelines/lib/sequence_lib.py` - sequence handling enhancements
- `src/nef_pipelines/lib/shift_lib.py` - shift processing updates
- `src/nef_pipelines/lib/structures.py` - data structure updates
- `src/nef_pipelines/lib/test_lib.py` - test utilities (excluding CI fix)
- `src/nef_pipelines/lib/util.py` - utility functions
- `src/nef_pipelines/main.py` - main application updates
- `src/nef_pipelines/tests/test_nef_lib.py` - library tests
- `src/nef_pipelines/tests/test_util.py` - utility tests

**Why together:** Core library changes that other components depend on.

#### Commit 2.a: Frames Delete Enhancement
**Message:** "Enhance frames delete command with improved filtering and tests"

**Files:**
- `src/nef_pipelines/tools/frames/delete.py` (~102 lines modified)
- `src/nef_pipelines/tests/frames/test_delete.py` (~296 lines modified)

**Changes:** ~218 lines
**Why separate:** Self-contained delete functionality enhancement

#### Commit 2.b: Frames List Enhancement
**Message:** "Enhance frames list command with improved output and filtering"

**Files:**
- `src/nef_pipelines/tools/frames/list.py` (~75 lines modified)
- `src/nef_pipelines/tests/frames/test_list.py` (~79 lines modified)

**Changes:** ~66 lines
**Why separate:** Independent list functionality improvement

#### Commit 2.c: Frames Tabulate and Init Updates
**Message:** "Update frames tabulate and module initialization"

**Files:**
- `src/nef_pipelines/tools/frames/__init__.py` (~3 lines)
- `src/nef_pipelines/tools/frames/tabulate.py` (~31 lines modified)

**Changes:** ~14 lines
**Why separate:** Minor tabulate improvements and init registration

#### Commit 3: Loops Tool Implementation
**Message:** "Add loops tool with split functionality"

**Files:**
- `src/nef_pipelines/tools/loops/__init__.py`
- `src/nef_pipelines/tools/loops/split.py` (new)
- `src/nef_pipelines/tests/loops/__init__.py` (new)
- `src/nef_pipelines/tests/loops/test_split.py` (new)
- `src/nef_pipelines/tests/loops/test_data/multi_chain_rdcs.nef` (new)

**Why together:** Complete loops tool feature addition.

#### Commit 4: Chains Tool Enhancement
**Message:** "Add chains tool initialization"

**Files:**
- `src/nef_pipelines/tools/chains/__init__.py`

**Why separate:** Minimal change, preparatory work for future chains functionality.

#### Commit 5: PALES Transcoder Updates
**Message:** "Update PALES transcoder for RDC handling and template generation"

**Files:**
- `src/nef_pipelines/transcoders/pales/exporters/rdcs.py`
- `src/nef_pipelines/transcoders/pales/exporters/template.py`
- `src/nef_pipelines/transcoders/pales/importers/rdcs.py`
- `src/nef_pipelines/tests/pales/test_export_rdcs.py`
- `src/nef_pipelines/tests/pales/test_import_rdcs.py`
- `src/nef_pipelines/tests/pales/test_template.py`
- `src/nef_pipelines/tests/pales/test_data/*.nef` (12 modified test data files)

**Why together:** Complete PALES transcoder enhancement with tests.

#### Commit 6: Other Transcoder Updates
**Message:** "Update NMRPipe, NMRStar, RCSB, TALOS, and XPLOR transcoders"

**Files:**
- `src/nef_pipelines/transcoders/nmrpipe/__init__.py`
- `src/nef_pipelines/transcoders/nmrpipe/nmrpipe_lib.py`
- `src/nef_pipelines/transcoders/nmrstar/importers/project.py`
- `src/nef_pipelines/transcoders/nmrstar/importers/project_cli.py`
- `src/nef_pipelines/transcoders/nmrstar/importers/rdcs.py`
- `src/nef_pipelines/transcoders/rcsb/importers/sequence.py`
- `src/nef_pipelines/transcoders/rcsb/rcsb_lib.py`
- `src/nef_pipelines/transcoders/talos/importers/restraints.py`
- `src/nef_pipelines/transcoders/xplor/__init__.py`
- `src/nef_pipelines/transcoders/xplor/xplor_lib.py`
- `src/nef_pipelines/tests/nmrstar/test_import_project.py`
- `src/nef_pipelines/tests/xplor/test_xplor_lib.py`

**Why together:** Bundled transcoder maintenance updates.

#### Commit 7: PIPP Transcoder Addition
**Message:** "Add PIPP transcoder for shift import"

**Files:**
- `src/nef_pipelines/transcoders/pipp/__init__.py` (new)
- `src/nef_pipelines/transcoders/pipp/importers/__init__.py` (new)
- `src/nef_pipelines/tests/pipp/__init__.py` (new)
- `src/nef_pipelines/tests/pipp/test.pipp` (new)

**Why separate:** New transcoder addition, self-contained feature.

#### Commit 8.a: Tabular Parser Infrastructure
**Message:** "Add generic whitespace-based tabular parser"

**Files:**
- `src/nef_pipelines/lib/tabular_parser.py` (new, ~311 lines)
- `src/nef_pipelines/tests/test_tabular_parser.py` (new, ~334 lines)

**Lines:** ~645 new
**Why separate:** Foundation parser used by Sparky, independent functionality
**Tests:** 16 tests, all passing

#### Commit 8.b: Sparky Block Parser Core
**Message:** "Add Sparky block structure parser and data types"

**Files:**
- `src/nef_pipelines/transcoders/sparky/sparky_block_lib.py` (new, ~434 lines)
- `src/nef_pipelines/transcoders/sparky/sparky_block_parser.py` (new, ~144 lines)
- `src/nef_pipelines/transcoders/sparky/sparky_structures.py` (new, ~25 lines)
- `src/nef_pipelines/transcoders/sparky/sparky_parser_lib.py` (new, ~743 lines)

**Lines:** ~1,346 new
**Why separate:** Core block parsing infrastructure, foundation for importers

#### Commit 8.c: Sparky Block Parser Tests
**Message:** "Add comprehensive tests for Sparky block parser"

**Files:**
- `src/nef_pipelines/tests/sparky/test_sparky_block_lib.py` (new, ~422 lines)
- `src/nef_pipelines/tests/sparky/test_sparky_parser_lib.py` (new, ~49 lines)
- `src/nef_pipelines/tests/sparky/test_data/minimal_example.proj` (new)
- `src/nef_pipelines/tests/sparky/test_data/minimal_example.save` (new)
- `src/nef_pipelines/tests/sparky/test_data/minimal_poky.save` (new)

**Lines:** ~471 new + test data
**Why separate:** Test suite for block parser, can verify 8.b independently

#### Commit 8.d: Sparky Integration and Refactoring
**Message:** "Integrate block parser into Sparky library and refactor existing code"

**Files:**
- `src/nef_pipelines/transcoders/sparky/sparky_lib.py` (~791 lines modified, net ~95 lines)
- `src/nef_pipelines/transcoders/sparky/__init__.py` (~2 lines)
- `src/nef_pipelines/transcoders/sparky/importers/sequence.py` (~45 lines modified)
- `src/nef_pipelines/tests/sparky/test_sparky_lib.py` (~189 lines modified)

**Lines:** ~95 net changes (561 insertions, 466 deletions)
**Why separate:** Integration layer, connects new parser to existing code

#### Commit 8.e: Sparky Project Shifts Importer
**Message:** "Add importer for chemical shifts from Sparky project files"

**Files:**
- `src/nef_pipelines/transcoders/sparky/importers/project_shifts.py` (new, ~194 lines)
- `src/nef_pipelines/tests/sparky/test_import_project_shifts.py` (new, ~files needed)

**Lines:** ~194+ new
**Why separate:** New feature, independent importer using block parser

#### Commit 8.f: Sparky Save File Importer
**Message:** "Add importer for Sparky save files"

**Files:**
- `src/nef_pipelines/transcoders/sparky/importers/save.py` (new, ~files needed)
- `src/nef_pipelines/tests/sparky/test_import_save.py` (new, ~files needed)

**Lines:** ~files needed new
**Why separate:** New feature, independent importer using block parser

**NOTE:** Do NOT commit: `sparky_parser_lib.py.backup_before_tabular_integration`

**Overall:** Complete Sparky parser refactor split into 6 logical commits. All 119 Sparky + 16 tabular tests pass.

#### Commit 9: Fix Failing Fit Tests
**Message:** "Fix fit tests - frame name mismatches and duplicate frame handling"

**Files:**
- `src/nef_pipelines/tools/fit/fit_lib.py` - fix frame naming to include output parameter
- `src/nef_pipelines/tests/tools/fit/test_exponential.py` - correct frame names
- `src/nef_pipelines/tests/tools/fit/test_fit.py` - correct frame names
- `src/nef_pipelines/tests/tools/fit/test_mean.py` - correct frame name case
- `src/nef_pipelines/tests/tools/fit/test_data/test_1_exponential.nef` (add)
- `src/nef_pipelines/tests/tools/fit/test_data/test_1_r1noe.nef` (add)

**Why together:** All related to fixing the fit test suite that's been failing since August.

#### Commit 10: Fix CI Test Detection
**Message:** "Fix nef test command to propagate pytest exit codes to CI"

**Files:**
- `src/nef_pipelines/tools/test.py` - add sys.exit(exit_code)

**Why separate:** Critical infrastructure fix. Makes CI actually fail when tests fail.

#### Commit 11: Add Streamfitter as Optional Dependency
**Message:** "Add streamfitter as optional dependency for fitting features"

**Files:**
- `pyproject.toml` - add [project.optional-dependencies]
- `.github/workflows/test.yml` - update to install with [fitting]
- `setup.cfg` - if needed for pytest configuration

**Why separate:** Dependency management change, affects installation behavior.

#### Commit 12: Add Documentation Build to CI
**Message:** "Add documentation build and doctests to CI workflow"

**Files:**
- `.github/workflows/test.yml` - docs job (if not already in commit 11)

**Why separate:** CI enhancement, isolated feature.

## Verification Steps

### After Each Commit Group

#### After Frames Commits (2.a, 2.b, 2.c):
```bash
pytest src/nef_pipelines/tests/frames/ -v
nef frames list --help
nef frames delete --help
nef frames tabulate --help
```
Expected: All frames tests passing

#### After Tabular Parser (8.a):
```bash
pytest src/nef_pipelines/tests/test_tabular_parser.py -v
```
Expected: 16/16 tests passing

#### After Sparky Block Core (8.b):
```bash
# Won't run tests yet, just verify imports
python -c "from nef_pipelines.transcoders.sparky.sparky_block_lib import *"
```

#### After Sparky Block Tests (8.c):
```bash
pytest src/nef_pipelines/tests/sparky/test_sparky_block_lib.py -v
pytest src/nef_pipelines/tests/sparky/test_sparky_parser_lib.py -v
```
Expected: Block parser tests passing

#### After Sparky Integration (8.d):
```bash
pytest src/nef_pipelines/tests/sparky/test_sparky_lib.py -v
```
Expected: Library tests passing

#### After Sparky Importers (8.e, 8.f):
```bash
pytest src/nef_pipelines/tests/sparky/ -v
```
Expected: 119/119 tests passing

#### After Fit Tests Fix (9):
```bash
pytest src/nef_pipelines/tests/tools/fit/ -v
```
Expected: 15/15 tests passing

#### After CI Test Fix (10):
```bash
# Test that exit code is propagated
pytest src/nef_pipelines/tests/frames/test_delete.py::test_nonexistent -v
echo $?  # Should be non-zero for failing test

nef test
echo $?  # Should be 0 if all tests pass
```

### Final Verification

```bash
# Run full test suite
nef test
```
Expected: Exit code 0, all tests passing

### Verify Streamfitter Integration (if Commit 11 done):
```bash
# Check optional dependency
python -c "import streamfitter"
pytest src/nef_pipelines/tests/tools/fit/ -v
```
Expected: All fit tests passing with streamfitter available

## Critical Files

### To Modify:
- `src/nef_pipelines/tests/tools/fit/test_exponential.py` (lines 69)
- `src/nef_pipelines/tests/tools/fit/test_fit.py` (line 48)
- `src/nef_pipelines/tests/tools/fit/test_mean.py` (line 48)
- `src/nef_pipelines/tools/fit/t1noe.py` (lines 151-274, pending investigation)
- `src/nef_pipelines/tools/test.py` (line 51)

### To Add (New Files):
- All Sparky-related files listed in Category 1
- `src/nef_pipelines/tests/tools/fit/test_data/test_1_exponential.nef`
- `src/nef_pipelines/tests/tools/fit/test_data/test_1_r1noe.nef`

## Decisions Made

1. **t1noe duplicate frames:** Investigated - it's a code issue in `fit_lib.py` where frame naming doesn't incorporate the output parameter. Will fix in commit 9.

2. **Other uncommitted changes:** User requested to "include everything" - organized into 12 focused commits covering all categories of work.

3. **Streamfitter dependency:** Recommended Option A (optional dependency) - best balance of discoverability and flexibility. Allows CI to install with `[fitting]` extra.

## Why This Matters

1. **Test Reliability:** Tests failing silently in CI defeats the purpose of CI
2. **Streamfitter Integration:** As a child project, streamfitter needs to be tested with nef-pipelines to ensure compatibility
3. **Technical Debt:** These tests have been failing since August 2025 without detection
4. **Code Organization:** 50+ modified files need organized commits for maintainable history

## Execution Summary

This plan addresses three main objectives:

1. **Fix Broken Tests** (Commit 9, 10)
   - Correct 6 failing fit tests
   - Fix CI to actually catch test failures

2. **Complete Recent Work** (Commits 1-8.f, 11, 12)
   - Organize and commit all pending changes
   - Group by functional area for clear history
   - Split large commits into reviewable units

3. **Improve Testing Infrastructure** (Commits 10, 11, 12)
   - Propagate pytest exit codes in CI
   - Add streamfitter as optional dependency
   - Document fitting feature requirements

**Commit Structure:**
- **Total:** 19 commits covering all uncommitted work
- **Core commits:** 1, 3, 4, 5, 6, 7, 8 (RCSB/XPLOR), 9, 10, 11, 12
- **Frames split (2 → 3):** 2.a (Delete), 2.b (List), 2.c (Tabulate)
- **Sparky split (8 → 6):** 8.a (Tabular Parser), 8.b (Block Core), 8.c (Tests), 8.d (Integration), 8.e (Project Importer), 8.f (Save Importer)

**Benefits of splitting:**
- Easier code review (smaller, focused commits)
- Better git history (logical progression)
- Independent verification at each step
- Easier to revert if needed

**Expected outcome:** Clean git history, all tests passing, CI working properly

---

## Review Effort Summary

### By Commit (Sorted by Effort)

| Rank | Commit | Area | Lines Changed | Review Effort | Type | Done ☐ to ☑ or ✓ |
|------|--------|------|---------------|---------------|------|------|
| 1 | 3 | Loops Tool | ~2,249 | 🔴 VERY LARGE | New Feature | ☐ |
| 2 | 10 | PIPP | ~1,972 | 🔴 LARGE | New Feature | ☐ |
| 3 | 5 | PALES | ~1,962 | 🔴 LARGE | Enhancement | ☐ |
| 4 | 1 | Core Library | ~1,773 | 🔴 LARGE | Enhancement | ☐ |
| 5 | 8.b | Sparky Block Core | ~1,346 | 🔴 LARGE | New Feature | ☐ |
| 6 | 8.a | Tabular Parser | ~645 | 🟡 MEDIUM | New Feature | ☐ |
| 7 | 8 | RCSB/XPLOR | ~622 | 🟡 MEDIUM | Update | ☐ |
| 8 | 8.c | Sparky Block Tests | ~471 | 🟡 MEDIUM | Tests | ☐ |
| 9 | 9 | Fit Tests Fix | ~2,284 | 🟡 MEDIUM | Bug Fix | ☐ |
| 10 | 2.a | Frames Delete | ~218 | 🟡 SMALL-MEDIUM | Enhancement | ☐ |
| 11 | 8.e | Sparky Project Importer | ~194+ | 🟡 SMALL-MEDIUM | New Feature | ☐ |
| 12 | 8.d | Sparky Integration | ~95 net | 🟢 SMALL | Refactor | ☐ |
| 13 | 6 | NMRPipe | ~88 | 🟢 SMALL | Update | ☐ |
| 14 | 11 | Config/CI | ~80 | 🟢 SMALL | Infrastructure | ☐ |
| 15 | 2.b | Frames List | ~66 | 🟢 SMALL | Enhancement | ☐ |
| 16 | 2.c | Frames Tabulate | ~14 | ⚪ TRIVIAL | Update | ☐ |
| 17 | 10 | CI Test Fix | ~6 | ⚪ TRIVIAL | Bug Fix | ☐ |
| 18 | 7 | NMRStar | ~4 | ⚪ TRIVIAL | Enhancement | ☐ |
| 19 | 4 | Chains Tool | ~1 | ⚪ TRIVIAL | Preparation | ☐ |

### Sparky Sub-commits (8.a-8.f)
- **8.a** Tabular Parser: ~645 lines (🟡 MEDIUM)
- **8.b** Block Core: ~1,346 lines (🔴 LARGE)
- **8.c** Block Tests: ~471 lines (🟡 MEDIUM)
- **8.d** Integration: ~95 net lines (🟢 SMALL)
- **8.e** Project Importer: ~194+ lines (🟡 SMALL-MEDIUM)
- **8.f** Save Importer: ~TBD lines (🟡 SMALL-MEDIUM)
- **Total Sparky:** ~2,951+ lines across 6 commits

### Frames Sub-commits (2.a-2.c)
- **2.a** Delete: ~218 lines (🟡 SMALL-MEDIUM)
- **2.b** List: ~66 lines (🟢 SMALL)
- **2.c** Tabulate: ~14 lines (⚪ TRIVIAL)
- **Total Frames:** ~298 lines across 3 commits

---

## Detailed Review Effort by Commit

### 🔴 VERY LARGE Commits (>1500 lines)

**Commit 3: Loops Tool (~2,249 lines)** - From other plan
- Estimated review time: 3-4 hours

**Commit 8.b: Sparky Block Core (~1,346 lines)**
- New parser implementation
- Complex hierarchical block parsing logic
- Estimated review time: 2-3 hours

### 🔴 LARGE Commits (500-1500 lines)

**Commit 1: Core Library (~1,773 lines)** - From other plan
- Estimated review time: 3-4 hours

**Commit 5: PALES (~1,962 lines)** - From other plan
- Estimated review time: 3-4 hours

**Commit 10: PIPP (~1,972 lines)** - From other plan
- Estimated review time: 2-3 hours

### 🟡 MEDIUM Commits (100-500 lines)

**Commit 8.a: Tabular Parser (~645 lines)**
- Well-tested generic parser
- Estimated review time: 1-1.5 hours

**Commit 8.c: Sparky Block Tests (~471 lines)**
- Comprehensive test suite
- Estimated review time: 1 hour

**Commit 9: Fit Tests Fix (~2,284 lines)**
- Mostly test data files (test_1_exponential.nef, test_1_r1noe.nef)
- Small code changes (3 test files, fit_lib.py)
- Estimated review time: 1-2 hours
  - Test data review: 1 hour
  - Code changes: 30 minutes

**Commit 8 (RCSB/XPLOR): (~622 lines)** - From other plan
- Estimated review time: 1-2 hours

**Commit 2.a: Frames Delete (~218 lines)**
- Focused enhancement
- Estimated review time: 30-45 minutes

**Commit 8.e: Sparky Project Importer (~194+ lines)**
- New importer using block parser
- Estimated review time: 30-45 minutes

### 🟢 SMALL Commits (<100 lines)

**Commit 8.d: Sparky Integration (~95 net lines)**
- Refactoring, many changes but net small
- Estimated review time: 30-45 minutes

**Commit 6: NMRPipe (~88 lines)** - From other plan
- Estimated review time: 20-30 minutes

**Commit 11: Config/CI (~80 lines)** - From other plan
- Estimated review time: 30 minutes

**Commit 2.b: Frames List (~66 lines)**
- Focused improvement
- Estimated review time: 15-20 minutes

### ⚪ TRIVIAL Commits (<10 lines)

**Commit 2.c: Frames Tabulate (~14 lines)**
- Estimated review time: 5 minutes

**Commit 10: CI Test Fix (~6 lines)**
- Critical but simple change
- Estimated review time: 5 minutes

**Commit 7: NMRStar (~4 lines)** - From other plan
- Estimated review time: 5 minutes

**Commit 4: Chains Tool (~1 line)** - From other plan
- Estimated review time: 2 minutes

---

## Total Estimated Review Time

### Sparky-Related Commits (8.a-8.f):
- 8.a (MEDIUM): 1-1.5 hours
- 8.b (LARGE): 2-3 hours
- 8.c (MEDIUM): 1 hour
- 8.d (SMALL): 30-45 minutes
- 8.e (SMALL-MEDIUM): 30-45 minutes
- 8.f (SMALL-MEDIUM): 30-45 minutes
- **Subtotal: 6-8.5 hours**

### Frames-Related Commits (2.a-2.c):
- 2.a (SMALL-MEDIUM): 30-45 minutes
- 2.b (SMALL): 15-20 minutes
- 2.c (TRIVIAL): 5 minutes
- **Subtotal: 50-70 minutes**

### Fit Tests and CI (9, 10):
- 9 (MEDIUM): 1-2 hours
- 10 (TRIVIAL): 5 minutes
- **Subtotal: 1-2 hours**

### Other Commits (1, 3, 4, 5, 6, 7, 8, 11):
- From other plan: ~14-19 hours

**GRAND TOTAL: ~22-30 hours** for complete review of all changes

---

## Recommended Review Sessions

### Session 1: Quick Wins (30 minutes)
- Commit 4 (Chains)
- Commit 7 (NMRStar)
- Commit 2.c (Frames Tabulate)
- Commit 10 (CI Test Fix)

### Session 2: Small Changes (2 hours)
- Commit 2.b (Frames List)
- Commit 6 (NMRPipe)
- Commit 11 (Config/CI)
- Commit 8.d (Sparky Integration)

### Session 3: Frames Enhancement (1 hour)
- Commit 2.a (Frames Delete)

### Session 4: Fit Tests Fix (2 hours)
- Commit 9 (Fit Tests Fix)
- Review test data and code changes

### Session 5: Tabular Parser (1.5 hours)
- Commit 8.a (Tabular Parser)
- Foundation for Sparky work

### Session 6: Sparky Block Parser (3 hours)
- Commit 8.b (Sparky Block Core)
- Most complex piece

### Session 7: Sparky Tests (1 hour)
- Commit 8.c (Sparky Block Tests)

### Session 8: Sparky Importers (2 hours)
- Commit 8.e (Project Importer)
- Commit 8.f (Save Importer)

### Sessions 9-13: Large Foundation Work (14-19 hours)
- Commit 1 (Core Library): 3-4 hours
- Commit 5 (PALES): 3-4 hours
- Commit 3 (Loops): 3-4 hours
- Commit 10 (PIPP): 2-3 hours
- Commit 8 (RCSB/XPLOR): 1-2 hours
