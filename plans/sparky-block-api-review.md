# SparkyBlock API Review: Minimal but Powerful

**STATUS: IMPLEMENTED IN .AWAITING FILES** ✅

**Implementation location:**
- ✅ `transcoders/sparky/sparky_block_lib.py.awaiting`
- ✅ `transcoders/sparky/sparky_block_parser.py.awaiting`
- ✅ `transcoders/sparky/sparky_structures.py.awaiting`
- ✅ Tests: `test_sparky_block_lib.py.awaiting`, `test_sparky_parser_lib.py.awaiting`

**Implementation matches API review recommendations:**
- ✅ Core: `SparkyBlock` dataclass with `block_type`, `content`, `parent`
- ✅ Core: `iter(mode, recursive)` and `__iter__()` methods
- ✅ Helper functions (standalone, not methods - cleaner design):
  - `get_lines_from_block()` - extract text lines
  - `find_child_block()`, `find_child_blocks()` - child search
  - `get_parent_blocks(depth)` - ancestor navigation
  - `find_block_by_path()` - path-based search
  - `find_block()`, `find_all_blocks()` - list utilities

**Design note**: Implementation uses standalone helper functions rather than methods on the class, following the plan's "minimal but powerful" philosophy even more strictly. The dataclass stays minimal; navigation logic is external.

---

## Current API (13 methods, 11 non-deprecated)

### Data Access
- `get_lines()` → List[str]

### Child Search
- `find_child(type)` → Optional[SparkyBlock]
- `find_children(type)` → List[SparkyBlock]

### Parent Navigation
- `get_parent(depth=1)` → Optional[SparkyBlock]
- `get_parent_path()` → List[SparkyBlock]
- `get_path_string(sep)` → str
- `get_depth()` → int

### Iteration
- `iter(mode, recursive)` → Iterator ✅ CORE
- `__iter__()` → Iterator ✅ CORE
- `iter_blocks(recursive)` → Iterator [DEPRECATED]
- `iter_content(recursive)` → Iterator [DEPRECATED]

### Path-based Search
- `find_by_path(path, sep)` → Optional[SparkyBlock]
- `find_all_by_path(path, sep, recursive)` → List[SparkyBlock]

---

## Analysis: What's Essential?

### ✅ Must Keep (Core Primitives)

**1. `iter(mode, recursive)` - Universal iterator**
- Can express all iteration patterns
- Cannot be simplified further
- Powers everything else

**2. `__iter__()` - Pythonic iteration**
- Delegates to iter()
- Makes blocks feel like native Python collections
- Zero maintenance cost (one-liner)

**3. Attributes: `block_type`, `content`, `parent`**
- Direct data access is fundamental
- Users can traverse manually if needed

### ❓ Questionable (Can be expressed with primitives)


**`get_lines()`**
```python
# Current
lines = block.get_lines()

# Could be
lines = list(block.iter(IterMode.LINES_ONLY))
```
**Verdict**: KEEP - Very common operation, saves boilerplate
#TODO: IterMode should be SparkyBlockItermode

**`find_child(type)` / `find_children(type)`**
```python
# Current
condition = molecule.find_child("condition")
conditions = molecule.find_children("condition")

# Could be
condition = next((b for b in molecule.iter(IterMode.BLOCKS_ONLY) if b.block_type == "condition"), None)
conditions = [b for b in molecule.iter(IterMode.BLOCKS_ONLY) if b.block_type == "condition"]
```
**Verdict**: KEEP - Extremely common pattern, much cleaner API

**`get_parent(depth)` / `get_parent_path()` / `get_depth()`**
```python
# Current
grandparent = block.get_parent(2)
path = block.get_parent_path()
depth = block.get_depth()

# Could be
grandparent = block.parent.parent if block.parent and block.parent.parent else None
path = []
current = block
while current:
    path.append(current)
    current = current.parent
path.reverse()
```
**Verdict**: BORDERLINE - Not frequently used, but traversing .parent is tedious
#TODO: make it getParents with a depth of None

**`get_path_string()`**
```python
# Current
path_str = block.get_path_string()  # "molecule/condition/resonances"

# Could be
path_str = "/".join(b.block_type for b in block.get_parent_path())
```
**Verdict**: REMOVE - Trivial wrapper, rarely used
#TODO: doit


**`find_by_path()` / `find_all_by_path()`**
```python
# Current
resonances = molecule.find_by_path("condition/resonances")

# Could be
condition = molecule.find_child("condition")
resonances = condition.find_child("resonances") if condition else None
```
**Verdict**: KEEP `find_by_path()`, REMOVE `find_all_by_path()` - Path finding is useful, but "find all" is overly complex
TODO: i agree
---

