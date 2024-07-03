from itertools import zip_longest
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry, Loop, Saveframe
from strenum import StrEnum

from nef_pipelines.lib.nef_lib import (
    NEF_PIPELINES_PREFIX,
    NEF_RELAXATION_VERSION,
    UNUSED,
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
    select_frames_by_name,
)
from nef_pipelines.lib.peak_lib import frame_to_peaks
from nef_pipelines.lib.shift_lib import IntensityMeasurementType
from nef_pipelines.lib.util import exit_error, parse_comma_separated_options
from nef_pipelines.tools.fit.fit_lib import (
    _exit_if_spectra_are_missing,
    _get_atoms_and_values,
    _get_spectra_by_series_variable,
)
from nef_pipelines.tools.series import series_app

NAMESPACE = NEF_PIPELINES_PREFIX


class SeriesSelectionMethod(StrEnum):
    """Selection types for selecting frames"""

    ASSIGNMENT = "name"
    POSITION = "position"
    TAG = "tag"


@series_app.command()
def table(
    input: Path = typer.Option(
        None,
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="read NEF data from a file instead of stdin",
    ),
    exact: bool = typer.Option(
        False,
        "--exact",
        help="use exact matching of frame names",
    ),
    # series_type: SeriesSelectionMethod = typer.Argument(
    #     SelectionType.ASSIGNMENT,
    #     help='how to select groups of peaks in the series frames',
    # ),
    frames_selectors: List[str] = typer.Argument(
        None,
        help="series frames to build data tables for",
    ),
    intensity_measurement_type: IntensityMeasurementType = typer.Option(
        IntensityMeasurementType.HEIGHT,
        "--measurement-type",
        help="measurement type to use for intensity values",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="force overwriting of the table if one alread exists",
    ),
    add_atom_names: bool = typer.Option(
        False,
        "--add-atom-names",
        help="decorate the table with the names of the atoms in the peaks",
    ),
):
    """- build a NEF data series from a set of spectra [alpha]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frame_selectors = parse_comma_separated_options(frames_selectors)

    _exit_if_no_frame_selectors(frame_selectors)

    frames = _select_series_frames(entry, frames_selectors, exact=exact)

    entry = pipe(
        entry,
        frames,
        intensity_measurement_type,
        SeriesSelectionMethod.ASSIGNMENT,
        force,
        add_atom_names,
    )

    print(entry)


# TODO: add checks if there are peaks with duplicate atom names and exit as error
def pipe(
    entry: Entry,
    series_frames: List[str],
    intensity_measurement_type: str,
    series_selection_method: SeriesSelectionMethod,
    force: bool,
    add_atom_names: bool,
) -> Entry:

    for series_frame in series_frames:
        relaxation_loop_name = series_frame.name
        series_data_loop = _build_series_data_loop(
            series_frame,
            intensity_measurement_type,
            entry,
            relaxation_loop_name,
            add_atom_names,
        )

        _exit_if_frame_has_loop_unless_force(
            series_frame, series_data_loop, entry, force
        )

        series_frame.add_loop(series_data_loop)
    return entry


def _exit_if_frame_has_loop_unless_force(series_frame, series_data_loop, entry, force):
    if series_data_loop.category in series_frame and not force:
        msg = f"""
                in the entry {entry.id}
                the frame {series_frame.name} already has a loop with the category {series_data_loop.category}

                to force addition of the loop use the --force option
            """
        exit_error(msg)


def _build_series_data_loop(
    series_frame,
    intensity_measurement_type,
    entry,
    relaxation_loop_name,
    add_atom_names,
):

    series_experiment_loop = (
        series_frame[f"_{NAMESPACE}_series_experiment"]
        if f"_{NAMESPACE}_series_experiment" in series_frame
        else None
    )

    spectra_by_times_and_indices = _get_spectra_by_series_variable(
        entry, series_experiment_loop
    )

    _exit_if_spectra_are_missing(spectra_by_times_and_indices, series_frame.name)

    peaks_by_times_and_indices = {
        key: frame_to_peaks(spectrum_frame)
        for key, spectrum_frame in spectra_by_times_and_indices.items()
    }

    atoms_and_values = _get_atoms_and_values(
        peaks_by_times_and_indices, intensity_measurement_type
    )

    series_data_loop = Loop.from_scratch(f"{NAMESPACE}_series_data")

    tags = [
        "version",
        "nmr_spectrum_id",
        "peak_id",
        "variable_value",
        "variable_error",
        "value",
        "value_error",
        "relaxation_list_id",
        "data_id",
    ]

    additional_tags = []
    if add_atom_names:
        max_num_atoms = max([len(atoms) for atoms in atoms_and_values.keys()])
        additional_tags = [
            f"nefpls_chain_code_{i} nefpls_sequence_code_{i} nefpls_residue_name_{i} nefpls_atom_name_{i}".split()
            for i in range(1, max_num_atoms + 1)
        ]
    tags.extend(additional_tags)

    series_data_loop.add_tag(tags)

    for group_index, (atoms, values) in enumerate(atoms_and_values.items(), start=1):
        zipper = zip_longest(
            values.spectra,
            values.peak_ids,
            values.variable_values,
            values.values,
            fillvalue=UNUSED,
        )

        for spectrum, peak_id, series_value, value in zipper:
            data = {
                "version": NEF_RELAXATION_VERSION,
                "nmr_spectrum_id": spectrum,
                "peak_id": peak_id,
                "variable_value": series_value,
                "variable_error": UNUSED,
                "value": value,
                "value_error": UNUSED,
                "relaxation_list_id": f"{relaxation_loop_name}_fitted",
                "data_id": group_index,
            }

            if add_atom_names:
                for i, atom in enumerate(atoms, start=1):
                    data.update(
                        {
                            f"nefpls_chain_code_{i}": atom.residue.chain_code,
                            f"nefpls_sequence_code_{i}": atom.residue.sequence_code,
                            f"nefpls_residue_name_{i}": atom.residue.residue_name,
                            f"nefpls_atom_name_{i}": atom.atom_name,
                        }
                    )

            series_data_loop.add_data(
                [
                    data,
                ]
            )

    return series_data_loop


def _select_series_frames(
    entry: Entry, frame_selectors: List[str], exact: bool
) -> List[Saveframe]:
    raw_series_frames = select_frames(
        entry, f"{NAMESPACE}_series_list", SelectionType.CATEGORY
    )

    return select_frames_by_name(raw_series_frames, frame_selectors, exact=exact)


def _exit_if_no_frame_selectors(frame_selectors):
    if len(frame_selectors) == 0:
        msg = "you must select some frames!"
        exit_error(msg)


# def _guess_experiment_type(name):
#     upper_name = name.upper()
#     for experiment_name in NAME_TO_EXPERIMENT_TYPE:
#         if experiment_name in upper_name:
#             result = NAME_TO_EXPERIMENT_TYPE[upper_name]
#             break
#         else:
#             result = "unknown"
#     return result
#
#
# def _guess_series_name(entry, frames_and_timings):
#     result = None
#     for relaxation_type in NAME_TO_EXPERIMENT_TYPE:
#         do_break = False
#         for name, _ in frames_and_timings.keys():
#             name = name.upper()
#             if relaxation_type in name.upper():
#                 start_index = name.index(relaxation_type)
#                 end_index = start_index + len(relaxation_type)
#                 found_relaxation_type = name[start_index:end_index]
#
#                 result = found_relaxation_type
#                 do_break = True
#                 break
#         if do_break:
#             break
#
#     if not result:
#         result = "unknown_type"
#
#     bad_frame_name = False
#     for frame in entry:
#         if frame.name == result:
#             bad_frame_name = True
#             break
#
#     if bad_frame_name:
#         base_result = result
#         for i in range(1, 100):
#             result = f"series`{i}`"
#             bad_frame_name = False
#             for frame in entry:
#                 if frame.name == result:
#                     bad_frame_name = True
#                     break
#
#     if bad_frame_name:
#         _exit_if_too_many_clashing_frame_names(bad_frame_name, base_result)
#
#     return result
#
#
# def _exit_if_too_many_clashing_frame_names(bad_frame_name, base_result):
#     if bad_frame_name:
#         msg = f"""
#             after searching the series of names {base_result}`1` to {base_result}`100` i could not find a name
#             that was not already in the entry, choose a name on the command line, you have way too much data!
#             more serious report this as a bug...
#         """
#         exit_error(msg)
#
#
# def _get_timings_and_units_for_frames(
#     frames, frame_selectors, timings, input_unit, display_parsed_values
# ):
#
#     if timings:
#         timings_and_units = _parse_timings(timings)
#         units = [timing_and_unit[1] for timing_and_unit in timings_and_units]
#
#         _exit_if_input_unit_defined_and_any_unit_parsed(
#             input_unit, units, timings_and_units
#         )
#
#         if input_unit:
#             timings_and_units = [
#                 (timing, input_unit) for timing, _ in timings_and_units
#             ]
#
#         _exit_error_it_number_of_timings_doesnt_match_number_of_frames(
#             frames, timings_and_units
#         )
#
#         frame_timings_and_units = {
#             (frame.name, id(frame)): timing_and_unit
#             for frame, timing_and_unit in zip(frames, timings_and_units)
#         }
#     else:
#         _exit_if_frame_selector_has_no_timing_selector(frame_selectors)
#         frame_timings_and_units = _parse_timings_from_frames_or_exit(
#             frames, frame_selectors[0], display_parsed_values
#         )
#
#     return frame_timings_and_units
#
#
# def _exit_if_input_unit_defined_and_any_unit_parsed(
#     input_unit, units, timings_and_units
# ):
#     if input_unit and any(unit != "" for unit in units):
#         units_and_timings_strings = [
#             f"{unit}{timing}" for unit, timing in timings_and_units if unit
#         ]
#         msg = f"""
#                 you cannot provide a unit on the command line [--unit] and units in the timings [--timings]
#                 at the same time command line unit was {input_unit} and the units and timings were
#                 {strings_to_tabulated_terminal_sensitive(units_and_timings_strings)}
#
#                 """
#         exit_error(msg)
#
#
# def _exit_error_it_number_of_timings_doesnt_match_number_of_frames(
#     frames, timings_and_units
# ):
#     if len(timings_and_units) != len(frames):
#         msg = f"the number of timings {len(timings_and_units)} does not match the number of frames {len(frames)}"
#         exit_error(msg)
#
#
# def _exit_if_frame_selector_has_no_timing_selector(frame_selectors):
#     if len(frame_selectors) != 1 or "{var}" not in frame_selectors[0]:
#         NEWLINE = "\n"
#         msg = f"""
#                     no timings provided to select timings you must have a single frame selector with
#                     a {{var}} placeholder i got {len(frame_selectors)} frame selectors and they were:
#                     {NEWLINE.join(frame_selectors)}
#                 """
#         exit_error(msg)
#
# def _exit_if_some_frames_are_not_spectra(non_spectrum_frame_names):
#     msg = f"""
#             some of the selected frames are not spectrum frames:
#             {non_spectrum_frame_names}
#             """
#     exit_error(msg)
#
# def _parse_timings_from_frames_or_exit(
#     save_frames: List[Saveframe], frame_selector: str, display_parsed_values: bool
# ) -> Dict[Tuple[str, int], List[Tuple[Union[int, float, bool], str]]]:
#     if "{var}" not in frame_selector:
#         msg = f"no timing selector placeholder {{var}} provided in frame selector {frame_selector}"
#         exit_error(msg)
#
#     frame_selector = frame_selector.replace("{var}", "{var}")
#     frame_selector = frame_selector.replace("*", "{:opt}")
#
#     parser = parse_compile(frame_selector)
#
#     parsed_values = []
#
#     frame_value_and_units = {}
#     for frame in save_frames:
#         frame_key = frame.name, id(frame)
#         result = parser.search(frame.name)
#
#         value, unit = None, None
#         if result and "var" in result:
#             raw_value = result["var"]
#             raw_value = raw_value.replace("_", ".")
#             raw_value = raw_value.replace("-", ".")
#
#             value, unit = _parse_value_and_unit(raw_value)
#
#         if display_parsed_values:
#             parsed_values.append([frame.name, raw_value, value, unit])
#
#         if value is None:
#             _exit_if_no_variable_found(frame, frame_selector)
#
#         if not (is_float(value) or value.lower() in "on off true false yes no"):
#             msg = f"the variable {value} in frame {frame.name} is not a number or a boolean"
#             exit_error(msg)
#
#         frame_value_and_units[frame_key] = value, unit
#
#     if display_parsed_values:
#         print(
#             tabulate(parsed_values, headers=["spectrum", "raw value", "value", "unit"]),
#             file=sys.stderr,
#         )
#         sys.exit(0)
#
#     return frame_value_and_units
#
#
# def _exit_if_no_variable_found(frame, frame_selector):
#     msg = f"no variable found in frame {frame.name} with the selector {frame_selector}"
#     exit_error(msg)
#
#
# def _parse_timings(timings: List[str]) -> List[Tuple[Union[int, float, bool], str]]:
#     timings = parse_comma_separated_options(timings)
#     parsed_timings = []
#     for timing in timings:
#         value, unit = _parse_value_and_unit(timing)
#         parsed_timings.append((value, unit))
#     return parsed_timings
#
#
# def _parse_value_and_unit(value: str) -> Tuple[Union[bool, int, float, None]]:
#
#     unit = value.lstrip(string.digits + ".eE")
#     len_digits = len(value) - len(unit)
#     value = value[:len_digits]
#
#
#     lower_unit = unit.lower()
#     if value and unit:
#         pass
#     elif not value and lower_unit in STR_TO_SATURATION_STATE:
#         unit = "bool"
#         value = STR_TO_SATURATION_STATE[lower_unit]
#     elif not unit:
#         if is_int(value):
#             value = int(value)
#         elif is_float(value):
#             value = float(value)
#     else:
#         unit =  None
#         value =  None
#
#     return value, unit
#

