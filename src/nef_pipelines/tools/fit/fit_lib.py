from dataclasses import dataclass, field
from itertools import combinations
from math import sqrt
from statistics import stdev
from typing import Dict, List, OrderedDict, Tuple, Union

from fyeah import f
from ordered_set import OrderedSet
from pynmrstar import Entry, Loop, Saveframe

from nef_pipelines.lib.interface import NoiseInfo
from nef_pipelines.lib.isotope_lib import (
    CODE_TO_ISOTOPE,
    GAMMA_RATIOS,
    MAGNETOGYRIC_RATIO_1H,
)
from nef_pipelines.lib.nef_lib import (
    NEF_RELAXATION_VERSION,
    UNUSED,
    SelectionType,
    create_nef_save_frame,
    loop_row_namespace_iter,
    select_frames,
)
from nef_pipelines.lib.peak_lib import frame_to_peaks
from nef_pipelines.lib.shift_lib import IntensityMeasurementType
from nef_pipelines.lib.structures import NEFPipelinesException

SERIES_DATA_CATEGORY = "_{NAMESPACE}_series_data"


class NEFPLSFitLibException(NEFPipelinesException):
    """Base exception class for NEF fit library errors."""

    ...


class NEFPLSFitLibNoIsotopeFrequenciesError(NEFPLSFitLibException):
    """Raised when no isotope frequencies are found in spectrum frames."""

    ...


class NEFPLSFitLibInconsistentSeriesDataError(NEFPLSFitLibException):
    """Raised when data is not consistent across series frames (frequencies or isotope axes)."""

    ...


class NEFPLSFitLibNoSeriesFramesSelectedError(NEFPLSFitLibException):
    """Raised when no series frames are selected by the given selectors."""

    ...


class NEFPLSFitLibNoFrameSelectorsError(NEFPLSFitLibException):
    """Raised when no frame selectors are provided."""

    ...


class NEFPLSFitLibMissingDataError(NEFPLSFitLibException):
    """Raised when expected data is missing (series data loop, spectrum frame, or data ID)."""

    ...


@dataclass
class RelaxationSeriesValues:
    spectra: List[str] = field(default_factory=list)
    peak_ids: List[int] = field(default_factory=list)
    variable_values: List[Union[int, float]] = field(default_factory=list)
    values: List[Union[int, float, bool]] = field(default_factory=list)


def _combine_relaxation_series(
    series1: RelaxationSeriesValues, series2: RelaxationSeriesValues
) -> RelaxationSeriesValues:
    """Combine two RelaxationSeriesValues into a single RelaxationSeriesValues.

    All fields from both series are combined as sequential blocks (series1 data first,
    then series2 data). Raises an exception if equivalent fields between the two series
    have different lengths.

    Args:
        series1: First RelaxationSeriesValues to combine
        series2: Second RelaxationSeriesValues to combine

    Returns:
        RelaxationSeriesValues with combined data

    Raises:
        NEFPLSFitLibInconsistentSeriesDataError: If equivalent fields have different lengths between series
    """
    # Validate that equivalent fields between series1 and series2 have the same length
    field_comparisons = [
        ("spectra", len(series1.spectra), len(series2.spectra)),
        ("peak_ids", len(series1.peak_ids), len(series2.peak_ids)),
        ("variable_values", len(series1.variable_values), len(series2.variable_values)),
        ("values", len(series1.values), len(series2.values)),
    ]

    for field_name, len1, len2 in field_comparisons:
        if len1 != len2:
            msg = f"Inconsistent field lengths for {field_name}: series1 has {len1}, series2 has {len2}"
            raise NEFPLSFitLibInconsistentSeriesDataError(msg)

    # Combine all fields as blocks (series1 first, then series2)
    combined = RelaxationSeriesValues(
        spectra=[*series1.spectra, *series2.spectra],
        peak_ids=[*series1.peak_ids, *series2.peak_ids],
        variable_values=[*series1.variable_values, *series2.variable_values],
        values=[*series1.values, *series2.values],
    )

    return combined


