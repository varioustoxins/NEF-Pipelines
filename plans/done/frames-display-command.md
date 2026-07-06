# Plan: Implement `nef frames display` Command

## Overview
Create a new `frames display` command that displays selected loops with only specified tags/columns in NEF loop format, using frame.loop:tag1,tag2 selector syntax.

## Requirements Summary
1. **Syntax**: Use existing `parse_frame_loop_and_tags()` parser - `frame.loop:tag1,tag2`
2. **Wildcards**: Support fnmatch patterns in frame, loop, and tag names
3. **Multiple selectors**: Support multiple selectors, combine when targeting same loop
4. **Output**: NEF loop or frame format with only selected tags, frame or loop context as comments if not part of the loop
5. **Input handling**: First arg is polymorphic (file vs selector, like `frames list`)
6. **Order preservation**: Maintain order from input NEF file

## Critical Files

### To Create
- `src/nef_pipelines/tools/frames/display.py` - Main command implementation
- `src/nef_pipelines/tests/frames/test_display.py` - Unit tests for the command
- `src/nef_pipelines/tests/framses/xxx.nef` - Test NEF files but only if you can use existing files

### To Modify
- None (new command only)

### Key References
- `src/nef_pipelines/lib/cli_lib.py:1399-1480` - `parse_frame_loop_and_tags()` parser
- `src/nef_pipelines/tools/frames/list.py:70-82, 244-250` - Polymorphic arg pattern
- `src/nef_pipelines/tools/frames/tabulate.py:426-451` - Column selection pattern
- `src/nef_pipelines/lib/structures.py:480-484` - `FrameLoopAndTags` dataclass

## Implementation Details

### Architecture (from user requirements):

1. **Frame/loop/tag matching**: Use cli_lib utilities, not direct fnmatch - note any limitations

2. **Output formatting**: Via PyNMRStar - build new frames/loops with selected tags only

3. **Pipe pattern** (CLAUDE.md convention):
   - CLI function (`display()`) handles I/O and argument parsing
   - Worker function signature: `pipe(entry, parsed_selectors, exact) -> Tuple[Optional[Entry], Dict[str, str]]`
   - Returns: (Entry to stream or None, Dict of {filename: display_output_text})
   - Parsing selectors happens OUTSIDE pipe - pipe receives parsed FrameLoopAndTags list

4. **File output behavior**:
   - Default (no --display-file): Display output to stdout (dict key "-"), stream entry or None
   - `--display-file <path>`: Write display output to file, stream entry to stdout
   - Use `-` for stdout designation in --display-file

5. **Dict output structure** (clarified):
   - Dict keys: filenames (or "-" for stdout)
   - Dict values: formatted display output text (NEF loop format)
   - Example: `{"-": "# save_frame\n loop_\n..."}` or `{"display.nef": "..."}`

### 1. CLI Argument Handling (Revised Architecture)

