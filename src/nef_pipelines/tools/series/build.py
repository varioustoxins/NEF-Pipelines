import string
import sys
from collections import Counter
from enum import IntEnum, auto
from pathlib import Path
from typing import Dict, List, Tuple, Union

import typer
from ordered_set import OrderedSet
from parse import compile as parse_compile
from pynmrstar import Entry, Loop, Saveframe
from strenum import StrEnum
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    NEF_PIPELINES_PREFIX,
    NEF_RELAXATION_VERSION,
    UNUSED,
    SelectionType,
    add_frames_to_entry,
    create_nef_save_frame,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.util import (
    exit_error,
    is_float,
    is_int,
    parse_comma_separated_options,
    strings_to_tabulated_terminal_sensitive,
)
from nef_pipelines.tools.series import series_app

NAMESPACE = NEF_PIPELINES_PREFIX

FRAMES_AND_TIMES_HELP = "the list of frame selectors and their values"


class RelaxationExperimentType(StrEnum):
    AUTO_RELAXATION = auto()
    DIPOLE_CSA_CROSS_CORRELATIONS = auto()
    DIPOLE_DIPOLE_CROSS_CORRELATIONS = auto()
    DIPOLE_DIPOLE_RELAXATION = auto()
    HETERONUCLEAR_NOES = auto()
    HETERONUCLEAR_R1_RELAXATION = auto()
    HETERONUCLEAR_R1RHO_RELAXATION = auto()
    HETERONUCLEAR_R2_RELAXATION = auto()
    H_EXCHANGE_PROTECTION_FACTORS = auto()
    H_EXCHANGE_RATES = auto()
    HOMONUCLEAR_NOES = auto()
    CPMG = auto()
    CEST = auto()
    OTHER = auto()
    T1 = HETERONUCLEAR_R1_RELAXATION
    T2 = HETERONUCLEAR_R2_RELAXATION
    T1RHO = HETERONUCLEAR_R1RHO_RELAXATION
    R1 = HETERONUCLEAR_R1_RELAXATION
    R2 = HETERONUCLEAR_R2_RELAXATION
    NOE = HETERONUCLEAR_NOES


EXPERIMENT_TYPE_TO_SERIES_VARIABLE_TYPE = {
    RelaxationExperimentType.HETERONUCLEAR_R1_RELAXATION: "time",
    RelaxationExperimentType.HETERONUCLEAR_R2_RELAXATION: "time",
    RelaxationExperimentType.HETERONUCLEAR_R1RHO_RELAXATION: "time",
    RelaxationExperimentType.HETERONUCLEAR_R1_RELAXATION: "time",
    RelaxationExperimentType.HETERONUCLEAR_R2_RELAXATION: "time",
    RelaxationExperimentType.HETERONUCLEAR_NOES: "saturation",
    RelaxationExperimentType.CPMG: "cycles",
    RelaxationExperimentType.CEST: "offset",
    RelaxationExperimentType.OTHER: "unknown",
}

EXPERIMENT_TYPE_TO_DATA_VARIABLE_TYPE = {
    RelaxationExperimentType.HETERONUCLEAR_R1_RELAXATION: "intensity",
    RelaxationExperimentType.HETERONUCLEAR_R2_RELAXATION: "intensity",
    RelaxationExperimentType.HETERONUCLEAR_R1RHO_RELAXATION: "intensity",
    RelaxationExperimentType.HETERONUCLEAR_R1_RELAXATION: "intensity",
    RelaxationExperimentType.HETERONUCLEAR_R2_RELAXATION: "intensity",
    RelaxationExperimentType.HETERONUCLEAR_NOES: "intensity",
    RelaxationExperimentType.CPMG: "intensity",
    RelaxationExperimentType.CEST: "intensity",
    RelaxationExperimentType.OTHER: "unknown",
}

DATA_VARIABLE_TYPE_TO_DATA_VARIABLE_UNIT = {
    "intensity": UNUSED,
    "volume": UNUSED,
    "unknown": UNUSED,
}

SERIES_VARIABLE_TYPE_TO_SERIES_VARIABLE_UNIT = {
    "time": "s",
    "saturation": "fraction",
    "cycles": UNUSED,
    "offset": "hz",
}

