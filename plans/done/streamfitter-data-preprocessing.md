# Streamfitter Data Preprocessing and Refinements

**Status:** Not started
**Created:** 2026-07-08
**Depends on:** refactor-streamfitter-failure-handling.md (Phase 1 complete ✅)

## Context

After completing the status-based refactoring (FitExitStatus, MC failure tracking, etc.), several data preprocessing and consistency issues remain:

1. **Unsorted xs**: Fitter `estimate()` methods may assume sorted x values but data isn't guaranteed to be sorted
2. **Duplicate xs**: Multiple y values at the same x point need aggregation (mean) for consistent estimation
3. **MC consistency**: Monte Carlo steps should use the same preprocessed (sorted, deduplicated) data as initial fit
4. **MC estimates**: Each MC cycle should include an initial parameter estimate for better convergence
5. **Naming**: `time_constant` should be renamed to `rate` for accuracy

the nuance of 3 and 4 may not be clear as each motecarlo step uses a new data array with the fitted value and
random added noise the averaging of replicates needs to be done at each round

## TODO Items

### 1. Preprocess Once for estimate() Only

**Problem:**
- Fitter `estimate()` methods may not handle unsorted/duplicate x data correctly
- Sorting/aggregating repeatedly is inefficient
- Moving preprocessing into fitter methods would break JAX (shape changes)

**IMPORTANT CONSTRAINTS:**
- **Preprocessing is ONLY for `estimate()` calls** (artifact of how estimators work)
- **Actual fitting (minimizer) uses ORIGINAL data with all points**
- Reason: Duplicates represent replicate measurements - removing them loses information about variance
- **Preprocessing should be in estimate() methods but without per-call overhead**

**Two solution options (no backward compatibility needed):**

**Option 1: External preprocessing**
- Preprocess outside `estimate()` before each call
- Pro: Simple, no changes to fitter classes
- Pro: Preprocessing visible at call site
- Con: Logic scattered across calling code
- Con: Not encapsulated in estimator where it belongs

**Option 2: Built-in with opt-out flag**
```python
def estimate(self, xs, ys, preprocess=True):
    """Estimate parameters from data.

    Args:
        xs, ys: Input data arrays
        preprocess: If True, sort and deduplicate xs (default True)
                   Set False when data already preprocessed (avoids overhead)
    """
    if preprocess:
        xs, ys = _preprocess_for_estimate(xs, ys)
    # ... existing estimate logic
```
- Pro: Preprocessing lives with estimator (belongs there conceptually)
- Pro: Opt-out when preprocessing already done (no overhead in MC loops)
- Pro: Default behavior is safe (always preprocesses)
- Pro: Single method, clear intent
- Con: Requires updating all fitter classes

**Recommendation:** Option 2 (built-in with opt-out)
- Preprocessing encapsulated where it belongs (in estimator)
- `preprocess=True` by default (safe, works for standalone use)
- `preprocess=False` for MC loops (performance, already preprocessed)
- No backward compatibility constraints simplify design

**Implementation:**
```python
def _preprocess_xy_data(xs, ys):
    """Sort and aggregate duplicate x values (done ONCE per series).

    1. Aggregate: Group duplicate xs, take mean of ys
    2. Sort: Order by x values

    Args:
        xs: Array of x values (may be unsorted, may have duplicates)
        ys: Array of y values

    Returns:
        tuple: (preprocessed_xs, preprocessed_ys) - sorted, no duplicates
    """
    from collections import defaultdict

    # Aggregate duplicate xs
    x_to_ys = defaultdict(list)
    for x, y in zip(xs, ys):
        x_to_ys[float(x)].append(float(y))

    # Sort and calculate means
    sorted_xs = sorted(x_to_ys.keys())
    unique_xs = np.array(sorted_xs)
    aggregated_ys = np.array([np.mean(x_to_ys[x]) for x in sorted_xs])

    return unique_xs, aggregated_ys
```

**Where to apply:**
```python
def _fit_series_nonlinear(passing_data, fitter, fits, estimates, stats, ...):
    """Fit NON_LINEAR series."""

    # Fit passing data
    func = fitter.get_wrapped_function()
    jacobian = fitter.get_wrapped_jacobian()

    for data_id, (xs, ys) in passing_data.items():
        stats['last_attempted_id'] = data_id

        # Preprocess ONLY for estimate (once per series)
        preprocessed_xs, preprocessed_ys = _preprocess_xy_data(xs, ys)

        # Get initial estimates using PREPROCESSED data
        estimated_parameters_dict = fitter.estimate(preprocessed_xs, preprocessed_ys)
        estimates[data_id] = estimated_parameters_dict

        # Build parameters from estimates
        params = Parameters()
        bounds = fitter.bounds() if hasattr(fitter, 'bounds') else {}
        for key, value in estimated_parameters_dict.items():
            min_val, max_val = bounds.get(key, (None, None))
            params.add(key, value=value, min=min_val, max=max_val)

        # Fit using ORIGINAL data (all points, including duplicates)
        minimizer = Minimizer(func, params, fcn_args=(xs,), fcn_kws={'data': ys})
        out = minimizer.leastsq(Dfun=jacobian, col_deriv=1)
        # ... rest of fitting
```