```python
@frames_app.command()
def display(
    context: Context,
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="read NEF data from a file instead of stdin",
    ),
    exact: bool = typer.Option(
        False,
        "-e",
        "--exact",
        help="use exact matching (no auto-wildcards)",
    ),
    display_file: Optional[Path] = typer.Option(
        None,
        "-d",
        "--display-file",
        help="write display output to file (use '-' for stdout explicitly)",
    ),
    selectors: Optional[List[str]] = typer.Argument(
        None,
        help="selectors in format frame.loop:tag1,tag2 (wildcards supported)"
    ),
):
    """- display selected loops/frames with specified tags only"""

    # 1. Handle polymorphic first arg (file vs selector)
    entry = None
    if selectors and len(selectors) > 0:
        entry = _if_is_nef_file_load_as_entry(selectors[0])
        if entry is not None:
            if input != STDIN:
                exit_error(f"two nef file paths: {input} and {selectors[0]}")
            input = selectors[0]
            selectors = selectors[1:]

    if not selectors:
        selectors = ["*.*:*"]  # Default

    if entry is None:
        entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # 2. Parse selectors OUTSIDE pipe (follows CLAUDE.md pattern)
    parsed_selectors = []
    for selector in selectors:
        parsed_selectors.append(parse_frame_loop_and_tags(selector))

    # 3. Call pipe function (business logic)
    result_entry, output_dict = pipe(entry, parsed_selectors, exact)

    # 4. Handle output based on --display-file option
    if display_file is None:
        # Default: display to stdout only (dict has "-" key)
        if "-" in output_dict:
            print(output_dict["-"], end="")
    elif str(display_file) == "-":
        # Explicit stdout
        if "-" in output_dict:
            print(output_dict["-"], end="")
    else:
        # Write display to file, stream entry to stdout
        with open(display_file, 'w') as f:
            if str(display_file) in output_dict:
                f.write(output_dict[str(display_file)])
            elif "-" in output_dict:
                f.write(output_dict["-"])

        # Stream entry to stdout
        if result_entry is not None:
            print(result_entry)


def _if_is_nef_file_load_as_entry(file_path):
    """Try to load file as NEF entry (pattern from list.py:244-250)."""
    entry = None
    try:
        entry = Entry.from_file(file_path)
    except Exception:
        pass
    return entry
```

### 2. Selector Parsing and Grouping

Parse all selectors and group by (frame, loop) to combine tag selections:

```python
from collections import defaultdict
from nef_pipelines.lib.cli_lib import parse_frame_loop_and_tags

def _parse_and_group_selectors(selectors):
    """Parse selectors and group by (frame, loop) for combining tags.

    Returns:
        dict: {(frame_pattern, loop_pattern): [tag_patterns]}
    """
    grouped = defaultdict(list)

    for selector in selectors:
        parsed = parse_frame_loop_and_tags(selector)
        # parsed is FrameLoopAndTags(frame_name, loop_name, tags)
        key = (parsed.frame_name, parsed.loop_name)
        grouped[key].extend(parsed.tags)

    return grouped
```

### 3. Frame and Loop Matching

Match frames and loops using wildcards (preserve file order):

```python
def _match_frames_and_loops(entry, grouped_selectors, exact):
    """Match frames and loops from selectors, preserving input file order.

    Returns:
        list: [(frame, loop, selected_tags, selector_info)]
    """
    match_flags = fnmatch.IGNORECASE if not exact else 0
    results = []

    # Iterate in file order
    for frame in entry.frame_list:
        for loop in frame.loops:
            # Check each selector pattern
            for (frame_pattern, loop_pattern), tag_patterns in grouped_selectors.items():

                # Match frame name (with auto-wildcard unless exact)
                frame_match_pattern = frame_pattern if exact else f"*{frame_pattern}*"
                if not fnmatch.fnmatch(frame.name, frame_match_pattern, flags=match_flags):
                    continue

                # Match loop category (strip leading underscore)
                loop_category = loop.category.lstrip("_")
                loop_match_pattern = loop_pattern if exact else f"*{loop_pattern}*"
                if not fnmatch.fnmatch(loop_category, loop_match_pattern, flags=match_flags):
                    continue

                # Match! Collect selected tags
                selected_tags = _select_tags(loop.tags, tag_patterns, exact)

                if selected_tags:
                    selector_info = {
                        'frame_pattern': frame_pattern,
                        'loop_pattern': loop_pattern,
                        'tag_patterns': tag_patterns
                    }
                    results.append((frame, loop, selected_tags, selector_info))

    return results
```

### 4. Tag Selection with Wildcards

Select tags using fnmatch (pattern from `tabulate.py:426-451`):

```python
def _select_tags(available_tags, tag_patterns, exact):
    """Select tags matching patterns, preserving order.

    Returns:
        list: Ordered list of matching tags
    """
    match_flags = fnmatch.IGNORECASE if not exact else 0
    selected = set()

    for pattern in tag_patterns:
        # Auto-wildcard unless exact
        match_pattern = pattern if exact else f"*{pattern}*"
        for tag in available_tags:
            if fnmatch.fnmatch(tag, match_pattern, flags=match_flags):
                selected.add(tag)

    # Preserve file order
    return [tag for tag in available_tags if tag in selected]
```

