# Refactor Streamfitter Failure Handling: Status-Based Results

**Status:** Phase 1 Complete ✅ (2026-07-08)
**Next Steps:** See `streamfitter-data-preprocessing.md` for remaining work

## User Comments (Requirements)

1. **Keep nef_pipelines dependency**: Making streamfitter independent is a later problem - use interface for now
2. **No exceptions**: Streamfitter should return results as it does now, but with more global result metadata
a3. **Two failure modes only**: Match FailureHandling enum - either STOP or SKIP (WARN & COMMENT are nefpipelines level flags)
4. **Need output status**: fit() needs to relay: stopped/completed status, how many calculated, last one calculated
5. **Two different error handling paths**:
   - **Initial fits**: Respect FailureHandling - either skip failed calculations or stop calculating entirely. Need exit status (completed vs stopped-due-to-error)
   - **Monte Carlo fits**: Always continue despite failures, record failure count by id
6. **Return dictionary not dataclass**: Linear fits don't need Monte Carlo baggage - keep flexible dict structure
7. **Linear fits have no failures**: Linear fits always succeed (no DOF check, no optimization failure)

## Context

Streamfitter's fit() function currently returns a dictionary with fit results, but lacks clear communication about:
- Whether the fitting process completed successfully or was stopped due to errors
- How many series were successfully fitted vs failed
- Which specific series was the last one attempted
- Detailed Monte Carlo failure statistics per series

**Current Problems:**
1. **No overall status**: Can't tell if fit() completed all series or stopped early
2. **Unclear progress**: No way to know how many series were processed before a stop
3. **Opaque failures**: Initial fit failures and Monte Carlo failures handled the same way
4. **Poor MC diagnostics**: Monte Carlo failures are silently skipped with minimal tracking

**Current Behavior:**
- Initial fits: Use `failure_handling` (STOP/WARN) and `failure_output` (COMMENT/SKIP)
- MC fits: Always use WARN/COMMENT internally (hardcoded defaults)
- Returns dict with 'fits', 'estimates', 'monte_carlo_errors', etc.
- Status communicated via `fit.fit_status` and `fit.success` flags on individual fits

## Proposed Solution

Wrap fit() results in a status structure and differentiate initial fit vs Monte Carlo failure handling.

### Phase 1: Enhance Dictionary Return Value

**Add exit status enum in `fitter.py`:**

```python
from enum import auto
from strenum import LowercaseStrEnum

class FitExitStatus(LowercaseStrEnum):
    """Overall exit status of fit() function."""
    OK = auto()  # All requested fits attempted
    STOPPED = auto()  # Stopped early due to error with STOP policy
```

**Enhance existing dictionary with new fields:**

```python
# Current return (dict):
return {
    'fit_type': fitter.type,
    'fits': fits,
    'estimates': estimates,
    'monte_carlo_errors': monte_carlo_errors,  # NON_LINEAR only
    'monte_carlo_value_stats': monte_carlo_value_stats,  # NON_LINEAR only
    'monte_carlo_param_values': monte_carlo_param_values,  # NON_LINEAR only
    'versions': versions_string,
    'calculation_time': time_delta,
    # ... other existing fields
}

# Enhanced return (still dict, add new fields):
return {
    'exit_status': FitExitStatus.OK,  # NEW - or STOPPED
    'total_requested': len(id_xy_data),  # NEW
    'failed_fits': failed_count,  # NEW
    'last_attempted_id': last_id,  # NEW - IDs attempted in sort order
    'fit_type': fitter.type,
    'fits': fits,
    'estimates': estimates,
    'monte_carlo_errors': monte_carlo_errors,  # NON_LINEAR only
    'monte_carlo_value_stats': monte_carlo_value_stats,  # NON_LINEAR only
    'monte_carlo_param_values': monte_carlo_param_values,  # NON_LINEAR only
    'mc_failed_cycles': mc_failed_cycles,  # NEW - NON_LINEAR only, Dict[id, int]
    'versions': versions_string,
    'calculation_time': time_delta,
    # ... other existing fields
}
```

