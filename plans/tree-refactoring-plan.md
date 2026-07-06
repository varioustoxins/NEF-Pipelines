# Plan: Refactor tree.py to Address TODOs

**STATUS: PARTIALLY IMPLEMENTED** ⚠️

**What was implemented:**
- ✅ `NefNode` custom class created in `tree.py` (line 72)
- ✅ Uses `EntryPart` enum for node types (imported line 26)
- ✅ Properties for namespace, entry_part, frame_name, loop_category, saveframe, loop

**What remains:**
- ❌ Still **10 TODOs** in `tree.py` (plan addressed 6)
- ❌ Helper function segmentation not fully completed
- ❌ Some functions still too long

**Current state**: Core infrastructure (NefNode class, EntryPart enum) implemented, but refactoring to split long functions and remove remaining TODOs incomplete.

---

## Context

The `tree.py` file has accumulated several TODOs requesting code improvements to reduce complexity, use EntryPart enum instead of string literals, improve naming clarity, and provide type-safe access to node metadata. This refactoring addresses 6 TODOs while maintaining all existing functionality.

## Current Issues

**File:** `src/nef_pipelines/tools/entry/tree.py`

1. **Lines 321-323**: `_filter_tree_by_namespace()` is too long (73 lines) - should be segmented into helper functions
2. **Line 322**: Uses string literals `node.data["node_type"] == "frame"` instead of EntryPart enum
3. **Lines 644-645**: `_build_nef_tree_structure()` is too long (98 lines) - should be subdivided
4. **Line 644**: Should store saveframe/loop structures in nodes for better namespace parsing
5. **Line 682**: Uses `node.data[]` dictionary access instead of properties
6. **Line 772**: Terminology "protected" is confusing - should be simpler

## Design Decisions

### Use EntryPart Enum for Node Types

Use the existing `EntryPart` enum from namespace_lib.py for node type classification:
- Reuses existing, well-tested enum
- Direct mapping: Saveframe → frame nodes, Loop → loop nodes, FrameTag/LoopTag → tag nodes
- Consistent with namespace extraction code

### Custom NefNode Subclass with Properties

**Create NefNode subclass of treelib.Node** with properties:
- treelib supports custom node classes via `tree.create_node(..., node_class=NefNode, ...)`
- Provides actual properties instead of dictionary access
- Type-safe with IDE completion
- Stores saveframe/loop objects for richer namespace parsing

```python
class NefNode(Node):
    def __init__(self, namespace: str, entry_part: EntryPart,
                 frame_name: Optional[str] = None,
                 loop_category: Optional[str] = None,
                 saveframe: Optional[Saveframe] = None,
                 loop: Optional[Loop] = None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.namespace = namespace
        self.entry_part = entry_part
        self.frame_name = frame_name
        self.loop_category = loop_category
        self.saveframe = saveframe
        self.loop = loop
```

Benefits: True properties, type safety, stores full structures, cleaner code

## Implementation Plan

### Task 1: Create NefNode Custom Class

**Location**: tree.py ~line 50 (after imports, before tree command definition)

Create custom Node subclass with properties:

```python
class NefNode(Node):
    """\
    Custom tree node for NEF structure with typed properties.

    Extends treelib.Node to add NEF-specific metadata as properties
    instead of dictionary access.
    """

    def __init__(
        self,
        namespace: str,
        entry_part: EntryPart,
        frame_name: Optional[str] = None,
        loop_category: Optional[str] = None,
        saveframe: Optional[Saveframe] = None,
        loop: Optional[Loop] = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.namespace = namespace
        self.entry_part = entry_part
        self.frame_name = frame_name
        self.loop_category = loop_category
        self.saveframe = saveframe
        self.loop = loop
```

**Required import additions**:
```python
from pynmrstar import Saveframe, Loop  # Add Loop to existing import
from nef_pipelines.lib.namespace_lib import EntryPart  # Add to imports
```

### Task 2: Segment _filter_tree_by_namespace()

**Extract 3 helper functions** (insert ~line 320):

1. `_collect_namespaces_from_tree(tree: Tree) -> Tuple[Set[str], List[str]]`
   - Scans NefNode instances and collects namespaces using `.namespace` property
   - Identifies null namespaces using `.entry_part` property
   - Returns (all_namespaces, null_namespace_nodes)
   - ~20 lines

2. `_filter_frames_by_namespace(tree: Tree, included_namespaces: Set[str]) -> Set[str]`
   - Finds frame nodes using `.entry_part == EntryPart.Saveframe`
   - Checks `.namespace in included_namespaces`
   - Returns set of kept frame IDs
   - ~12 lines

