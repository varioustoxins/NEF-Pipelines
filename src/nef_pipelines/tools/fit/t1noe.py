from math import sqrt
from pathlib import Path
from statistics import mean
from typing import List

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry, Saveframe

from nef_pipelines.lib.interface import LoggingLevels, NoiseInfo, NoiseInfoSource
from nef_pipelines.lib.nef_frames_lib import NEF_PIPELINES_NAMESPACE
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.shift_lib import IntensityMeasurementType
from nef_pipelines.lib.util import exit_error, parse_comma_separated_options
from nef_pipelines.tools.fit import fit_app
from nef_pipelines.tools.fit.fit_lib import (
    NEFPLSFitLibException,
    _combine_relaxation_series,
    _exit_if_no_frame_selectors,
    _exit_if_no_series_frames_selected,
    _fit_results_as_frame,
    _select_relaxation_series_or_exit,
    _series_frame_to_id_series_data,
    _series_frame_to_outputs,
    calculate_noise_level_from_replicates,
)

VERBOSE_HELP = """
how verbose to be, each call of verbose increases the verbosity, note this currently only reports JAX warnings
"""


def _chunker(seq, size):
    return (seq[pos : pos + size] for pos in range(0, len(seq), size))


@fit_app.command()
def t1noe(
    input: Path = typer.Option(
        None,
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="read NEF data from a file instead of stdin",
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
    verbose: int = typer.Option(LoggingLevels.WARNING, count=True, help=VERBOSE_HELP),
    frames_selectors: List[str] = typer.Argument(
        None, help="select frames to fit, these must come in pairs"
    ),
    outputs: List[str] = typer.Option(
        None,
        "--outputs",
        help="""\
            a list of output relaxation list names, there should be two in the order R1 and then NOE, these
            override values in the input frames
        """,
    ),
):
    """- fit pairs of series to exponential decays with a shared R1, amplitude and asymtote  with error propagation
    to measure T1s and {1H}–15N nOes as described in 'TROSY pulse sequence for simultaneous measurement of the
    15N R1 and {1H}–15N NOE in deuterated proteins' O’Brien & Palmer doi://10.1007/s10858-018-0181-6 [alpha]
    """

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

    _exit_if_series_frame_not_in_pairs(series_frames)

    _exit_if_no_series_frames_selected(series_frames, frame_selectors)

    if outputs:
        outputs = parse_comma_separated_options(outputs)

    # TODO outputs should be a list of pairs, isolate in function
    if outputs and len(outputs) != 2:
        joined_outputs = ", ".join(outputs)
        msg = f"""
            when fitting symmetrical R1 curves and {{1H}}-15N nOes there must be two output relaxation lists
            the first will contain R1 fits and the second {{1H}}-15N nOes, you gave {len(outputs)} outputs
            which were:

            {joined_outputs}
        """

        exit_error(msg)

    entry = pipe(
        entry, series_frames, cycles, noise_level, data_type, seed, verbose, outputs
    )

    print(entry)


def pipe(
    entry: Entry,
    series_frames: List[Saveframe],
    cycles: int,
    noise_level,
    data_type: IntensityMeasurementType,
    seed: int,
    verbose: int = 0,
    outputs=None,
) -> Entry:

    try:
        from streamfitter import fitter

        function = fitter.get_function(
            fitter.FUNCTION_TWO_EXPONENTIAL_DECAYS_2_PAMETER_SHARED_RATE
        )

    except ImportError as e:

        msg = f"""
                error the package streamfitter is not installed or is not importing properly
                the error was {e}
            """

        exit_error(msg)

    for series_frame_1, series_frame_2 in _chunker(series_frames, 2):

        id_series_data_1 = _series_frame_to_id_series_data(
            series_frame_1, NEF_PIPELINES_NAMESPACE, entry
        )

        id_series_data_2 = _series_frame_to_id_series_data(
            series_frame_2, NEF_PIPELINES_NAMESPACE, entry
        )

        id_outputs_1 = _series_frame_to_outputs(
            series_frame_1, NEF_PIPELINES_NAMESPACE, entry
        )

        id_outputs_2 = _series_frame_to_outputs(
            series_frame_2, NEF_PIPELINES_NAMESPACE, entry
        )

        if noise_level is not None:
            requested_noise_source = NoiseInfoSource.CLI
            noise_source = NoiseInfoSource.CLI
            noise_error_fraction = None
            num_replicates = None
        else:
            requested_noise_source = NoiseInfoSource.REPLICATES
            noise_level_1, noise_1_error_fraction, num_replicates_1 = (
                calculate_noise_level_from_replicates(id_series_data_1)
            )

            noise_level_2, _noise_2_error_fraction, num_replicates_2 = (
                calculate_noise_level_from_replicates(id_series_data_2)
            )

            if noise_level_1 and noise_level_2:
                noise_level = sqrt(noise_level_1**2 + noise_level_2**2)
                noise_error_fraction = (
                    mean(noise_1_error_fraction, noise_1_error_fraction) * 1 / sqrt(2)
                )
                noise_source = NoiseInfoSource.REPLICATES
            else:
                noise_level = None
                noise_error_fraction = None
                noise_source = NoiseInfoSource.NONE
            num_replicates = num_replicates_1 + num_replicates_2

        if num_replicates == 0:
            noise_source = NoiseInfoSource.NONE

        noise_info = NoiseInfo(
            noise_source,
            noise_level,
            noise_error_fraction,
            num_replicates,
            requested_noise_source,
        )

        print("#", noise_info)

        data_ids = OrderedSet([*id_series_data_1.keys(), *id_series_data_2.keys()])

        if not outputs:
            outputs = OrderedSet()
            for data_id in data_ids:
                outputs.update(id_outputs_1[data_id])
                outputs.update(id_outputs_2[data_id])
            outputs = list(outputs)

        outputs = [output.replace("nefpls_relaxation_list_", "") for output in outputs]

        try:

            id_series_data = {
                data_id: _combine_relaxation_series(
                    id_series_data_1[data_id], id_series_data_2[data_id]
                )
                for data_id in data_ids
            }
        except NEFPLSFitLibException as e:
            msg = f"""
                merging the series {series_frame_1.name} and {series_frame_2.name} in entry {entry.entry_id}
                failed because {e}
            """
            exit_error(msg)

        id_xy_data = {
            data_id: (series_datum.variable_values, series_datum.values)
            for data_id, series_datum in id_series_data.items()
        }

        results = fitter.fit(
            function(),
            id_xy_data,
            cycles,
            noise_info,
            seed,
            verbose=verbose,
        )

        fits = results["fits"]
        monte_carlo_errors = results["monte_carlo_errors"]
        monte_carlo_value_stats = results["monte_carlo_value_stats"]
        monte_carlo_param_values = results["monte_carlo_param_values"]
        noise_level = results["noise_level"]
        version_strings = results["versions"]

        fit_ids = ["time_constant", "offset"]
        for fit_name, output in zip(fit_ids, outputs):
            frame = _fit_results_as_frame(
                series_frame_1,
                NEF_PIPELINES_NAMESPACE,
                entry,
                fits,
                fit_name,
                output,
                monte_carlo_errors,
                monte_carlo_value_stats,
                monte_carlo_param_values,
                seed,
                noise_info,
                version_strings,
                "r1-noe-symmetric-double-exponential",
            )

            entry.add_saveframe(frame)

    return entry


def _exit_if_series_frame_not_in_pairs(series_frames):

    if len(series_frames) % 2 != 0:
        frame_names = [
            "{i}. {frame.name}" for i, frame in enumerate(series_frames, start=1)
        ]
        msg = f"""
            This fitter requires pairs of data to fit pairs of exponentials you provided and odd number of data sets:

            {frame_names}
        """
        exit_error(msg)


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
