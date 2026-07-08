# Degrees of Freedom Checking and Failure Policies

## Context

Currently, streamfitter does not validate sufficient data points before fitting, leading to fits with zero or negative degrees of freedom and producing unreliable results. Additionally, there's no graceful way to handle fit failures - fits either succeed silently or crash.

This change adds:

1. **Degrees of freedom checking** for both NONLINEAR and LINEAR fits before attempting to fit
2. **FailureHandling** enum (FAIL, WARN, IGNORE) to control error behavior when DOF check fails
3. **FailureOutput** enum (COMMENT, SKIP) to control whether failed fits produce output rows
4. **Graceful failure handling** with `.fit_status` attribute on each fit object
5. **Auto-determined min_dof** via protocol's existing `params()` method

The motivation is to make fitting more robust, transparent about failures, and configurable for different use cases (strict validation vs permissive data collection).

## Design Decisions (Addressing Original Comments)

### Comment: "FailurePolicy as well as we may need a FailureOutputPolicy"

**Resolution**: Split into two independent enums:
- `FailureHandling(FAIL, WARN, IGNORE)` - What to do when DOF check fails
- `FailureOutput(COMMENT, SKIP)` - What to output for failed fits

**Rationale**: Allows flexible combinations:
- `WARN + COMMENT` (default): Log warning, output UNUSED values
- `FAIL + SKIP`: Strict validation, exit on error
- `IGNORE + SKIP`: Silent skip for exploratory data collection
- `WARN + SKIP`: Log warning but omit failed rows

### Comment: "just determine it from function by inspection"

**Resolution**: Default `min_dof()` implementation uses `len(self.params())`, which already uses `inspect.signature()`.

**Rationale**:
- Protocol already has `params()` that uses inspect on `function()`
- All fitters (NONLINEAR and LINEAR) should implement `function()`
- Default `params()` works for all fitters that implement `function()`
- Can override min_dof() if special logic needed (e.g., weighted fits)

**Note**: All fitters must implement `function()` for params() to work. LINEAR fitters like Mean fit constant or linear functions. Derived statistical outputs (like stddev) are not function parameters.

### Comment: "fit parameters getting so long it needs to be structured as dataclasses"

**Resolution**: Keep plain parameters for now (8 total after adding failure policies).

**Rationale**: Simpler immediate change. If we add more parameters in future, we can refactor to FitConfig dataclass then.

### Comment: "what if we want to warn and comment"

**Resolution**: Split policies enable WARN (handling) + COMMENT (output) combination.

**Rationale**: Two orthogonal concerns can be independently controlled.

### Comment: "fit status should be in the fit dictionary for the fit not an extra field"

**Resolution**: Add `.fit_status` attribute to each fit object instead of separate dict.

**Rationale**:
- Status travels with fit - better encapsulation
- Python allows adding attributes dynamically to both lmfit results and custom Fit objects
- Cleaner API than parallel dict

### Comment: "not only NONLINEAR fitting has this problem"

**Resolution**: Add DOF checking to both NONLINEAR and LINEAR branches of `_fit_series()`.

**Rationale**: Mean with 1 point can't compute meaningful stddev. LINEAR fits need validation too.

### Comment: "All NEF-Pipelines fitters will need updating, but this is really a change to streamfitter and fit_lib and this is where most of the testing should land"

**Resolution**: Focus testing strategy on streamfitter:
- **streamfitter**: 10+ comprehensive tests covering all policies, both fit types, edge cases
- **nef_pipelines**: 2-3 minimal integration tests verifying wiring works

**Rationale**: Core logic lives in streamfitter. nef_pipelines just wires CLI → streamfitter.

## Implementation Plan

### Phase 1: Add Enums and Update Protocol

#### 1.1 Add FailureHandling and FailureOutput enums

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/lib/interface.py`

After existing enums (around line 30), add:

```python
class FailureHandling(LowercaseStrEnum):
    FAIL = auto()      # Raise exception when fit fails DOF check
    WARN = auto()      # Log warning and continue
    IGNORE = auto()    # Silently continue (useful for exploratory data collection)


class FailureOutput(LowercaseStrEnum):
    COMMENT = auto()   # Output row with UNUSED values and fit_status="insufficient_dof"
    SKIP = auto()      # Skip row entirely, no output