def _fit_results_as_frame(
    series_frame,
    prefix,
    entry,
    fits,
    fit_name,
    output,
    monte_carlo_errors,
    monte_carlo_value_stats,
    monte_carlo_param_values,
    monte_carlo_random_seed,
    noise_info: NoiseInfo,
    version_strings,
    fitter_name,
):

    spectrum_frames = _series_frame_to_spectrum_frames(series_frame, prefix, entry)

    data_id_to_spectrum_peak_ids = _series_frame_to_data_id_to_spectrum_peak_id(
        series_frame, prefix
    )

    spectrum_peak_id_to_axis_atoms = _build_spectrum_peak_id_to_axis_atoms(
        spectrum_frames
    )

    isotope_axes = spectra_to_isotope_axes(spectrum_frames)

    _exit_if_isotope_axes_are_not_unique(isotope_axes, spectrum_frames, entry.entry_id)

    isotope_frequencies = spectra_to_isotope_frequencies(spectrum_frames)

    _exit_if_isotope_frequencies_are_not_unique(
        isotope_frequencies, spectrum_frames, entry.entry_id
    )

    isotope_frequencies = _get_unique_isotope_frequencies(isotope_frequencies)

    _exit_if_no_frequencies_found(isotope_frequencies, series_frame, entry)

    field_strength = frequencies_to_field_strength(isotope_frequencies)

    axis_of_lowest_gamma = _isotope_axes_to_lowest_gamma_axis(isotope_axes)

    result_frame = create_nef_save_frame(f"{prefix}_relaxation_list", output)

    result_frame.add_tag("version", NEF_RELAXATION_VERSION)
    result_frame.add_tag("experiment_type", series_frame.get_tag("experiment_type")[0])
    result_frame.add_tag("field_strength", field_strength)
    result_frame.add_tag("value_unit", "s-1")
    result_frame.add_tag("relaxation_atom_id", axis_of_lowest_gamma)
    result_frame.add_tag("ref_value", UNUSED)
    result_frame.add_tag("source", "experimental")
    result_frame.add_tag("fitting_function", fitter_name)
    # TODO fix this
    result_frame.add_tag("minimizer", "leastsq")

    result_frame.add_tag("error_method", noise_info.source)

    # TODO move these to tags under nefpls...
    comment = f"""
        fitting software: {version_strings}
        random seed {monte_carlo_random_seed}
        requested noise estimate source: {noise_info.requested_noise_source}
        source of noise estimate: {noise_info.source}
        noise estimate: {noise_info.noise}
        noise estimate fractional error: {noise_info.fraction_error_in_noise}
        noise estimate number replicates: {noise_info.num_replicates}
    """
    # error_in_noise-estimate {}
    # fit_time {}
    result_frame.add_tag("comment", comment)

    relaxation_loop = Loop.from_scratch(f"{prefix}_relaxation")
    result_frame.add_loop(relaxation_loop)

    RELAXATION_LOOP_TAGS = "index data_id data_combination_id value value_error".split()
    RELAXATION_LOOP_ATOM_TAGS = (
        "chain_code_{axis} sequence_code_{axis} residue_name_{axis} atom_name_{axis}"
    )

    all_tags = [
        *RELAXATION_LOOP_TAGS,
    ]
    for axis in range(1, len(isotope_axes) + 1):
        all_tags.append(RELAXATION_LOOP_ATOM_TAGS.format(axis=axis).split())

    relaxation_loop.add_tag(all_tags)

    data = []
    for index, (data_id, fit) in enumerate(fits.items(), start=1):
        data_row = {"index": index, "data_id": index, "data_combination_id": UNUSED}

        peak_atoms = []
        atom_key = next(iter(data_id_to_spectrum_peak_ids[data_id]))

        # TODO check if peak exists or error
        for axis_atoms in spectrum_peak_id_to_axis_atoms[atom_key].values():
            peak_atoms.extend(axis_atoms)

        for i, atom in enumerate(peak_atoms, start=1):
            residue = atom.residue
            data_row.update(
                {
                    f"chain_code_{i}": residue.chain_code,
                    f"sequence_code_{i}": residue.sequence_code,
                    f"residue_name_{i}": residue.residue_name,
                    f"atom_name_{i}": atom.atom_name,
                }
            )

        if monte_carlo_errors:
            mc_error = monte_carlo_errors[data_id].get(f"{fit_name}_mc_error", UNUSED)
        else:
            mc_error = UNUSED
        data_row.update(
            {
                "value": f"{fit.params[fit_name].value:.6f}",
                "value_error": f"{mc_error:.6}",
            }
        )
        data.append(data_row)

    relaxation_loop.add_data(data)

    return result_frame