## Proposed Minimal API (8 methods)

### Core (2 methods)
```python
def iter(mode: IterMode = BOTH, recursive: bool = False) -> Iterator
def __iter__() -> Iterator  # Delegates to iter()
```
#TODO: no not this one

### Convenience (6 methods)
```python
# Data access
def get_lines() -> List[str]

# Child search (common operations)
def find_child(block_type: str) -> Optional[SparkyBlock]
def find_children(block_type: str) -> List[SparkyBlock]

# Navigation (useful for tree walking)
def get_parent(depth: int = 1) -> Optional[SparkyBlock]
def get_depth() -> int

# Path-based search (complex but powerful)
def find_by_path(path: str, separator: str = "/") -> Optional[SparkyBlock]
```
#TODO: we don't need get_depth

### Removed (5 methods)
```python
# ❌ get_parent_path() - Easy to implement externally
# ❌ get_path_string() - Trivial wrapper
# ❌ find_all_by_path() - Too complex, rarely used
# ❌ iter_blocks() - DEPRECATED, use iter(BLOCKS_ONLY)
# ❌ iter_content() - DEPRECATED, use iter(BOTH)
```

---

## Usage Comparison

### Before (Current API - 13 methods)
```python
# Multiple ways to do the same thing
blocks = block.iter_blocks()  # DEPRECATED
blocks = block.iter(IterMode.BLOCKS_ONLY)

lines = block.get_lines()
lines = list(block.iter(IterMode.LINES_ONLY))

path = block.get_path_string()
path = "/".join(b.block_type for b in block.get_parent_path())
```

### After (Minimal API - 8 methods)
```python
# One obvious way for each operation
blocks = block.iter(IterMode.BLOCKS_ONLY)
for item in block:  # Or just iterate directly
    ...

lines = block.get_lines()  # Common operation, kept

# Users implement custom helpers if needed
def get_path_string(block):
    path = []
    while block:
        path.append(block.block_type)
        block = block.parent
    return "/".join(reversed(path))
```

---

## Recommendation

**Remove these 5 methods:**
1. ✅ `iter_blocks()` - Already marked deprecated
2. ✅ `iter_content()` - Already marked deprecated
3. ⚠️ `get_parent_path()` - Check usage first
4. ⚠️ `get_path_string()` - Check usage first
5. ⚠️ `find_all_by_path()` - Check usage first

**Keep these 8 methods:**
- ✅ Core: `iter()`, `__iter__()`
- ✅ Convenience: `get_lines()`, `find_child()`, `find_children()`
- ✅ Navigation: `get_parent()`, `get_depth()`
- ✅ Advanced: `find_by_path()`

This gives a **minimal, powerful, and learnable** API.

---

## Power-to-Complexity Ratio

| API Size | Methods | Learning Curve | Expressiveness |
|----------|---------|----------------|----------------|
| Current | 13 | Medium | High |
| Proposed | 8 | Low | High |
| Absolute Minimum | 2 | Very Low | Medium |

The proposed 8-method API hits the sweet spot: powerful enough for all use cases, small enough to learn in 5 minutes.

---

## Usage Analysis (Actual Data)

Checked actual usage in codebase:

| Method | External Usage | Internal Usage | Verdict |
|--------|---------------|----------------|---------|
| `get_parent_path()` | **0** | 1 (called by `get_path_string()`) | ✅ SAFE TO REMOVE |
| `get_path_string()` | **0** | 0 | ✅ SAFE TO REMOVE |
| `find_all_by_path()` | **0** | 1 (recursive self-call) | ✅ SAFE TO REMOVE |

**Finding**: All 3 questionable methods have ZERO external usage! They're only used internally or not at all.

### Specific Usages

1. **`get_parent_path()`**: Only called internally by `get_path_string()` at line 658
2. **`get_path_string()`**: Not used anywhere in the codebase
3. **`find_all_by_path()`**: Only calls itself recursively at line 823, no external callers

---

## Final Recommendation: Remove 5 Methods

**Safe to remove immediately** (no external usage):
1. ✅ `iter_blocks()` - Deprecated, use `iter(BLOCKS_ONLY)`
2. ✅ `iter_content()` - Deprecated, use `iter(BOTH)`
3. ✅ `get_parent_path()` - Only used by `get_path_string()`
4. ✅ `get_path_string()` - Unused
5. ✅ `find_all_by_path()` - Unused (only recursive self-call)

**Result**: Clean 8-method API with zero breaking changes to external code!

---

## Next Steps

1. **Remove the 5 methods** from `SparkyBlock` class
2. **Update tests** - Remove tests for deleted methods
3. **Update docstrings** - Document the minimal 8-method API
4. **No deprecation needed** - No external code is using these methods
