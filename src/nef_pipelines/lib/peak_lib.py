import copy
from textwrap import dedent
from typing import Any, Dict, List, Tuple, Union

from frozendict import frozendict
from ordered_set import OrderedSet
from pynmrstar import Loop, Saveframe

from nef_pipelines.lib.isotope_lib import GAMMA_RATIOS, Isotope
from nef_pipelines.lib.nef_frames_lib import (
    ABSOLUTE_PEAK_POSITIONS,
    ATOM_NAME,
    ATOM_NAME__DIMENSION_INDEX,
    AXIS_CODE,
    AXIS_UNIT,
    CCPN_COMMENT,
    CCPN_MERIT,
    CHAIN_CODE,
    CHAIN_CODE__DIMENSION_INDEX,
    CHEMICAL_SHIFT_LIST,
    DIMENSION__DIMENSION_INDEX,
    DIMENSION_ID,
    DIMENSION_INDEX,
    DIMENSION_LOOP_TAGS,
    EXPERIMENT_CLASSIFICATION,
    EXPERIMENT_TYPE,
    FOLDING,
    HEIGHT,
    HEIGHT_UNCERTAINTY,
    INDEX,
    IS_ACQUISITION,
    IS_INDIRECT,
    NEF_PPM,
    NUM_DIMENSIONS,
    ONE_BOND,
    PEAK_ID,
    PEAK_LOOP_TAGS,
    POSITION__DIMENSION_INDEX,
    POSITION_UNCERTAINTY__DIMENSION_INDEX,
    RESIDUE_NAME,
    RESIDUE_NAME__DIMENSION_INDEX,
    SEQUENCE_CODE,
    SEQUENCE_CODE__DIMENSION_INDEX,
    SF_CATEGORY,
    SF_FRAMECODE,
    SPECTRAL_WIDTH,
    SPECTROMETER_FREQUENCY,
    SPECTRUM_DIMENSION_LOOP_CATEGORY,
    SPECTRUM_DIMENSION_TRANSFER_LOOP_CATEGORY,
    SPECTRUM_FRAME_CATEGORY,
    SPECTRUM_PEAK_LOOP_CATEGORY,
    TRANSFER_LOOP_TAGS,
    TRANSFER_TYPE,
    VALUE_FIRST_POINT,
    VOLUME,
    VOLUME_UNCERTAINTY,
)
from nef_pipelines.lib.nef_lib import (
    NEF_FALSE,
    NEF_NONE,
    NEF_TRUE,
    UNUSED,
    loop_row_dict_iter,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    DimensionInfo,
    LineInfo,
    NewPeak,
    Residue,
    ShiftData,
)
from nef_pipelines.lib.util import (
    _row_to_table,
    exit_error,
    is_float,
    is_int,
    remove_duplicates_stable,
    unused_to_empty_string,
    unused_to_none,
)


class BadPositionException(Exception):
    """
    The position of a peak in the frame couldn't be converted to a float
    """

    ...


# noinspection PyUnusedLocal
def proton_frequency_to_axis_frequency(
    spectrometer_frequency: float, isotope: Isotope
) -> float:
    """
    Give a proton frequency in MHz and an isotope return the equivalent spectrometer
    frequency for the isotopes
    :param spectrometer_frequency: spectrometer frequency
    :param isotope: an NMR isotope
    :return: the spectrometer frequency for the isotope
    """
    result = float(spectrometer_frequency) * GAMMA_RATIOS[isotope]
    return result


def peaks_to_sweep_width_and_reference_shift(
    peaks: List[NewPeak], dim: int, multiplier: float = 1.1
) -> Tuple[float, float]:
    """
    Given a set of peaks synthesise a sweep width and reference ppm from the min and max shifts of the peaks
    plus a margin
    :param peaks: A list of peaks
    :param dim: the dimesnion of the peaks to use
    :param multiplier: how much to increase the range of the observed chemical shifts by to get a sweep width
    :return: tuple sweep width [ppm], reference shift[ppm]
    """
    shifts = []
    for peak in peaks:
        shifts.append(peak.shifts[dim].value)

    min_shift = min(shifts)
    max_shift = max(shifts)

    width = max_shift - min_shift
    width_d2 = width / 2.0
    middle = min_shift + width_d2

    width_d2_mult = width_d2 * multiplier
    width_mult = width_d2_mult * 2
    min_shift_mult = middle + width_d2_mult

    return width_mult, min_shift_mult