#
# def _ensure_units_consistent_and_get_unit_and_timings_or_exit(frames_timings_and_units):
#
#     _exit_units_not_consistent(frames_timings_and_units)
#
#     _exit_if_numbers_and_bools_are_mixed(frames_timings_and_units)
#
#     float_counter = Counter()
#     int_counter = Counter()
#     for frame, (value, unit) in frames_timings_and_units.items():
#         if isinstance(value, int):
#             int_counter[value] += 1
#         elif isinstance(value, float):
#             float_counter[value] += 1
#
#     if int_counter and float_counter:
#         for frame_key, (value, unit) in frames_timings_and_units.items():
#             value = float(value)
#
#             frames_timings_and_units[frame_key] = value, unit
#
#     unit = list(frames_timings_and_units.values())[0][1]
#     frames_and_timings = {
#         frame_key: value for frame_key, (value, _) in frames_timings_and_units.items()
#     }
#
#     return frames_and_timings, unit
#
#
# def _exit_if_numbers_and_bools_are_mixed(frame_timings_and_units):
#
#     counter_numbers = Counter()
#     couter_booleans = Counter()
#
#     for frame, (value, unit) in frame_timings_and_units.items():
#         if isinstance(value, bool):
#             couter_booleans[value] += 1
#         elif is_float(value):
#             counter_numbers[value] += 1
#
#     if counter_numbers and couter_booleans:
#         numbers_strings = ", ".join(counter_numbers.keys())
#         booleans_strings = ", ".join(couter_booleans.keys())
#         msg = f"""
#                 you cannot have both numbers and booleans in the values
#                 the booleans were
#                 {booleans_strings}
#                 the numbers were
#                 {numbers_strings}
#             """
#         exit_error(msg)
#
#
# def _exit_units_not_consistent(frame_timings_and_units):
#
#     unit_counter = Counter()
#     for frame, (value, unit) in frame_timings_and_units.items():
#         unit_counter[unit] += 1
#
#     if len(unit_counter) > 1:
#         unit_strings = ", ".join(unit_counter.keys())
#         msg = f"""
#             the units of the timings are not consistent, the units found were
#             {unit_strings}
#             """
#         exit_error(msg)
#
#
# def _exit_if_units_are_not_compatible(frame_timings_and_units):
#     units = {unit for timing, unit in frame_timings_and_units.values()}
#     if len(units) > 1:
#         units_and_timings_strings = [
#             f"{unit}{timing}" for timing, unit in frame_timings_and_units.values()
#         ]
#         msg = f"""
#                 the units of the timings are not compatible they are {units}
#                 the timings and units were
#                 {strings_to_tabulated_terminal_sensitive(units_and_timings_strings)}
#                 """
#         exit_error(msg)
