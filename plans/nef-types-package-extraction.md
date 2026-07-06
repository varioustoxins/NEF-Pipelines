# Plan: Extract Shared Types into nef-types Package

**STATUS: NOT IMPLEMENTED**

The circular dependency between streamfitter and nef-pipelines still exists:
- streamfitter depends on nef-pipelines (via `dependencies` in pyproject.toml)
- streamfitter imports from `nef_pipelines.lib.interface` (FitType, NoiseInfoSource, FailureHandling, FailureOutput)
- No nef-types package has been created

**Current workaround**: Still using `uv pip install --no-deps -e /path/to/streamfitter` for local development.

---

## Problem Statement

Currently, streamfitter and nef-pipelines have a circular dependency:

```
streamfitter → depends on → nef-pipelines (for FitType in lib.interface)
nef-pipelines → depends on → streamfitter (for fitting functionality)
```

**Consequences:**
- Installing streamfitter pulls in nef-pipelines
- nef-pipelines in streamfitter's dependencies has old typer/click versions
- This downgrades nef-pipelines' dependencies (typer 0.23.2 → 0.7.0)
- Breaks nef-pipelines functionality
- Difficult to develop both packages simultaneously
- Can't install streamfitter standalone without pulling full nef-pipelines

**Current Workaround:**
```bash
uv pip install --no-deps -e /path/to/streamfitter
```
This is fragile and error-prone.

## Solution: Create nef-types Package

Extract shared type definitions and interfaces into a lightweight standalone package that both packages depend on.

```
nef-types (new package)
    ↑                ↑
    |                |
nef-pipelines   streamfitter
    ↓
streamfitter (optional)
```

**Benefits:**
- No circular dependencies
- Single source of truth for shared types
- Each package can be developed/installed independently
- Minimal package with no heavy dependencies
- Future-proof for other tools that need NEF types

## Package Structure

### nef-types Package

```
nef-types/
├── pyproject.toml
├── setup.cfg
├── setup.py
├── README.md
├── LICENSE
└── src/
    └── nef_types/
        ├── __init__.py
        ├── fit_types.py      # FitType and fitting-related types
        ├── nef_types.py      # NEF-specific types if needed
        └── py.typed          # PEP 561 marker for type checking
```

### Initial Types to Extract

**From nef_pipelines.lib.interface:**
- `FitType` (enum) - Currently used by streamfitter
- Any other types/interfaces that streamfitter or external tools need

**Potential future additions:**
- `ChemicalShiftType`
- `RestraintType`
- Common data structure interfaces
- Protocol definitions for plugins

## Implementation Steps

### Phase 1: Create nef-types Package

1. **Create repository/directory structure:**
   ```bash
   mkdir -p ~/Dropbox/git/nef-types
   cd ~/Dropbox/git/nef-types
   mkdir -p src/nef_types
   ```

2. **Create pyproject.toml:**
   ```toml
   [build-system]
   requires = ["setuptools>=64", "setuptools_scm>=8"]
   build-backend = "setuptools.build_meta"

   [project]
   name = "nef-types"
   dynamic = ["version"]
   description = "Shared type definitions for NEF (NMR Exchange Format) tools"
   readme = "README.md"
   requires-python = ">=3.9"
   license = {text = "MIT"}
   authors = [
       {name = "Your Name", email = "your.email@example.com"}
   ]
   classifiers = [
       "Development Status :: 4 - Beta",
       "Intended Audience :: Science/Research",
       "License :: OSI Approved :: MIT License",
       "Programming Language :: Python :: 3",
       "Programming Language :: Python :: 3.9",
       "Programming Language :: Python :: 3.10",
       "Programming Language :: Python :: 3.11",
       "Programming Language :: Python :: 3.12",
   ]
   dependencies = []  # No dependencies - just types!

   [project.optional-dependencies]
   dev = [
       "pytest>=7.0",
       "mypy>=1.0",
   ]

   [tool.setuptools_scm]
   version_scheme = "no-guess-dev"
   ```

3. **Create setup.cfg (minimal):**
   ```ini
   [metadata]
   name = nef-types

   [options]
   package_dir =
       = src
   packages = find:
   python_requires = >=3.9

   [options.packages.find]
   where = src
   ```

