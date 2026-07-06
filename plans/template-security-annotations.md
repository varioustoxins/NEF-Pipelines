# Template Security for NEF Pipelines CLI

## Context

NEF pipelines CLI commands accept user input that may contain template syntax (e.g., `"output_{frame}.nef"`). When these templates are formatted with `.format()` or f-strings, they could potentially:
1. Inject malicious template placeholders
2. Generate file paths that escape the sandbox
3. Bypass security checks if not properly validated

**The Solution**: Implement a type annotation system to mark template parameters and route all template formatting through gatekeeper functions. This provides:
- Clear identification of which parameters accept templates
- Centralized template formatting and validation
- Ability to audit and test template usage
- Prevention of direct `.format()` calls on user input

## Annotation Design

Using `typing_extensions.Annotated` for Python 3.9 compatibility with marker classes:

```python
from typing_extensions import Annotated

# Marker classes for introspection
class FilenameTemplate:
    """Marks a parameter that contains filename template syntax (e.g., 'output_{frame}.nef')."""
    pass

class GeneralTemplate:
    """Marks a parameter that contains general template syntax for non-filename content."""
    pass

# Type aliases for CLI parameters
FilenameTemplateStr = Annotated[str, FilenameTemplate]
GeneralTemplateStr = Annotated[str, GeneralTemplate]
```

**Usage in CLI commands:**
```python
def save_command(
    filename: FilenameTemplateStr,  # e.g., "output_{frame}.nef"
    header: Optional[GeneralTemplateStr] = None,  # e.g., "Frame {number}"
) -> None:
    # Implementation routes through gatekeeper
    ...
```

## Implementation Steps

### 1. Create Template Annotation Module

**File**: `src/nef_pipelines/lib/template_annotations.py` (new file)

```python
"""Type annotations for template parameters in NEF pipelines.

Provides marker classes and type aliases to identify parameters that
contain template syntax (e.g., '{placeholder}') which must be routed
through gatekeeper functions for safe formatting.
"""

from typing_extensions import Annotated

class FilenameTemplate:
    """Marker class for filename template parameters.

    Indicates a string parameter accepts template syntax for generating
    filenames, e.g., 'output_{frame}.nef' or 'result_{index:03d}.txt'.

    Must be processed through format_filename_template() gatekeeper.
    """
    pass

class GeneralTemplate:
    """Marker class for general template parameters.

    Indicates a string parameter accepts template syntax for non-filename
    content, e.g., headers, labels, or text content.

    Must be processed through format_general_template() gatekeeper.
    """
    pass

# Type aliases for use in CLI parameter annotations
FilenameTemplateStr = Annotated[str, FilenameTemplate]
GeneralTemplateStr = Annotated[str, GeneralTemplate]
```

### 2. Create Gatekeeper Functions

**File**: `src/nef_pipelines/lib/template_formatting.py` (new file)

Two gatekeeper functions that:
1. Accept annotated template strings and formatting context
2. Safely format templates with validation
3. For filename templates: ensure results don't escape sandbox or contain dangerous characters
4. Return formatted strings

```python
"""Safe template formatting gatekeepers for NEF pipelines.

All template formatting MUST go through these functions to ensure:
- Template syntax is safely evaluated
- Resulting paths stay within sandbox boundaries
- No injection of malicious placeholders
"""

from typing import Any, Dict
from pathlib import Path

def format_filename_template(template: str, context: Dict[str, Any]) -> str:
    """Format a filename template safely.

    Args:
        template: Template string (e.g., 'output_{frame}.nef')
        context: Variables for formatting (e.g., {'frame': 'A'})

    Returns:
        Formatted filename

    Raises:
        ValueError: If formatted result contains path traversal or invalid characters
    """
    # Format template
    result = template.format(**context)

    # Validate result (delegate to existing sandbox validation)
    # - No absolute paths
    # - No path traversal (../)
    # - No null bytes or control characters
    # - Filename length limits

    return result

def format_general_template(template: str, context: Dict[str, Any]) -> str:
    """Format a general template safely.

    Args:
        template: Template string
        context: Variables for formatting

    Returns:
        Formatted string
    """
    # Format and return (less strict validation for non-path content)
    return template.format(**context)
```

### 3. Scan and Annotate CLI Commands

**Process:**
1. Find all CLI command functions (search for `@.*app.command` decorators)
2. Identify parameters that currently accept templates:
   - Look for `.format()` calls on the parameter
   - Look for f-strings using the parameter
   - Check parameter names like "template", "pattern", "filename" with placeholders
3. Add annotations to those parameters
4. Route formatting through gatekeeper functions