def _series_frame_to_data_id_to_spectrum_peak_id(series_frame, prefix):
    result = {}
    series_loop_id = f"_{prefix}_series_data"

    series_loop = (
        series_frame[series_loop_id] if series_loop_id in series_frame else None
    )
    for row in loop_row_namespace_iter(series_loop):
        spectrum_peak_id = row.nmr_spectrum_id, row.peak_id
        result.setdefault(row.data_id, set()).add(spectrum_peak_id)
    return result


def _build_spectrum_peak_id_to_axis_atoms(spectrum_frames):
    result = {}
    for spectrum_frame in spectrum_frames:
        peaks = frame_to_peaks(spectrum_frame)

        for peak in peaks:
            axis_atoms = {}
            key = spectrum_frame.name, peak.id
            result[key] = axis_atoms

            for i, shift in enumerate(peak.shifts, start=1):
                axis_atoms.setdefault(i, set()).add(shift.atom)

    return result


def _isotope_axes_to_lowest_gamma_axis(isotope_axes):
    return min(
        isotope_axes,
        key=lambda x: min(GAMMA_RATIOS[isotope] for isotope in isotope_axes[x]),
    )


def _exit_if_no_frequencies_found(isotope_frequencies, series_frame, entry):
    if not isotope_frequencies:
        msg = f"""
            no isotope frequencies found in the series frame {series_frame.name} in entry {entry.entry_id}
            this indcates that the series frame is incomplete or missing...
        """
        raise NEFPLSFitLibNoIsotopeFrequenciesError(msg)


def _get_unique_isotope_frequencies(isotope_frequencies):

    return {
        isotope: list(frequency)[0]
        for isotope, frequency in isotope_frequencies.items()
    }


def _series_frame_to_spectrum_frames(series_frame, prefix, entry):

    spectrum_frames = []

    for i, row in enumerate(
        loop_row_namespace_iter(
            series_frame.get_loop(f"{prefix}_series_experiment"), convert=True
        ),
        start=1,
    ):
        spectrum_frame_name = row.nmr_spectrum_id
        if spectrum_frame_name in entry.frame_dict.keys():
            spectrum_frame = entry.get_saveframe_by_name(spectrum_frame_name)
            spectrum_frames.append(spectrum_frame)

    return spectrum_frames


# TODO:  there is some duplication here!
def _select_relaxation_series_or_exit(
    entry: Entry, frame_selectors: List[str]
) -> Tuple:
    relaxation_frames = select_frames(
        entry, "nefpls_series_list", SelectionType.CATEGORY
    )
    series_frames_and_ids = OrderedSet(
        [
            (relaxation_series.name, id(relaxation_series))
            for relaxation_series in relaxation_frames
        ]
    )

    if frame_selectors:
        named_frames = []
        for frame_selector in frame_selectors:
            named_frames.extend(
                select_frames(entry, frame_selector, SelectionType.NAME)
            )

        named_frames_and_ids = OrderedSet(
            [(named_frame.name, id(named_frame)) for named_frame in named_frames]
        )
    elif len(relaxation_frames) == 1:
        relaxation_frame = relaxation_frames[0]
        frame_key = (relaxation_frame.name, id(relaxation_frame))
        named_frames_and_ids = OrderedSet(
            [
                frame_key,
            ]
        )
    else:
        # No frame selectors provided and multiple frames available - use all relaxation frames
        named_frames_and_ids = series_frames_and_ids

    selected_frames_and_ids = series_frames_and_ids.intersection(named_frames_and_ids)

    result = [
        entry.get_saveframe_by_name(frame_name)
        for frame_name, _ in selected_frames_and_ids
    ]

    return result