```

#### 1.2 Add min_dof() default to FitterProtocol

**File**: `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/fitter_protocol.py`

After the `params()` method (around line 29), add:

```python
def min_dof(self):
    """Return minimum degrees of freedom required for fitting.

    Default: number of parameters. Requires n+1 data points for positive DOF.
    Override for custom requirements (e.g., weighted fits, special constraints).

    For a 2-parameter exponential, this returns 2, requiring ≥3 data points (DOF > 0).
    For Mean (mean + stddev), this returns 2, requiring ≥3 data points (DOF > 0).
    """
    return len(self.params())
```

**Note**: Uses existing `params()` method which already leverages `inspect.signature()` for NONLINEAR fitters.

#### 1.3 Add function() to Mean (LINEAR fitter)

**File**: `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/mean.py`

After the `type` property (around line 22), add:

```python
def function(self, mean, xs):
    """Return constant function for mean.

    Note: stddev is a derived statistical output, not a function parameter.
    """
    from jax.numpy import ones
    return ones(len(xs)) * mean
```

**Rationale**:
- Mean fits a constant function with parameter 'mean'
- stddev is a derived statistical result, not part of the function
- With function() defined, default params() returns ['mean']
- min_dof() = 1, requiring > 1 data points (DOF > 0)

### Phase 2: Add DOF Checking to streamfitter

#### 2.1 Add exception class

**File**: `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/fitter.py`

After existing exceptions (around line 56), add:

```python
@dataclass
class InsufficientDegreesOfFreedomException(StreamFitterException):
    data_id: int
    num_points: int
    min_required: int

    def __str__(self):
        dof = self.num_points - self.min_required
        return (f"Insufficient degrees of freedom for data_id '{self.data_id}': "
                f"has {self.num_points} points, needs >{self.min_required} "
                f"(DOF = {dof}, should be > 0)")
```

#### 2.2 Modify fit() function

**File**: `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/fitter.py`

**Import new enums** (line ~28):
```python
from nef_pipelines.lib.interface import FitType, NoiseInfoSource, FailureHandling, FailureOutput
```

**Update function signature** (line 277):

```python
def fit(
    fitter,
    id_xy_data,
    cycles: int,
    noise_info,
    seed: int = STREAMFITTER_DEFAULT_SEED,
    verbose=0,
    failure_handling: FailureHandling = FailureHandling.WARN,      # NEW
    failure_output: FailureOutput = FailureOutput.COMMENT,         # NEW
) -> Dict:
```

**Pass to _fit_series()** (line ~293):
```python
fits, estimates = _fit_series(id_xy_data, fitter, failure_handling, failure_output)
```

**Results dict unchanged** (fits now contain .fit_status attribute):
```python
results = {
    'fit_type': fitter.type,
    'fits': fits,  # Each fit has .fit_status attribute
    'estimates': estimates,
    'monte_carlo_errors': monte_carlo_errors,
    # ... rest unchanged
}
```

#### 2.3 Modify _fit_series() function

**File**: `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/fitter.py`

**Update signature and add helper** (line 348):

```python
def _fit_series(ids_and_values, fitter,
                failure_handling=FailureHandling.WARN,
                failure_output=FailureOutput.COMMENT,
                debug=False):
   fits = {}
   estimates = {}

   min_dof = fitter.minimum_degrees_of_freedom()  # Get minimum DOF requirement once

   def _check_and_handle_dof(data_id, xs, ys):
      """Check DOF and handle failure according to policies.

      Returns: (should_skip: bool, placeholder_fit: Fit|None)
      """
      num_points = len(xs)

      if num_points <= min_dof:
         # DOF check failed

         if failure_handling == FailureHandling.STOP:
            raise InsufficientDegreesOfFreedomException(
               data_id, num_points, min_dof
            )
         elif failure_handling == FailureHandling.WARN:
            logging.warning(
               f"Insufficient DOF for {data_id}: "
               f"{num_points} points, needs >{min_dof} "
               f"(DOF = {num_points - min_dof}, should be > 0)"
            )
         # IGNORE: no logging

         if failure_output == FailureOutput.SKIP:
            return True, None  # Skip this fit entirely
         else:  # COMMENT
            placeholder = _create_failed_fit(fitter, "insufficient_dof")
            return True, placeholder

      return False, None  # Continue with normal fitting