3. `_filter_frame_descendants_by_namespace(tree: Tree, frame_ids: Set[str], included_namespaces: Set[str]) -> Set[str]`
   - Filters descendants within kept frames
   - Uses `.namespace` property for filtering
   - Preserves ancestor chains
   - Returns all node IDs to keep
   - ~25 lines

**Refactored main function** becomes ~25 lines (was 73):
```python
def _filter_tree_by_namespace(tree, namespace_selectors, no_initial_selection):
    # Collect and check namespaces
    all_namespaces, null_nodes = _collect_namespaces_from_tree(tree)
    _warn_null_namespaces(null_nodes)

    # Determine included namespaces
    included = filter_namespaces(all_namespaces, namespace_selectors, ...)

    # Filter frames then descendants
    kept_frames = _filter_frames_by_namespace(tree, included)
    nodes_to_keep = _filter_frame_descendants_by_namespace(tree, kept_frames, included)

    return build_filtered_tree_from_retained_nodes(tree, nodes_to_keep)
```

### Task 3: Segment _build_nef_tree_structure()

**Extract 2 helper functions** (insert ~line 645):

1. `_add_frame_to_tree(tree: Tree, frame: Saveframe) -> None`
   - Creates NefNode for frame using `node_class=NefNode`
   - Passes saveframe object: `saveframe=frame`
   - Sets properties: `namespace`, `entry_part=EntryPart.Saveframe`, `frame_name`
   - Adds frame tag nodes as children (also using NefNode)
   - Tag nodes use `entry_part=EntryPart.FrameTag`
   - ~30 lines

2. `_add_loop_to_tree(tree: Tree, frame: Saveframe, loop: Loop) -> None`
   - Creates NefNode for loop using `node_class=NefNode`
   - Passes loop object: `loop=loop`
   - Sets properties: `namespace`, `entry_part=EntryPart.Loop`, `frame_name`, `loop_category`
   - Adds loop column tag nodes as children (also using NefNode)
   - Tag nodes use `entry_part=EntryPart.LoopTag`
   - ~35 lines

**Example node creation**:
```python
tree.create_node(
    tag=f"{frame.name} \\[frame: {loop_count} {loops_text}]",
    identifier=frame_id,
    parent="entry",
    node_class=NefNode,
    namespace=frame_namespace,
    entry_part=EntryPart.Saveframe,
    frame_name=frame.name,
    saveframe=frame,
)
```

**Refactored main function** becomes ~15 lines (was 98):
```python
def _build_nef_tree_structure(entry: Entry) -> Tree:
    tree = Tree()
    tree.create_node(tag=entry.entry_id, identifier="entry")

    for frame in entry.frame_list:
        _add_frame_to_tree(tree, frame)
        for loop in frame.loops:
            _add_loop_to_tree(tree, frame, loop)

    return tree
```

### Task 4: Simplify "protected" Terminology

**Function**: `_expand_tree_with_children()` (line 773)

**Changes**:
- Rename parameter: `protected_ids` → `descendants`
- Rename variable in caller: `protected_descendants` → `descendants`
- Update docstring to use simpler "descendants" terminology
- Update call site in `_expand_filtered_tree_with_children_of_nodes()`

**Rationale**: "Descendants" is clearer and more direct than "protected descendants" or "preserved descendants"

### Task 5: Update All Code to Use NefNode Properties

**Throughout tree.py**, replace node.data[] access with properties:
- `node.data["namespace"]` → `node.namespace`
- `node.data["node_type"] == "frame"` → `node.entry_part == EntryPart.Saveframe`
- `node.data["frame_name"]` → `node.frame_name`
- `node.data["loop_category"]` → `node.loop_category`

**Entry part mappings**:
- Frame nodes: `node.entry_part == EntryPart.Saveframe`
- Loop nodes: `node.entry_part == EntryPart.Loop`
- Frame tag nodes: `node.entry_part == EntryPart.FrameTag`
- Loop tag nodes: `node.entry_part == EntryPart.LoopTag`

**Functions to update**:
- `_filter_by_namespace()` (lines 396-443)
- `_expand_filtered_tree_with_children_of_nodes()` (line 283)
- All extracted helper functions from Tasks 2-3
- Any other code accessing node.data for namespace/type information

**Note**: Root "entry" node may still use basic Node class, not NefNode

## Implementation Sequence

**Phase 1: Create NefNode Class**
1. Add NefNode class definition with properties
2. Add required imports (EntryPart, Loop to imports)
3. Test: `nefl test src/nef_pipelines/tests/entry/test_tree.py` (should still pass with no tree changes yet)