def _exit_if_no_series_frames_selected(active_relaxation_frames, frame_selectors):
    if not active_relaxation_frames:
        msg = f"""
            no series frames selected by the selectors
            {" ".join(frame_selectors)}
        """
        raise NEFPLSFitLibNoSeriesFramesSelectedError(msg)


def _exit_if_no_frame_selectors(frame_selectors):
    if len(frame_selectors) == 0:
        msg = "you must select some frames!"
        raise NEFPLSFitLibNoFrameSelectorsError(msg)

    return None


def _exit_if_isotope_frequencies_are_not_unique(
    isotope_frequencies, series_frame, entry_id
):
    # TODO: should identify common frames and swapped ones
    for isotope, frequencies in isotope_frequencies.items():
        if len(frequencies) > 1:
            msg = f"""
                in the series frame {series_frame.name} in entry {entry_id}
                isotope {isotope} has multiple frequencies {frequencies}
                the frequencies are {', '.join(frequencies)}
                spectrometer frequencies must be consistent in a series frame
            """

            raise NEFPLSFitLibInconsistentSeriesDataError(msg)


def _exit_if_isotope_axes_are_not_unique(isotope_axes, series_frame, entry_id):

    # TODO: should identify common frames and swapped ones
    for axis, isotopes in isotope_axes.items():
        if len(isotopes) > 1:
            msg = f"""
                in the series frame {series_frame.name} in entry {entry_id}
                the isotopes {', '.join(isotopes)} appears on multiple different axes
                this variation is not compatible with the nef relaxation lists model
                the axes must be consistent in a series frame
            """

            raise NEFPLSFitLibInconsistentSeriesDataError(msg)


def spectra_to_isotope_axes(spectrum_frames):
    isotope_axes = {}
    for spectrum_frame in spectrum_frames:
        spectrum_dimension_loop = loop_row_namespace_iter(
            spectrum_frame.get_loop("nef_spectrum_dimension")
        )

        for row in spectrum_dimension_loop:
            isotope = CODE_TO_ISOTOPE.get(row.axis_code)
            isotope_axes.setdefault(row.dimension_id, set()).add(isotope)

    return isotope_axes


def spectra_to_isotope_frequencies(spectrum_frames):

    frequencies = {}
    for spectrum_frame in spectrum_frames:
        spectrum_dimension_loop = loop_row_namespace_iter(
            spectrum_frame.get_loop("nef_spectrum_dimension")
        )
        for row in spectrum_dimension_loop:
            frequencies.setdefault(row.axis_code, set()).add(row.spectrometer_frequency)

    return frequencies


def frequencies_to_field_strength(frequencies):
    fields_by_gamma_and_isotope = {}
    for isotope_code, frequency in frequencies.items():

        if isotope_code not in CODE_TO_ISOTOPE:
            continue

        isotope = CODE_TO_ISOTOPE[isotope_code]
        gamma_ratio = GAMMA_RATIOS[isotope]

        field = frequency / MAGNETOGYRIC_RATIO_1H / gamma_ratio

        fields_by_gamma_and_isotope[gamma_ratio, isotope] = field

    highest_gamma_isotope = max(fields_by_gamma_and_isotope, key=lambda x: x[0])

    return fields_by_gamma_and_isotope[highest_gamma_isotope]


def _get_spectra_by_series_variable(entry, series_experiment_loop):
    from nef_pipelines.lib.nef_lib import loop_row_namespace_iter

    spectra_by_times = {}
    for i, row in enumerate(
        loop_row_namespace_iter(series_experiment_loop, convert=True), start=1
    ):
        spectrum_frame_name = row.nmr_spectrum_id
        series_variable = row.series_variable

        spectrum_frame = entry.get_saveframe_by_name(spectrum_frame_name)

        key = i, series_variable, spectrum_frame_name
        spectra_by_times[key] = spectrum_frame

    return spectra_by_times


def _exit_if_spectra_are_missing(spectra_by_times_and_indices, series_name):
    for (
        _,
        _,
        spectrum_frame_name,
    ), spectrum_frame in spectra_by_times_and_indices.items():
        if not spectrum_frame:
            msg = f"no spectrum frame found for series {series_name} for spectrum {spectrum_frame_name}"
            raise NEFPLSFitLibMissingDataError(msg)