### 5. Combining Multiple Selectors for Same Loop

When multiple selectors target same loop with different tags, combine them:

```python
def _combine_matches(matches):
    """Combine matches for same (frame, loop) with different tag selections.

    Returns:
        list: [(frame, loop, combined_tags, selector_infos)]
    """
    from collections import OrderedDict

    combined = OrderedDict()  # Preserve first occurrence order

    for frame, loop, selected_tags, selector_info in matches:
        key = (frame.name, loop.category)

        if key not in combined:
            combined[key] = {
                'frame': frame,
                'loop': loop,
                'tags': [],
                'tag_set': set(),
                'selectors': []
            }

        # Add tags (preserve order, avoid duplicates)
        for tag in selected_tags:
            if tag not in combined[key]['tag_set']:
                combined[key]['tags'].append(tag)
                combined[key]['tag_set'].add(tag)

        # Track selector info for comments
        combined[key]['selectors'].append(selector_info)

    results = []
    for key, data in combined.items():
        results.append((
            data['frame'],
            data['loop'],
            data['tags'],
            data['selectors']
        ))

    return results
```

### 6. Output Formatting

Output in NEF loop format with frame context as comments:

```python
def _output_loop_display(frame, loop, selected_tags, selector_infos):
    """Output loop in NEF format with selected tags only."""

    # Frame context as comment
    print(f"# save_{frame.name}")
    print(f"#    {frame.category}")
    print()

    # If multiple selectors combined, add comment
    if len(selector_infos) > 1:
        print(f"# Combined {len(selector_infos)} selectors:")
        for info in selector_infos:
            pattern_str = f"{info['frame_pattern']}.{info['loop_pattern']}:{','.join(info['tag_patterns'])}"
            print(f"#   - {pattern_str}")
        print()

    # Loop header
    print("   loop_")

    # Tag headers (with loop category prefix)
    for tag in selected_tags:
        print(f"      {loop.category}.{tag}")

    print()

    # Data rows (only selected columns, in order)
    tag_indices = [loop.tags.index(tag) for tag in selected_tags]
    for row in loop.data:
        values = [row[i] for i in tag_indices]
        formatted_values = [f"{v:>10}" if isinstance(v, (int, float)) else f"{v}" for v in values]
        print(f"      {' '.join(formatted_values)}")

    print()
    print("   stop_")
    print()
    print("# save_")
    print()
```

### 7. Pipe Function (Business Logic)

```python
def pipe(
    entry: Entry,
    parsed_selectors: List[FrameLoopAndTags],
    exact: bool
) -> Tuple[Optional[Entry], Dict[str, str]]:
    """Worker function that builds display output.

    Args:
        entry: Input NEF entry
        parsed_selectors: List of FrameLoopAndTags from parse_frame_loop_and_tags()
        exact: Whether to use exact matching (no auto-wildcards)

    Returns:
        (entry_to_stream, output_dict)
        - entry_to_stream: Entry to stream to stdout (or None)
        - output_dict: Dict mapping filename -> display output text
    """

    # 1. Group selectors by (frame, loop) to combine tags
    grouped_selectors = _parse_and_group_selectors(parsed_selectors)

    # 2. Match frames and loops (preserving file order)
    matches = _match_frames_and_loops(entry, grouped_selectors, exact)

    # 3. Combine multiple selectors for same loop
    combined = _combine_matches(matches)

    # 4. Build display output text (NEF loop format)
    display_lines = []
    for frame, loop, selected_tags, selector_infos in combined:
        display_lines.extend(_format_loop_display(frame, loop, selected_tags, selector_infos))

    # 5. Build output dict
    output_text = "\n".join(display_lines)
    output_dict = {"-": output_text}  # Default to stdout

    # 6. Return entry and output dict
    return entry, output_dict  # Stream original entry


def _parse_and_group_selectors(parsed_selectors: List[FrameLoopAndTags]):
    """Group parsed selectors by (frame, loop) to combine tag selections."""
    from collections import defaultdict

    grouped = defaultdict(list)
    for selector in parsed_selectors:
        key = (selector.frame_name, selector.loop_name)
        grouped[key].extend(selector.tags)

    return grouped
```

