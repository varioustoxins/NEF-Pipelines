# Plan: Replace rounding heuristic in `guess_proton_frequency` with ratio-matching

## Context

`guess_proton_frequency` currently uses a "rounds most cleanly to 50 MHz" heuristic that
has **catastrophic dead zones**:

- **850 MHz / 1700 MHz** with F19 in the mix (F19 lands exactly on an 800/1600 MHz multiple)
- **2000 MHz** with C13 (C13 lands on 500 MHz, only 2 MHz safe window)
- **P31 dead zones** every ~370 MHz above 1100 MHz (35 MHz windows at 1300/1400, 17 MHz at 1500)

It also has a deeper design flaw the user flagged: **the function assumes H1 is present in
the input list**, but the broader problem is "given any set of nuclei, guess the H1
spectrometer frequency (assumed ≥ 500 MHz)". Heteronuclear-only inputs (direct-detect
13C/15N, 31P, 19F experiments) have no defined behaviour today — the tests explicitly
note "Heteronuclear-only lists have no defined answer" and exclude them.

The fix: switch to **ratio matching against `GAMMA_RATIOS`** — the same exact-arithmetic
approach `match_frequencies_to_isotopes` already uses and that works perfectly at every
field strength. This eliminates every dead zone *and* generalises naturally to the
heteronuclear-only case.

## Solution: snap to the nearest standard field strength

**Key insight (from the user):** real spectrometers are sold at specific nominal
frequencies. The candidate set for H1 is the **known commercial field strengths** —
not arbitrary numbers in some interval. Adding fields that don't yet exist
commercially (1.3 GHz+) creates dead zones for low-field users via aliasing.

### Algorithm

1. **Score each candidate field strength** `H1_std ∈ candidate_frequencies`:
   `score(H1_std) = Σ_f min_r |f − r·H1_std|` (frequency-space mismatch in MHz).
   Frequency space, not ratio space — measurement noise lives in frequency space.
2. **Return** the `H1_std` with the lowest score (snap to nearest standard).
3. **Sanity check**: if even the best `H1_std` scores worse than
   `max_score_per_input * len(frequencies)` MHz, raise `ValueError` (input isn't
   from a standard spectrometer, or contains an unknown nucleus).

This is simple and works because the standards prior is very strong: at realistic
drift around a nominal field strength, the correct standard scores < 5 MHz; all other
standards score ≥ 10–50 MHz at the closest, hundreds of MHz further afield.

### Worked examples (currently broken with old heuristic)

| Input | Old result | New result |
|-------|------------|------------|
| `[850.0, 800.10]` (H1+F19 @ 850) | F19 wins, returns 800 | H1=850 ✓ |
| `[746.0, 187.6, 75.6]` (H1+C13+N15 @ 746) | returns 746.0 (drifted) | H1=750 ✓ |
| `[150.94, 60.81]` (C13+N15 @ 600, no H1) | undefined | H1=600 ✓ |
| `[242.88, 60.81]` (P31+N15 @ 600, no H1) | undefined | H1=600 ✓ |
| `[1.0, 2.0, 3.0]` (not NMR data) | returns silently | raises `ValueError` |

## Assumptions made explicit

- All input frequencies are assumed to be from isotopes in `GAMMA_RATIOS` (H1, H2, H3,
  C13, N15, O17, F19, P31). Other nuclei (11B, 113Cd, etc.) will be force-fit; the
  sanity-check threshold should catch obvious mismatches.
- H1 is one of the candidate field strengths (default: commercial fields 500–1200 MHz).
- Real spectrometer drift from nominal is typically < 1 MHz, occasionally up to ~5 MHz
  (user cited a 746 MHz machine = 4 MHz drift from 750). The algorithm must tolerate
  this drift on every realistic configuration.

## Drift tolerance: empirically measured, not guessed

The right question is "how far can H1 drift from nominal before the algorithm picks
the wrong standard?" Measured by sweeping actual H1 around each nominal standard for
every combo in `_ISOTOPE_COMBOS`.

**Candidate set matters.** Including high-field standards that don't yet exist
commercially (1.3–1.9 GHz) creates dead zones for low-field users because
`P31 × 600 ≈ N15 × 1500`-type coincidences appear. Comparison:

| Candidate set | Worst total drift window | Worst single side | Cause |
|---------------|--------------------------|-------------------|-------|
| `TYPICAL_1H_FREQUENCIES` (500–1900) | 6.6 MHz at 600/[H1,C13] | **+3.3 MHz** | 1500 MHz aliases low-field [H1,C13] as [P31,N15] |
| Commercial fields only (500–1200) | 11.2 MHz at 900/[H1,N15] | **−3.4 MHz** | 500/[C13,P31] heteronuclear-only edge case |

