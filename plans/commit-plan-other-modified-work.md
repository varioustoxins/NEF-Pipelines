# Commit Plan: Other Previously Modified Work

This plan covers all modified files that are not part of the Sparky block parser implementation. These changes represent various improvements, bug fixes, and new features developed over time.

## Overview

**Total Modified Files:** 55
**Total New Files:** 8
**Recommended Commits:** 19 (11 base + 8 from splits)

**Note:** Commits 2 (Frames) and 8 (Sparky) are split into sub-commits for easier review:
- **Commit 2** split into 2.a, 2.b, 2.c (3 commits)
- **Commit 8** split into 8.a, 8.b, 8.c, 8.d, 8.e, 8.f (6 commits)
- See "Fix Failing Tests and Improve CI" plan for split details

---

## Commit 1: Core Library Enhancements

**Message:** "Add core library functions and improve error handling"

### Modified Files:
- `src/nef_pipelines/lib/nef_lib.py` - NEF library improvements
- `src/nef_pipelines/lib/sequence_lib.py` - sequence handling enhancements
- `src/nef_pipelines/lib/shift_lib.py` - shift processing updates
- `src/nef_pipelines/lib/structures.py` - data structure updates
- `src/nef_pipelines/lib/test_lib.py` - test utilities
- `src/nef_pipelines/lib/util.py` - utility functions
- `src/nef_pipelines/main.py` - main application updates

### Test Files:
- `src/nef_pipelines/tests/test_nef_lib.py` - library tests
- `src/nef_pipelines/tests/test_util.py` - utility tests

### Rationale:
Core library changes that other components depend on. Should be committed first as foundation for other changes.

### Verification:
```bash
pytest src/nef_pipelines/tests/test_nef_lib.py -v
pytest src/nef_pipelines/tests/test_util.py -v
```

---

## Commit 2: Frames Tool Improvements

**Message:** "Enhance frames tool with improved list, delete, and tabulate functions"

### Modified Files:
- `src/nef_pipelines/tools/frames/__init__.py`
- `src/nef_pipelines/tools/frames/delete.py`
- `src/nef_pipelines/tools/frames/list.py`
- `src/nef_pipelines/tools/frames/tabulate.py`

### Test Files:
- `src/nef_pipelines/tests/frames/test_delete.py`
- `src/nef_pipelines/tests/frames/test_list.py`

### Rationale:
Related frame manipulation functionality. Grouped together as coherent feature set.

### Verification:
```bash
pytest src/nef_pipelines/tests/frames/ -v
nef frames list --help
nef frames delete --help
nef frames tabulate --help
```

---

## Commit 3: Loops Tool Implementation

**Message:** "Add loops tool with split functionality"

### New Files:
- `src/nef_pipelines/tools/loops/split.py`
- `src/nef_pipelines/tests/loops/__init__.py`
- `src/nef_pipelines/tests/loops/test_split.py`
- `src/nef_pipelines/tests/loops/test_data/multi_chain_rdcs.nef`

### Modified Files:
- `src/nef_pipelines/tools/loops/__init__.py`

### Rationale:
Complete new tool feature addition with tests and test data. Self-contained functionality.

### Verification:
```bash
pytest src/nef_pipelines/tests/loops/test_split.py -v
nef loops split --help
```

---

## Commit 4: Chains Tool Enhancement

**Message:** "Add chains tool initialization"

### Modified Files:
- `src/nef_pipelines/tools/chains/__init__.py`

### Rationale:
Minimal preparatory change for future chains functionality. Separate to keep history clean.

### Verification:
```bash
python -c "from nef_pipelines.tools.chains import *"
```

---

## Commit 5: PALES Transcoder Updates

**Message:** "Update PALES transcoder for RDC handling and template generation"

### Modified Files:
- `src/nef_pipelines/transcoders/pales/exporters/rdcs.py`
- `src/nef_pipelines/transcoders/pales/exporters/template.py`
- `src/nef_pipelines/transcoders/pales/importers/rdcs.py`

