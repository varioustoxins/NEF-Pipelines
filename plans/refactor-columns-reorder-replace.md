# Refactor columns reorder and columns replace

## Context

Both `columns reorder` and `columns replace` violate core architectural principles:

**Current Problems:**
1. **Low-level CLI/pipe functions**: Mix parsing, validation, and business logic instead of being high-level pseudo-code
2. **String accumulation errors**: Use `error_msg = None` pattern instead of typed exceptions
3. **No _or_raise/_or_exit_error separation**: Call `exit_error()` directly from library code
4. **Parsing embedded in CLI**: Not reusable or testable independently
5. **No typed data structures**: Use tuples instead of dataclasses

**Target Architecture** (from `columns insert` and `columns rename`):
- CLI and pipe functions should read like pseudo-code with high-level function calls
- Library functions raise typed exceptions inheriting from `NEFPipelinesException`
- CLI functions catch exceptions and format with `exit_error()`
- Parsing functions in `columns_cli_lib.py` with `_or_raise` suffix
- Typed data structures in `columns_structures.py`

**Key Architectural Decisions (UPDATED):**
1. **Reuse existing structures**: `FrameLoopTags` for reorder, `InsertInstruction` for replace
2. **CLI validation**: All validation happens in CLI layer before calling pipe
3. **Silent pipes**: Pipe functions assume validation is complete, no exceptions thrown
4. **Code reuse**: Replace leverages insert infrastructure (parsing, file reading, validation)
5. **Specific exception types**: Each error type gets its own exception class (not fat interfaces with `error_type` fields)

## Key Findings from Exploration

### columns reorder (168 lines)
**Critical Issues:**
- CLI has 20+ lines of inline parsing logic (lines 64-82) - should delegate
- Pipe function has validation mixed with logic (lines 99-152)
- Uses string accumulation (`error_msg = None`) instead of exceptions
- Multiple nested `if error_msg: break` statements - code smell
- No reusable parsing or validation functions

**Current pseudo-code readability:** ❌ Poor
```python
def reorder(selector, column_order, ...):
    # 20 lines of parsing logic inline
    # Multiple if/else branches
    # String error accumulation
    entry = read_entry(...)
    entry = pipe(entry, ...) # But pipe also has complex validation
    print(entry)
```

**Should be:**
```python
def reorder(selector, column_order, ...):
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    reorder_instructions = _parse_reorder_arguments_or_exit_error(selector, column_order, ...)
    entry = pipe(entry, reorder_instructions)
    print(entry)
```

### columns replace (159 lines)
**Better but still issues:**
- Has `_parse_replace_args` function (good!) but calls `exit_error()` directly (bad)
- Helper `_check_row_count` calls `exit_error()` instead of raising
- File reference parsing (`_is_file_ref`, `_parse_file_ref`) should be in shared library
- Pipe function has repeated near-identical blocks (lines 87-96, 98-110)

**Current pseudo-code readability:** ⚠️ Moderate
```python
def replace(selector, replacements, ...):
    entry = read_entry(...)
    selector, pairs = _parse_replace_args(...)  # Good: extracted parsing
    # But _parse_replace_args calls exit_error() - should raise exception
    entry = pipe(entry, selector, pairs)
    print(entry)
```

**Should be:**
```python
def replace(selector, replacements, ...):
    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    replace_instructions = _parse_replace_arguments_or_exit_error(selector, replacements, entry, input)
    entry = pipe(entry, replace_instructions)
    print(entry)
```

## Refactoring Plan

### Phase 1: Create Exception Classes (columns_structures.py)

**UPDATED: Use individual exception classes for each error type, not fat interfaces with error_type fields**

**For reorder:**
```python
@dataclass
class NEFColumnsReorderMissingSelectorException(NEFPipelinesException):
    """No selector provided and first argument doesn't contain frame.loop: prefix."""
    first_arg: Optional[str] = None

@dataclass
class NEFColumnsReorderInvalidPolicyException(NEFPipelinesException):
    """Invalid policy specified (not exact/append/prepend)."""
    policy: str
    valid_policies: List[str]

@dataclass
class NEFColumnsReorderUnknownColumnsException(NEFPipelinesException):
    """Specified columns don't exist in loop."""
    unknown_columns: List[str]
    selector: str
    available_columns: List[str]

@dataclass
class NEFColumnsReorderDuplicateColumnsException(NEFPipelinesException):
    """Duplicate columns in reorder specification."""
    duplicate_columns: List[str]
    selector: str
```