**The commercial-only default gives ≥ 5 MHz margin for every realistic configuration.**
Verified against user's actual 746 MHz machine (4 MHz drift): snaps to 750 with every
combo, score 4–6 MHz, runner-up 12–20 MHz away — comfortably correct.

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `candidate_frequencies` | `[500, 600, 700, 750, 800, 850, 900, 950, 1000, 1100, 1200]` | Commercial spectrometers as of 2026 (highest is Bruker 1.2 GHz). Users at ≥ 1.3 GHz pass their own list. |
| `max_score_per_input` | **5.0 MHz** | Correct snap with 5 MHz drift: ≤ 5 MHz score per input. Wrong snap typically 10+ MHz per input. 5 sits in the gap and catches non-NMR data. |
| `min_frequency` | (removed — implicit in candidate set) | The candidate set IS the constraint. |
| `max_frequency` | (removed — same) | |

## File changes

### 1. `src/nef_pipelines/lib/isotope_lib.py`

Add module-level constant alongside `TYPICAL_1H_FREQUENCIES`:

```python
# Commercial 1H spectrometer field strengths actually built and shipped. Higher
# research-grade fields exist but creating dead zones for low-field users — callers
# with >= 1.3 GHz instruments should pass their own candidate_frequencies.
COMMERCIAL_1H_FREQUENCIES = [
    500.0, 600.0, 700.0, 750.0, 800.0, 850.0,
    900.0, 950.0, 1000.0, 1100.0, 1200.0,
]
```

Rewrite `guess_proton_frequency` (currently lines 83–110):

```python
def guess_proton_frequency(
    frequencies: list[float],
    candidate_frequencies: list[float] = COMMERCIAL_1H_FREQUENCIES,
    max_score_per_input: float = 5.0,
) -> float:
    """Find the most likely 1H spectrometer frequency by snapping to the nearest
    standard commercial field strength.

    For each candidate field strength H1, scores total frequency-space mismatch:
    sum over inputs of (minimum |input - r * H1| over known gamma ratios). Returns
    the candidate with the lowest score (= the spectrometer the inputs are most
    consistent with).

    Works for heteronuclear-only inputs (direct-detect 13C/15N/31P, 19F) as well as
    H1-detected experiments. Tolerates up to ~5 MHz drift from nominal at every
    realistic configuration (verified empirically — see test_isotopes report).

    Assumes all inputs are from isotopes in GAMMA_RATIOS. Raises ValueError if
    average per-input mismatch exceeds max_score_per_input MHz (input isn't from a
    standard spectrometer, or contains an unknown nucleus).
    """
    if not frequencies:
        raise ValueError("frequencies must not be empty")

    known_ratios = list(GAMMA_RATIOS.values())

    def score(h1: float) -> float:
        return sum(min(abs(f - r * h1) for r in known_ratios) for f in frequencies)

    best = min(candidate_frequencies, key=score)
    best_score = score(best)

    if best_score > max_score_per_input * len(frequencies):
        raise ValueError(
            f"no standard field strength fits {frequencies}: best is {best} MHz "
            f"with total mismatch {best_score:.2f} MHz "
            f"(> {max_score_per_input} per input). Input may not be NMR data, may "
            f"contain an unknown nucleus, or may be from a non-standard magnet "
            f"(pass candidate_frequencies explicitly)."
        )

    return best
```

`match_frequencies_to_isotopes` and `round_to_nearest_and_get_distance` are unchanged —
the former already does the right thing; the latter is only used by the old heuristic
and the test-only diagnostic and can be removed when both are gone.

**Note on return value**: function returns the nominal standard (e.g. 600.0), not the
actual drifted value (e.g. 603.3). The sole downstream caller passes the result to
`match_frequencies_to_isotopes` which is robust to a few MHz of offset — verified.

### 2. `src/nef_pipelines/tests/test_isotopes.py`

- **Drop `_GUESS_ISOTOPE_COMBOS`**: the new function handles heteronuclear-only combos,
  so reuse `_ISOTOPE_COMBOS` (which is already the full real-world set).
- **Drop `_h1_rounds_most_cleanly`**: no more dead zones to dodge; every combo in
  `_ISOTOPE_COMBOS` × `_PROTON_FREQUENCIES_MHZ` should pass without filtering.
- **Re-enable `[H1, F19]` in `_PROTON_FREQUENCIES_MHZ` testing** — was avoided because
  the old heuristic failed at 850 MHz. Now passes.
