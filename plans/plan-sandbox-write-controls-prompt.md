# Plan: Sandbox Write Controls - Template Validation and I/O Security (Audit Hook Approach)

**STATUS: PARTIALLY IMPLEMENTED - Audit hooks only**

**What was implemented:**
- ✅ **Stage 1, item 1**: `--sandbox-path` option in `tools/ai/server.py`
- ✅ **Stage 6, item 1**: Audit hook enforcement in `tools/ai/sandbox_audit.py`
  - Intercepts all file operations (`open`, `os.rename`, `shutil.move`, etc.)
  - Validates paths against sandbox boundary
  - Raises `SandboxViolation` on violations

**What was NOT implemented:**
- ❌ **Stage 1, item 2**: `secure_templates.py` with `expand_path_template()` and `expand_template()`
- ❌ **Stages 2-5**: Template type identification, path template bottlenecks, template refactoring
- ❌ **Stage 6, item 2**: Meta-tests for template enforcement

**Current state**: Audit hooks provide runtime sandbox enforcement, but no compile-time/static validation of templates. Template injection vulnerabilities may still exist at the application layer, though audit hooks prevent actual filesystem escapes.

**What needs to be done to complete this plan:**

1. **Create `secure_templates.py`** (Stage 1, item 2):
   - Implement `expand_path_template(template, context, sandbox)` with:
     - Template syntax validation (reject `{0}`, `__`, arbitrary expressions)
     - Key allowlist enforcement (`{entry_id}`, `{chain_code}`, `{frame_name}`, etc.)
     - Sandbox boundary validation
     - Path traversal prevention
   - Implement `expand_template(template, context)` as marker function for non-path templates
   - Add type annotations: `PathTemplate` and `Template`

2. **Refactor exporters** (Stages 2-5):
   - Audit and categorize all template usage across ~18 file write locations
   - Replace direct `.format()` calls with `expand_path_template()` or `expand_template()`
   - Add type annotations to all template parameters
   - Update all exporters: sparky, mars, shifty, pales, nmrview, etc.

3. **Add meta-tests** (Stage 6, item 2):
   - Create `test_banned_template_usage.py` using AST scanning
   - Ban bare `.format()` calls (must use bottleneck functions)
   - Allow exceptions with `# SAFE_FORMAT_ALLOWED` marker if needed

4. **Testing & Documentation**:
   - Unit tests for template functions
   - Integration tests for sandbox enforcement
   - Update MCP server documentation with security model
   - Add CLAUDE.md section on secure template/I/O patterns

---

Implement comprehensive security controls for file writes in NEF-Pipelines, particularly for the MCP server context. Secure all path template generation and enforce sandbox boundaries using Python's audit hook mechanism as the primary defense.

## Core Strategy

**Audit Hook Primary Defense**: Use `sys.addaudithook()` as the main enforcement mechanism:
- ✅ Intercepts ALL file operations at CPython C-API level
- ✅ Catches `open()`, `Path.write_text()`, `os.rename()`, etc. automatically
- ✅ Can veto operations by raising `PermissionError`
- ✅ Single enforcement point - impossible to bypass from Python code
- ⚠️ **Limitation**: C-level file I/O from compiled extensions won't be caught (acceptable trade-off)

**Template Expansion Bottleneck**: Control path template generation to prevent injection:
- `expand_path_template(template, context, sandbox)` → validates template syntax, expands safely, checks sandbox
- `expand_template(template, context)` → regular formatting for non-paths (documentation/enforceability)

**Three-Layer Defense**:
- Layer 1: Type annotations (`PathTemplate`, `Template`) - static identification and documentation
- Layer 2: Template expansion bottleneck - prevents injection attacks, validates paths
- Layer 3: Audit hooks - runtime enforcement (vetoes ALL file I/O outside sandbox)

## Steps

### **Stage 1: Root-Level Sandbox Path Option & Infrastructure**

1. Add `--sandbox-path` option to `main.py`'s `main_callback()` to set a global sandbox path variable that MCP server can use **[DONE]**

2. Create `src/nef_pipelines/lib/secure_templates.py` with:
    - `expand_path_template(template: str, context: dict, sandbox: Optional[Path]) -> Path`
      - Validates template syntax (rejects `{0}`, `__`, arbitrary Python expressions)
      - Enforces key allowlist: `{entry_id}`, `{chain_code}`, `{frame_name}`, `{shift_list}`, `{chain}`
      - Expands template with provided context
      - Validates result is within sandbox using `_validate_path_in_sandbox()` from `mcp_lib.py`
      - Returns Path object ready for use with normal `open()`
    - `expand_template(template: str, context: dict) -> str`
      - Regular string formatting with no security checks
      - Marker function for "this is NOT a file path"
      - Enables meta-test enforcement
    - Type annotations: `PathTemplate = Annotated[str, "path_template"]` and `Template = Annotated[str, "template"]` for typer parameters