**For replace (reuse existing exceptions + rename for consistency):**

**UPDATED: Rename existing exceptions for consistency:**
```python
# Rename these existing exceptions in columns_structures.py:
# NEFColumnsFileColumnNotFoundException → NEFColumnsColumnNotFoundInFileException
# NEFColumnsLoopColumnNotFoundException → NEFColumnsColumnNotFoundInLoopException

# Keep as-is:
# - NEFColumnsFileNotFoundException (file doesn't exist)

# After rename, replace will reuse:
# - NEFColumnsFileNotFoundException (file doesn't exist)
# - NEFColumnsColumnNotFoundInFileException (column not in file)
# - NEFColumnsColumnNotFoundInLoopException (column not in loop)
```

**UPDATED: Row count handling (consistent with insert):**
```python
# Row count mismatch is NOT an error - handle gracefully:
# 1. File has MORE rows than loop: Extend loop by padding other columns with '.'
# 2. File has FEWER rows: Fill remaining with '.' (UNUSED)
# Both cases should WARN user about the padding
# This matches insert behavior (verify insert does this)

# No exception needed for row count mismatches - handle gracefully

@dataclass
class NEFColumnsReplaceInvalidFormatException(NEFPipelinesException):
    """Invalid replace specification format."""
    arg: str
    expected_format: str = "selector @file:col or col @file:col"
```

### Phase 2: Extract Parsing Functions (columns_cli_lib.py)

**For reorder:**
```python
def _parse_reorder_arguments_or_raise(
    selector: Optional[str],
    column_order: List[str],
    policy: str
) -> FrameLoopTags:
    """Parse reorder arguments into FrameLoopTags with new column order.

    Returns FrameLoopTags where loop_tags specifies the new order.
    Columns not in loop_tags stay at end in current order.

    Raises:
        NEFColumnsReorderMissingSelectorException: no selector and no frame.loop: prefix
        NEFColumnsReorderInvalidPolicyException: invalid policy value
        NEFColumnsReorderDuplicateColumnsException: duplicate columns in specification
    """
    # Pure parsing logic, raises specific exceptions with data

def _parse_reorder_arguments_or_exit_error(
    selector, column_order, policy, entry, input_file
) -> FrameLoopTags:
    """Wrapper that formats exceptions and exits."""
    try:
        return _parse_reorder_arguments_or_raise(selector, column_order, policy)
    except NEFPipelinesException as e:
        msg = _format_exception_with_context(e, entry, input_file)
        exit_error(msg)
```

**For replace:**
```python
def _parse_replace_arguments_or_raise(
    selector: Optional[str],
    replacements: List[str]
) -> List[InsertInstruction]:
    """Parse replace arguments into InsertInstructions.

    Replace is just insert with @file:col specifications.
    Creates InsertInstructions with FileValueSpecification.

    Raises:
        NEFColumnsReplaceInvalidFormatException: invalid argument format
        (other exceptions from reused insert parsing)
    """
    # Pure parsing logic, raises specific exceptions with data
    # Reuses existing insert parsing infrastructure

def _parse_replace_arguments_or_exit_error(
    selector, replacements, entry, input_file
) -> List[InsertInstruction]:
    """Wrapper that formats exceptions and exits."""
    try:
        return _parse_replace_arguments_or_raise(selector, replacements)
    except NEFPipelinesException as e:
        msg = _format_exception_with_context(e, entry, input_file)
        exit_error(msg)
```

**Shared utilities to extract:**
```python
def _parse_file_reference_or_raise(ref: str) -> Tuple[Path, Optional[str]]:
    """Parse @file:col or @file syntax, raise on invalid."""
    # Reusable across replace, insert, and any command using file refs

def _validate_columns_exist_or_raise(loop, columns: List[str]):
    """Check columns exist in loop, raise typed exception if not."""
    # Reusable validation
```

### Phase 3: Reuse Existing Data Structures

**UPDATED: No new data structures needed - reuse existing ones:**

**For reorder:**
- Use existing `FrameLoopTags` structure (from `lib.structures`)
- The `loop_tags` field specifies the new column order
- Columns not listed in `loop_tags` remain at the end in their current order
- This matches the command-line behavior