```

**Update NONLINEAR section** (around line 351):
```python
if fitter.type == FitType.NON_LINEAR:
    func = fitter.get_wrapped_function()
    jacobian = fitter.get_wrapped_jacobian()

    for data_id, (xs, ys) in ids_and_values.items():
        # DOF check
        should_skip, placeholder = _check_and_handle_dof(data_id, xs, ys)

        if should_skip:
            if placeholder is not None:
                fits[data_id] = placeholder
                estimates[data_id] = {param: 0.0 for param in fitter.params()}
            continue

        # Existing fitting logic
        params = Parameters()
        estimated_parameters_dict = fitter.estimate(xs, ys)
        estimates[data_id] = estimated_parameters_dict
        bounds = fitter.bounds() if hasattr(fitter, 'bounds') else {}
        for key, value in estimated_parameters_dict.items():
            min_val, max_val = bounds.get(key, (None, None))
            params.add(key, value=value, min=min_val, max=max_val)

        minimizer = Minimizer(func, params, fcn_args=(xs,), fcn_kws={'data': ys})
        out = minimizer.leastsq(Dfun=jacobian, col_deriv=1)

        # Add status to fit object
        out.fit_status = "success" if out.success else "fit_failed"

        if debug:
            print(data_id, out.params)
        fits[data_id] = out
```

**Update LINEAR section** (around line 370):
```python
elif fitter.type == FitType.LINEAR:
    for data_id, (xs, ys) in ids_and_values.items():
        # DOF check (same as NONLINEAR)
        should_skip, placeholder = _check_and_handle_dof(data_id, xs, ys)

        if should_skip:
            if placeholder is not None:
                fits[data_id] = placeholder
            continue

        # Existing fitting logic
        out = fitter.fit(xs, ys)

        # Add status to fit object
        out.fit_status = "success"

        fits[data_id] = out
```

**Add helper function** (after _fit_series):
```python
def _create_failed_fit(fitter, status="insufficient_dof"):
    """Create placeholder fit object for failed fits.

    Returns object compatible with both NONLINEAR (MinimizerResult-like)
    and LINEAR (Fit-like) result handling.
    """
    class FailedFit:
        def __init__(self, param_names, status):
            self.success = False
            self.fit_status = status
            self.params = {}

            # Create param dict compatible with both LINEAR and NONLINEAR
            for name in param_names:
                self.params[name] = type('FitParam', (), {'value': 0.0})()

            self.message = f"Fit failed: {status}"

    return FailedFit(fitter.params(), status)
```

### Phase 3: Update nef_pipelines Integration

#### 3.1 Update exponential.py

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/exponential.py`

**Import new enums** (line ~24):
```python
from nef_pipelines.lib.interface import (
    LoggingLevels, NoiseInfo, NoiseInfoSource,
    FailureHandling, FailureOutput
)
```

**Add CLI options** (in exponential() function, around line 60):
```python
failure_handling: FailureHandling = typer.Option(
    FailureHandling.WARN,
    "--failure-handling",
    help="how to handle DOF failures: fail (exit on error), warn (log warning), ignore (silent)",
),
failure_output: FailureOutput = typer.Option(
    FailureOutput.COMMENT,
    "--failure-output",
    help="output format for failed fits: comment (UNUSED values), skip (omit row)",
),
```

**Pass to pipe()** (line ~91):
```python
entry = pipe(entry, series_frames, cycles, noise_level, data_type, seed, verbose,
             failure_handling, failure_output)
```

**Update pipe() signature** (line ~104):
```python
def pipe(
    entry: Entry,
    series_frames: List[Saveframe],
    cycles: int,
    noise_level,
    data_type: IntensityMeasurementType,
    seed: int,
    verbose: int = 0,
    failure_handling: FailureHandling = FailureHandling.WARN,
    failure_output: FailureOutput = FailureOutput.COMMENT,
) -> Entry:
```

**Pass to fitter.fit()** (line ~172):
```python
results = fitter.fit(
    function(),
    id_xy_data,
    cycles,
    noise_info,
    seed,
    verbose=verbose,
    failure_handling=failure_handling,
    failure_output=failure_output,
)
```

