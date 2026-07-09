"""Test series build pipe function and CLI."""

# TODO: may more test
from pynmrstar import Entry

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.series import series_app
from nef_pipelines.tools.series.build import pipe

EXPECTED_SERIES_FRAME = """
save_nefpls_series_list_T1_test_series
   _nefpls_series_list.sf_category           nefpls_series_list
   _nefpls_series_list.sf_framecode          nefpls_series_list_T1_test_series
   _nefpls_series_list.experiment_type       heteronuclear_R1_relaxation
   _nefpls_series_list.series_variable_type  time
   _nefpls_series_list.series_variable_unit  s
   _nefpls_series_list.data_variable_type    time
   _nefpls_series_list.data_variable_unit    s
   _nefpls_series_list.data_value_type       .
   _nefpls_series_list.data_value_unit       .
   _nefpls_series_list.version               0.1.0a
   _nefpls_series_list.comment               .

   loop_
      _nefpls_series_experiment.nmr_spectrum_id
      _nefpls_series_experiment.reference_experiment
      _nefpls_series_experiment.combination_id
      _nefpls_series_experiment.pseudo_dimension
      _nefpls_series_experiment.pseudo_dimension_point
      _nefpls_series_experiment.series_variable
      _nefpls_series_experiment.series_variable_error

      nef_nmr_spectrum_T1_1_8ms`1`    false   .   .   .    0.008   .
      nef_nmr_spectrum_T1_2_48ms`1`   false   .   .   .    0.048   .

   stop_

save_
"""


def test_build_creates_series_from_spectra():
    """Test that series build creates correct series frame from spectrum data.

    Uses GB1_T1_Relaxation_minimal.nef which has 2 T1 spectrum frames.
    Tests complete frame structure using assert_lines_match.
    """

    test_file = path_in_test_data(__file__, "GB1_T1_Relaxation_minimal.nef")
    entry = Entry.from_file(test_file)

    # Build series from the two T1 spectra
    frame_timings = {
        ("nef_nmr_spectrum_T1_1_8ms`1`", 1): (0.008, "s"),
        ("nef_nmr_spectrum_T1_2_48ms`1`", 1): (0.048, "s"),
    }

    result_entry = pipe(
        entry,
        frame_timings,
        unit="s",
        name="T1_test_series",
        experiment_type="HETERONUCLEAR_R1_RELAXATION",
    )

    # Get the series frame and compare complete structure
    series_frame_text = isolate_frame(
        str(result_entry), "nefpls_series_list_T1_test_series"
    )
    assert_lines_match(EXPECTED_SERIES_FRAME, series_frame_text)


def test_build_cli_with_frame_selector():
    """Test series build CLI with frame selector syntax.

    Uses frame selector: 'nef_nmr_spectrum_T1_{}_{var}`1`'
    where {var} is replaced with timing values.
    Tests complete frame structure using assert_lines_match.
    """

    test_file = path_in_test_data(__file__, "GB1_T1_Relaxation_minimal.nef")

    # Run series build CLI with frame selector
    result = run_and_report(
        series_app,
        [
            "build",
            "--in",
            str(test_file),
            "nef_nmr_spectrum_T1_{}_{var}`1`",
            "--name",
            "T1_test_series",
            "--experiment-type",
            "HETERONUCLEAR_R1_RELAXATION",
        ],
    )

    # Get the series frame and compare complete structure (same as pipe test)
    series_frame_text = isolate_frame(
        result.stdout, "nefpls_series_list_T1_test_series"
    )
    assert_lines_match(EXPECTED_SERIES_FRAME, series_frame_text)


def test_build_cli_with_explicit_spectra():
    """Test series build CLI with explicit frame names and timings.

    Uses explicit frame selectors (exact names, not patterns) with --timings.
    Each selector matches exactly one frame (itself) and pairs 1:1 with timings.
    """

    test_file = path_in_test_data(__file__, "GB1_T1_Relaxation_minimal.nef")

    # Run series build with explicit frames and timings
    result = run_and_report(
        series_app,
        [
            "build",
            "--in",
            str(test_file),
            "nef_nmr_spectrum_T1_1_8ms`1`",
            "nef_nmr_spectrum_T1_2_48ms`1`",
            "--name",
            "T1_test_series",
            "--experiment-type",
            "HETERONUCLEAR_R1_RELAXATION",
            "--unit",
            "ms",
            "--timings",
            "8,48",
        ],
    )

    # Get the series frame and compare complete structure (same expected output)
    series_frame_text = isolate_frame(
        result.stdout, "nefpls_series_list_T1_test_series"
    )
    assert_lines_match(EXPECTED_SERIES_FRAME, series_frame_text)