### Test Files:
- `src/nef_pipelines/tests/pales/test_export_rdcs.py`
- `src/nef_pipelines/tests/pales/test_import_rdcs.py`
- `src/nef_pipelines/tests/pales/test_template.py`

### Test Data Files (12 files):
- `src/nef_pipelines/tests/pales/test_data/1AKI_pales_short.nef`
- `src/nef_pipelines/tests/pales/test_data/anA.nef`
- `src/nef_pipelines/tests/pales/test_data/anDC_short.nef`
- `src/nef_pipelines/tests/pales/test_data/dadrFixed_short.nef`
- `src/nef_pipelines/tests/pales/test_data/dadrOnlyFixed_short.nef`
- `src/nef_pipelines/tests/pales/test_data/saupePred_short.nef`
- `src/nef_pipelines/tests/pales/test_data/ssiaA.nef`
- `src/nef_pipelines/tests/pales/test_data/ssiaB_short.nef`
- `src/nef_pipelines/tests/pales/test_data/ssiaC_short.nef`
- `src/nef_pipelines/tests/pales/test_data/ssiaF.nef`
- `src/nef_pipelines/tests/pales/test_data/ssia_short.nef`
- `src/nef_pipelines/tests/pales/test_data/svd_short.nef`

### Rationale:
Complete PALES transcoder enhancement with comprehensive tests and test data. All related to RDC functionality.

### Verification:
```bash
pytest src/nef_pipelines/tests/pales/ -v
nef pales import rdcs --help
nef pales export rdcs --help
nef pales export template --help
```

---

## Commit 6: NMRPipe Transcoder Updates

**Message:** "Update NMRPipe transcoder initialization and library"

### Modified Files:
- `src/nef_pipelines/transcoders/nmrpipe/__init__.py`
- `src/nef_pipelines/transcoders/nmrpipe/nmrpipe_lib.py`

### Rationale:
NMRPipe-specific updates. Separate from other transcoders for focused history.

### Verification:
```bash
python -c "from nef_pipelines.transcoders.nmrpipe import *"
```

---

## Commit 7: NMRStar Transcoder Updates

**Message:** "Update NMRStar transcoder for improved project and RDC import"

### Modified Files:
- `src/nef_pipelines/transcoders/nmrstar/importers/project.py`
- `src/nef_pipelines/transcoders/nmrstar/importers/project_cli.py`
- `src/nef_pipelines/transcoders/nmrstar/importers/rdcs.py`

### Test Files:
- `src/nef_pipelines/tests/nmrstar/test_import_project.py`

### Rationale:
NMRStar import improvements. Keep transcoder-specific changes isolated.

### Verification:
```bash
pytest src/nef_pipelines/tests/nmrstar/test_import_project.py -v
nef nmrstar import project --help
```

---

## Commit 8: RCSB and XPLOR Transcoder Updates

**Message:** "Update RCSB and XPLOR transcoders"

### Modified Files - RCSB:
- `src/nef_pipelines/transcoders/rcsb/importers/sequence.py`
- `src/nef_pipelines/transcoders/rcsb/rcsb_lib.py`

### Modified Files - XPLOR:
- `src/nef_pipelines/transcoders/xplor/__init__.py`
- `src/nef_pipelines/transcoders/xplor/xplor_lib.py`

### Test Files:
- `src/nef_pipelines/tests/xplor/test_xplor_lib.py`

### Rationale:
Minor updates to two transcoders. Grouped together as maintenance work.

### Verification:
```bash
pytest src/nef_pipelines/tests/xplor/test_xplor_lib.py -v
nef rcsb import sequence --help
```

---

## Commit 9: TALOS Transcoder Updates

**Message:** "Update TALOS restraints importer"

### Modified Files:
- `src/nef_pipelines/transcoders/talos/importers/restraints.py`

### Rationale:
Single transcoder update, separate for clarity.

### Verification:
```bash
nef talos import restraints --help
```

---

## Commit 10: PIPP Transcoder Addition

**Message:** "Add PIPP transcoder for shift import"