## Edge Cases and Error Handling

1. **No matches**: Print warning "No frames/loops matched selectors"
2. **Invalid selector syntax**: `parse_frame_loop_and_tags()` raises `BadFrameLoopTagSyntaxException`
3. **Tag pattern matches nothing**: Skip loop if no tags selected
4. **Empty loop**: Display structure with no data rows
5. **Both --in and file arg**: Error "two nef file paths supplied"
6. **No input (no stdin, no --in, no file arg)**: Show help and exit

## Testing Strategy

### Test File
`src/nef_pipelines/tests/frames/test_display.py`

### Test Cases

1. **Basic selection**: `molecular_system.nef_sequence:chain_code,sequence_code,residue_name`
2. **Wildcard in tags**: `*.nef_sequence:*code*` (matches chain_code, sequence_code)
3. **Wildcard in frame**: `*shift*.nef_chemical_shift:atom_name,value`
4. **Wildcard in loop**: `molecular_system.*:index`
5. **Multiple selectors, different loops**: Two separate selectors
6. **Multiple selectors, same loop**: Combine with comment showing both selectors
7. **Polymorphic arg - file first**: `display test.nef *.sequence:*`
8. **Polymorphic arg - selector first**: `display *.sequence:* --in test.nef`
9. **Error: both file and --in**: Should exit with error
10. **No matches**: Should print warning
11. **Exact matching**: `--exact` flag disables auto-wildcards
12. **Default selector**: No args = `*.*:*` (everything)

### Test Data
Use existing `multi_frame_test.nef` or create minimal test file with:
- 1 molecular_system frame with nef_sequence loop
- 2 ccpn_additional_data frames with ccpn_data loops

### Expected Output Example

For selector `molecular_system.nef_sequence:chain_code,residue_name`:

```
# save_nef_molecular_system
#    nef_molecular_system

   loop_
      _nef_sequence.chain_code
      _nef_sequence.residue_name

      A   ALA
      A   GLY
      A   VAL

   stop_

# save_

```

For combined selectors `ccpn.*:key additional_data.*:value`:

```
# save_ccpn_additional_data_1
#    ccpn_additional_data

# Combined 2 selectors:
#   - ccpn.*:key
#   - additional_data.*:value

   loop_
      _ccpn_data.key
      _ccpn_data.value

      frame1_key1  frame1_value1
      frame1_key2  frame1_value2

   stop_

# save_

```

## Verification Steps

1. **Run unit tests**: `pytest src/nef_pipelines/tests/frames/test_display.py -v`
2. **Manual test with file arg**: `nef frames display test.nef molecular_system.sequence:*code*`
3. **Manual test with stdin**: `cat test.nef | nef frames display *.sequence:chain*,residue*`
4. **Manual test with --in**: `nef frames display *.sequence:* --in test.nef`
5. **Test wildcards**: `nef frames display test.nef *.*:*code*`
6. **Test combining**: `nef frames display test.nef ccpn.*:key ccpn.*:value`
7. **Test exact mode**: `nef frames display test.nef --exact nef_molecular_system.nef_sequence:chain_code`
8. **Full test suite**: `pytest src/nef_pipelines/tests -v` (ensure no regressions)

## Implementation Notes

- Follow CLAUDE.md testing guidelines: use EXPECTED_ constants, assert_lines_match()
- Use existing utilities: `parse_frame_loop_and_tags()`, `fnmatch`, `read_entry_from_file_or_stdin_or_raise()`
- Maintain file order throughout (frames, loops, tags, rows)
- Comments for frame context enhance readability without breaking NEF parsing
- Combining multiple selectors reduces output redundancy