def format_7_3_f(value: Union[int, float]) -> str:
    """
    format a number with 7.3f formatting as a string
    :param value: an int of a float
    :return: a formatted string
    """
    return f"{value:7.3f}".strip()


def _expand_templates(
    template: List[Union[str, List[str]]], values_list: List[Dict[str, Any]]
) -> List[str]:
    """
    expand a list of templates into strings using a list of sets (dicts) of values
    :param templates: the tags to format
    :param values_list: a list of dictionaries of values
    :return: a list of formatted strings
    """
    result = OrderedSet()
    for tag_or_tag_list in template:
        if isinstance(tag_or_tag_list, str):
            for values in values_list:
                result.add(tag_or_tag_list.format(**values))
        elif isinstance(tag_or_tag_list, list):
            for values in values_list:
                for tag in tag_or_tag_list:
                    result.add(tag.format(**values))

    return list(result)


DEFAULT_EXTRA_TAGS = {
    CHEMICAL_SHIFT_LIST: UNUSED,
    EXPERIMENT_CLASSIFICATION: UNUSED,
    EXPERIMENT_TYPE: UNUSED,
}


def peaks_to_frame(
    peaks: List[NewPeak],
    dimensions: List[DimensionInfo],
    spectrometer_frequency: float,
    frame_code: str = "peaks",
    extra_tags: Dict[str, str] = frozendict(DEFAULT_EXTRA_TAGS),
    source: str = "unknown",
) -> Saveframe:

    # TODO needs a list of transfers
    """
    convert a list of peaks to a nef spectrum frame
    :param peaks: the peaks
    :param dimensions: the dimensions of the peak list
    :param spectrometer_frequency: the 1H spectrometer frequency of the peak list
    :param frame_code: the name for the frame
    :param extra_tags: extra tags to be used in the frame, non nef tags will be appended
    :param source: the source of the data for error reporting
    :return: a NEF Spectrum save frame
    """

    mutable_extra_tags = {**DEFAULT_EXTRA_TAGS}
    mutable_extra_tags.update(extra_tags)
    extra_tags = mutable_extra_tags

    frame_code = f"{SPECTRUM_FRAME_CATEGORY}_{frame_code}"

    frame = Saveframe.from_scratch(frame_code, SPECTRUM_FRAME_CATEGORY)

    frame.add_tag(SF_CATEGORY, SPECTRUM_FRAME_CATEGORY)
    frame.add_tag(SF_FRAMECODE, frame_code)

    have_comments = False
    for peak in peaks:
        if peak.comment != "":
            have_comments = True
            break

    have_merits = False
    for peak in peaks:
        if peak.figure_of_merit != UNUSED and peak.figure_of_merit is not None:
            have_merits = True
            break

    peak_dimensions = []
    for peak in peaks:
        peak_dimensions.append(len(peak.shifts))

    peak_dimensions.sort()
    peak_dimensions = remove_duplicates_stable(peak_dimensions)

    if len(peak_dimensions) > 1:
        msg = f"""\
            unexpected! in the file {source} there are peaks with different numbers of different dimensions
            the dimensions were: {' '.join([str(dimension) for dimension in peak_dimensions])}
        """
        exit_error(msg)

    frame.add_tag(NUM_DIMENSIONS, peak_dimensions[0])

    shift_list_name = (
        extra_tags[CHEMICAL_SHIFT_LIST] if CHEMICAL_SHIFT_LIST in extra_tags else UNUSED
    )
    frame.add_tag(
        CHEMICAL_SHIFT_LIST, shift_list_name
    )  # technically not correct to use unused by default here but this is a nef file building
    # tool kit so an empty shift list maybe what we need
    # we may need to add a flag to build the shift list on the fly at a later date...

    experiment_classification = (
        extra_tags[EXPERIMENT_CLASSIFICATION]
        if EXPERIMENT_CLASSIFICATION in extra_tags
        else UNUSED
    )
    frame.add_tag(
        EXPERIMENT_CLASSIFICATION, experiment_classification
    )  # add via an experiment info structure currently uses extra tags?

    experiment_type = (
        extra_tags[EXPERIMENT_TYPE] if EXPERIMENT_TYPE in extra_tags else UNUSED
    )
    frame.add_tag(EXPERIMENT_TYPE, experiment_type)

    dimension_loop = Loop.from_scratch(SPECTRUM_DIMENSION_LOOP_CATEGORY)
    frame.add_loop(dimension_loop)

    dimension_loop.add_tag(DIMENSION_LOOP_TAGS)

    dimensions = copy.deepcopy(dimensions)
    for i, dimension in enumerate(dimensions):
        dimension[DIMENSION_ID] = i + 1

        dimension[AXIS_UNIT] = NEF_PPM

        axis_code = dimension[AXIS_CODE]

        # TODO: need to check we have an axis code here
        # TODO: need to reasonable translations here H-> 1H H1 -> 1H [especially as 1H isn't possible because of
        #  technical limitations python names can't start with a number]
        dimension_spectrometer_frequency = proton_frequency_to_axis_frequency(
            spectrometer_frequency, axis_code
        )
        dimension[SPECTROMETER_FREQUENCY] = format_7_3_f(
            dimension_spectrometer_frequency
        )

        sweep_width, max_shift = peaks_to_sweep_width_and_reference_shift(peaks, i)

        dimension[SPECTRAL_WIDTH] = format_7_3_f(sweep_width)
        dimension[VALUE_FIRST_POINT] = format_7_3_f(max_shift)
        dimension[FOLDING] = NEF_NONE

        dimension[ABSOLUTE_PEAK_POSITIONS] = NEF_TRUE

        acquisition = NEF_TRUE if i == len(dimensions) - 1 else NEF_FALSE

        dimension[IS_ACQUISITION] = acquisition

        dimension_loop.add_data([dimension])

    transfer_loop = Loop.from_scratch(SPECTRUM_DIMENSION_TRANSFER_LOOP_CATEGORY)
    frame.add_loop(transfer_loop)

    transfer_loop_indices = [{"dimension_index": 1}, {"dimension_index": 2}]
    transfer_loop_tags = _expand_templates(TRANSFER_LOOP_TAGS, transfer_loop_indices)

    transfer_loop.add_tag(transfer_loop_tags)
    for dim_index in range(1, len(dimensions)):
        dim_1 = dim_index
        dim_2 = dim_index + 1

        transfer_data = {
            DIMENSION__DIMENSION_INDEX.format(**{DIMENSION_INDEX: 1}): dim_1,
            DIMENSION__DIMENSION_INDEX.format(**{DIMENSION_INDEX: 2}): dim_2,
            TRANSFER_TYPE: ONE_BOND,  # TODO: this is not correct
            IS_INDIRECT: NEF_FALSE,
        }

        transfer_loop.add_data(
            [
                transfer_data,
            ]
        )

    peak_loop = Loop.from_scratch(SPECTRUM_PEAK_LOOP_CATEGORY)
    frame.add_loop(peak_loop)

    dimension_indices = [
        {"dimension_index": dimension_index}
        for dimension_index in range(1, len(dimensions) + 1)
    ]

    peak_loop_tags = _expand_templates(PEAK_LOOP_TAGS, dimension_indices)

    if have_comments:
        peak_loop_tags.append(CCPN_COMMENT)

    if have_merits:
        peak_loop_tags.append(CCPN_MERIT)

    peak_loop.add_tag(peak_loop_tags)

    for index, peak in enumerate(peaks, start=1):
        peak_data = {
            INDEX: index,
            PEAK_ID: index if peak.id is None else peak.id,
            HEIGHT: peak.height,
            HEIGHT_UNCERTAINTY: peak.height_uncertainty,
            VOLUME: peak.volume,
            VOLUME_UNCERTAINTY: peak.volume_uncertainty,
        }

        for dim_index, shift in enumerate(peak.shifts, start=1):
            peak_data[CHAIN_CODE__DIMENSION_INDEX.format(dimension_index=dim_index)] = (
                shift.atom.residue.chain_code
            )
            peak_data[
                SEQUENCE_CODE__DIMENSION_INDEX.format(dimension_index=dim_index)
            ] = shift.atom.residue.sequence_code
            peak_data[
                RESIDUE_NAME__DIMENSION_INDEX.format(dimension_index=dim_index)
            ] = shift.atom.residue.residue_name
            peak_data[ATOM_NAME__DIMENSION_INDEX.format(dimension_index=dim_index)] = (
                shift.atom.atom_name
            )

            peak_data[POSITION__DIMENSION_INDEX.format(dimension_index=dim_index)] = (
                shift.value
            )
            peak_data[
                POSITION_UNCERTAINTY__DIMENSION_INDEX.format(dimension_index=dim_index)
            ] = shift.value_uncertainty

            if have_comments:
                peak_data[CCPN_COMMENT] = (
                    peak.comment if peak.comment is not None else UNUSED
                )
            if have_merits:
                peak_data[CCPN_MERIT] = (
                    peak.figure_of_merit if peak.figure_of_merit is not None else UNUSED
                )
        peak_loop.add_data(
            [
                peak_data,
            ]
        )

    return frame