4. **Create setup.py:**
   ```python
   from setuptools import setup

   if __name__ == "__main__":
       setup(use_scm_version={"version_scheme": "no-guess-dev"})
   ```

5. **Create src/nef_types/__init__.py:**
   ```python
   """Shared type definitions for NEF (NMR Exchange Format) tools."""

   from nef_types.fit_types import FitType

   __all__ = ["FitType"]

   try:
       from importlib.metadata import version
       __version__ = version("nef-types")
   except ImportError:
       __version__ = "unknown"
   ```

6. **Create src/nef_types/fit_types.py:**
   ```python
   """Fitting-related type definitions."""

   from enum import Enum

   class FitType(Enum):
       """Types of fitting algorithms available."""
       LINEAR = "linear"
       # Add other fit types as needed
       # Copy from current nef_pipelines.lib.interface.FitType
   ```

7. **Create src/nef_types/py.typed:**
   ```
   # PEP 561 marker file for type checking support
   ```

8. **Create README.md:**
   ```markdown
   # nef-types

   Shared type definitions for NEF (NMR Exchange Format) tools.

   This package provides common type definitions, enums, and interfaces used by
   NEF-related tools such as nef-pipelines and streamfitter. It has zero runtime
   dependencies and serves as a lightweight contract between packages.

   ## Installation

   ```bash
   pip install nef-types
   ```

   ## Usage

   ```python
   from nef_types import FitType

   fit_type = FitType.LINEAR
   ```
   ```

### Phase 2: Update streamfitter

1. **Update streamfitter/pyproject.toml dependencies:**
   ```toml
   dependencies = [
       "numpy>=1.26.4",
       "jax>=0.4.28",
       "lmfit>=1.3.1",
       "runstats>=2.0.0",
       "tabulate==0.8.9",
       "classprop>=0.1.1",
       "nef-types>=0.1.0",  # NEW: lightweight types package
       # REMOVED: "nef-pipelines",  # No longer a required dependency!
       "pynmrstar==3.3.4",
       "jaxlib>=0.4.28",
   ]

   [project.optional-dependencies]
   nef = [
       "nef-pipelines>=0.1.120",  # Optional for NEF integration
   ]
   ```

2. **Update streamfitter imports:**

   **Before:**
   ```python
   from nef_pipelines.lib.interface import FitType
   ```

   **After:**
   ```python
   from nef_types import FitType
   ```

3. **Search and replace across streamfitter:**
   ```bash
   cd /Users/garythompson/Dropbox/git/streamfitter
   grep -r "from nef_pipelines.lib.interface import FitType" src/
   # Replace all occurrences with: from nef_types import FitType
   ```

### Phase 3: Update nef-pipelines

1. **Add nef-types to nef-pipelines/setup.cfg:**
   ```ini
   install_requires =
       annotated-types~=0.6.0
       beautifulsoup4~=4.12.3
       # ... other dependencies ...
       nef-types>=0.1.0
       # ... rest of dependencies ...
   ```

2. **Update nef_pipelines/lib/interface.py:**

   **Before:**
   ```python
   from enum import Enum

   class FitType(Enum):
       LINEAR = "linear"
       # ...
   ```

   **After:**
   ```python
   # Re-export from nef-types for backward compatibility
   from nef_types import FitType

   __all__ = ["FitType"]
   ```

   This maintains backward compatibility for existing code that imports from nef_pipelines.lib.interface.

3. **Update nef-pipelines imports (if needed):**

   Most code should continue to work via the re-export, but you can optionally update imports to:
   ```python
   from nef_types import FitType
   ```

### Phase 4: Testing & Verification

1. **Test nef-types package:**
   ```bash
   cd ~/Dropbox/git/nef-types
   uv pip install -e ".[dev]"
   python -c "from nef_types import FitType; print(FitType.LINEAR)"
   pytest  # If you add tests
   ```

