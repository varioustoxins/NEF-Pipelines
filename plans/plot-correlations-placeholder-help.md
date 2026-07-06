# Plot Correlations: Placeholder Help Improvement Plan

Date: 2026-03-11

## Current Status

### What's Implemented
- `--title` option with f-string style placeholders
- Placeholders for: `{frame1}`, `{frame2}`, `{frame1_raw}`, `{frame2_raw}`
- Per-dataset placeholders: `{atom_name_1}`, `{atom_name_2}`, `{chain_code_1}`, `{chain_code_2}`, `{residue_name_1}`, `{residue_name_2}`
- Shared placeholders when values match: `{atom_name}`, `{chain_code}`, `{residue_name}`
- `{sequence_code}` placeholder
- `--help-placeholders` option (verbose, static documentation)
- `--verbose` mode shows available placeholders during plotting
- Error messages show available placeholders when invalid placeholder used

### Current Problem
- `--help-placeholders` shows static, verbose reference documentation (100+ lines)
- Doesn't adapt to actual input data
- Too much information - user feedback: "too much"
- Violates principle: placeholders "should adapt to input"

## Proposed Solutions

### Option A: Dynamic Help (Read Input First)
Make `--help-placeholders` analyze the actual input data before showing placeholders.

**Pros:**
- Shows only placeholders available for user's specific data
- More useful than static reference
- Adapts to input as requested

**Cons:**
- Requires reading and parsing input just to show help
- More complex implementation
- Still an extra flag to remember

**Implementation:**
```python
if help_placeholders:
    entry = read_entry_from_file_or_stdin_or_exit_error(input_path)
    # Parse first pair of frame specs
    spec1, spec2 = parse_and_resolve_specs(entry, frame_specs[0:2])
    # Extract sample data
    sample_data = extract_sample_correlation_data(entry, spec1, spec2)
    # Show actual placeholders
    show_dynamic_placeholders(sample_data)
    raise typer.Exit()
```

### Option B: Remove --help-placeholders, Use --verbose Only
Simplest approach - rely on existing `--verbose` mode and error messages.

**Pros:**
- Simpler - one less flag
- `--verbose` already shows placeholders during actual plotting
- Error messages already list available placeholders
- Less code to maintain
- User discovers placeholders organically

**Cons:**
- No standalone help without running actual correlation
- User must try and fail to see available placeholders (but error is helpful)

**Implementation:**
1. Remove `_show_placeholder_help()` function
2. Remove `--help-placeholders` option
3. Remove `_help_placeholders_callback()` function
4. Update `--title` help text to mention `--verbose`
5. Ensure error messages are clear (already done)

**Updated help text:**
```
--title TEXT    custom title template with placeholders like {frame1}, {atom_name_1}.
                Use --verbose to see available placeholders for your data
```

### Option C: Minimal Static Help
Keep `--help-placeholders` but make it very brief - just placeholder names, no examples.

**Pros:**
- Quick reference available
- Doesn't require reading input
- Brief enough to not overwhelm

**Cons:**
- Still static, doesn't adapt to input
- Doesn't show what's actually available for user's data
- Violates "adapt to input" principle

**Implementation:**
```
--help-placeholders output:

Title Placeholders:
  {frame1}, {frame2}           - Frame names (cleaned)
  {frame1_raw}, {frame2_raw}   - Frame names (raw)
  {atom_name_1}, {atom_name_2} - Atom names from each dataset
  {chain_code_1}, {chain_code_2} - Chain codes from each dataset
  {residue_name_1}, {residue_name_2} - Residue names from each dataset
  {atom_name}, {chain_code}, {residue_name} - When values match
  {sequence_code}              - Residue number

Use --verbose with --title to see actual values for your data.
```

## Recommendation: Option B

**Remove `--help-placeholders` entirely**

### Rationale
1. **Simpler is better** - One less flag, less code
2. **Adapts to input** - `--verbose` shows actual placeholders for actual data
3. **Good error messages** - Already implemented, shows available placeholders when user makes mistake
4. **Discovery through use** - User tries `--title "{atom_name}"`, if it fails, error shows what's available
5. **Consistent with NEF-Pipelines** - Other tools don't have separate help flags for template variables

### User Workflow
```bash
# User wants custom title
nef plot correlations frame1 frame2 --title "{atom_name}"

# If placeholder unavailable, helpful error:
Error: Invalid placeholder {atom_name} in title template
Available: {atom_name_1}, {atom_name_2}, {chain_code}, {frame1}, {frame2}, ...

# User can also debug with verbose:
nef plot correlations frame1 frame2 --title "{atom_name_1}" --verbose
# Shows:
#     Available placeholders:
#       {atom_name_1} = CA
#       {atom_name_2} = CB
#       ...
```

## Implementation Steps

### Phase 1: Cleanup (Immediate)
1. Remove `_show_placeholder_help()` function (lines ~1070-1175)
2. Remove `help_placeholders` parameter from `correlations()` command
3. Remove `_help_placeholders_callback()` function
4. Change `frame_specs` back to required argument (`...` not `None`)
5. Remove validation check for `frame_specs` (no longer needed)

### Phase 2: Update Documentation
1. Update `--title` help text to be concise and mention `--verbose`
2. Update docstring in `_format_title_with_placeholders()` to be brief

### Phase 3: Verify (Testing)
1. Test that error messages show available placeholders clearly
2. Test that `--verbose` mode works as expected
3. Update any tests that reference `--help-placeholders` (if any)

## Files to Modify

1. `src/nef_pipelines/tools/plot/correlations.py`:
   - Remove `_show_placeholder_help()` (~100 lines)
   - Remove `_help_placeholders_callback()` (~4 lines)
   - Update `correlations()` command signature
   - Update `--title` help text

## Alternative: If User Strongly Wants Placeholder Help

If standalone help is essential, implement **Option A** (dynamic help) instead:
- Make `--help-placeholders` read actual input
- Show only placeholders available for user's specific correlation
- This satisfies "adapt to input" requirement
- More complex but more useful

## Decision Needed

Which option?
- **Option B (Recommended)**: Remove `--help-placeholders`, rely on `--verbose` and error messages
- **Option A**: Make `--help-placeholders` dynamic (reads input, shows actual placeholders)
- **Option C**: Keep `--help-placeholders` but make it minimal

## Current State (End of Day)

- `--help-placeholders` option exists but is too verbose (static 100+ line reference)
- All placeholder functionality is working correctly
- `--verbose` mode shows placeholders during plotting
- Error messages show available placeholders on failure
- Ready to implement chosen simplification approach

## Next Session

1. Get user decision on which option
2. Implement cleanup (likely Option B)
3. Test that workflow remains smooth
4. Consider if any documentation needs updating
