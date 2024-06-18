import math
from enum import auto
from pathlib import Path
from typing import List, Tuple

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry, Loop, Saveframe
from strenum import StrEnum

from nef_pipelines.lib.isotope_lib import (
    CODE_TO_ISOTOPE,
    GAMMA_RATIOS,
    MAGNETOGYRIC_RATIO_1H,
)
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    SelectionType,
    create_nef_save_frame,
    get_frame_id,
    loop_row_namespace_iter,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.shift_lib import IntensityMeasurementType
from nef_pipelines.lib.util import exit_error, parse_comma_separated_options
from nef_pipelines.tools.fit import fit_app

streamfitter_install_failure = None
try:
    from streamfitter.fitter import ErrorPropogation, fitter

    stream_fitter = fitter

except ImportError as e:
    streamfitter_intall_failure = e

    # this is partial copy of the enum to avoid errors
    class ErrorPropogation(StrEnum):
        PROPOGATION = "error stream fitter package not installed"
        ERROR_STREAM_FITTER_NOT_INSTALLED = auto()

    stream_fitter = None


@fit_app.command()
def exponential(
    input: Path = typer.Option(
        None,
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="read NEF data from a file instead of stdin",
    ),
    error_method: ErrorPropogation = typer.Option(
        ErrorPropogation.PROPOGATION,
        "-e",
        "--error-method",
        help="error propogation method",
    ),
    cycles: int = typer.Option(
        1000,
        "-c",
        "--cycles",
        help="number of cycles for error propogation",
    ),
    noise_level: float = typer.Option(
        None,
        "-n",
        "--noise-level",
        help="noise level to use instead of value from replicates",
    ),
    seed: int = typer.Option(
        42, "-s", "--seed", help="seed for random number generator"
    ),
    data_type: IntensityMeasurementType = typer.Option(
        IntensityMeasurementType.HEIGHT, "-d", "--data-type", help="data type to fit"
    ),
    frames_selectors: List[str] = typer.Argument(None, help="select frames to fit"),
):
    """- fit a data series to an exponential decay with error propogation"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frame_selectors = parse_comma_separated_options(frames_selectors)

    if not frames_selectors:
        series_frames = entry.get_saveframes_by_category("nef_series_list")
        if len(series_frames) == 1:
            frame_selectors = [
                series_frames[0].name,
            ]

    _exit_if_no_frame_selectors(frame_selectors)

    series_frames = _select_relaxation_series_or_exit(entry, frames_selectors)

    _exit_if_no_series_frames_selected(series_frames, frame_selectors)

    entry = pipe(
        entry, series_frames, error_method, cycles, noise_level, data_type, seed
    )

    print(entry)


def pipe(
    entry: Entry,
    series_frames: List[Saveframe],
    error_method: ErrorPropogation,
    cycles: int,
    noise_level,
    data_type: IntensityMeasurementType,
    seed: int,
) -> Entry:

    if stream_fitter is None:
        msg = f"""
                error the package streamfitter is not installed or is not importing properly
                the error was {streamfitter_intall_failure}
            """

        exit_error(msg)

    fitted_data = stream_fitter(
        entry, series_frames, error_method, cycles, noise_level, data_type, seed
    )

    for data, series_frame in zip(fitted_data, series_frames):
        fits = data["fits"]
        monte_carlo_errors = data["monte_carlo_errors"]
        monte_carlo_value_stats = data["monte_carlo_value_stats"]
        monte_carlo_param_values = data["monte_carlo_param_values"]
        noise_level = data["noise_level"]
        version_strings = data["versions"]

        frame = _results_as_frame(
            series_frame,
            entry,
            fits,
            monte_carlo_errors,
            monte_carlo_value_stats,
            monte_carlo_param_values,
            noise_level,
            version_strings,
        )

        entry.add_saveframe(frame)

    return entry


def _results_as_frame(
    series_frame,
    entry,
    fits,
    monte_carlo_errors,
    monte_carlo_value_stats,
    monte_carlo_param_values,
    noise_level,
    version_strings,
):
    spectrum_frames = _series_frame_to_spectrum_frames(series_frame, entry)

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

    frame_id = get_frame_id(series_frame)

    result_frame = create_nef_save_frame("nef_relaxation_list", f"{frame_id}_fitted")

    result_frame.add_tag("experiment_type", series_frame.get_tag("experiment_type")[0])
    result_frame.add_tag("field_strength", field_strength)
    result_frame.add_tag("value_unit", "s-1")
    result_frame.add_tag("relaxation_atom_id", axis_of_lowest_gamma)
    result_frame.add_tag("ref_value", UNUSED)
    result_frame.add_tag("source", "experimental")
    result_frame.add_tag("fitting_function", "ExponentialDecay")
    result_frame.add_tag("minimizer", "leastsq")
    result_frame.add_tag("error_method", "montecarlo")
    comment = f"""
        fitting software {version_strings}
        random_seed 42
        noise_estimate {noise_level}

        source_of_noise_estimate 'replicates'
        number_of_replicates: {len(spectrum_frames)}
    """
    # error_in_noise-estimate {}
    # fit_time {}
    result_frame.add_tag("comment", comment)

    relaxation_loop = Loop.from_scratch("nef_relaxation")
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
    for index, (atom_key, fit) in enumerate(fits.items(), start=1):
        data_row = {"index": index, "data_id": index, "data_combination_id": UNUSED}
        for i, atom in enumerate((atom_key), start=1):
            residue = atom.residue
            data_row.update(
                {
                    f"chain_code_{i}": residue.chain_code,
                    f"sequence_code_{i}": residue.sequence_code,
                    f"residue_name_{i}": residue.residue_name,
                    f"atom_name_{i}": atom.atom_name,
                }
            )
        data.append(data_row)
        mc_error = monte_carlo_errors[atom_key]["time_constant_mc_error"]
        data_row.update(
            {
                "value": f'{fit.params["time_constant"].value:.20f}',
                "value_error": f"{mc_error:.20f}",
            }
        )

    relaxation_loop.add_data(data)

    return result_frame


def _isotope_axes_to_lowest_gamma_axis(isotope_axes):
    return min(
        isotope_axes,
        key=lambda x: min(GAMMA_RATIOS[isotope] for isotope in isotope_axes[x]),
    )


def _exit_if_no_frequencies_found(isotope_frequencies, series_frame, entry):
    if not isotope_frequencies:
        msg = f"""
            no isotope frequencies found in the series frame {series_frame.name} in entry {entry.entry_id}
        """
        exit_error(msg)


def _get_unique_isotope_frequencies(isotope_frequencies):

    return {
        isotope: list(frequency)[0]
        for isotope, frequency in isotope_frequencies.items()
    }


def _series_frame_to_spectrum_frames(series_frame, entry):

    spectrum_frames = []
    for i, row in enumerate(
        loop_row_namespace_iter(
            series_frame.get_loop("nef_series_experiment"), convert=True
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
    relaxation_frames = select_frames(entry, "nef_series_list", SelectionType.CATEGORY)
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

    selected_frames_and_ids = series_frames_and_ids.intersection(named_frames_and_ids)

    return [
        entry.get_saveframe_by_name(frame_name)
        for frame_name, _ in selected_frames_and_ids
    ]


def _exit_if_no_series_frames_selected(active_relaxation_frames, frame_selectors):
    if not active_relaxation_frames:
        msg = f"""
            no series frames selected by the selectors
            {" ".join(frame_selectors)}
        """
        exit_error(msg)


def _exit_if_no_frame_selectors(frame_selectors):
    if len(frame_selectors) == 0:
        msg = "you must select some frames!"
        exit_error(msg)

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

            exit_error(msg)


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

            exit_error(msg)


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

        if not isotope_code in CODE_TO_ISOTOPE:
            continue

        isotope = CODE_TO_ISOTOPE[isotope_code]
        gamma_ratio = GAMMA_RATIOS[isotope]

        field = frequency / MAGNETOGYRIC_RATIO_1H / gamma_ratio

        fields_by_gamma_and_isotope[gamma_ratio, isotope] = field

    highest_gamma_isotope = max(fields_by_gamma_and_isotope, key=lambda x: x[0])

    return fields_by_gamma_and_isotope[highest_gamma_isotope]


def orderOfMagnitude(number):
    return math.floor(math.log(number, 10))


# implementation thoughts
# 1. having a spectrometer frequency and field strength in the same construct is a pain, what do we dfeine as the
#    conversion ratio i took  alue in cavanagh and cross-checked it with from https://www.kherb.io/docs/nmr_table.html
#    which uses the codata value for 1H [but not for 15N and 13C which use the IAEA values]
# 2. if we have 1H and 15N and 13C spectrometer frequencies which should we use to
#    calculate the field strength? i chose the one with the highest gamma, but note my gamma ratios do not those in
#    https://www.kherb.io/docs/nmr_table.html exacly
# 3. do we need the value type should it be Nz for a 15N experiment, what are I and S defined as in this context
# 4. how do we determine the relaxation_atom_id shouldn't also be available on the series data or come from the series
#    data as it's the type of experiment and the experimenta series that determine this, currently choose lowest gamma!
# 5. the value doesn't have a type just a unit, should it?
# 6. the source maybe should be on the data series rather than the relaxation list -  it knoes what its is
#    the relaxation list doesn't need tow
# 7. the nef_relaxation doesn't leave room for other fit values e.g I or the baseline offset for a 3 point fit...
# 8. room for a comment on each fit would be good...
# 9. when would the index and data_id in a nef_relaxation_list be different?
# 10. we should say the value error is sigma
# 11. why are some of our constants capitalised and others not - we should be consistent
#     e.g. experimental | simulated | theoretical vs OnePhaseDecay | ExponentialDecay | InversionRecovery | other