2. **Test streamfitter with nef-types:**
   ```bash
   cd ~/Dropbox/git/streamfitter
   uv pip install --no-deps -e .
   uv pip install nef-types  # or -e /path/to/nef-types
   python -c "import streamfitter; print('Streamfitter imports successfully')"
   ```

3. **Test nef-pipelines with nef-types:**
   ```bash
   cd ~/Dropbox/nef_pipelines/nef_pipelines
   uv pip install nef-types  # or -e /path/to/nef-types
   python -c "from nef_pipelines.lib.interface import FitType; print(FitType.LINEAR)"
   nef test  # Run full test suite
   ```

4. **Test integration (nef-pipelines + streamfitter):**
   ```bash
   uv pip install -e /path/to/nef-types
   uv pip install --no-deps -e /path/to/streamfitter
   uv pip install -e /path/to/nef-pipelines
   nef test  # Should pass all tests including streamfitter integration
   ```

## Development Workflow

### Local Development Setup

For working on all three packages simultaneously:

```bash
# Install nef-types in editable mode
uv pip install -e ~/Dropbox/git/nef-types

# Install streamfitter in editable mode (no deps needed, nef-types already installed)
uv pip install --no-deps -e ~/Dropbox/git/streamfitter

# Install nef-pipelines in editable mode
uv pip install -e ~/Dropbox/nef_pipelines/nef_pipelines
```

All changes to any package are immediately reflected without reinstalling!

### Publishing Workflow

1. **Publish nef-types first:**
   ```bash
   cd ~/Dropbox/git/nef-types
   python -m build
   twine upload dist/*
   ```

2. **Then publish streamfitter:**
   ```bash
   cd ~/Dropbox/git/streamfitter
   python -m build
   twine upload dist/*
   ```

3. **Finally publish nef-pipelines:**
   ```bash
   cd ~/Dropbox/nef_pipelines/nef_pipelines
   python -m build
   twine upload dist/*
   ```

## Migration Path

### Version 1 (Immediate - Backward Compatible)

- Create nef-types package
- nef-pipelines re-exports FitType from nef-types
- streamfitter uses nef-types
- Existing code using `nef_pipelines.lib.interface.FitType` continues to work

### Version 2 (Future - Cleanup)

- Deprecate re-export in nef-pipelines.lib.interface
- Update all nef-pipelines code to import from nef_types directly
- Remove re-export in next major version

## Future Enhancements

### Additional Types to Extract

As more integrations develop, consider moving:
- Chemical shift types and validation
- Restraint type definitions
- Spectrum metadata types
- Plugin protocols/interfaces
- Common data structure contracts

### Versioning Strategy

**nef-types semantic versioning:**
- MAJOR: Breaking changes to existing types
- MINOR: New types added (backward compatible)
- PATCH: Bug fixes, documentation

**Compatibility:**
- nef-types 0.x → nef-pipelines 0.1.120+
- nef-types 1.0 → nef-pipelines 0.2.0+

## Rollback Plan

If issues arise:

1. **Immediate rollback (streamfitter):**
   ```bash
   # Revert streamfitter to use nef-pipelines directly
   git revert <commit-hash>
   ```

2. **Keep nef-types for future:**
   - nef-types package is harmless even if unused
   - Can be adopted gradually

## Checklist

- [ ] Create nef-types repository/directory
- [ ] Implement nef-types package structure
- [ ] Copy FitType definition from nef-pipelines
- [ ] Add tests for nef-types
- [ ] Update streamfitter dependencies
- [ ] Update streamfitter imports
- [ ] Test streamfitter standalone
- [ ] Update nef-pipelines dependencies
- [ ] Add re-export in nef-pipelines.lib.interface
- [ ] Test nef-pipelines standalone
- [ ] Test integration (all packages together)
- [ ] Update documentation
- [ ] Publish nef-types to PyPI
- [ ] Update streamfitter on PyPI
- [ ] Update nef-pipelines on PyPI
- [ ] Update GitHub Actions CI
- [ ] Announce changes to users

## Notes

- **Timeline:** 1-2 days for implementation and testing
- **Breaking changes:** None (backward compatible via re-export)
- **Dependencies:** Zero runtime dependencies for nef-types
- **Maintenance:** Minimal - types change infrequently