**Why no `secure_open()` wrapper?**
- Audit hooks already intercept ALL `open()` calls at C-API level
- `expand_path_template()` validates paths BEFORE they're used
- Normal `open()` is fine after path validation
- Simpler code, less refactoring needed
- Works automatically with libraries (matplotlib, pandas, etc.)

### **Stage 2: Template Type Identification & Categorisation**

1. Audit all `typer.Option()` and `typer.Argument()` declarations containing templates:
   - Path templates: `sparky/exporters/shifts.py:42` `DEFAULT_OUTPUT_TEMPLATE`, `shifty/exporters/shifts.py:25` `FILE_NAME_TEMPLATE`, `pales/exporters/rdcs.py:50` `file_name_template`, `mars/exporters/input.py:104` f-string templates, `save.py:37` `template`
   - Non-path templates: any `.format()` calls on non-file content (help text, error messages, data formatting)
2. Create inventory in `plans/sandbox-writes.md` categorising:
   - Commands with path template options
   - Commands with direct file writes (no templates)
   - Commands with non-path template usage
3. Add type annotations: `PathTemplate` for path templates, `Template` for non-path templates

### **Stage 3: Path Template Bottleneck Refactoring**

1. Refactor exporters to use `PathTemplate`:
   - `sparky/exporters/shifts.py:369` `_build_filename()` → use `expand_path_template()`
   - `tools/save.py` template expansion
   - All exporters in `mars/exporters/`, `shifty/exporters/`, `pales/exporters/`, `nmrview/exporters/`
2. All template expansions must go through `expand_path_template()` which enforces:
   - Template key allowlist
   - Sandbox boundary checks
   - Path traversal prevention (no `..`, no absolute paths escaping sandbox)

### **Stage 4: Direct File Path Generation**

1. Refactor file write locations to use `expand_path_template()` for path generation:
   - `mars/exporters/input.py:107` - validate `output_path` before `open(output_path, "w")`
   - `sparky/exporters/shifts.py:397` - validate `filename` before `open(filename, "w")`
   - All 18 locations from grep search for `open\([^,]+,\s*["']w`
2. Pattern to follow:
   ```python
   # Generate validated path
   output_path = expand_path_template(
       template, context, sandbox=get_sandbox()
   )
   # Use normal open() - audit hook provides secondary check
   with open(output_path, "w") as f:
       f.write(content)
   ```
3. Special cases:
   - `STDOUT` constant - already handled by audit hook (sys.stdout bypass)
   - matplotlib `plt.savefig()` - path validated via `expand_path_template()` before passing to savefig
   - All library calls work automatically (audit hooks catch them all)

### **Stage 5: Non-Path Template Bottleneck**

1. Refactor all non-path `.format()` calls to use `expand_template()`:
   - Help text generation
   - Table/tabular output formatting
   - Log messages
   - Error messages with dynamic content
2. **Purpose**: Forces ALL formatting through bottlenecks (enforceability):
   - `expand_template()` does NO security checks - it's just a marker function
   - Enables meta-test to ban bare `.format()` calls
   - Documents developer intent: "this is not a file path"
   - Makes audit trail: `expand_path_template()` = all file operations

### **Stage 6: Enforcement via Audit Hook & Meta-Test**

1. **Audit Hook (PRIMARY ENFORCEMENT)** - already implemented in `tools/ai/mcp_lib.py:202-312`:
   - Intercepts: `open`, `os.chdir`, `os.mkdir`, `os.rmdir`, `os.remove`, `os.unlink`, `os.rename`, `os.replace`, `os.symlink`, `os.link`, `shutil.copyfile`, `shutil.copytree`, `shutil.move`, etc.
   - Validates ALL paths against sandbox boundary
   - **Vetoes violations by raising `PermissionError`**
   - Works for: builtin `open()`, `pathlib.Path.write_text()`, `io.open()`, external libraries
   - **Limitation**: Won't catch pure C-level file I/O from compiled extensions (acceptable trade-off)

