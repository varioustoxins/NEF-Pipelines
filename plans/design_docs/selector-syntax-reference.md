# Frame.Loop:Tag Selector Syntax Reference

## Overview

Selectors use `.` (dot) and `:` (colon) to specify what to select:
- **No dot** = frame-level (saveframe metadata only)
- **Has dot** = loop-level (loops within frames)
- **Colon** = tags/columns (after the selector type)

## Selector Patterns

| Selector | Frame | Loop | Frame Tags | Loop Tags | Description                                  |
|----------|-------|------|------------|----|----------------------------------------------|
| **Frame-Level (no dot)** |
| `frame` | name | None | [] | [] | Complete saveframe                           |
| `frame:tag` | name | None | [tag] | [] | Specific frame tag                           |
| `frame:tag1,tag2` | name | None | [tag1, tag2] | [] | Multiple frame tags                          |
| `:tag` | * | None | [tag] | [] | Frame tag in all frames                      |
| **Loop-Level (has dot)** |
| `frame.loop` | name | loop | [] | [] | Entire loop                                  |
| `frame.loop:col` | name | loop | [] | [col] | Specific loop column                         |
| `frame.loop:col1,col2` | name | loop | [] | [col1, col2] | Multiple loop columns                        |
| `frame.` | name | * | [] | [] | All loops in frame      |
| `frame.*` | name | * | [] | [] | All loops in frame (                |
| `.loop` | * | loop | [] | [] | Loop in all frames                           |
| `.loop:col` | * | loop | [] | [col] | Loop column in all frames                    |
| `.:col` | * | * | [] | [col] | Column in all loops/frames                   |
| **Wildcards** |
| `*` | * | None | [] | [] | All saveframes (all tags, no loops)          |
| `*:*` | * | None | [*] | [] | Wildcard frame tags in all frames            |
| `*.*` | * | * | [] | ['*'] | All loops in all frames (shows tags + loops) |
| `*.*:*` | * | * | [] | [*] | All columns in all loops                     |

**Note:** Empty `frame_tags=[]` means no frame tags selected, whether this means a wildcard is _context_ dependant.
Commands interpret this as selecting the frame. Similarly, `loop_tags=[]` means no loops selected and loop_tags = ['*']
means all loop tags (columns) selected.

## Examples

### Frame Metadata Operations

```bash
# Get sf_category from shifts frame
tool shifts:sf_category

# Get multiple frame tags
tool shifts:sf_category,sf_framecode

# Get tag from all frames
tool :sf_category
```

### Loop Operations

```bash
# Delete specific loop
loops delete shifts.chemical_shift

# Delete all loops in frame (explicit wildcard)
loops delete shifts.

# Select loop column
tool shifts.chemical_shift:atom_name

# Multiple columns
tool shifts.chemical_shift:atom_name,value

# Specific loop across all frames
loops delete .chemical_shift

# All loops in all frames
loops delete *.*
```

### Wildcard Patterns

```bash
# All saveframes (metadata only)
tool *

# All frame tags in all frames
tool *:*

# All loops in all frames
loops delete *.*

# All columns in all loops/frames
tool *.*:*
```

## Selector Rules

### Empty Parts Default to Wildcard (*)

- `.loop` = `*.loop` (loop in all frames)
- `frame.` = `frame.*` (all loops in frame)
- `:tag` = `*:tag` (tag in all frames)

### Multiple Values Use Commas

**Tags within a selector:**
```bash
frame:tag1,tag2           # Multiple frame tags in ONE selector
frame.loop:col1,col2      # Multiple loop columns in ONE selector
```

**Multiple selectors:**
```bash
frame1.loop1,frame2.loop2 # TWO separate selectors (comma before colon)
```

### Comma Context Matters

- **After `:` (colon)** → multiple tags/columns in ONE selector
  - `frame:tag1,tag2` = one selector with two tags
  - `frame.loop:col1,col2` = one selector with two columns

- **Before `:` or no `:`** → multiple separate selectors
  - `frame1.loop1,frame2.loop2` = two selectors
  - `frame1,frame2` = two selectors

## Breaking Change from v1.x

### Old Behavior (v1.x)

```bash
# Bare frame name selected ALL loops (implicit)
loops delete myshifts  # ← Deleted all loops in myshifts frame
```

### New Behavior (v2.0+)

```bash
# Bare frame name selects metadata ONLY
loops delete myshifts   # ← ERROR: no loop specified

# Must be explicit to select all loops
loops delete myshifts.  # ← Deletes all loops (explicit wildcard)

# Or select specific loop
loops delete myshifts.chemical_shift  # ← Deletes specific loop
```

## Migration Guide

| Old (v1.x) | New (v2.0+) | Notes |
|------------|-------------|-------|
| `frame` | `frame.` | All loops in frame (now explicit) |
| `frame` | `frame` | Frame metadata only (new meaning) |
| `frame.loop` | `frame.loop` | Unchanged |
| `frame:tag` | `frame:tag` | Unchanged |

### Why This Change?

**More Explicit:**
- `frame` = the thing itself (metadata)
- `frame.` = contents of the thing (loops)
- `frame.loop` = specific content (one loop)

**More Consistent:**
- Bare names always select metadata only
- Dot (`.`) always means "go into structure"
- Wildcards must be explicit

**Less Surprising:**
- Users don't expect `frame` alone to select loops
- Matches mental model: dot notation = navigation into structure

## Implementation Details

### Selector Components

Each selector has four components:

1. **Frame Name** - Which saveframe(s) to select from
   - Explicit: `myframe`
   - Wildcard: `*` (all frames)
   - Empty before dot: defaults to `*`

2. **Loop Name** - Which loop(s) to select
   - `None` - No loops (frame-level only)
   - Explicit: `chemical_shift`
   - Wildcard: `*` (all loops)
   - Empty after dot: defaults to `*`

3. **Frame Tags** - Which frame tags to select
   - Empty list `[]` - No frame tags
   - Explicit: `["sf_category"]`
   - Multiple: `["sf_category", "sf_framecode"]`
   - Wildcard: `["*"]` (all frame tags)

4. **Loop Tags** - Which loop columns to select
   - Empty list `[]` - Entire loop (all columns)
   - Explicit: `["atom_name"]`
   - Multiple: `["atom_name", "value"]`
   - Wildcard: `["*"]` (all columns)

### Parsing Logic

```python
# No dot, no colon: frame metadata only
"frame"           → (frame="frame", loop=None, frame_tags=[], loop_tags=[])

# No dot, with colon: frame tags
"frame:tag"       → (frame="frame", loop=None, frame_tags=["tag"], loop_tags=[])

# Has dot, no colon: entire loop
"frame.loop"      → (frame="frame", loop="loop", frame_tags=[], loop_tags=[])

# Has dot, with colon: loop columns
"frame.loop:col"  → (frame="frame", loop="loop", frame_tags=[], loop_tags=["col"])

# Empty after dot: all loops
"frame."          → (frame="frame", loop="*", frame_tags=[], loop_tags=[])
```

## Common Patterns

### Select All Loops in Specific Frame

```bash
# Explicit wildcard (recommended)
loops delete myshifts.

# Or explicit asterisk
loops delete myshifts.*
```

### Select Specific Loop Across All Frames

```bash
# All chemical_shift loops in all frames
loops delete .chemical_shift
```

### Select Multiple Things

```bash
# Multiple frame tags from one frame
tool myshifts:sf_category,sf_framecode

# Multiple columns from one loop
tool myshifts.chemical_shift:atom_name,value

# Multiple separate selectors
loops delete frame1.loop1,frame2.loop2
```

### Wildcards at Different Levels

```bash
# All frames, specific loop
loops delete .chemical_shift

# Specific frame, all loops
loops delete myshifts.

# All frames, all loops
loops delete *.*

# All frames, all loops, all columns
tool *.*:*
```