**For Monte Carlo (each cycle needs own estimate due to different noise):**
```python
# In _calculate_monte_carlo_error or similar:
for id, fit in fits.items():
    xs = id_xy_data[id][0]  # Same xs for all MC cycles

    # OPTIMIZATION: xs are the same for all MC cycles
    # Preprocess xs structure once, reuse for all cycles
    if has_duplicates(xs):
        # Get mapping of unique xs to indices
        unique_xs, indices_map = _get_unique_xs_map(xs)
    else:
        unique_xs = xs
        indices_map = None

    for i in range(num_cycles):
        # Generate noisy ys (xs stay same)
        mc_ys = back_calculated + noise

        # Aggregate ys if needed (using cached indices_map)
        if indices_map:
            aggregated_ys = _aggregate_ys_by_map(mc_ys, indices_map)
        else:
            aggregated_ys = mc_ys

        # Get MC estimates using preprocessed data
        mc_estimates = fitter.estimate(unique_xs, aggregated_ys)

        # Build params from estimates
        params = create_params(mc_estimates, fitter.bounds())

        # Fit using ORIGINAL MC data (with noise, all points)
        minimizer = Minimizer(func, params, fcn_args=(xs,), fcn_kws={'data': mc_ys})
        fit = minimizer.leastsq(Dfun=jacobian, col_deriv=1)
        # ... rest of MC processing
```

**MC Optimization:**
- xs are identical for all MC cycles (same measurement points)
- Only ys change (different noise each cycle)
- Can preprocess xs structure once, apply to all cycles
- Saves repeated sorting overhead (sort once, aggregate ys per cycle)

**Key points:**
- ✅ Preprocessing happens **once per series** when calling `estimate()`
- ✅ `estimate()` gets sorted, deduplicated data
- ✅ Minimizer/fitting uses **ORIGINAL data** (all points, including duplicates)
- ✅ MC estimates also use preprocessed data (once per cycle)
- ✅ MC fitting uses original noisy data (all points)
- ✅ JAX-safe: preprocessing happens outside fitter methods
- ✅ Preserves replicate information in fits

---

### 2. Linear fits preprocessing

**Problem:** LINEAR fits also call `estimate()` - do they need preprocessing?

**Solution:** Check if LINEAR fitters have `estimate()` methods:
- If yes: preprocess before calling `estimate()`, fit with original
- If no: no preprocessing needed (LINEAR is simpler)

**Implementation (if needed):**
```python
def _fit_series_linear(passing_data, fitter, fits, estimates, stats):
    """Fit LINEAR series."""
    stats['last_attempted_id'] = list(passing_data.keys())[-1] if passing_data else None

    for data_id, (xs, ys) in passing_data.items():
        # Check if fitter has estimate method
        if hasattr(fitter, 'estimate'):
            # Preprocess for estimate only
            preprocessed_xs, preprocessed_ys = _preprocess_xy_data(xs, ys)
            estimated_params = fitter.estimate(preprocessed_xs, preprocessed_ys)
            estimates[data_id] = estimated_params

        # Fit with original data
        out = fitter.fit(xs, ys)
        out.fit_status = 'success'
        fits[data_id] = out

        if not hasattr(fitter, 'estimate'):
            # Extract params from fit if no estimate method
            estimates[data_id] = {param: out.params[param].value for param in fitter.params()}

    return FitExitStatus.OK, fits, estimates, stats
```

---

### 4. Include initial estimate in each MC cycle

**Problem:** MC fits don't provide initial parameter estimates, potentially affecting convergence.

**Solution:**
- Run `fitter.estimate()` for each MC dataset before fitting
- Use MC-specific estimates as starting points for minimization

**Implementation:**
```python
# In _process_mc_fit_results or similar:
for data_id, (xs, mc_ys) in mc_keys_and_values.items():
    # Get initial estimate for this MC dataset
    mc_estimates = fitter.estimate(xs, mc_ys)

    # Use estimates as starting point for fit
    params = Parameters()
    for param_name, initial_value in mc_estimates.items():
        bounds = fitter.bounds().get(param_name, (None, None))
        params.add(param_name, value=initial_value,
                   min=bounds[0], max=bounds[1])

    # Fit with initial estimates
    minimizer = Minimizer(func, params, fcn_args=(xs,), fcn_kws={'data': mc_ys})
    out = minimizer.leastsq(Dfun=jacobian, col_deriv=1)
```

**Where to apply:**
- In the MC fitting loop (currently around line 227 in _process_mc_fit_results)
- Each MC cycle gets fresh estimate from its noisy data
- May improve convergence for difficult fits

**Note:** This changes MC behavior - verify it doesn't break existing tests or significantly change MC error estimates.

---