# TODO: test empt frames and loops
def frame_to_peaks(frame: Saveframe, source="unknown") -> List[NewPeak]:
    """
    convert a NEF spectrum frame to a list of peaks

    :param frame: the spectrum save frame
    :param source: the source of the save frame (for error reporting)
    :return: a list of Peak structures
    """
    loop = frame.get_loop("nef_peak")

    num_dimensions = _get_peak_loop_dimensions(loop)

    peaks = []

    for line_number, row in enumerate(loop_row_dict_iter(loop), start=1):
        shift_data = []
        for dim_index in range(1, num_dimensions + 1):

            values = {}
            fields = [CHAIN_CODE, SEQUENCE_CODE, RESIDUE_NAME, ATOM_NAME]
            raw_tags = [
                CHAIN_CODE__DIMENSION_INDEX,
                SEQUENCE_CODE__DIMENSION_INDEX,
                RESIDUE_NAME__DIMENSION_INDEX,
                ATOM_NAME__DIMENSION_INDEX,
            ]
            dimension_tags = [
                raw_tag.format(dimension_index=dim_index) for raw_tag in raw_tags
            ]
            for name, tag in zip(fields, dimension_tags):
                value = unused_to_empty_string(row[tag])
                values[name] = value

            residue_values = {
                key: value
                for key, value in values.items()
                if not key.startswith(ATOM_NAME)
            }

            residue = Residue(**residue_values)

            if values[ATOM_NAME] == "":
                values[ATOM_NAME] = "?"

            atom_label = AtomLabel(residue, values[ATOM_NAME])

            position = row[POSITION__DIMENSION_INDEX.format(dimension_index=dim_index)]

            line_info = LineInfo(
                f"{source}[{frame.name} ]", line_number, _row_to_table(row)
            )
            _raise_if_position_isnt_float(position, line_info)

            position_uncertainty = unused_to_none(
                row[
                    POSITION_UNCERTAINTY__DIMENSION_INDEX.format(
                        dimension_index=dim_index
                    )
                ]
            )

            shift_datum = ShiftData(atom_label, position, position_uncertainty)

            shift_data.append(shift_datum)

        height_volume_data = {}
        for name in [VOLUME, VOLUME_UNCERTAINTY, HEIGHT, HEIGHT_UNCERTAINTY]:

            value = unused_to_none(row[name])
            height_volume_data[name] = unused_to_none(value)

        peak = NewPeak(tuple(shift_data), **height_volume_data, id=row["peak_id"])

        peaks.append(peak)

    return peaks


def _raise_if_position_isnt_float(value: str, line_info: LineInfo):
    """
    raise an exception if a value which can't be converted to a float
    :param value: the value to check for conversion to a float
    :param line_info: where the error occured
    """
    if not is_float(value):
        msg = f"""
                    in the spectrum save frame  in {line_info.file_name} at row {line_info.line_number}
                    the position wasn't a float: {value}

                    processed values from row are:

                """

        msg = dedent(msg)

        msg += line_info.line

        raise BadPositionException(msg)


def _get_peak_loop_dimensions(loop: Loop) -> int:
    """
    from the peak loop of a spectrum work out the number of dimensions by counting the number of position_xxx tags

    Note: we do it this way rather than depending on the _nef_spectrum_dimension's as this is the more fundamental data
    :param loop: the peak loop
    :return: the number of dimensions detected
    """

    num_dimensions = 0
    for tag in loop.tags:
        tag_fields = tag.split("_")
        if (
            len(tag_fields) == 2
            and tag_fields[0] == "position"
            and is_int(tag_fields[1])
        ):
            num_dimensions += 1
    return num_dimensions