**Extract fits** (line ~181):
```python
fits = results["fits"]  # Each fit now has .fit_status attribute
monte_carlo_errors = results["monte_carlo_errors"]
```

**Pass to _fit_results_as_frame()** (line ~193):
```python
frame = _fit_results_as_frame(
    series_frame,
    NEF_PIPELINES_NAMESPACE,
    entry,
    fits,  # fits contain status as .fit_status attribute
    fit_name,
    # ... rest of arguments unchanged
)
```

#### 3.2 Update fit_lib.py

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/fit_lib.py`

**Update _fit_results_as_frame()** - signature unchanged (line 118), but update implementation:

**Update frame comment** (lines 178-189):
```python
# Count failures by checking fit_status on each fit object
failed_fits = [
    data_id for data_id, fit in fits.items()
    if hasattr(fit, 'fit_status') and fit.fit_status != "success"
]
num_failed = len(failed_fits)
num_total = len(fits)

comment = f"""
    fitting software: {version_strings}
    ...existing fields...
    fits: {num_total - num_failed} successful, {num_failed} failed
    {f"failed data_ids: {', '.join(map(str, failed_fits))}" if failed_fits else ""}
"""
```

**Handle failed fits in result loop** (lines 208-239):
```python
for index, (data_id, fit) in enumerate(fits.items(), start=1):
    data_row = {"index": index, "data_id": index, "data_combination_id": UNUSED}

    # ... existing atom extraction code ...

    # Check fit status from fit object
    status = getattr(fit, 'fit_status', 'success')

    if status != "success":
        # Use UNUSED ('.') for failed fits
        data_row.update({
            "value": UNUSED,
            "value_error": UNUSED,
        })
    else:
        # Existing success handling
        if monte_carlo_errors:
            mc_error = monte_carlo_errors[data_id].get(f"{fit_name}_mc_error", UNUSED)
        else:
            mc_error = UNUSED
        data_row.update({
            "value": f"{fit.params[fit_name].value:.6f}",
            "value_error": f"{mc_error:.6}",
        })

    data.append(data_row)
```

### Phase 4: Add Tests (Focus on streamfitter)

**Testing strategy**: Comprehensive tests in streamfitter (core logic), minimal integration tests in nef_pipelines (wiring verification).

#### 4.1 streamfitter tests (PRIMARY TEST FOCUS)

**File**: `/Users/garythompson/Dropbox/git/streamfitter/tests/test_fitter.py`

Add comprehensive test suite:

```python
import pytest
import logging
from streamfitter.fitter import (
   fit, InsufficientDegreesOfFreedomException,
)
from streamfitter.ExponentialDecay2Parameter import ExponentialDecay2ParameterFitter
from streamfitter.mean import Mean
from nef_pipelines.lib.interface import FailureHandling, FailureOutput


# Test min_dof determination
def test_min_dof_exponential():
   """Verify ExponentialDecay2ParameterFitter.min_dof() returns correct value."""
   fitter = ExponentialDecay2ParameterFitter()
   params = fitter.params()
   assert fitter.minimum_degrees_of_freedom() == len(params)
   assert len(params) == 2  # A, T2 (or similar)


def test_min_dof_mean():
   """Verify Mean.min_dof() returns 1 (only mean is a function parameter)."""
   fitter = Mean()
   assert fitter.params() == ['mean']  # stddev is derived, not a parameter
   assert fitter.minimum_degrees_of_freedom() == 1


# Test DOF checking with FAIL policy
def test_insufficient_dof_nonlinear_fail_policy():
   """2 points with FAIL policy should raise exception for 2-param exponential."""
   fitter = ExponentialDecay2ParameterFitter()
   id_xy_data = {1: ([0.0, 1.0], [100.0, 50.0])}  # Only 2 points, need >2

   with pytest.raises(InsufficientDegreesOfFreedomException) as exc_info:
      fit(fitter, id_xy_data, cycles=0, noise_info=None,
          failure_handling=FailureHandling.STOP)

   assert exc_info.value.data_id == 1
   assert exc_info.value.num_points == 2
   assert exc_info.value.min_required == 2