def _get_atoms_and_values(
    peaks_by_times_and_indices, data_type: IntensityMeasurementType
) -> Dict:
    atoms_to_values = {}
    for (index, x_value, spectrum_name), peaks in peaks_by_times_and_indices.items():

        for peak in peaks:
            peak_atoms = tuple([shift.atom for shift in peak.shifts])
            x_and_y = atoms_to_values.setdefault(
                tuple(peak_atoms), RelaxationSeriesValues()
            )
            x_and_y.peak_ids.append(peak.id)
            x_and_y.variable_values.append(x_value)
            y_value = (
                peak.height
                if data_type == IntensityMeasurementType.HEIGHT
                else peak.volume
            )
            x_and_y.values.append(y_value)
            x_and_y.spectra.append(spectrum_name)

    return atoms_to_values


def calculate_noise_level_from_replicates(xy_data: RelaxationSeriesValues) -> float:

    repetitons = []

    for series_values in xy_data.values():
        xs = series_values.variable_values
        ys = series_values.values
        ys_by_x = {}
        for x, y in zip(xs, ys):
            ys_by_x.setdefault(float(x), []).append(float(y))
        repeated_values = [values for values in ys_by_x.values() if len(values) > 1]
        repetitons.extend(repeated_values)

    differences = []
    for repetiton_set in repetitons:
        for combination in combinations(repetiton_set, 2):
            differences.append(combination[0] - combination[1])

    noise_level = stdev(differences) if differences else None

    fraction_error_in_stdev = (
        1 / sqrt(2) * 1 / sqrt(len(differences)) if differences else None
    )

    return noise_level, fraction_error_in_stdev, len(differences)


def _series_frame_to_outputs(series_frame: Saveframe, prefix: str, entry: Entry):
    NAMESPACE = prefix  # noqa: F841
    series_category = f(SERIES_DATA_CATEGORY)
    series_data_loop = (
        series_frame.get_loop(series_category)
        if series_category in series_frame
        else None
    )

    _exit_if_no_series_data_loop(series_data_loop, series_frame, entry, series_category)

    ids_to_outputs = OrderedDict()
    for row in loop_row_namespace_iter(series_data_loop):

        data_id = row.data_id
        if row.relaxation_list_id != UNUSED:
            ids_to_outputs.setdefault(data_id, OrderedSet()).add(row.relaxation_list_id)

    return ids_to_outputs


def _series_frame_to_id_series_data(series_frame: Saveframe, prefix: str, entry: Entry):

    NAMESPACE = prefix  # noqa: F841
    series_category = f(SERIES_DATA_CATEGORY)
    series_data_loop = (
        series_frame.get_loop(series_category)
        if series_category in series_frame
        else None
    )

    _exit_if_no_series_data_loop(series_data_loop, series_frame, entry, series_category)

    de_duped_data = OrderedDict()
    for row in loop_row_namespace_iter(series_data_loop):
        data_id = row.data_id

        nmr_spectrum_id = row.nmr_spectrum_id
        peak_id = row.peak_id
        variable_value = row.variable_value
        value = row.value

        values = (nmr_spectrum_id, peak_id, variable_value, value)

        de_duped_data.setdefault(data_id, OrderedSet()).add(values)

    id_to_xy_data = {}
    for data_id, rows in de_duped_data.items():
        relaxation_series = id_to_xy_data.setdefault(data_id, RelaxationSeriesValues())
        for row in rows:
            nmr_spectrum_id, peak_id, variable_value, value = row
            relaxation_series.spectra.append(nmr_spectrum_id)
            relaxation_series.peak_ids.append(peak_id)
            relaxation_series.variable_values.append(variable_value)
            relaxation_series.values.append(value)

    return id_to_xy_data


def _exit_if_no_series_data_loop(
    series_data_loop, series_frame, entry, series_category
):
    if series_data_loop is None:
        msg = f"""
            in the entry {entry.entry_id}
            the series frame {series_frame.name} does not have a {series_category} loop
        """
        raise NEFPLSFitLibMissingDataError(msg)