EXPERIMENT_TO_IDENTIFIER = {
    RelaxationExperimentType.AUTO_RELAXATION: "auto_relaxation",
    RelaxationExperimentType.DIPOLE_CSA_CROSS_CORRELATIONS: "dipole_CSA_cross_correlations",
    RelaxationExperimentType.DIPOLE_DIPOLE_CROSS_CORRELATIONS: "dipole_dipole_cross_correlations",
    RelaxationExperimentType.DIPOLE_DIPOLE_RELAXATION: "dipole_dipole_relaxation",
    RelaxationExperimentType.HETERONUCLEAR_NOES: "heteronuclear_NOEs",
    RelaxationExperimentType.HETERONUCLEAR_R1_RELAXATION: "heteronuclear_R1_relaxation",
    RelaxationExperimentType.HETERONUCLEAR_R1RHO_RELAXATION: "heteronuclear_R1rho_relaxation",
    RelaxationExperimentType.HETERONUCLEAR_R2_RELAXATION: "heteronuclear_R2_relaxation",
    RelaxationExperimentType.H_EXCHANGE_PROTECTION_FACTORS: "H_exchange_protection_factors",
    RelaxationExperimentType.H_EXCHANGE_RATES: "H_exchange_rates",
    RelaxationExperimentType.HOMONUCLEAR_NOES: "homonuclear_NOEs",
    RelaxationExperimentType.CPMG: "CPMG",
    RelaxationExperimentType.CEST: "CEST",
    RelaxationExperimentType.OTHER: "other",
}

NAME_TO_EXPERIMENT_TYPE = {
    "T1": RelaxationExperimentType.HETERONUCLEAR_R1_RELAXATION,
    "T2": RelaxationExperimentType.HETERONUCLEAR_R2_RELAXATION,
    "T1rho": RelaxationExperimentType.HETERONUCLEAR_R1RHO_RELAXATION,
    "T1p": RelaxationExperimentType.HETERONUCLEAR_R1RHO_RELAXATION,
    "R1": RelaxationExperimentType.HETERONUCLEAR_R1_RELAXATION,
    "R2": RelaxationExperimentType.HETERONUCLEAR_R2_RELAXATION,
    "NOE": RelaxationExperimentType.HETERONUCLEAR_NOES,
    "CPMG": RelaxationExperimentType.CPMG,
    "REX": RelaxationExperimentType.CPMG,
    "CEST": RelaxationExperimentType.CEST,
    "DEST": RelaxationExperimentType.CEST,
}


class SaturationState(IntEnum):
    SATURATED = 1
    UNSATURATED = 0


STR_TO_SATURATION_STATE = {
    "saturated": SaturationState.SATURATED,
    "unsaturated": SaturationState.UNSATURATED,
    "on": SaturationState.SATURATED,
    "off": SaturationState.UNSATURATED,
    "true": SaturationState.SATURATED,
    "false": SaturationState.UNSATURATED,
    "yes": SaturationState.SATURATED,
    "no": SaturationState.UNSATURATED,
    "1": SaturationState.SATURATED,
    "0": SaturationState.UNSATURATED,
}