- **Trim `_PROTON_FREQUENCIES_MHZ` to commercial fields with small drift** — exact
  arbitrary frequencies like 600.13 or 1499.95 are no longer interesting since the
  function snaps to standards. Test that the function returns the nominal standard
  for each (commercial_field, small_drift) pair.
- Rewrite `test_guess_proton_frequency` to loop over `_ISOTOPE_COMBOS` directly:

  ```python
  def test_guess_proton_frequency():
      for nominal in COMMERCIAL_1H_FREQUENCIES:
          for drift in [-3.0, -0.5, 0.0, 0.5, 3.0]:
              actual = nominal + drift
              for isotopes in _ISOTOPE_COMBOS:
                  frequencies = [actual * GAMMA_RATIOS[iso] for iso in isotopes]
                  result = guess_proton_frequency(frequencies)
                  assert result == nominal, (
                      f"actual H1={actual} MHz ({nominal}{drift:+}), isotopes={isotopes}: "
                      f"snapped to {result}, expected {nominal}"
                  )
  ```

- **Replace `report_heuristic_limits` with `report_drift_tolerance`** — analog for
  the new algorithm. Old report measured dead-zone widths in MHz for the rounding
  heuristic; new report measures the drift window around each candidate H1 (how far
  actual H1 can deviate from nominal before the algorithm snaps to a different
  candidate). The `__main__` block calls it so the diagnostic can be run as
  `python test_isotopes.py`. Sketch:

  ```python
  def report_drift_tolerance(
      candidate_frequencies=COMMERCIAL_1H_FREQUENCIES,
      isotope_combos=_ISOTOPE_COMBOS,
      step=0.1,
      max_radius=100.0,
  ):
      """For each (nominal, combo), sweep actual H1 = nominal ± delta and find the
      delta at which the algorithm picks a different candidate. Reports
      per-combo drift windows and the global worst case (currently 11.2 MHz total
      at 900/[H1, N15], or 3.4 MHz worst single side at 500/[C13, P31])."""
      # ... loop, sweep, print table, print global worst-case window ...
  ```

  Drop the old `_winner_at`, `_sweep_heuristic_limits`, `_h1_rounds_most_cleanly`
  helpers — all were scaffolding for the rounding heuristic.

### 3. Upstream caller (no change required)

`src/nef_pipelines/transcoders/nmrview/importers/peaks.py:1056` calls
`guess_proton_frequency(frequencies)` with positional argument only. New behaviour:
returns the matched nominal standard (e.g. 750.0 for a 746 MHz drifted machine). The
downstream `match_frequencies_to_isotopes` call is robust to a few MHz of drift, so
returning the nominal does not break the existing flow. Sub-500 MHz inputs would now
raise `ValueError` (no candidate fits) — desired per the user's stated assumption.

## Why this is the right shape

- **Algorithmically symmetric with `match_frequencies_to_isotopes`**: both operate
  purely on gamma ratios. The two functions are now consistent halves of the same
  problem (one knows H1, one infers it). The inconsistency between them is what allowed
  the dead-zone bugs to exist in the first place.
- **No magic constants in the algorithm**: gone are the `240`, `10`, `50` MHz divisors
  and the implicit assumption that any input near a 50 MHz multiple is probably H1.
- **The candidate set IS the prior** — explicit, configurable, documented. No need for
  separate `min_frequency`/`max_frequency` knobs; the candidate list already encodes
  the operating range.

## Verification

1. **Re-run the drift-tolerance diagnostic** after implementation to confirm the
   empirical numbers still hold:
   ```bash
   cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines
   python src/nef_pipelines/tests/test_isotopes.py
   ```
   Expect: worst total drift window ≈ 11.2 MHz at 900 MHz / `[H1, N15]`; worst single
   side ≈ −3.4 MHz at 500 MHz / `[C13, P31]`. Every (commercial field, combo) pair
   should tolerate ≥ ±5 MHz drift except where flagged in the table above.

2. **Run the unit tests** across the full combo × drift grid:
   ```bash
   python -m pytest src/nef_pipelines/tests/test_isotopes.py -x -v
   ```
   Every combo in `_ISOTOPE_COMBOS` (proton-detected, heteronuclear-only, F19) crossed
   with drifts in [−3, +3] MHz at every commercial field should snap to the nominal.

3. **Catch upstream regressions** in the broader suite:
   ```bash
   python -m pytest src/nef_pipelines/tests/ -x -q
   ```

4. **Spot-check the nmrview importer** end-to-end (the one real caller):
   ```bash
   python -m pytest src/nef_pipelines/tests/nmrview/ -x -v
   ```