**Note:** successful_fits removed - can be calculated as `total_requested - failed_fits`

**Key points:**
- Keep dict structure for flexibility (LINEAR vs NON_LINEAR needs)
- LINEAR fits: no MC fields, exit_status always OK (no failures)
- NON_LINEAR fits: includes MC fields and can have STOPPED status

**TODO (future enhancement):**
- Consider using TypedDict for type hints (TypedDicts can inherit for LINEAR vs NON_LINEAR variants)
- Not in scope for this refactoring

### Phase 2: Refactor Initial Fit Handling

**FailureHandling in streamfitter (NON_LINEAR only):**
- **STOP**: Stop on first error, return dict with `exit_status=STOPPED`
- **SKIP**: Skip failed series, continue with rest, return `exit_status=OK`
- Note: WARN is a NEF-Pipelines level concern (logs then treats as SKIP)

**LINEAR fits:**
- No DOF checking (always enough degrees of freedom)
- No failure handling needed (always succeed)
- Always return `exit_status=OK`
- No need to pass `failure_handling` parameter (ignored)

**Create helper `_check_dof()` - simple boolean check:**

```python
def _check_dof(data_id, num_points, min_dof):
    """Check if data has sufficient degrees of freedom.

    Returns:
        bool: True if insufficient DOF (failed), False if sufficient (passed)
    """
    return num_points <= min_dof
```

**Create `_filter_data_by_dof()` to respect STOP:**

Currently DOF checking doesn't actually stop - it just creates placeholders. Change to:

**Remove failure_output parameter - streamfitter always creates failed fit placeholders:**

```python
def _filter_data_by_dof(ids_and_values, fitter, fits, estimates,
                        failure_handling):
    """Filter data by DOF check, mutating fits/estimates for failing data.

    Returns:
        tuple: (passing_data, should_stop, last_attempted_id)
        - passing_data: dict of series that passed DOF check
        - should_stop: bool, True if STOP policy triggered
        - last_attempted_id: ID of last series checked before stop
    """
    min_dof = fitter.minimum_degrees_of_freedom()
    passing_data = {}
    should_stop = False
    last_attempted_id = None

    for data_id, (xs, ys) in ids_and_values.items():
        last_attempted_id = data_id
        dof_failed = _check_dof(data_id, len(xs), min_dof)  # Returns bool, doesn't raise

        if dof_failed:
            if failure_handling == FailureHandling.STOP:
                should_stop = True
                break  # Stop immediately, don't process more series

            # SKIP mode - always create placeholder (COMMENT is NEF-Pipelines concern)
            fits[data_id] = _create_failed_fit(fitter, "insufficient_dof")
            estimates[data_id] = {param: 0.0 for param in fitter.params()}
        else:
            passing_data[data_id] = (xs, ys)

    return passing_data, should_stop, last_attempted_id
```
**Rename function:** `_fit_series_or_raise_if_required()` → `_fit_series()` (simpler name, raising is internal detail)

**Update `_fit_series()` similarly:**

Add progress tracking and early exit on STOP:

