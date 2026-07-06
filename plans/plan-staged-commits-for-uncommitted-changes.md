# Plan: Staged Commits for Uncommitted Changes

## Summary

  Organize uncommitted changes in the nef_pipelines repository into logical, staged commits. The repository has significant work including 3 new major features (loops split, frames set, plot correlations), transcoder enhancements, library additions, and refactoring work.

**Key Challenge:** Some new features are missing tests entirely, which should be created before committing.

  ---

  ## Changelog Summary (Layperson-Friendly)

  ### New Features

  - **Split multi-chain data into separate files** - New `loops split` command lets you split NEF files containing data from multiple molecular chains into separate files for each chain
  - **Set tag values in bulk** - New `frames set` command allows you to update values in your NEF files using flexible pattern matching (e.g., set all chemical shift uncertainties to a specific value)
  - **Create correlation plots** - New `plot correlations` command generates publication-quality scatter plots comparing data between different NEF frames, with regression lines, statistics, and customizable layouts
  - **Mathematical operations on data** - New `loops maths` command performs calculations on numeric columns (add, subtract, multiply, divide)

  ### Enhancements

  - **Better PALES file handling** - Improved support for importing and exporting PALES RDC (residual dipolar coupling) files with better chain handling options
  - **XPlor RDC support** - Added ability to import RDC restraints from XPlor format files
  - **NMRPipe RDC import** - Added support for importing RDC data from NMRPipe format
  - **Enhanced frame listing** - The `frames list` command now shows loop tag details when using verbose mode (`-vv`)
  - **Better documentation** - Added automated documentation building and testing to ensure docs stay current

  ### Infrastructure

  - **Documentation system** - Set up MkDocs for better project documentation
  - **CI improvements** - Added documentation building and testing to continuous integration

  ### For Developers

  - **New library functions** - Added reusable functions for selecting loops by category and enhanced warning messages
  - **PALES refactoring** - Extracted common PALES functionality into a shared library for easier maintenance

  ---

  ## Missing Tests Analysis

  ### CRITICAL - Features Without Tests:

  1. **`loops/maths.py`** (431 lines) - NO TEST FILE
     - Complex mathematical operations on NEF loop columns
     - Multiple parsing modes and auto-detection logic
     - **Action Required**: Create `src/nef_pipelines/tests/loops/test_maths.py`

  2. **`nmrpipe/importers/rdcs.py`** - NO TEST FILE
     - New NMRPipe RDC importer
     - **Action Required**: Create `src/nef_pipelines/tests/nmrpipe/test_import_rdcs.py`

  3. **`pales/pales_lib.py`** (150 lines) - NO DEDICATED TEST
     - Shared library with ChainPolicy enum, validation functions
     - **Action Required**: Create `src/nef_pipelines/tests/pales/test_pales_lib.py`

  ### MINOR - Tests Exist But Untracked:

  4. **`plot/correlations.py`** - test exists at `src/nef_pipelines/tests/plot/test_correlations.py` (untracked)
  5. **`xplor/importers/rdcs.py`** - test exists at `src/nef_pipelines/tests/xplor/test_import_rdcs.py` (untracked)

  ---

  ## Staged Commit Plan

  ### Stage 1: Library Enhancements (Foundation)

  **Rationale:** Commit library changes first since other features depend on them.

  **Files:**
  - `src/nef_pipelines/lib/nef_lib.py` (adds `select_loops_by_category()`)
  - `src/nef_pipelines/lib/sequence_lib.py`
  - `src/nef_pipelines/lib/translation_lib.py`
  - `src/nef_pipelines/lib/util.py` (adds prepend parameter to `warn()`, stream handling)

  **Commit Message:**
  Add library functions for loop selection and enhanced warnings

  - Add select_loops_by_category() to nef_lib for selecting loops by category
  - Add prepend parameter to warn() in util for message formatting
  - Enhance stream handling utilities
  - Update sequence_lib and translation_lib with supporting changes

  ---

  ### Stage 2: Loops Split Command

  **Files:**
  - `src/nef_pipelines/tools/loops/split.py` (new, 390 lines)
  - `src/nef_pipelines/tests/loops/test_split.py` (new, 371 lines)
  - `src/nef_pipelines/tests/loops/__init__.py` (new)
  - `src/nef_pipelines/tests/loops/test_data/multi_chain_rdcs.nef` (new test data)
  - `src/nef_pipelines/tests/loops/test_data/multi_loop_frame.nef` (new test data)
  - `src/nef_pipelines/tools/loops/__init__.py` (modified - registers split command)

  **Commit Message:**
  Add loops split command for splitting frames by tag values

  - Implement loops split command to split NEF frames by unique combinations of loop tag values
  - Support splitting multi-chain RDC data into separate frames per chain
  - Add --split-on option for specifying tag combinations
  - Add --chain-codes option for explicit chain assignment
  - Include comprehensive test coverage with multi-chain test data

  ---

  ### Stage 3: Frames Set Command

  **Files:**
  - `src/nef_pipelines/tools/frames/set.py` (new, 347 lines)
  - `src/nef_pipelines/tests/frames/test_set.py` (new, 269 lines)
  - `src/nef_pipelines/tools/frames/__init__.py` (modified - registers set command)

  **Commit Message:**
  Add frames set command for setting loop tag values

  - Implement frames set command with flexible selector syntax
  - Support three selector formats: frame.loop:tags, frame:tags, loop:tags
  - Add wildcard support for frame, loop, and tag matching
  - Add --exact flag for exact matching without wildcards
  - Add --create flag to allow creating new tags (default: False)
  - Add --verbose flag for detailed diagnostic output
  - Use priority-based selection: saveframe name → frame category → loop category
  - Include comprehensive test coverage (14 test cases)

  ---

  ### Stage 4: Frames List Enhancement

  **Files:**
  - `src/nef_pipelines/tools/frames/list.py` (modified)

  **Commit Message:**
  Enhance frames list to show loop tags at verbose level 2

  - Add loop tag display when --verbose is specified multiple times (-vv)
  - Helps users understand loop structure before using frames set command

  ---

  ### Stage 5: PALES Transcoder Refactoring

  **Files:**
  - `src/nef_pipelines/transcoders/pales/pales_lib.py` (new, 149 lines - shared library)
  - `src/nef_pipelines/transcoders/pales/exporters/rdcs.py` (modified)
  - `src/nef_pipelines/transcoders/pales/exporters/template.py` (modified)
  - `src/nef_pipelines/transcoders/pales/importers/rdcs.py` (modified)
  - `src/nef_pipelines/tests/pales/test_export_rdcs.py` (modified - updated tests)
  - `src/nef_pipelines/tests/pales/test_template.py` (modified - updated tests)

  **Note:** Consider creating `src/nef_pipelines/tests/pales/test_pales_lib.py` first for better test coverage.

  **Commit Message:**
  Refactor PALES transcoder with shared pales_lib for chain policy handling

  - Extract shared functionality into pales_lib.py
  - Add ChainPolicy enum (SPLIT/SEGID/CHAIN) for chain handling strategies
  - Add validation functions for chain codes and weights
  - Add weight parsing utilities
  - Update exporters and importers to use shared library
  - Update tests to reflect refactored structure

  ---

  ### Stage 6: XPlor and NMRPipe Transcoder Enhancements

  **Files:**
  - `src/nef_pipelines/transcoders/xplor/xplor_lib.py` (modified - adds RDC support)
  - `src/nef_pipelines/transcoders/xplor/__init__.py` (modified)
  - `src/nef_pipelines/transcoders/xplor/importers/rdcs.py` (new, untracked)
  - `src/nef_pipelines/tests/xplor/test_import_rdcs.py` (new, untracked)
  - `src/nef_pipelines/tests/xplor/test_xplor_lib.py` (modified)
  - `src/nef_pipelines/transcoders/nmrpipe/nmrpipe_lib.py` (modified - line-based reading)
  - `src/nef_pipelines/transcoders/nmrpipe/__init__.py` (modified)
  - `src/nef_pipelines/transcoders/nmrpipe/importers/rdcs.py` (new, untracked)

  **Note:** Missing test for nmrpipe RDC importer - should create `src/nef_pipelines/tests/nmrpipe/test_import_rdcs.py`.

  **Commit Message:**
  Add RDC support to XPlor and enhance NMRPipe file handling

  - Add RDC restraint support to XPlor transcoder
  - Add new exception classes for XPlor error handling
  - Add xplor/importers/rdcs.py for importing RDC restraints
  - Update NMRPipe library to use line-based file reading instead of file handles
  - Add nmrpipe/importers/rdcs.py for importing RDC data
  - Add comprehensive test coverage for XPlor RDC import
  - Update existing tests to reflect library changes

  TODO: Add test coverage for NMRPipe RDC importer

  ---

  ### Stage 7: Plot Correlations Command

  **Files:**
  - `src/nef_pipelines/tools/plot/` (new directory)
  - `src/nef_pipelines/tools/plot/__init__.py` (new)
  - `src/nef_pipelines/tools/plot/correlations.py` (new, 1109 lines)
  - `src/nef_pipelines/tests/plot/` (new directory)
  - `src/nef_pipelines/tests/plot/__init__.py` (new)
  - `src/nef_pipelines/tests/plot/test_correlations.py` (new, 411 lines)
  - `src/nef_pipelines/tests/plot/test_data/chemical_shifts.nef` (new test data)
  - `src/nef_pipelines/main.py` (modified - registers plot module)

  **Commit Message:**
  Add plot correlations command for creating correlation plots

  - Implement sophisticated correlation plotting between NEF frame data
  - Support flexible frame specification with wildcards (frame.loop:tags)
  - Add automatic field detection for sequence codes, chain codes, atom names
  - Add grid layout support with configurable rows/columns
  - Add PDF/PNG/SVG output with template-based filenames (correlation_{count}.pdf)
  - Add --calculate flag for regression analysis (R-value, equation, SD)
  - Add --no-regression-line flag to hide regression line but show statistics
  - Add --no-error-bars flag to hide uncertainty bars
  - Add --split-by option for creating separate plots by field values
  - Add --force flag to overwrite existing files
  - Add --open flag to automatically open generated plots
  - Support diagonal reference lines and customizable styling
  - Support binary stdout mode with --out -
  - Include comprehensive test coverage (14 test cases)

  TODO: Rename --calculate to --fit in future version

  ---

  ### Stage 8: Loops Maths Command (BLOCKED - MISSING TESTS)

  **Files:**
  - `src/nef_pipelines/tools/loops/maths.py` (new, untracked, 431 lines)
  - `src/nef_pipelines/tools/loops/__init__.py` (modified - registers maths command)

  **BLOCKER:** No test file exists. Should create `src/nef_pipelines/tests/loops/test_maths.py` before committing.

  **Commit Message (once tests created):**
  Add loops maths command for mathematical operations on loop columns

  - Implement loops maths command for +, -, *, / operations on numeric columns
  - Support auto-detection of numeric columns with --auto flag
  - Support explicit column specification with --columns
  - Support multiple parsing modes for flexible input
  - Add error handling for non-numeric values
  - Include comprehensive test coverage

  [Tests to be created before commit]

  ---

  ### Stage 9: NMRStar and RCSB Transcoder Updates

  **Files:**
  - `src/nef_pipelines/transcoders/nmrstar/importers/project.py` (modified)
  - `src/nef_pipelines/transcoders/nmrstar/importers/project_cli.py` (modified)
  - `src/nef_pipelines/transcoders/nmrstar/importers/rdcs.py` (modified)
  - `src/nef_pipelines/transcoders/rcsb/importers/sequence.py` (modified)

  **Note:** Need to examine diffs to understand specific changes and write appropriate commit message.

  **Commit Message (TBD):**
  Update NMRStar and RCSB importers

  [Examine diffs to determine specific changes]

  ---

  ### Stage 10: Other Tool Updates

  **Files:**
  - `src/nef_pipelines/tools/frames/delete.py` (modified)
  - `src/nef_pipelines/tools/frames/rename.py` (modified)
  - `src/nef_pipelines/tools/frames/tabulate.py` (modified)
  - `src/nef_pipelines/tools/entry/rename.py` (modified)
  - `src/nef_pipelines/tools/chains/__init__.py` (modified)

  **Note:** Need to examine diffs to understand if these are:
  - Bug fixes
  - Formatting/style changes
  - Feature enhancements
  - Refactoring to use new library functions

  **Commit Message (TBD):**
  [Examine diffs to determine appropriate message]

  ---

  ### Stage 11: Documentation Infrastructure

  **Commit 11a: Add MkDocs Dependencies**

  **Files:**
  - `setup.cfg` (modified - adds mkdocs dependencies)

  **Commit Message:**
  Add MkDocs documentation dependencies to setup.cfg

  - Add mkdocs-material for modern documentation theme
  - Add mkdocstrings for API documentation generation
  - Prepare for comprehensive documentation build

  **Commit 11b: Add Documentation Build to CI**

  **Files:**
  - `.github/workflows/test.yml` (modified - adds docs build job)

  **Commit Message:**
  Add documentation build and testing to CI workflow

  - Add docs build job using tox
  - Run doctests as part of CI
  - Upload built documentation as artifacts
  - Ensure documentation stays up to date with code changes

  ---

  ## Files to EXCLUDE from Commits

  **IDE Configuration:**
  - `.idea/vcs.xml` - Should be in .gitignore

  **Test Artifacts/Temporary Files:**
  - All `_private_var_folders_*` directories
  - `.hypothesis/` directory
  - Test output files: `*.nefx`, `*.tab`, `*.tbl`, `*.out`, etc.

  **Personal/Development Files:**
  - `nef_pipelines.profile`
  - `nef_pipelines_tuna/`
  - `old/` directory
  - `examples/` (unless explicitly needed)
  - `info/` directory

  ---

  ## Pre-Commit Actions Required

  ### 0. Create Changelog File:

  ```bash
  # Create CHANGELOG.md with the summary of changes
  # Use the "Changelog Summary (Layperson-Friendly)" section from this plan

  1. Create Missing Test Files:

  Priority 1 (CRITICAL):
  # Create test for loops maths command
  touch src/nef_pipelines/tests/loops/test_maths.py
  # Write comprehensive tests covering:
  # - Basic arithmetic operations (+, -, *, /)
  # - Auto-detection mode
  # - Explicit column specification
  # - Error handling for non-numeric values
  # - Multiple parsing modes

  Priority 2 (IMPORTANT):
  # Create test for NMRPipe RDC importer
  touch src/nef_pipelines/tests/nmrpipe/test_import_rdcs.py
  # Write tests covering:
  # - Basic RDC data import
  # - Format validation
  # - Error handling

  Priority 3 (RECOMMENDED):
  # Create unit tests for pales_lib
  touch src/nef_pipelines/tests/pales/test_pales_lib.py
  # Write unit tests for:
  # - ChainPolicy enum usage
  # - Chain code validation
  # - Weight parsing functions

  2. Add Untracked Test Files:

  # Add plot correlations test (already exists, just untracked)
  git add src/nef_pipelines/tests/plot/

  # Add xplor RDC import test (already exists, just untracked)
  git add src/nef_pipelines/tests/xplor/test_import_rdcs.py

  3. Review Diffs for Tool Updates:

  # Examine what changed in these files to write appropriate commit messages
  git diff src/nef_pipelines/tools/frames/delete.py
  git diff src/nef_pipelines/tools/frames/rename.py
  git diff src/nef_pipelines/tools/frames/tabulate.py
  git diff src/nef_pipelines/tools/entry/rename.py
  git diff src/nef_pipelines/tools/chains/__init__.py
  git diff src/nef_pipelines/transcoders/nmrstar/importers/project.py
  git diff src/nef_pipelines/transcoders/nmrstar/importers/project_cli.py
  git diff src/nef_pipelines/transcoders/nmrstar/importers/rdcs.py
  git diff src/nef_pipelines/transcoders/rcsb/importers/sequence.py

  4. Update .gitignore:

  # Add IDE files if not already present
  echo ".idea/" >> .gitignore

  # Add test artifacts
  echo "_private_var_folders_*/" >> .gitignore
  echo ".hypothesis/" >> .gitignore
  echo "*.nefx" >> .gitignore

  ---
  Commit Execution Order

  Phase 1: Foundation (can commit immediately)
  1. Stage 1: Library Enhancements
  2. Stage 4: Frames List Enhancement
  3. Stage 11a: MkDocs Dependencies
  4. Stage 11b: CI Documentation Build

  Phase 2: New Features with Complete Tests (can commit immediately)
  5. Stage 2: Loops Split Command
  6. Stage 3: Frames Set Command
  7. Stage 5: PALES Refactoring (consider adding pales_lib tests first)
  8. Stage 7: Plot Correlations Command

  Phase 3: Transcoder Enhancements (consider adding NMRPipe RDC test first)
  9. Stage 6: XPlor and NMRPipe Enhancements

  Phase 4: BLOCKED - Requires Test Creation
  10. Stage 8: Loops Maths Command (BLOCKED - create tests first)

  Phase 5: To Be Determined
  11. Stage 9: NMRStar/RCSB Updates (examine diffs first)
  12. Stage 10: Other Tool Updates (examine diffs first)

  ---
  Verification Plan

  After each commit:

  1. Run relevant tests:
  # For loops split
  pytest src/nef_pipelines/tests/loops/test_split.py -v

  # For frames set
  pytest src/nef_pipelines/tests/frames/test_set.py -v

  # For plot correlations
  pytest src/nef_pipelines/tests/plot/test_correlations.py -v

  # Full test suite (after all commits)
  pytest src/nef_pipelines/tests/ -v
  2. Verify no regressions:
  # Run full test suite
  tox -e default
  3. Check documentation build:
  tox -e docs
  4. Manual smoke tests:
  # Test loops split
  nefl loops split --help

  # Test frames set
  nefl frames set --help

  # Test plot correlations
  nefl plot correlations --help

  ---
  Summary

  Total Commits Planned: 12-13 commits organized into logical feature groups

  Critical Path:
  - 3 test files MUST be created before committing related features
  - 2 test files exist but are untracked (easy fix - just add them)
  - Several diffs need examination to write appropriate commit messages

  Recommended Approach:
  1. Create missing test files first (loops maths, nmrpipe rdcs, pales_lib)
  2. Add existing untracked test files
  3. Examine remaining diffs to understand changes
  4. Execute commits in the recommended order
  5. Verify each commit with tests before proceeding to next

  This staged approach ensures:
  - Each commit is logical and self-contained
  - All features have test coverage
  - Dependencies are committed in order
  - No broken states in git history

  The plan is now complete! Would you like me to exit plan mode and help you execute any of these commits?