@series_app.command()
def build(
    input: Path = typer.Option(
        None,
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="read NEF data from a file instead of stdin",
    ),
    timings: List[str] = typer.Option(
        None,
        help="the list of relaxation times or values",
    ),
    input_unit: str = typer.Option(
        None,
        "--unit",
        help="the unit of the relaxation times",
    ),
    name: str = typer.Option(
        None,
        help="the name of the series, if not provided it will be guessed from the frames",
    ),
    experiment_type: str = typer.Option(None, help="the type of the experiment"),
    display_parsed_values: bool = typer.Option(False, help="display the parsed values"),
    frames_selectors: List[str] = typer.Argument(
        None,
        help=FRAMES_AND_TIMES_HELP,
    ),
):
    """- build a NEF data series from a set of spectra [alpha]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frame_selectors = parse_comma_separated_options(frames_selectors)

    _exit_if_no_frame_selectors(frame_selectors)

    frames = _select_relaxation_frames(entry, frames_selectors)

    frame_timings_and_units = _get_timings_and_units_for_frames(
        frames, frame_selectors, timings, input_unit, display_parsed_values
    )

    frames_and_timings, unit = (
        _ensure_units_consistent_and_get_unit_and_timings_or_exit(
            frame_timings_and_units
        )
    )

    # TODO arenn't these the same? add a name and expt attribute to the template and only use this notherwise
    if not name:
        name = _guess_series_name(entry, frames_and_timings)

    if not experiment_type:
        experiment_type = _guess_experiment_type(name)

    entry = pipe(entry, frames_and_timings, unit, name, experiment_type)

    print(entry)


def pipe(
    entry: Entry,
    frame_timings: Dict[Tuple[str, int], Union[int, float, bool]],
    unit: str,
    name: str,
    experiment_type: str,
) -> Entry:

    series_frame = create_nef_save_frame(f"{NAMESPACE}_series_list", name)

    series_variable_type = EXPERIMENT_TYPE_TO_SERIES_VARIABLE_TYPE[
        RelaxationExperimentType[experiment_type]
    ]
    series_variable_unit = SERIES_VARIABLE_TYPE_TO_SERIES_VARIABLE_UNIT[
        series_variable_type
    ]

    series_variable_unit = (
        unit if unit != series_variable_unit else series_variable_unit
    )

    data_value_type = EXPERIMENT_TYPE_TO_DATA_VARIABLE_TYPE[
        RelaxationExperimentType[experiment_type]
    ]
    data_value_unit = DATA_VARIABLE_TYPE_TO_DATA_VARIABLE_UNIT[data_value_type]

    experiment_type = EXPERIMENT_TO_IDENTIFIER[
        RelaxationExperimentType[experiment_type]
    ]
    tags = [
        ("experiment_type", experiment_type),
        ("series_variable_type", series_variable_type),
        ("series_variable_unit", series_variable_unit),
        ("data_variable_type", series_variable_type),
        ("data_variable_unit", series_variable_unit),
        ("data_value_type", data_value_type),
        ("data_value_unit", data_value_unit),
        ("comment", UNUSED),
    ]
    series_frame.add_tags(tags)

    # TODO: pynmstar doesn't catch prepended spaces here it just gives and obscure error report!
    series_experiment_loop = Loop.from_scratch(f"{NAMESPACE}_series_experiment")
    series_frame.add_loop(series_experiment_loop)
    series_experiment_loop.add_tag(
        [
            "version",
            "nmr_spectrum_id",
            "reference_experiment",
            "combination_id",
            "pseudo_dimension",
            "pseudo_dimension_point",
            "series_variable",
            "series_variable_error",
        ]
    )

    loop_data = []
    for frame_key, value in frame_timings.items():
        frame_name, _ = frame_key
        loop_data.append(
            {
                "version": NEF_RELAXATION_VERSION,
                "nmr_spectrum_id": frame_name,
                "reference_experiment": "false",
                "combination_id": UNUSED,
                "pseudo_dimension": UNUSED,
                "pseudo_dimension_point": UNUSED,
                "series_variable": value,
                "series_variable_error": UNUSED,
            }
        )

    series_experiment_loop.add_data(loop_data)

    add_frames_to_entry(
        entry,
        [
            series_frame,
        ],
    )

    return entry


def _guess_experiment_type(name):
    upper_name = name.upper()
    for experiment_name in NAME_TO_EXPERIMENT_TYPE:
        if experiment_name in upper_name:
            result = NAME_TO_EXPERIMENT_TYPE[upper_name]
            break
        else:
            result = "unknown"
    return result


def _guess_series_name(entry, frames_and_timings):
    result = None
    for relaxation_type in NAME_TO_EXPERIMENT_TYPE:
        do_break = False
        for name, _ in frames_and_timings.keys():
            name = name.upper()
            if relaxation_type in name.upper():
                start_index = name.index(relaxation_type)
                end_index = start_index + len(relaxation_type)
                found_relaxation_type = name[start_index:end_index]

                result = found_relaxation_type
                do_break = True
                break
        if do_break:
            break

    if not result:
        result = "unknown_type"

    bad_frame_name = False
    for frame in entry:
        if frame.name == result:
            bad_frame_name = True
            break

    if bad_frame_name:
        base_result = result
        for i in range(1, 100):
            result = f"series`{i}`"
            bad_frame_name = False
            for frame in entry:
                if frame.name == result:
                    bad_frame_name = True
                    break

    if bad_frame_name:
        _exit_if_too_many_clashing_frame_names(bad_frame_name, base_result)

    return result


def _exit_if_too_many_clashing_frame_names(bad_frame_name, base_result):
    if bad_frame_name:
        msg = f"""
            after searching the series of names {base_result}`1` to {base_result}`100` i could not find a name
            that was not already in the entry, choose a name on the command line, you have way too much data!
            more serious report this as a bug...
        """
        exit_error(msg)


def _get_timings_and_units_for_frames(
    frames, frame_selectors, timings, input_unit, display_parsed_values
):

    if timings:
        timings_and_units = _parse_timings(timings)
        units = [timing_and_unit[1] for timing_and_unit in timings_and_units]

        _exit_if_input_unit_defined_and_any_unit_parsed(
            input_unit, units, timings_and_units
        )

        if input_unit:
            timings_and_units = [
                (timing, input_unit) for timing, _ in timings_and_units
            ]

        _exit_error_it_number_of_timings_doesnt_match_number_of_frames(
            frames, timings_and_units
        )

        frame_timings_and_units = {
            (frame.name, id(frame)): timing_and_unit
            for frame, timing_and_unit in zip(frames, timings_and_units)
        }
    else:
        _exit_if_frame_selector_has_no_timing_selector(frame_selectors)
        frame_timings_and_units = _parse_timings_from_frames_or_exit(
            frames, frame_selectors[0], display_parsed_values
        )

    return frame_timings_and_units


def _exit_if_input_unit_defined_and_any_unit_parsed(
    input_unit, units, timings_and_units
):
    if input_unit and any(unit != "" for unit in units):
        units_and_timings_strings = [
            f"{unit}{timing}" for unit, timing in timings_and_units if unit
        ]
        msg = f"""
                you cannot provide a unit on the command line [--unit] and units in the timings [--timings]
                at the same time command line unit was {input_unit} and the units and timings were
                {strings_to_tabulated_terminal_sensitive(units_and_timings_strings)}

                """
        exit_error(msg)


def _exit_error_it_number_of_timings_doesnt_match_number_of_frames(
    frames, timings_and_units
):
    if len(timings_and_units) != len(frames):
        msg = f"the number of timings {len(timings_and_units)} does not match the number of frames {len(frames)}"
        exit_error(msg)


def _exit_if_frame_selector_has_no_timing_selector(frame_selectors):
    if len(frame_selectors) != 1 or "{var}" not in frame_selectors[0]:
        NEWLINE = "\n"
        msg = f"""
                    no timings provided to select timings you must have a single frame selector with
                    a {{var}} placeholder i got {len(frame_selectors)} frame selectors and they were:
                    {NEWLINE.join(frame_selectors)}
                """
        exit_error(msg)


def _select_relaxation_frames(entry: Entry, frame_selectors: List[str]) -> List[str]:
    spectrum_frames = select_frames(entry, "nef_nmr_spectrum", SelectionType.CATEGORY)
    spectrum_frame_ids = OrderedSet(
        [
            (spectrum_frame.name, id(spectrum_frame))
            for spectrum_frame in spectrum_frames
        ]
    )

    frame_selectors = [selector.replace("{var}", "*") for selector in frame_selectors]
    frame_selectors = [selector.replace("{}", "*") for selector in frame_selectors]

    relaxation_frames = []
    for frame_selector in frame_selectors:
        relaxation_frames.extend(
            select_frames(entry, frame_selector, SelectionType.NAME)
        )

    relaxation_frame_ids = OrderedSet(
        [
            (relaxation_frame.name, id(relaxation_frame))
            for relaxation_frame in relaxation_frames
        ]
    )

    # TODO: just do an intersection dummy!
    if not relaxation_frame_ids.issubset(spectrum_frame_ids):
        non_spectrum_frames = relaxation_frame_ids.difference(spectrum_frame_ids)
        non_spectrum_frame_names = "\n".join(
            [non_spectrum_frame[0] for non_spectrum_frame in non_spectrum_frames]
        )
        # TODO: just filter out non spectra frames...
        _exit_if_some_frames_are_not_spectra(non_spectrum_frame_names)

    return relaxation_frames


def _exit_if_some_frames_are_not_spectra(non_spectrum_frame_names):
    msg = f"""
            some of the selected frames are not spectrum frames:
            {non_spectrum_frame_names}
            """
    exit_error(msg)


def _parse_timings_from_frames_or_exit(
    save_frames: List[Saveframe], frame_selector: str, display_parsed_values: bool
) -> Dict[Tuple[str, int], List[Tuple[Union[int, float, bool], str]]]:
    if "{var}" not in frame_selector:
        msg = f"no timing selector placeholder {{var}} provided in frame selector {frame_selector}"
        exit_error(msg)

    frame_selector = frame_selector.replace("{var}", "{var}")
    frame_selector = frame_selector.replace("*", "{:opt}")

    parser = parse_compile(frame_selector)

    parsed_values = []

    frame_value_and_units = {}
    for frame in save_frames:
        frame_key = frame.name, id(frame)
        result = parser.search(frame.name)

        value, unit = None, None
        if result and "var" in result:
            raw_value = result["var"]
            raw_value = raw_value.replace("_", ".")
            raw_value = raw_value.replace("-", ".")

            value, unit = _parse_value_and_unit(raw_value)

        if display_parsed_values:
            parsed_values.append([frame.name, raw_value, value, unit])

        if value is None:
            _exit_if_no_variable_found(frame, frame_selector)

        if not (is_float(value) or value.lower() in "on off true false yes no"):
            msg = f"the variable {value} in frame {frame.name} is not a number or a boolean"
            exit_error(msg)

        frame_value_and_units[frame_key] = value, unit

    if display_parsed_values:
        print(
            tabulate(parsed_values, headers=["spectrum", "raw value", "value", "unit"]),
            file=sys.stderr,
        )
        sys.exit(0)

    return frame_value_and_units


def _exit_if_no_variable_found(frame, frame_selector):
    msg = f"no variable found in frame {frame.name} with the selector {frame_selector}"
    exit_error(msg)


def _parse_timings(timings: List[str]) -> List[Tuple[Union[int, float, bool], str]]:
    timings = parse_comma_separated_options(timings)
    parsed_timings = []
    for timing in timings:
        value, unit = _parse_value_and_unit(timing)
        parsed_timings.append((value, unit))
    return parsed_timings


def _parse_value_and_unit(value: str) -> Tuple[Union[bool, int, float, None]]:

    unit = value.lstrip(string.digits + ".eE")
    len_digits = len(value) - len(unit)
    value = value[:len_digits]

    lower_unit = unit.lower()
    if value and unit:
        pass
    elif not value and lower_unit in STR_TO_SATURATION_STATE:
        unit = "bool"
        value = STR_TO_SATURATION_STATE[lower_unit]
    elif not unit:
        if is_int(value):
            value = int(value)
        elif is_float(value):
            value = float(value)
    else:
        unit = None
        value = None

    return value, unit


def _exit_if_no_frame_selectors(frame_selectors):
    if len(frame_selectors) == 0:
        msg = "you must select some frames!"
        exit_error(msg)


def _ensure_units_consistent_and_get_unit_and_timings_or_exit(frames_timings_and_units):

    _exit_units_not_consistent(frames_timings_and_units)

    _exit_if_numbers_and_bools_are_mixed(frames_timings_and_units)

    float_counter = Counter()
    int_counter = Counter()
    for frame, (value, unit) in frames_timings_and_units.items():
        if isinstance(value, int):
            int_counter[value] += 1
        elif isinstance(value, float):
            float_counter[value] += 1

    if int_counter and float_counter:
        for frame_key, (value, unit) in frames_timings_and_units.items():
            value = float(value)

            frames_timings_and_units[frame_key] = value, unit

    unit = list(frames_timings_and_units.values())[0][1]
    frames_and_timings = {
        frame_key: value for frame_key, (value, _) in frames_timings_and_units.items()
    }

    return frames_and_timings, unit


def _exit_if_numbers_and_bools_are_mixed(frame_timings_and_units):

    counter_numbers = Counter()
    couter_booleans = Counter()

    for frame, (value, unit) in frame_timings_and_units.items():
        if isinstance(value, bool):
            couter_booleans[value] += 1
        elif is_float(value):
            counter_numbers[value] += 1

    if counter_numbers and couter_booleans:
        numbers_strings = ", ".join(counter_numbers.keys())
        booleans_strings = ", ".join(couter_booleans.keys())
        msg = f"""
                you cannot have both numbers and booleans in the values
                the booleans were
                {booleans_strings}
                the numbers were
                {numbers_strings}
            """
        exit_error(msg)


def _exit_units_not_consistent(frame_timings_and_units):

    unit_counter = Counter()
    for frame, (value, unit) in frame_timings_and_units.items():
        unit_counter[unit] += 1

    if len(unit_counter) > 1:
        unit_strings = ", ".join(unit_counter.keys())
        msg = f"""
            the units of the timings are not consistent, the units found were
            {unit_strings}
            """
        exit_error(msg)


def _exit_if_units_are_not_compatible(frame_timings_and_units):
    units = {unit for timing, unit in frame_timings_and_units.values()}
    if len(units) > 1:
        units_and_timings_strings = [
            f"{unit}{timing}" for timing, unit in frame_timings_and_units.values()
        ]
        msg = f"""
                the units of the timings are not compatible they are {units}
                the timings and units were
                {strings_to_tabulated_terminal_sensitive(units_and_timings_strings)}
                """
        exit_error(msg)
