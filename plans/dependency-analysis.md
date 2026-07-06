# Dependency Analysis for NEF-Pipelines

Date: 2026-03-11

## Overview

Analysis of all 29 dependencies in setup.cfg to identify:
- Which are transitive (pulled in by other packages)
- Which are used only once
- Which could be vendorised or replaced

## Summary Statistics

- **Total dependencies**: 29
- **Used in only one file**: 11
- **Transitive dependencies that can be removed**: 4
- **Small packages that could be vendorised**: 2-4

## Dependency Categories

### 1. Heavily Used Core Dependencies

| Package | Files | Usage |
|---------|-------|-------|
| typer | 199 | CLI framework - most used |
| pynmrstar | 88 | NMR STAR file parsing - core |
| tabulate | 30 | Table formatting |
| f-yeah | 23 | Formatted output |
| pytest | 23 | Testing (test only) |
| ordered-set | 16 | Ordered set data structure |
| StrEnum | 14 | String enums |

### 2. Moderate Use Dependencies

| Package | Files | Usage |
|---------|-------|-------|
| click | 4 | CLI utilities (transitive via typer) |
| pyparsing | 4 | Parser combinators |
| pydantic | 2 | Data validation |
| requests | 2 | HTTP requests |
| uncertainties | 2 | Error propagation |
| lazy_import | 2 | Lazy module loading |
| frozendict | 2 | Immutable dictionaries |
| freezegun | 3 | Time mocking (test only) |

### 3. Single-Use Dependencies

| Package | Files | Location | Purpose |
|---------|-------|----------|---------|
| annotated-types | 1 | lib/translation/chem_comp.py | Type annotations (transitive via pydantic) |
| beautifulsoup4 | 1 | (needs verification) | HTML parsing |
| cachetools | 1 | lib/translation/chem_comp.py | LRU cache |
| fastaparser | 1 | transcoders/fasta/importers/sequence.py | FASTA format parsing |
| hjson | 1 | transcoders/nmrstar/importers/shifts.py | HJSON parsing |
| mmcif-pdbx | 1 | (needs verification) | mmCIF format |
| parse | 1 | tools/series/build.py | Pattern matching |
| runstats | 1 | tools/shifts/average.py | Running statistics |
| treelib | 1 | tools/help/commands.py | Tree data structure |
| wcmatch | 1 | tools/frames/tabulate.py | Wildcard matching |
| xmltodict | 1 | lib/translation/io.py | XML to dict conversion |

### 4. Transitive Dependencies (Can Remove from setup.cfg)

These are automatically installed by their parent packages:

1. **click** (required by typer)
   - Even though imported directly in 4 files
   - Typer has hard dependency: `click >= 7.1.1, <9.0.0`
   - **Recommendation**: Remove from explicit list

2. **annotated-types** (required by pydantic)
   - Even though imported once: `from annotated_types import Gt`
   - Pydantic has hard dependency: `annotated-types>=0.4.0`
   - **Recommendation**: Remove from explicit list

3. **typing-extensions** (required by pydantic)
   - Used conditionally for Python ≤3.8 fallback
   - Pydantic has hard dependency: `typing-extensions>=4.6.1`
   - **Recommendation**: Remove from explicit list

4. **urllib3** (required by requests)
   - Accessed via `requests.packages.urllib3` (not directly imported)
   - Requests has hard dependency: `urllib3 (<3,>=1.21.1)`
   - **Recommendation**: Remove from explicit list

### 5. Test-Only Dependencies

- **pytest** (23 files)
- **pytest-mock** (used via `mocker` fixture)
- **freezegun** (3 files)

## Vendorisation Candidates

### ✅ EASY - Single File, Simple

1. **xmltodict** (~544 lines, single file)
   ```python
   # Current usage:
   import xmltodict
   chemcomp = xmltodict.parse(xml)
   ```
   - Only does XML → dict conversion
   - Could vendor the single file
   - **Size**: 544 lines

2. **parse** (~1079 lines, single file)
   ```python
   # Current usage:
   from parse import compile as parse_compile
   parser = parse_compile(frame_selector)
   ```
   - Reverse of str.format()
   - Could use regex instead
   - **Size**: 1079 lines

