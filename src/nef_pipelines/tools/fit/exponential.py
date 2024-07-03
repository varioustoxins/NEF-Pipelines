from enum import auto
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry, Saveframe
from strenum import StrEnum

from nef_pipelines.lib.nef_lib import (
    NEF_PIPELINES_PREFIX,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.shift_lib import IntensityMeasurementType
from nef_pipelines.lib.util import exit_error, parse_comma_separated_options
from nef_pipelines.tools.fit import fit_app
from nef_pipelines.tools.fit.fit_lib import (
    _exit_if_no_frame_selectors,
    _exit_if_no_series_frames_selected,
    _fit_results_as_frame,
    _select_relaxation_series_or_exit,
    _series_frame_to_id_series_data,
)

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

NAMESPACE = NEF_PIPELINES_PREFIX


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
    """- fit a data series to an exponential decay with error propagation [alpha]"""

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

    for series_frame in series_frames:
        id_series_data = _series_frame_to_id_series_data(
            series_frame, NEF_PIPELINES_PREFIX, entry
        )

        id_xy_data = {
            id: (series_datum.variable_values, series_datum.values)
            for id, series_datum in id_series_data.items()
        }

        results = stream_fitter(id_xy_data, error_method, cycles, noise_level, seed)

        fits = results["fits"]
        monte_carlo_errors = results["monte_carlo_errors"]
        monte_carlo_value_stats = results["monte_carlo_value_stats"]
        monte_carlo_param_values = results["monte_carlo_param_values"]
        noise_level = results["noise_level"]
        version_strings = results["versions"]

        frame = _fit_results_as_frame(
            series_frame,
            NAMESPACE,
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


# implementation thoughts
# 1. having a spectrometer frequency and field strength in the same construct is a pain, what do we define as the
#    conversion ratio i took value in cavanagh and cross-checked it with from https://www.kherb.io/docs/nmr_table.html
#    which uses the codata value for 1H [but not for 15N and 13C which use the IAEA values]
# 2. if we have 1H and 15N and 13C spectrometer frequencies which should we use to
#    calculate the field strength? i chose the one with the highest gamma, but note my gamma ratios do not match
#    those in https://www.kherb.io/docs/nmr_table.html exacly
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
# 12. why is relaxation_list_id repeated when nef_series_list isn't a singleton and applies to only one experimental
# series?
# 13. question can you use _nef_series_data as an input table for a calculation and leave relaxation_list_id blank to be
# filled out by the calculation engine. Also for het noe should the series list values be  bool or 1 and 0 for the
# saturation
# 14. not sure not repeating the atom names in the series data is a good idea as the _nef_relaxation loop needs
# them for the result and you have to wade through all the spectra again while dou don't need to for the actual dat and
# they can be inconsistent or even missing...
# 15. there is no connection from the nef_relaxation_list to the original nef_series_list specifically
#     it has a data_id but series list that data_id refers to isn't mentioned... to find it i have to scan
#     through all save_nef_series_lists and what happens if 2 refer to this nef_relaxation_list...
# 16 experiment_ypes homonuclear_NOEs is plural and some are singular
# 17. shouldn't it be value_uncertainty