2. **Meta-test for template usage** - `tests/meta_tests/test_banned_template_usage.py`:
   - AST-based scanner (like `test_banned_functions.py`)
   - **Detect ANY bare `.format()` calls** not going through `expand_path_template()` or `expand_template()`
   - Allow exceptions with `# SAFE_FORMAT_ALLOWED` marker (for stdlib/vendored code if needed)
   - Fail on violations - enforces bottleneck pattern
   - **Purpose**: Prevent template injection attacks, ensure audit trail

**No meta-test for `open()` calls needed:**
- Audit hooks provide runtime enforcement automatically
- AST scanning can't verify path safety (would need data flow analysis)
- Better to have one strong enforcement point (audit hooks) than weak static checks

### **Stage 7: Standardised Output Return Format**

## Further Considerations

1. **Backward Compatibility**:
   - Existing commands continue working during migration
   - Consider feature flag or gradual rollout per-transcoder
   - Audit hook provides safety net during transition

2. **Performance**:
   - Path validation on every write-mode `open()` - minimal overhead (one path check)
   - Template expansion happens once per file, not per line - negligible impact
   - Could cache sandbox validation results if needed (optimization, not requirement)

3. **Template Key Allowlist**:
   - Initial allowlist: `{entry_id}`, `{chain_code}`, `{frame_name}`, `{shift_list}`, `{chain}`
   - Additional keys like `{timestamp}`, `{user}` - evaluate per security model
   - Document allowed keys in `secure_templates.py` and `CLAUDE.md`

4. **Matplotlib/External Libraries**:
   - `plt.savefig()` and similar - wrap in helper that validates path first
   - Create `secure_savefig(path, **kwargs)` that calls `expand_path_template()` then `plt.savefig()`
   - Document pattern for other libraries

5. **Testing Strategy**:
   - Unit tests for `expand_path_template()`, `expand_template()`, `secure_open()` in `tests/lib/`
   - Integration tests for sandbox enforcement in `tests/ai/test_nef_mcp_server.py`
   - Meta-tests for enforcement in `tests/meta_tests/`
   - Each stage independently testable

6. **Documentation**:
   - Update MCP server docs in `resources/mcp_server/` with security model
   - Add section to `CLAUDE.md` on secure template/I/O patterns
   - Document migration path for existing exporters

## Scope Exclusions

**Not in this plan** (separate efforts):
- Stage 7 (Standardised Output Return Format) → separate plan `plan-standardisedPipeOutput.prompt.md`
  - Return format: `pipe(Entry,...) -> Tuple[Entry, List[Tuple[str, Path]]]`
  - Standardized `--out` handling across commands
  - This is API design, not security enforcement

## Context References

### Key Files Identified

**Template Usage:**
- `sparky/exporters/shifts.py:42` - `DEFAULT_OUTPUT_TEMPLATE = "{shift_list}_{chain}_shifts.txt"`
- `shifty/exporters/shifts.py:25` - `FILE_NAME_TEMPLATE = "{nef_entry_id}_{chain_code}.shifty"`
- `pales/exporters/rdcs.py:50` - `file_name_template: str = typer.Option("%s.out", ...)`
- `save.py:37` - `template: str = typer.Option("{entry_id}.nef", ...)`
- `mars/exporters/input.py:104` - Uses f-strings: `f"{entry.entry_id}.inp"`

**Direct File Writes (18 locations identified):**
- `mars/exporters/input.py:107` - `open(output_path, "w")`
- `sparky/exporters/shifts.py:397` - `open(filename, "w")`
- `sparky/exporters/peaks.py:200` - `open(file_name, "w")`
- `mars/exporters/fragments.py:98` - `open(output_file, "w")`
- `mars/exporters/fixed.py:108` - `open(output_file, "w")`
- `mars/exporters/shifts.py:201` - `open(output_file, "w")`
- `shifty/exporters/shifts.py:183` - `open(output_file, "w")`
- `xcamshift/exporters/shifts.py:100` - `open(output_file, "w")`
- `fasta/exporters/sequence.py:84` - `open(output_file, "w")`
- `nmrview/exporters/shifts.py:289` - `open(file_name, "w")`
- `nmrview/exporters/sequences.py:212` - `open(file_name, "w")`
- `rpf/exporters/shifts.py:372` - `open(file_name, "w")`
- `rcsb/align.py:342, 418` - `open(output_file, "w")`
- `rcsb/trim.py:371, 430` - `open(output_file, "w")`
- `shiftx2/importers/shifts.py:777` - `open(file_path, "w")`
- `lib/translation/io.py:556` - `open(json_chem_comp, "w")`