**Example locations to check:**
- `src/nef_pipelines/tools/frames/` - frame operations
- `src/nef_pipelines/tools/save.py` or similar - save commands
- Any export/output commands

**Example transformation:**
```python
# Before
def save(filename: str, ...):
    output = filename.format(frame=frame_id)
    Path(output).write_text(data)

# After
from nef_pipelines.lib.template_annotations import FilenameTemplateStr
from nef_pipelines.lib.template_formatting import format_filename_template

def save(filename: FilenameTemplateStr, ...):
    output = format_filename_template(filename, {'frame': frame_id})
    Path(output).write_text(data)
```

### 4. Add Meta Test for string.format()

**File**: `src/nef_pipelines/tests/meta/test_template_security.py` (new file)

Test that scans the codebase for:
1. `.format()` calls outside gatekeeper functions
2. Direct string formatting on parameters
3. Ensures all template parameters use annotations

```python
"""Meta tests for template security enforcement."""

import ast
import inspect
from pathlib import Path
from typing import get_type_hints, get_args, get_origin

def test_no_format_outside_gatekeepers():
    """Ensure .format() is only called in gatekeeper functions."""

    # Walk source tree
    # Parse Python files with ast
    # Find .format() calls
    # Verify they're only in template_formatting.py
    # Fail if found elsewhere (with file:line info)

def test_template_annotations_used():
    """Verify all template parameters have proper annotations."""

    # Find CLI command functions
    # Check type hints for template-like parameters
    # Ensure FilenameTemplateStr or GeneralTemplateStr is used
    # Fail if templates found without annotations
```

### 5. Add Integration Tests

**File**: `src/nef_pipelines/tests/ai/test_template_sandbox.py` (new file)

Test that commands using file templates don't write outside sandbox:

```python
"""Integration tests for template formatting with sandbox enforcement."""

def test_filename_template_respects_sandbox(tmp_path):
    """Verify filename templates can't escape sandbox."""

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Test various escape attempts via templates
    dangerous_templates = [
        "../escape_{frame}.nef",
        "/tmp/absolute_{frame}.nef",
        "good_{frame}/../../../etc/passwd",
    ]

    for template in dangerous_templates:
        with pytest.raises(ValueError, match="sandbox|traversal|absolute"):
            format_filename_template(template, {'frame': 'A'})

def test_real_nef_save_with_template(mcp_context):
    """Test actual NEF save command with template doesn't escape sandbox."""

    # Call nef save command with templated filename
    # Verify file written inside sandbox
    # Verify template was properly formatted
```

## Files to Create

1. `src/nef_pipelines/lib/template_annotations.py` - Marker classes and type aliases
2. `src/nef_pipelines/lib/template_formatting.py` - Gatekeeper functions
3. `src/nef_pipelines/tests/meta/test_template_security.py` - Meta tests
4. `src/nef_pipelines/tests/ai/test_template_sandbox.py` - Integration tests

## Files to Modify

**To find:** Scan for CLI commands that use templates:
- Search for `.format(` calls
- Search for parameters named "template", "pattern", "filename" that get formatted
- Focus on save/export commands first

**Modifications:**
- Add import: `from nef_pipelines.lib.template_annotations import FilenameTemplateStr, GeneralTemplateStr`
- Add import: `from nef_pipelines.lib.template_formatting import format_filename_template, format_general_template`
- Change parameter type: `filename: str` → `filename: FilenameTemplateStr`
- Replace formatting: `filename.format(...)` → `format_filename_template(filename, {...})`

## Verification

1. **Run meta test**: `pytest src/nef_pipelines/tests/meta/test_template_security.py -v`
   - Should pass, confirming no `.format()` outside gatekeepers

2. **Run integration tests**: `pytest src/nef_pipelines/tests/ai/test_template_sandbox.py -v`
   - Should pass, confirming templates respect sandbox

3. **Manual verification**:
   - Search codebase: `git grep -n '\.format('` - should only show gatekeeper files
   - Check annotations: Files with template parameters should use `FilenameTemplateStr` or `GeneralTemplateStr`

4. **Functional test via MCP**:
   - Start MCP server with sandbox
   - Execute command with filename template: `nef save --filename "output_{frame}.nef"`
   - Verify file created with formatted name inside sandbox
   - Try escape attempt: `nef save --filename "../escape_{frame}.nef"` → should fail

## Notes

- Annotations are **markers only** - they identify template parameters but don't enforce anything
- Gatekeepers do the actual validation and formatting
- Meta test ensures developers can't bypass gatekeepers
- Integration tests verify sandbox boundary enforcement
- Python 3.9+ compatible via `typing_extensions.Annotated`