**Phase 2: Update Tree Building**
4. Extract `_add_frame_to_tree()` helper using NefNode
5. Extract `_add_loop_to_tree()` helper using NefNode
6. Update `_build_nef_tree_structure()` to use helpers
7. Test after each extraction to ensure tree still builds correctly

**Phase 3: Update Filtering Functions**
8. Extract `_collect_namespaces_from_tree()` using node properties
9. Extract `_filter_frames_by_namespace()` using node properties
10. Extract `_filter_frame_descendants_by_namespace()` using node properties
11. Update `_filter_tree_by_namespace()` to use helpers
12. Update `_filter_by_namespace()` to use node properties
13. Test after each change

**Phase 4: Final Cleanup**
14. Rename "protected" → "descendants" throughout
15. Update `_expand_filtered_tree_with_children_of_nodes()` to use node properties
16. Run full test suite
17. Verify no node.data[] accesses remain (except possibly entry node)

## Critical Files

- `src/nef_pipelines/tools/entry/tree.py` - Main refactoring target
- `src/nef_pipelines/lib/namespace_lib.py` - Reference for EntryPart enum and NO_NAMESPACE
- `src/nef_pipelines/tests/entry/test_tree.py` - Verification tests
- `src/nef_pipelines/lib/tree_lib.py` - Tree utility functions
- `src/nef_pipelines/lib/util.py` - For warn() function

## Verification

### Tests to Pass
```bash
# Run tree tests
nefl test src/nef_pipelines/tests/entry/test_tree.py

# Run namespace lib tests (NefNode might be used elsewhere)
nefl test src/nef_pipelines/tests/lib/test_namespace_lib.py

# Run full test suite to catch any edge cases
nefl test
```

### Critical Test Cases
From `test_tree.py`:
- `test_tree_basic` - Basic tree structure unchanged
- `test_tree_stdin` - Stdin input handling
- `test_tree_filter_tag` - Tag filtering with properties
- `test_tree_filter_loop` - Loop filtering with properties
- `test_tree_filter_frame` - Frame filtering with properties
- `test_tree_multiple_filters` - AND logic still works
- `test_tree_children_flag` - Descendant preservation with new naming
- `test_tree_selector_syntax` - frame.loop:tag syntax
- `test_tree_namespace_*` - Namespace filtering using EntryPart enum
- `test_tree_case_sensitive` - Case sensitivity preserved

### Verification Checklist
- [ ] All existing tests pass without modification
- [ ] No changes to tree output format or structure
- [ ] NefNode properties accessible: `.namespace`, `.entry_part`, `.frame_name`, etc.
- [ ] Saveframe/loop objects stored and accessible: `.saveframe`, `.loop`
- [ ] EntryPart enum used consistently for node type checks
- [ ] Main functions reduced to 15-25 lines (from 73-98 lines)
- [ ] Code follows British spelling (colour, etc.)
- [ ] No remaining node.data[] accesses (except entry node if needed)

### Expected Impact
- **Lines of code**: Net increase ~80 lines (NefNode class + helpers)
- **Main function complexity**: 80-85% reduction
- **Type safety**: Properties + EntryPart enum instead of strings
- **Richer metadata**: Full saveframe/loop objects available for advanced parsing
- **Maintainability**: Single-responsibility helpers, cleaner property access

## Benefits of This Refactoring

### Immediate Benefits

1. **Type Safety**: NefNode properties and EntryPart enum prevent string literal typos
2. **IDE Support**: Auto-completion for `node.namespace`, `node.entry_part`, etc.
3. **Cleaner Code**: `node.namespace` instead of `node.data["namespace"]`
4. **Better Organization**: Long functions (73-98 lines) split into focused helpers (12-35 lines)
5. **Rich Metadata**: Full saveframe/loop objects accessible via `.saveframe` and `.loop` properties

### Use Cases Enabled by Saveframe/Loop Storage

1. **Advanced Namespace Parsing**: Access full saveframe structure without re-parsing
2. **Richer Filtering**: Filter by saveframe/loop metadata beyond just names
3. **Better Error Messages**: Can reference actual NEF objects in warnings
4. **Future Extensions**: Foundation for more sophisticated tree operations
5. **Debugging**: Direct access to NEF objects from tree nodes

### Code Quality Improvements

- **Main functions**: 15-25 lines (was 73-98 lines) - 80-85% reduction
- **Single-responsibility helpers**: Each helper does one thing well
- **Type-safe property access**: No more dict key typos
- **Reusable helper functions**: Can be tested independently
- **Consistent enum usage**: EntryPart enum throughout instead of magic strings