**Plot Output:**
- `tools/shifts/correlation.py:602` - `plt.savefig(f"{output_path}{file_format}", dpi=300)`

**Existing Security Infrastructure:**
- `tools/ai/mcp_lib.py:202-312` - `_validate_path_in_sandbox()` function
- `tools/ai/mcp_commands.py:101-122` - `nef_upload_file()` with sandbox validation
- `tests/meta_tests/test_banned_functions.py` - AST-based function banning pattern

## Implementation Notes

### Bottleneck Rationale

**Why force ALL `.format()` through bottlenecks (even non-path templates)?**

1. **Enforceability**: Meta-test can ban ALL bare `.format()` - no exceptions to track
2. **Audit Trail**: `git grep expand_path_template` finds every file operation
3. **Intent Declaration**: Code self-documents: "this is/isn't a file path template"
4. **Future-Proof**: If security model changes, easy to add checks to `expand_template()`
5. **Consistency**: Single pattern across entire codebase

**Why `expand_template()` does NO security checks?**

- Only file paths need sandbox validation
- Help text, log messages, table formatting are not security concerns
- `expand_template()` is a marker/documentation function, not a security boundary
- Keeps implementation simple: security only in `expand_path_template()`

### Usage Examples

```python
from typing_extensions import Annotated
from pathlib import Path
import typer
from nef_pipelines.lib.secure_templates import expand_path_template, expand_template
from nef_pipelines.lib.secure_io import secure_open

# TYPE ANNOTATIONS for typer parameters (enables meta-test checking)
PathTemplate = Annotated[str, "path_template"]
Template = Annotated[str, "template"]

@app.command()
def export_shifts(
    output_template: PathTemplate = typer.Option(
        "{entry_id}_{chain}.shifts",
        help="Output filename template"
    ),
    chain: str = typer.Option("A", help="Chain code")
):
    """Export shifts with path template"""
    # PATH TEMPLATE - goes through expand_path_template() with sandbox check
    output_path = expand_path_template(
        output_template,
        {"entry_id": entry.entry_id, "chain": chain},
        sandbox=get_global_sandbox()  # from main.py --sandbox-path
    )
    with secure_open(output_path, "w") as f:
        f.write(content)

# NON-PATH TEMPLATE - goes through expand_template() with NO checks
error_msg = expand_template(
    "Failed to process chain {chain} at residue {res}",
    {"chain": "A", "res": 42}
)
warn(error_msg)

# BANNED - bare .format() caught by meta-test
filename = "{entry_id}.nef".format(entry_id=entry.entry_id)  # ❌ FAILS META-TEST

# BANNED - bare open() caught by meta-test
with open(filename, "w") as f:  # ❌ FAILS META-TEST
    f.write(content)
```

### Template Security Warning

From `docs/design_overview.md:343`:
> The way filename templates are currently supported makes NEF-Pipelines insecure to use as web service as
> the internal data can be leaked from the program and arbitrary code run as part of file name templates.
> This will be addressed in a future version of NEF-Pipelines if there is a need or a request is received to
> use it as part of a web service.

This plan directly addresses this documented security concern.

### Existing Patterns to Follow

1. **AST-based enforcement**: Follow pattern from `test_banned_functions.py` which checks for `fnmatch.fnmatch` usage
2. **Sandbox validation**: Reuse `_validate_path_in_sandbox()` logic from `mcp_lib.py`
3. **Meta-tests**: Add to `tests/meta_tests/` directory alongside existing meta-tests

## Success Criteria

**This plan is complete when:**

1. ✅ All path templates go through `expand_path_template()` with sandbox validation
2. ✅ All non-path `.format()` calls go through `expand_template()` (marker function)
3. ✅ All write-mode `open()` calls go through `secure_open()` with sandbox validation
4. ✅ Meta-tests detect and fail on:
   - Any bare `.format()` calls
   - Any direct `open()` calls for writing
5. ✅ Audit hook provides runtime defense-in-depth (intercepts and vetoes via exceptions)
6. ✅ Type annotations (`PathTemplate`, `Template`) enable static identification
7. ✅ MCP server runs with sandbox enabled and all file operations are contained
8. ✅ Existing commands continue working (backward compatible migration)

**Security Goals Achieved:**
- ✅ No arbitrary code execution via template injection
- ✅ No path traversal attacks (no `..`, no absolute paths escaping sandbox)
- ✅ No information disclosure via reading outside sandbox
- ✅ Audit trail: easy to find all file operations via `expand_path_template()`
- ✅ Enforceability: automated checks prevent future violations