### New Files:
- `src/nef_pipelines/transcoders/pipp/__init__.py`
- `src/nef_pipelines/transcoders/pipp/importers/__init__.py`
- `src/nef_pipelines/tests/pipp/__init__.py`
- `src/nef_pipelines/tests/pipp/test.pipp`

### Rationale:
New transcoder addition. Self-contained feature, deserves its own commit.

### Verification:
```bash
python -c "from nef_pipelines.transcoders.pipp import *"
nef pipp import --help
```

---

## Commit 11: Configuration and CI Updates

**Message:** "Update project configuration and add documentation build to CI"

### Modified Files:
- `pyproject.toml` - project metadata updates
- `setup.cfg` - setup configuration
- `.github/workflows/test.yml` - CI workflow enhancements (docs job)

### Rationale:
Infrastructure and configuration changes. Keep separate from feature code.

### Note:
Review changes in these files carefully - they may include:
- Version bumps
- Dependency updates
- CI improvements already added in previous session

### Verification:
```bash
# Check pyproject.toml is valid
python -m pip install --dry-run -e .

# Validate workflow syntax
gh workflow view
```

---

## Additional Files to Review

### Fit Tests Fix (Covered in Main Plan)
- `src/nef_pipelines/tools/fit/fit_lib.py` - **DO NOT include in these commits**
- This is part of "Fix Failing Fit Tests" plan

### Files to Exclude from Commits

These are backup/old files that should NOT be committed:
- `src/nef_pipelines/lib/*.old`
- `src/nef_pipelines/tests/*/*.old`
- `src/nef_pipelines/tools/*/*.old`
- `src/nef_pipelines/transcoders/*/*.old`
- `*.py_vsc`
- `*.py.backup_before_*`

---

## Summary - Sorted by Review Effort

| Rank | Commit | Area | Lines Changed | Files | Review Effort | Type | Split? | Done |
|------|--------|------|---------------|-------|---------------|------|--------|------|
| 1 | 3 | Loops Tool | ~2,249 | 5 | 🔴 VERY LARGE | New Feature | No | ☐ |
| 2 | 10 | PIPP | ~1,972 | 4 | 🔴 LARGE | New Feature | No | ☐ |
| 3 | 5 | PALES | ~1,962 | 15 | 🔴 LARGE | Enhancement | No | ☐ |
| 4 | 1 | Core Library | ~1,773 | 9 | 🔴 LARGE | Enhancement | No | ☐ |
| 5 | 8 | RCSB/XPLOR | ~622 | 5 | 🟡 MEDIUM | Update | No | ☐ |
| 6 | 2 | Frames Tool | ~298 | 6 | 🟡 MEDIUM | Enhancement | **Yes (→ 2.a, 2.b, 2.c)** | ☐ |
| 7 | 6 | NMRPipe | ~88 | 2 | 🟢 SMALL | Update | No | ☐ |
| 8 | 11 | Config/CI | ~80 | 3 | 🟢 SMALL | Infrastructure | No | ☐ |
| 9 | 7 | NMRStar | ~4 | 4 | ⚪ TRIVIAL | Enhancement | No | ☐ |
| 10 | 9 | TALOS | 0 | 1 | ⚪ TRIVIAL | Update | No | ☐ |
| 11 | 4 | Chains Tool | 1 | 1 | ⚪ TRIVIAL | Preparation | No | ☐ |

**Note:** Commits 2 and 8 (Sparky) are detailed with splits in the "Fix Failing Tests" plan

**Total:** 55 files, ~9,049 lines changed across 11 commits

### Review Effort Legend:
- 🔴 **VERY LARGE** (>1500 lines): Requires detailed review, allocate significant time
- 🔴 **LARGE** (500-1500 lines): Substantial review needed
- 🟡 **MEDIUM** (100-500 lines): Moderate review effort
- 🟢 **SMALL** (<100 lines): Quick review
- ⚪ **TRIVIAL** (<10 lines): Minimal review needed

### Recommended Review Order:
1. **Start with TRIVIAL commits** (4, 9, 7) - Quick wins, build confidence
2. **Then SMALL commits** (11, 6) - Manageable infrastructure changes
3. **Then MEDIUM commits** (2, 8) - Moderate complexity
4. **Finally LARGE commits** (1, 5, 10, 3) - Save the heavy lifting for when fresh

