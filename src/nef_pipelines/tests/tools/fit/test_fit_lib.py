import pytest

from nef_pipelines.tools.fit.fit_lib import (
    NEFPLSFitLibInconsistentSeriesDataError,
    RelaxationSeriesValues,
    _combine_relaxation_series,
)

SPECTRA_1 = ["spectrum_A", "spectrum_B"]
PEAK_IDS_1 = [10, 20]
VARIABLE_VALUES_1 = [
    0.1,
    0.2,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
]
VALUES_1 = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0]

SPECTRA_2 = ["spectrum_C", "spectrum_D"]
PEAK_IDS_2 = [30, 40]
VALUES_2 = [
    1100.0,
    1200.0,
    1300.0,
    1400.0,
    1500.0,
    1600.0,
    1700.0,
    1800.0,
    1900.0,
    2000.0,
]
VARIABLE_VALUES_2 = [1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.0]

EXPECTED_SPECTRA = [*SPECTRA_1, *SPECTRA_2]
EXPECTED_PEAK_IDS = [*PEAK_IDS_1, *PEAK_IDS_2]
EXPECTED_VALUES = [*VALUES_1, *VALUES_2]
EXPECTED_VARIABLE_VALUES = [*VARIABLE_VALUES_1, *VARIABLE_VALUES_2]


class TestCombineRelaxationSeries:
    """Test cases for _combine_relaxation_series function."""

    def test_successful_combination_basic(self):
        """Test successful combination of two basic RelaxationSeriesValues."""
        series1 = RelaxationSeriesValues(
            spectra=SPECTRA_1,
            peak_ids=PEAK_IDS_1,
            variable_values=VARIABLE_VALUES_1,
            values=VALUES_1,
        )

        series2 = RelaxationSeriesValues(
            spectra=SPECTRA_2,
            peak_ids=PEAK_IDS_2,
            variable_values=VARIABLE_VALUES_2,
            values=VALUES_2,
        )

        result = _combine_relaxation_series(series1, series2)

        # Verify result is the correct type
        assert isinstance(result, RelaxationSeriesValues)

        # Verify all fields are combined as blocks (series1 first, then series2)
        assert result.spectra == EXPECTED_SPECTRA
        assert result.peak_ids == EXPECTED_PEAK_IDS
        assert result.variable_values == EXPECTED_VARIABLE_VALUES
        assert result.values == EXPECTED_VALUES

    def test_inconsistent_spectra_length_error(self):
        """Test error when spectra field lengths don't match between series."""
        series1 = RelaxationSeriesValues(
            spectra=SPECTRA_1,  # length 2
            peak_ids=PEAK_IDS_1,
            variable_values=VARIABLE_VALUES_1,
            values=VALUES_1,
        )

        series2 = RelaxationSeriesValues(
            spectra=SPECTRA_2[:1],  # length 1 - mismatch!
            peak_ids=PEAK_IDS_2,
            variable_values=VARIABLE_VALUES_2,
            values=VARIABLE_VALUES_2,
        )

        with pytest.raises(
            NEFPLSFitLibInconsistentSeriesDataError,
            match=r"Inconsistent field lengths for spectra: series1 has 2, series2 has 1",
        ):
            _combine_relaxation_series(series1, series2)

    def test_inconsistent_peak_ids_length_error(self):
        """Test error when peak_ids field lengths don't match between series."""
        series1 = RelaxationSeriesValues(
            spectra=SPECTRA_1,  # length 2
            peak_ids=PEAK_IDS_1,
            variable_values=VARIABLE_VALUES_1,
            values=VALUES_1,
        )

        series2 = RelaxationSeriesValues(
            spectra=SPECTRA_2,  # length 1 - mismatch!
            peak_ids=PEAK_IDS_2[:1],
            variable_values=VARIABLE_VALUES_2,
            values=VARIABLE_VALUES_2,
        )

        with pytest.raises(
            NEFPLSFitLibInconsistentSeriesDataError,
            match=r"Inconsistent field lengths for peak_ids: series1 has 2, series2 has 1",
        ):
            _combine_relaxation_series(series1, series2)

    def test_inconsistent_variable_values_length_error(self):
        """Test error when variable_values field lengths don't match between series."""
        series1 = RelaxationSeriesValues(
            spectra=SPECTRA_1,  # length 2
            peak_ids=PEAK_IDS_1,
            variable_values=VARIABLE_VALUES_1,
            values=VALUES_1,
        )

        series2 = RelaxationSeriesValues(
            spectra=SPECTRA_2,  # length 1 - mismatch!
            peak_ids=PEAK_IDS_2,
            variable_values=VARIABLE_VALUES_2[:5],
            values=VARIABLE_VALUES_2,
        )

        with pytest.raises(
            NEFPLSFitLibInconsistentSeriesDataError,
            match=r"Inconsistent field lengths for variable_values: series1 has 10, series2 has 5",
        ):
            _combine_relaxation_series(series1, series2)

    def test_inconsistent_values_length_error(self):
        """Test error when values field lengths don't match between series."""
        series1 = RelaxationSeriesValues(
            spectra=SPECTRA_1,  # length 2
            peak_ids=PEAK_IDS_1,
            variable_values=VARIABLE_VALUES_1,
            values=VALUES_1,
        )

        series2 = RelaxationSeriesValues(
            spectra=SPECTRA_2,  # length 1 - mismatch!
            peak_ids=PEAK_IDS_2,
            variable_values=VARIABLE_VALUES_2,
            values=VARIABLE_VALUES_2[:5],
        )

        with pytest.raises(
            NEFPLSFitLibInconsistentSeriesDataError,
            match=r"Inconsistent field lengths for values: series1 has 10, series2 has 5",
        ):
            _combine_relaxation_series(series1, series2)

    def test_multiple_field_length_mismatches(self):
        """Test that the first field mismatch is reported when multiple fields have mismatches."""
        series1 = RelaxationSeriesValues(
            spectra=SPECTRA_1,  # length 2
            peak_ids=PEAK_IDS_1[:5],
            variable_values=VARIABLE_VALUES_1,
            values=VALUES_1[:5],
        )

        series2 = RelaxationSeriesValues(
            spectra=SPECTRA_2[:1],  # length 1 - mismatch!
            peak_ids=PEAK_IDS_2,
            variable_values=VARIABLE_VALUES_2[:5],
            values=VARIABLE_VALUES_2,
        )

        # Should report the first field that has a mismatch (spectra)
        with pytest.raises(
            NEFPLSFitLibInconsistentSeriesDataError,
            match=r"Inconsistent field lengths for spectra: series1 has 2, series2 has 1",
        ):
            _combine_relaxation_series(series1, series2)