### 5. Rename time_constant → rate

**Problem:** Parameter is called `time_constant` but represents a rate (inverse time constant).

**Solution:**
- Rename parameter in fitter classes
- Update all references in code and tests
- Document the change

**Files to update:**
- `ExponentialDecay2Parameter.py`: Rename parameter
- `ExponentialDecay3Parameter.py`: Rename parameter (if exists)
- `SymmetricExponentialPair.py`: Rename parameter (if exists)
- All tests: Update assertions and expected parameter names
- Documentation: Update parameter descriptions

**Implementation:**
```python
# Old:
def params(self):
    return ['amplitude', 'time_constant']

# New:
def params(self):
    return ['amplitude', 'rate']

# Update bounds, estimate, function, jacobian accordingly
```

**Breaking change:** This changes the API - existing code expecting `time_constant` will break.

**Migration:**
- Deprecation warning for one release?
- Or direct rename with clear release notes?

---

## Implementation Order

**Recommended sequence:**

1. **Phase 1: Preprocessing function** (simple, self-contained)
   - Implement `_preprocess_xy_data()` (sort + aggregate in one function)
   - Add unit tests:
     - Test with unsorted data
     - Test with duplicate xs
     - Test with both unsorted and duplicates
     - Test preserves data integrity
     - Test empty/single-point edge cases

2. **Phase 2: Apply preprocessing once in fit()** (minimal changes)
   - Add preprocessing loop at top of `fit()` function
   - Create `preprocessed_data` dict with same IDs as `id_xy_data`
   - Pass `preprocessed_data` instead of `id_xy_data` to:
     - `_fit_series()`
     - `_calculate_monte_carlo_error()`
   - **No changes needed** to internal functions (signature-compatible!)
   - Verify existing tests still pass (or update expectations)

3. **Phase 3: MC initial estimates** (optional/experimental)
   - Update MC fitting loop to call `estimate()` per cycle
   - Use MC-specific estimates as initial values
   - Benchmark impact on MC runtime and accuracy
   - May be skipped if overhead is too high

4. **Phase 4: Rename time_constant → rate** (breaking change)
   - Update fitter classes
   - Update all tests
   - Update NEF-Pipelines tools
   - Document in release notes as breaking change

---

## Critical Files

**Streamfitter:**
- `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/fitter.py`
  - Add preprocessing functions
  - Update `_fit_series()` to preprocess data
  - Update `_calculate_monte_carlo_error()` to use preprocessed xs
  - Update MC fitting to include initial estimates

- `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/ExponentialDecay2Parameter.py`
  - Rename `time_constant` → `rate`

- `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/ExponentialDecay3Parameter.py`
  - Rename `time_constant` → `rate` (if applicable)

- `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/SymmetricExponentialPair.py`
  - Rename `time_constant` → `rate` (if applicable)

**Tests:**
- `/Users/garythompson/Dropbox/git/streamfitter/tests/test_fitter.py`
  - Add tests for preprocessing functions
  - Update tests for parameter rename

- `/Users/garythompson/Dropbox/git/streamfitter/tests/test_3_parameter_exponential_fitter.py`
  - Update parameter name references

**NEF-Pipelines (if time_constant exposed):**
- Search codebase for `time_constant` references and update

---

## Verification

**Unit tests:**
1. Test `_sort_xy_data()` with unsorted data
2. Test `_aggregate_duplicate_xs()` with duplicates
3. Test `_preprocess_xy_data()` combines both correctly
4. Test preprocessing preserves data integrity (no lost points)
5. Test MC uses preprocessed data (not original)
6. Test MC estimates improve convergence (benchmark)
7. Test parameter rename doesn't break fits

**Integration tests:**
1. Run full streamfitter test suite
2. Run NEF-Pipelines fit tests
3. Verify MC errors are consistent with expectations
4. Benchmark MC runtime with/without per-cycle estimates

**Manual verification:**
1. Fit exponential with unsorted data - should work
2. Fit exponential with duplicate xs - should aggregate
3. Check MC datasets use preprocessed xs
4. Verify `rate` parameter appears in output (not `time_constant`)

---

## Benefits

1. **Robustness**: Handles unsorted and duplicate input data
2. **Consistency**: MC and initial fits use identical preprocessed data
3. **Accuracy**: Duplicate xs properly aggregated (mean), not ignored or duplicated
4. **Convergence**: MC estimates may improve fit quality
5. **Clarity**: `rate` is more accurate name than `time_constant`

## Risks

1. **Behavior change**: Preprocessing may change fit results for existing data
2. **Performance**: Sorting/aggregation adds overhead (likely negligible)
3. **MC estimates**: Per-cycle estimates may slow MC significantly
4. **Breaking change**: Parameter rename breaks existing scripts

## Open Questions

1. Should preprocessing be optional (flag) or always-on?
2. Should MC estimates be configurable (may be slow)?
3. How to handle time_constant → rate migration (deprecation period)?
4. Should preprocessed data be included in fit results for transparency?