---

## Execution Order

1. Commit core library first (foundation)
2. Commit tools (frames, loops, chains)
3. Commit transcoders (grouped by type)
4. Commit configuration last (infrastructure)

This order ensures dependencies are satisfied and each commit is independently testable.

---

## Final Verification

After all commits, run full test suite:
```bash
nef test
```

Expected: All tests passing (once fit tests are also fixed per main plan)

---

## Detailed Review Effort Breakdown

### 🔴 VERY LARGE Commits (>1500 lines)

**Commit 3: Loops Tool Implementation (~2,249 lines)**
- New feature with extensive implementation
- `split.py`: 950 lines
- `test_split.py`: 1,296 lines
- High test coverage, thorough implementation
- **Estimated review time:** 3-4 hours

### 🔴 LARGE Commits (500-1500 lines)

**Commit 10: PIPP Transcoder Addition (~1,972 lines)**
- New transcoder, self-contained
- All new files, no modifications to existing code
- **Estimated review time:** 2-3 hours

**Commit 5: PALES Transcoder Updates (~1,962 lines)**
- Major enhancement across 18 files
- Affects exporters, importers, tests, and test data
- Complex RDC handling logic
- **Estimated review time:** 3-4 hours

**Commit 1: Core Library Enhancements (~1,773 lines)**
- Foundation changes affecting entire codebase
- Touches 9 critical files
- Significant test additions (604 lines in test_nef_lib.py alone)
- **Estimated review time:** 3-4 hours
- **Priority:** HIGH - other commits may depend on this

### 🟡 MEDIUM Commits (100-500 lines)

**Commit 8: RCSB/XPLOR Transcoder Updates (~622 lines)**
- Moderate changes across 5 files
- XPLOR lib has most changes (406 lines added)
- **Estimated review time:** 1-2 hours

**Commit 2: Frames Tool Improvements (~298 lines)**
- Enhancement to existing tool
- Well-tested (375 test lines)
- **Estimated review time:** 1 hour

### 🟢 SMALL Commits (<100 lines)

**Commit 6: NMRPipe Transcoder Updates (~88 lines)**
- Refactoring/cleanup
- **Estimated review time:** 20-30 minutes

**Commit 11: Configuration and CI Updates (~80 lines)**
- Infrastructure changes
- Review pyproject.toml and CI workflow carefully
- **Estimated review time:** 30 minutes

### ⚪ TRIVIAL Commits (<10 lines)

**Commit 7: NMRStar Transcoder Updates (~4 lines)**
- Minor fixes
- **Estimated review time:** 5 minutes

**Commit 9: TALOS Transcoder Updates (0 net lines)**
- Pure refactoring, no functional change
- **Estimated review time:** 5 minutes

**Commit 4: Chains Tool Enhancement (1 line)**
- Preparatory work
- **Estimated review time:** 2 minutes

---

## Total Estimated Review Time

- **VERY LARGE:** 3-4 hours (Commit 3)
- **LARGE:** 8-11 hours (Commits 1, 5, 10)
- **MEDIUM:** 2-3 hours (Commits 2, 8)
- **SMALL:** 50 minutes (Commits 6, 11)
- **TRIVIAL:** 12 minutes (Commits 4, 7, 9)

**TOTAL: 14-19 hours** for complete review of all changes

### Recommended Review Sessions

**Session 1 (Easy wins - 1 hour):**
- Commits 4, 9, 7 (TRIVIAL)
- Commits 11, 6 (SMALL)

**Session 2 (Medium complexity - 2-3 hours):**
- Commits 2, 8 (MEDIUM)

**Session 3 (Foundation - 3-4 hours):**
- Commit 1 (Core Library - HIGH PRIORITY)

**Session 4 (Large features - 3-4 hours):**
- Commit 5 (PALES)

**Session 5 (New features - 5-7 hours):**
- Commit 10 (PIPP)
- Commit 3 (Loops Tool)