**For replace:**
- Use existing `InsertInstruction` structure (from `columns_structures`)
- Replace is just insert with `@file:col` value specification
- Parser should create `InsertInstruction` with `FileValueSpecification`
- Reuses all insert infrastructure (parsing, validation, file handling)

### Phase 4: Refactor CLI Functions (High-Level Pseudo-Code)

**reorder.py:**
```python
@columns_app.command()
def reorder(
    column_order: List[str] = typer.Argument(...),
    input: Path = typer.Option(STDIN, "--in"),
    selector: str = typer.Option(None, "--selector", "-s"),
    policy: str = typer.Option("exact", "--policy"),
) -> None:
    """- reorder columns in loops"""
    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # Parse arguments into FrameLoopTags structure
    frame_loop_tags = _parse_reorder_arguments_or_exit_error(
        selector, column_order, policy, entry, input
    )

    # UPDATED: CLI validation happens here (before pipe)
    # - Validate frame/loop exist
    # - Validate columns exist
    # - Check for duplicates
    # All validation raises exceptions, caught and formatted by CLI
    _validate_reorder_or_exit_error(entry, frame_loop_tags, input)

    entry = pipe(entry, frame_loop_tags)
    print(entry)
```

**replace.py:**
```python
@columns_app.command()
def replace(
    replacements: List[str] = typer.Argument(...),
    input: Path = typer.Option(STDIN, "--in"),
    selector: str = typer.Option(None, "--selector", "-s"),
) -> None:
    """- replace column data from files"""
    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # Parse arguments into InsertInstructions (reuses insert infrastructure)
    instructions = _parse_replace_arguments_or_exit_error(
        selector, replacements, entry, input
    )

    # UPDATED: CLI validation happens here (before pipe, like insert does)
    # - Validate files exist
    # - Warn if row counts don't match (will pad with '.' either way)
    # - Validate columns specified in files exist
    # All validation raises exceptions, caught and formatted by CLI
    _validate_replace_or_exit_error(entry, instructions, input)
    _warn_if_row_count_mismatch(entry, instructions)  # Warning for both too long and too short

    entry = pipe(entry, instructions)
    print(entry)
```

### Phase 5: Refactor Pipe Functions (High-Level Pseudo-Code)

**UPDATED: Pipe functions are silent - no validation, pure transformation**

**reorder pipe:**
```python
def pipe(entry: Entry, frame_loop_tags: FrameLoopTags) -> Entry:
    """Reorder columns - high-level orchestration only.

    Assumes CLI has validated:
    - Frame/loop exist
    - All columns in loop_tags exist
    - No duplicates
    """
    loops = _select_loops(entry, frame_loop_tags.frame_name, frame_loop_tags.loop_name)

    for frame, loop in loops:
        new_order = _compute_new_column_order(loop, frame_loop_tags.loop_tags)
        _apply_column_reorder(frame, loop, new_order)

    return entry
```

**replace pipe:**
```python
def pipe(entry: Entry, instructions: List[InsertInstruction]) -> Entry:
    """Replace column data - high-level orchestration only.

    Assumes CLI has validated:
    - Files exist
    - Row counts match
    - File columns exist

    Replace is just insert with existing columns - delegates to insert_pipe or reuses logic.
    """
    for instruction in instructions:
        loops = _select_loops(entry, instruction.frame_pattern, instruction.loop_pattern)
        file_data = _read_column_data(instruction.value_spec)  # Reuses insert file reading

        for frame, loop in loops:
            _apply_column_replacement(frame, loop, instruction.col_name, file_data)

    return entry
```

### Phase 6: Extract Validation and Transformation Helpers

**UPDATED: Validation in CLI layer, transformation in library layer**