```python
def _fit_series(ids_and_values, fitter,
                failure_handling=FailureHandling.SKIP,
                debug=False):
    """Fit multiple series with failure handling.

    NON_LINEAR: Checks DOF, respects failure_handling
    LINEAR: No DOF check, always succeeds

    Returns:
        tuple: (fits, estimates, exit_status, stats)
        - fits: dict of fit results
        - estimates: dict of parameter estimates
        - exit_status: OK or STOPPED
        - stats: dict with 'failed', 'last_attempted_id'
    """
    fits = {}
    estimates = {}
    stats = {
        'failed': 0,
        'last_attempted_id': None
    }

    if fitter.type == FitType.NON_LINEAR:
        # Pre-check DOF (can fail and stop)
        passing_data, should_stop, last_id = _filter_data_by_dof(
            ids_and_values, fitter, fits, estimates, failure_handling
        )
        stats['last_attempted_id'] = last_id

        if should_stop:
            stats['failed'] = 1  # At least one failed to trigger stop
            return fits, estimates, FitExitStatus.STOPPED, stats

        # Fit passing data with progress tracking
        # ... (NON_LINEAR fitting logic, count failures)

    elif fitter.type == FitType.LINEAR:
        # LINEAR: no DOF check, always succeeds
        passing_data = ids_and_values  # All data passes
        stats['last_attempted_id'] = list(ids_and_values.keys())[-1] if ids_and_values else None

        # Fit all data (always succeeds, failed=0)
        # ... (LINEAR fitting logic)

    return fits, estimates, FitExitStatus.OK, stats
```

### Phase 3: Enhanced Monte Carlo Statistics

**Track MC failures - simple dict, no dataclass needed:**

```python
def _calculate_monte_carlo_error(fitter, id_xy_data, fits, noise_level, num_cycles, ...):
    """Calculate MC errors with per-series failure tracking.

    MC failures never stop calculation - they are tracked but processing continues.

    Returns existing dicts plus:
        mc_failed_cycles: Dict[data_id, int] - count of failed MC cycles per series
    """
    mc_failed_cycles = {}  # NEW: data_id -> failed count

    for row_count, (id, fit) in enumerate(fits.items()):
        # ... existing setup ...

        failed_count = 0

        # Generate and fit MC data
        for i in range(num_cycles):
            # ... generate MC data ...

            # Try to fit - if it fails, count it but continue
            try:
                mc_fit = _fit_single_series(data_id, xs, mc_data, fitter)
                # ... accumulate statistics from successful fit ...
            except (InsufficientDegreesOfFreedomException, Exception):
                failed_count += 1
                # Don't stop - just count and continue

        # Store failed count for this series
        mc_failed_cycles[id] = failed_count

    return mc_fitted_params, mc_value_stats, mc_fitted_param_values, mc_failed_cycles
```

### Phase 4: Update fit() Return Value

**Enhance fit() to return dict with new fields (remove failure_output parameter):**

```python
def fit(fitter, id_xy_data, cycles, noise_info, seed=42, verbose=0,
        failure_handling=FailureHandling.SKIP) -> Dict:
    """Fit data series with optional Monte Carlo error propagation.

    Args:
        failure_handling: STOP or SKIP (NON_LINEAR only; LINEAR ignores)

    Returns:
        Dict with:
        - exit_status: OK or STOPPED (FitExitStatus enum)
        - total_requested, failed_fits, last_attempted_id (NEW)
        - fits, estimates: existing result dicts
        - monte_carlo_*: existing MC dicts (NON_LINEAR only)
        - mc_failed_cycles: Dict[id, int] - NEW (NON_LINEAR only)
        - fit_type, versions, calculation_time, etc.: existing metadata
        Note: successful_fits = total_requested - failed_fits (calculated by caller if needed)
    """
    start_time = time.time()

    # Initial fit with progress tracking (no failure_output)
    fits, estimates, exit_status, stats = _fit_series(
        id_xy_data, fitter, failure_handling
    )

    # Monte Carlo (only for NON_LINEAR if initial fit had successes)
    mc_failed_cycles = {}
    monte_carlo_errors = {}
    # ... other MC dicts ...

    if fits and fitter.type == FitType.NON_LINEAR and noise_info:
        # ... MC calculation ...
        _, _, _, mc_failed_cycles = _calculate_monte_carlo_error(...)

    end_time = time.time()

    # Build result dict
    result = {
        'exit_status': exit_status,
        'total_requested': len(id_xy_data),
        'failed_fits': stats['failed'],
        'last_attempted_id': stats['last_attempted_id'],
        'fit_type': fitter.type,
        'fits': fits,
        'estimates': estimates,
        'versions': versions_string,
        'calculation_time': timedelta(seconds=end_time - start_time),
        # ... other existing fields ...
    }

    # Add MC fields only for NON_LINEAR
    if fitter.type == FitType.NON_LINEAR:
        result.update({
            'monte_carlo_errors': monte_carlo_errors,
            'monte_carlo_value_stats': monte_carlo_value_stats,
            'monte_carlo_param_values': monte_carlo_param_values,
            'mc_failed_cycles': mc_failed_cycles,
        })

    return result
```