def test_insufficient_dof_linear_fail_policy():
   """1 point with FAIL policy should raise exception for Mean."""
   fitter = Mean(id_xy_data={1: ([0.0], [100.0])}  # Only 1 point, need >1

   with pytest.raises(InsufficientDegreesOfFreedomException) as exc_info:
      fit(fitter, id_xy_data, cycles=0, noise_info=None,
          failure_handling=FailureHandling.STOP)

   assert exc_info.value.num_points == 1
   assert exc_info.value.min_required == 1

   # Test DOF checking with COMMENT policy


def test_insufficient_dof_comment_policy():
   """2 points with COMMENT policy should return placeholder fit."""
   fitter = ExponentialDecay2ParameterFitter()
   id_xy_data = {1: ([0.0, 1.0], [100.0, 50.0])}

   results = fit(fitter, id_xy_data, cycles=0, noise_info=None,
                 failure_handling=FailureHandling.WARN,
                 failure_output=FailureOutput.COMMENT)

   fits = results['fits']
   assert 1 in fits
   assert hasattr(fits[1], 'fit_status')
   assert fits[1].fit_status == "insufficient_dof"
   assert fits[1].success == False


# Test DOF checking with SKIP policy
def test_insufficient_dof_skip_policy():
   """2 points with SKIP policy should omit fit from results."""
   fitter = ExponentialDecay2ParameterFitter()
   id_xy_data = {
      1: ([0.0, 1.0], [100.0, 50.0]),  # Insufficient
      2: ([0.0, 1.0, 2.0, 3.0], [100.0, 50.0, 25.0, 12.5]),  # Sufficient
   }

   results = fit(fitter, id_xy_data, cycles=0, noise_info=None,
                 failure_handling=FailureHandling.IGNORE,
                 failure_output=FailureOutput.SKIP)

   fits = results['fits']
   assert 1 not in fits  # Skipped
   assert 2 in fits  # Included
   assert fits[2].fit_status in ["success", "fit_failed"]


# Test sufficient DOF succeeds
def test_sufficient_dof_succeeds_nonlinear():
   """3 points (minimal DOF=1) should succeed for 2-param exponential."""
   fitter = ExponentialDecay2ParameterFitter()
   id_xy_data = {1: ([0.0, 1.0, 2.0], [100.0, 50.0, 25.0])}

   results = fit(fitter, id_xy_data, cycles=0, noise_info=None)

   fits = results['fits']
   assert 1 in fits
   assert hasattr(fits[1], 'fit_status')
   assert fits[1].fit_status in ["success", "fit_failed"]


def test_sufficient_dof_succeeds_linear():
   """2 points (minimal DOF=1) should succeed for Mean."""
   fitter = Mean()
   id_xy_data = {1: ([0.0, 1.0], [100.0, 50.0])}  # 2 points, min_dof=1, DOF=1

   results = fit(fitter, id_xy_data, cycles=0, noise_info=None)

   fits = results['fits']
   assert 1 in fits
   assert fits[1].fit_status == "success"


# Test mixed scenarios
def test_mixed_dof_scenarios():
   """Multiple series with different point counts."""
   fitter = ExponentialDecay2ParameterFitter()
   id_xy_data = {
      1: ([0.0, 1.0], [100.0, 50.0]),  # Insufficient: DOF = 0
      2: ([0.0, 1.0, 2.0], [100.0, 50.0, 25.0]),  # Minimal: DOF = 1
      3: ([0.0, 1.0, 2.0, 3.0], [100.0, 50.0, 25.0, 12.5]),  # Good: DOF = 2
   }

   results = fit(fitter, id_xy_data, cycles=0, noise_info=None,
                 failure_handling=FailureHandling.WARN,
                 failure_output=FailureOutput.COMMENT)

   fits = results['fits']
   assert fits[1].fit_status == "insufficient_dof"
   assert fits[2].fit_status in ["success", "fit_failed"]  # May fail to converge
   assert fits[3].fit_status in ["success", "fit_failed"]


# Test policy combinations
def test_warn_plus_skip():
   """WARN+SKIP should log warning and skip output."""
   fitter = ExponentialDecay2ParameterFitter()
   id_xy_data = {1: ([0.0, 1.0], [100.0, 50.0])}

   # Capture logging
   with pytest.warns(None) as warning_list:
      results = fit(fitter, id_xy_data, cycles=0, noise_info=None,
                    failure_handling=FailureHandling.WARN,
                    failure_output=FailureOutput.SKIP)

   fits = results['fits']
   assert 1 not in fits  # Skipped


def test_ignore_plus_comment():
   """IGNORE+COMMENT should silently create placeholder."""
   fitter = ExponentialDecay2ParameterFitter()
   id_xy_data = {1: ([0.0, 1.0], [100.0, 50.0])}

   results = fit(fitter, id_xy_data, cycles=0, noise_info=None,
                 failure_handling=FailureHandling.IGNORE,
                 failure_output=FailureOutput.COMMENT)

   fits = results['fits']
   assert fits[1].fit_status == "insufficient_dof"


def test_warn_plus_comment_default():
   """Default behavior should be WARN+COMMENT."""
   fitter = ExponentialDecay2ParameterFitter()
   id_xy_data = {1: ([0.0, 1.0], [100.0, 50.0])}

   # No policy specified - should use defaults
   results = fit(fitter, id_xy_data, cycles=0, noise_info=None)

   fits = results['fits']
   assert 1 in fits  # COMMENT creates output
   assert fits[1].fit_status == "insufficient_dof"
```

#### 4.2 nef_pipelines integration tests (MINIMAL)

**File**: `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/tools/fit/test_exponential.py`

Add minimal integration tests to verify CLI → streamfitter wiring:

```python
def test_exponential_insufficient_dof_comment_policy():
    """NEF data with 2 points should produce UNUSED values with COMMENT policy."""
    # Use existing test infrastructure
    # Create minimal NEF input with 2 time points
    # Run: pipe(..., failure_handling=WARN, failure_output=COMMENT)
    # Verify: output frame contains row with '.' for value/value_error
    pass  # Implement using existing test patterns

def test_exponential_sufficient_dof_success():
    """NEF data with 4+ points should produce numeric values."""
    # Create NEF input with 4 time points
    # Run: pipe(...)
    # Verify: output contains numeric values for fit parameters
    pass  # Implement using existing test patterns

def test_exponential_fail_policy_raises():
    """FAIL policy should exit with error on insufficient DOF."""
    # Create NEF input with 2 time points
    # Run: pipe(..., failure_handling=FAIL)
    # Verify: raises InsufficientDegreesOfFreedomException
    pass  # Implement using existing test patterns
```

**Test data files** (if needed):
Create in test_data/ directory:
- `minimal_dof.nef` - 3 time points (DOF=1, minimal but sufficient)
- `insufficient_dof.nef` - 2 time points (DOF=0, insufficient)

### Phase 5: Apply to Other Fitters (Future Work)

Once exponential.py is working, apply same pattern to:
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/mean.py`
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/t1noe.py`
- Any other fitter CLI entry points

Changes needed:
1. Import FailureHandling and FailureOutput
2. Add CLI options (--failure-handling, --failure-output)
3. Pass through to fitter.fit()

## Verification

### Unit Tests (streamfitter - PRIMARY)
```bash
cd /Users/garythompson/Dropbox/git/streamfitter

# Test min_dof determination
pytest tests/test_fitter.py::test_min_dof_exponential -v
pytest tests/test_fitter.py::test_min_dof_mean -v

# Test NONLINEAR DOF checking
pytest tests/test_fitter.py::test_insufficient_dof_nonlinear_fail_policy -v
pytest tests/test_fitter.py::test_insufficient_dof_comment_policy -v
pytest tests/test_fitter.py::test_sufficient_dof_succeeds_nonlinear -v

# Test LINEAR DOF checking
pytest tests/test_fitter.py::test_insufficient_dof_linear_fail_policy -v
pytest tests/test_fitter.py::test_sufficient_dof_succeeds_linear -v

# Test policy combinations
pytest tests/test_fitter.py::test_mixed_dof_scenarios -v
pytest tests/test_fitter.py::test_warn_plus_skip -v
pytest tests/test_fitter.py::test_ignore_plus_comment -v
pytest tests/test_fitter.py::test_warn_plus_comment_default -v

# Run all DOF tests
pytest tests/test_fitter.py -v -k "dof"
```

### Integration Tests (nef_pipelines - MINIMAL)
```bash
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines
nefl test tests/tools/fit/test_exponential.py::test_exponential_insufficient_dof_comment_policy -v
nefl test tests/tools/fit/test_exponential.py::test_exponential_sufficient_dof_success -v
nefl test tests/tools/fit/test_exponential.py::test_exponential_fail_policy_raises -v
```

### Manual Testing

**Test 1: Default behavior (WARN+COMMENT)**
```bash
cat test_2_points.nef | nef_pipelines exponential T2 --cycles 0
```
Expected:
- Warning logged about insufficient DOF
- Output contains relaxation_list frame
- Failed fits have '.' for value/value_error
- Frame comment mentions failures

**Test 2: Strict validation (FAIL)**
```bash
cat test_2_points.nef | nef_pipelines exponential T2 --failure-handling fail --cycles 0
```
Expected:
- Exit code 1
- Error: "Insufficient degrees of freedom for data_id '...': has 2 points, needs >2 (DOF = 0)"

**Test 3: Silent skip (IGNORE+SKIP)**
```bash
cat test_2_points.nef | nef_pipelines exponential T2 --failure-handling ignore --failure-output skip --cycles 0
```
Expected:
- No warnings
- Output contains relaxation_list frame
- Failed fits silently omitted (no rows)

**Test 4: Mixed data**
```bash
cat mixed_data.nef | nef_pipelines exponential T2 --cycles 0
```
With mixed_data.nef containing some series with 2 points, some with 4+ points:
- Output contains all series
- Failed series have UNUSED values
- Successful series have numeric values
- Frame comment shows count of each

## Critical Files

**streamfitter** (PRIMARY CHANGES):
- `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/fitter_protocol.py` - Add min_dof()
- `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/fitter.py` - Add DOF checking, exceptions, helpers
- `/Users/garythompson/Dropbox/git/streamfitter/src/streamfitter/mean.py` - Override params() for LINEAR
- `/Users/garythompson/Dropbox/git/streamfitter/tests/test_fitter.py` - Comprehensive tests

**nef_pipelines** (INTEGRATION):
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/lib/interface.py` - Add enums
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/exponential.py` - Wire CLI options
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tools/fit/fit_lib.py` - Handle fit_status
- `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/tools/fit/test_exponential.py` - Integration tests

## Implementation Order

1. **Phase 1: Protocol and enums** (streamfitter + nef_pipelines)
   - Add FailureHandling and FailureOutput enums
   - Add min_dof() to FitterProtocol
   - Override params() in Mean
   - Write tests for min_dof determination

2. **Phase 2: Core DOF checking** (streamfitter)
   - Add InsufficientDegreesOfFreedomException
   - Modify fit() signature with new parameters
   - Implement _check_and_handle_dof() helper
   - Implement _create_failed_fit() helper
   - Update _fit_series() for NONLINEAR and LINEAR
   - Write comprehensive tests for all policies

3. **Phase 3: CLI integration** (nef_pipelines)
   - Update exponential.py: add CLI options, wire to fitter.fit()
   - Update fit_lib.py: read fit.fit_status, handle failures
   - Write minimal integration tests
   - Manual verification with NEF files

4. **Phase 4: Other fitters** (nef_pipelines - future)
   - Apply same pattern to mean.py, t1noe.py, etc.

## Policy Combination Matrix

| FailureHandling | FailureOutput | Behavior |
|----------------|---------------|----------|
| FAIL | COMMENT | Raise exception (output ignored) |
| FAIL | SKIP | Raise exception (output ignored) |
| **WARN** | **COMMENT** | **Log warning, output UNUSED row** ✅ **DEFAULT** |
| WARN | SKIP | Log warning, omit row |
| IGNORE | COMMENT | Silent, output UNUSED row |
| IGNORE | SKIP | Silent, omit row |

## Breaking Changes

This is a breaking change to streamfitter and nef_pipelines:

**streamfitter**:
- `fit()` signature changed: added `failure_handling` and `failure_output` parameters
- Fit objects now have `.fit_status` attribute
- Will raise `InsufficientDegreesOfFreedomException` by default for insufficient data

**nef_pipelines**:
- All fitter CLI commands need new `--failure-handling` and `--failure-output` options
- pipe() functions need new parameters
- Frame generation must handle fit.fit_status

**Migration**:
- Update all callers of `fitter.fit()` to pass new parameters (or rely on defaults)
- Update all fitter CLI commands (exponential, mean, t1noe, etc.)
- Existing NEF files with insufficient data will now get UNUSED values instead of bad fits