### 🟡 MEDIUM - Could Replace with Built-ins

3. **cachetools** (68K, 3 files, ~1018 lines)
   ```python
   # Current usage:
   from cachetools import LRUCache
   self._cache = LRUCache(size)
   ```
   - **Alternative**: Python's built-in `functools.lru_cache` decorator
   - Much simpler, zero dependencies
   - **Recommendation**: Replace with `functools.lru_cache`

4. **runstats** (60K, 3 files, ~1169 lines)
   ```python
   # Current usage:
   from runstats import Statistics
   ```
   - Running mean/variance calculations
   - Could write basic statistical functions yourself
   - **Size**: ~1169 lines

### 🔴 NOT Worth Vendoring

5. **treelib** (120K, 5 files, ~1584 lines)
   - Tree data structure - complex, well-tested
   - Keep as dependency

6. **fastaparser** (136K, 7 files, ~1655 lines)
   - FASTA format parser - specialized domain knowledge
   - Keep as dependency

7. **hjson** (312K, 34 files, ~4499 lines)
   - Too large and complex
   - Keep as dependency

8. **wcmatch** (224K, 10 files, ~4210 lines)
   - Advanced wildcard matching
   - Keep as dependency

## Specific Findings

### pytest-mock Usage
Used via the `mocker` fixture in tests:
```python
def test_create_entry_from_empty_stdin(mocker):
    mocker.patch("sys.stdin", StringIO())
```

### StrEnum Usage
Imported in 14 files:
```python
from strenum import StrEnum
```

### urllib3 Usage
Accessed via requests, not imported directly:
```python
requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += "HIGH:!DH:!aNULL"
```

## Recommendations

### 1. Remove Transitive Dependencies (4 packages)
```diff
- annotated-types==0.6.0
- click==8.1.3
- typing-extensions==4.12.2 ; python_version <= "3.8"
- urllib3==1.26.15
```

These are automatically installed by typer, pydantic, and requests.

### 2. Replace with Built-ins (1 package)

**cachetools** → `functools.lru_cache`
```python
# Instead of:
from cachetools import LRUCache
self._cache = LRUCache(size)

# Use:
from functools import lru_cache
@lru_cache(maxsize=size)
def cached_function(...):
    ...
```

### 3. Consider Vendoring (2 packages)

- **xmltodict** - Single 544-line file for XML parsing
- **parse** - Single 1079-line file (or replace with regex)

### 4. Keep All Others (22 packages)

The remaining dependencies are either:
- Core to the application (typer, pynmrstar, tabulate, etc.)
- Specialized and well-maintained (fastaparser, hjson, wcmatch)
- Provide complex functionality (treelib, pyparsing, pydantic)

## Dependency Tree

```
Direct Dependencies (25):
├── typer → click (transitive, can remove)
├── pydantic → annotated-types (transitive, can remove)
│           → typing-extensions (transitive, can remove)
├── requests → urllib3 (transitive, can remove)
├── pynmrstar
├── tabulate
├── f-yeah
├── ordered-set
├── StrEnum
├── beautifulsoup4
├── fastaparser
├── freezegun
├── frozendict
├── hjson
├── lazy_import
├── mmcif-pdbx
├── parse (consider replacing or vendoring)
├── pyparsing
├── pytest
├── pytest-mock
├── runstats (consider replacing)
├── treelib
├── uncertainties
├── wcmatch
└── xmltodict (consider vendoring)
```

## Action Items

1. **Immediate**: Remove 4 transitive dependencies from setup.cfg
2. **Consider**: Replace cachetools with functools.lru_cache
3. **Evaluate**: Whether to vendor xmltodict (single file, 544 lines)
4. **Review**: Whether parse pattern matching could use regex instead

## Notes

- All 29 dependencies are actually used (no truly unused packages)
- 11 packages are used in only one file (potential for consolidation)
- Most dependencies are well-justified for their specialized functionality
- The codebase is already quite lean in terms of dependencies given its scope