**Validation helpers (called by CLI, raise specific exceptions):**
```python
# In columns_cli_lib.py
def _validate_reorder_or_exit_error(entry: Entry, frame_loop_tags: FrameLoopTags, input_file: Path):
    """Validate reorder can be performed, exit with formatted error if not.

    Each validation raises specific exception type (not generic with error_type field).
    """
    try:
        _validate_frame_loop_exists_or_raise(entry, frame_loop_tags)
        # Raises NEFColumnsLoopColumnNotFoundException for unknown columns
        _validate_columns_exist_or_raise(entry, frame_loop_tags)
    except NEFPipelinesException as e:
        exit_error(_format_exception_with_context(e, entry, input_file))

def _validate_replace_or_exit_error(entry: Entry, instructions: List[InsertInstruction], input_file: Path):
    """Validate replace can be performed, exit with formatted error if not.

    Reuses insert validation logic which raises specific exception types.
    """
    try:
        # Raises NEFColumnsFileNotFoundException
        _validate_files_exist_or_raise(instructions)
        # UPDATED: No row count validation - both too long and too short are handled
        # (extend loop or fill with '.' - warn in both cases)
        # Raises NEFColumnsColumnNotFoundInFileException
        _validate_file_columns_exist_or_raise(instructions)
    except NEFPipelinesException as e:
        exit_error(_format_exception_with_context(e, entry, input_file))

def _warn_if_row_count_mismatch(entry: Entry, instructions: List[InsertInstruction]):
    """Warn if file row count doesn't match loop (will pad with '.' either way)."""
    for instruction in instructions:
        loops = _select_loops(entry, instruction.frame_pattern, instruction.loop_pattern)
        file_data = _read_column_data(instruction.value_spec)

        for frame, loop in loops:
            loop_rows = len(list(loop_row_dict_iter(loop)))
            file_rows = len(file_data)

            if file_rows > loop_rows:
                warn(f"file {instruction.value_spec.path} has {file_rows} rows, loop has {loop_rows} - extending loop with '.' in other columns")
            elif file_rows < loop_rows:
                warn(f"file {instruction.value_spec.path} has {file_rows} rows, loop has {loop_rows} - filling remaining with '.'")

```

**Exception formatting (generic handler for all exception types):**
```python
def _format_exception_with_context(
    e: NEFPipelinesException,
    entry: Optional[Entry] = None,
    input_file: Optional[Path] = None
) -> str:
    """Format any NEFPipelinesException with entry/file context.

    Uses exception's __str__() for base message, adds context.
    Each exception class defines its own __str__() with specific fields.
    """
    msg = str(e)

    context_parts = []
    if entry:
        context_parts.append(f"entry '{entry.entry_id}'")
    if input_file and input_file != STDIN:
        context_parts.append(f"file '{input_file}'")

    if context_parts:
        msg = f"{msg} [{', '.join(context_parts)}]"

    return msg
```

**Transformation helpers (called by pipe, no exceptions):**
```python
# In columns_lib.py
def _compute_new_column_order(loop: Loop, ordered_tags: List[str]) -> List[str]:
    """Compute new column order: ordered_tags first, then remaining in current order."""

def _apply_column_reorder(frame, loop, new_order: List[str]):
    """Apply new column order to loop."""

def _apply_column_replacement(frame, loop, col_name: str, data: List[str]):
    """Replace column data (reuses insert logic)."""
```

## Files to Modify

1. **columns_structures.py**:
   - Add 4 new reorder exception classes
   - Add 1 new replace exception class
   - **UPDATED**: Rename 2 existing exceptions for consistency:
     - `NEFColumnsFileColumnNotFoundException` → `NEFColumnsColumnNotFoundInFileException`
     - `NEFColumnsLoopColumnNotFoundException` → `NEFColumnsColumnNotFoundInLoopException`
2. **columns_cli_lib.py**: Add parsing functions with _or_raise/_or_exit_error pattern
3. **columns_lib.py**: Add shared validation and transformation helpers
4. **reorder.py**: Refactor CLI and pipe to high-level pseudo-code
5. **replace.py**: Refactor CLI and pipe to high-level pseudo-code
6. **Any files using renamed exceptions**: Update imports

## Success Criteria

**High-level function test:**
Both CLI and pipe functions should be readable as pseudo-code with ~5-10 high-level function calls:
- ✅ Read entry
- ✅ Parse arguments (delegates to _or_exit_error wrapper)
- ✅ Select loops (delegates to helper)
- ✅ Validate (delegates to helpers that raise)
- ✅ Transform (delegates to helpers)
- ✅ Print result

**No embedded logic:**
- ❌ No inline parsing
- ❌ No error string accumulation
- ❌ No direct exit_error() calls from library code
- ❌ No break cascades

## Verification

```bash
nefl test src/nef_pipelines/tests/columns/test_reorder.py -v
nefl test src/nef_pipelines/tests/columns/test_replace.py -v
```

All existing tests should pass with enhanced error messages (now with context).