### Phase 5: NEF-Pipelines Integration

**Update exponential.py to handle FitResult:**


**COMMENT** remmeber to apply claude.md [mutiline strings!]

```python
result = fitter.fit(...)  # Returns FitResult now

# Check exit status
if result.exit_status == FitExitStatus.STOPPED:
    exit_error(
        f"Fitting stopped on error at series {result.last_attempted_id}. "
        f"Processed {result.successful_fits}/{result.total_requested} series."
    )

# Extract results (same dict structure as before)
fits = result.fits
monte_carlo_errors = result.monte_carlo_errors
# ... etc
```

**Update fit_lib.py to include MC statistics in output:**

```python
def _fit_results_as_frame(..., monte_carlo_statistics, ...):
    # ... existing code ...

    # Add MC statistics to comment
    if monte_carlo_statistics:
        total_cycles = sum(s.total_cycles for s in monte_carlo_statistics.values())
        total_successful = sum(s.successful_cycles for s in monte_carlo_statistics.values())
        total_failed = sum(s.failed_cycles for s in monte_carlo_statistics.values())

        mc_info = f"""
        monte carlo total cycles: {total_cycles}
        monte carlo successful: {total_successful}
        monte carlo failed: {total_failed}
        """

        comment += mc_info
```

**COMMENT** total cycles and number failed is all thats needed [this is per fit]
**COMMENT** failure statistics are per fit so may need to be an extra column in output table

## Critical Files

**Streamfitter (to modify):**
- `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/fitter.py`
  - Add `FitExitStatus` enum (OK, STOPPED)
  - Rename `_filter_data_by_dof_or_raise()` → `_filter_data_by_dof()` and:
    - Remove failure_output parameter
    - Support early STOP (break on first failure when STOP policy)
  - Rename `_fit_series_or_raise_if_required()` → `_fit_series()` and:
    - Remove failure_output parameter
    - Return exit status and stats tuple (no successful_fits in stats)
    - Skip DOF check for LINEAR fits (always succeed)
  - Update `_calculate_monte_carlo_error()` to track failed cycles per series (return Dict[id, int])
  - Enhance `fit()` to:
    - Remove failure_output parameter
    - Return enhanced dict with new fields: exit_status, total_requested, failed_fits, last_attempted_id, mc_failed_cycles
    - Note: successful_fits removed (= total_requested - failed_fits)

**NEF-Pipelines (to modify):**
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/exponential.py`
  - Update to handle enhanced dict return value (still dict, new fields)
  - Check `result['exit_status']` and handle STOPPED case
  - Remove failure_output parameter from fit() call
  - Extract `result['mc_failed_cycles']` for display

- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/fit_lib.py`
  - Add `mc_failed_cycles` parameter to `_fit_results_as_frame()`
  - Include MC failure statistics in frame comments

- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/mean.py`
  - Update to handle enhanced dict (if it uses fitter.fit())

- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/t1noe.py`
  - Update to handle enhanced dict (if it uses fitter.fit())

**Existing functions to modify/reuse:**
- `_create_failed_fit()` - keep for creating placeholder fit objects (NON_LINEAR only)
- `_check_dof()` - simplify from `_check_dof_and_raise_if_required`: just return bool, no exceptions
- `InsufficientDegreesOfFreedomException` - keep defined but may not be used (no exceptions in this design)

## Verification

**Unit tests (streamfitter):**
1. Test `FitResult` dataclass structure and fields
2. Test `MonteCarloStatistics` dataclass
3. Test `_filter_data_by_dof_or_raise()` with STOP - should return `should_stop=True` and break early
4. Test `_filter_data_by_dof_or_raise()` with SKIP - should continue through all series
5. Test `_fit_series_or_raise_if_required()` returns STOPPED when DOF check fails with STOP
6. Test `_fit_series_or_raise_if_required()` returns COMPLETED when using SKIP
7. Test `fit()` returns FitResult with correct `exit_status`
8. Test `fit()` populates `total_requested`, `successful_fits`, `failed_fits`, `last_attempted_id`
9. Test MC statistics tracking: all successful, partial failures, all failed
10. Test MC failures don't stop calculation (always continue)

**Integration tests (NEF-Pipelines):**
1. Run `nefl test` on streamfitter tests - all should pass
2. Test `nef fit exponential` with --failure-handling=stop and bad data - should exit with error showing last_attempted_id
3. Test `nef fit exponential` with --failure-handling=skip and bad data - should complete and skip failed series
4. Test `nef fit exponential` with noisy data causing MC failures - check output includes MC statistics
5. Verify tools handle `FitResult` return type correctly

**Manual verification:**
1. Run exponential fit with --failure-handling=stop on data with insufficient DOF
   - Should see error message: "Fitting stopped on error at series X. Processed N/M series."
2. Run exponential fit with --failure-handling=skip
   - Should complete successfully, output includes all passing series
3. Check output frames include MC statistics comments:
   ```
   monte carlo total cycles: 10000
   monte carlo successful: 9876
   monte carlo failed: 124
   ```
4. Verify per-series MC failure counts are reasonable (not too high)

## Benefits

1. **Clear exit status**: Can tell if fitting completed or stopped early via `exit_status` field
2. **Progress visibility**: Know exactly how many series succeeded/failed and which was last attempted
3. **Better diagnostics**: Per-series MC failure counts in `mc_failed_cycles`
4. **Semantic clarity**: Initial fit failures (can stop) vs MC failures (always continue) handled differently
5. **Flexible dict structure**: LINEAR fits omit MC fields, NON_LINEAR includes them
6. **Simpler than exceptions**: No exception handling needed in NEF-Pipelines tools
7. **Mostly backward compatible**: Still returns dict, just with new fields
8. **LINEAR simplicity**: No failure handling for LINEAR fits (always succeed)

## Migration Impact

**Minor breaking change:** fit() signature changes (removes failure_output parameter)

**NEF-Pipelines tools must update:**
```python
# Old:
result = fitter.fit(..., failure_handling=..., failure_output=...)
fits = result['fits']

# New:
result = fitter.fit(..., failure_handling=...)  # No failure_output
fits = result['fits']  # Still a dict!

# Access new fields:
if result['exit_status'] == FitExitStatus.STOPPED:
    # Handle early termination
    print(f"Stopped at {result['last_attempted_id']}")
    successful = result['total_requested'] - result['failed_fits']
    print(f"Processed {successful}/{result['total_requested']}")

# Access MC failures (NON_LINEAR only):
if 'mc_failed_cycles' in result:
    for series_id, failed_count in result['mc_failed_cycles'].items():
        print(f"Series {series_id}: {failed_count} MC cycles failed")
```

**All tools using fitter.fit() must update:**
- tools/fit/exponential.py - remove failure_output parameter, handle new dict fields
- tools/fit/mean.py - remove failure_output (if applicable)
- tools/fit/t1noe.py - remove failure_output (if applicable)
- tools/fit/fit_lib.py - pass `mc_failed_cycles` to frame builder

**WARN and COMMENT handling moves to NEF-Pipelines:**
- NEF-Pipelines tools decide whether to log warnings for failures
- NEF-Pipelines tools decide whether to skip or include failed fits in output
