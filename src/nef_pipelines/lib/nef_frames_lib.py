NEF = "nef"
SF = "sf"

SHIFT_LIST_FRAME_CATEGORY = f"{NEF}_chemical_shift_list"

SPECTRUM_FRAME_CATEGORY = f"{NEF}_nmr_spectrum"
SPECTRUM_DIMENSION_LOOP_CATEGORY = f"{NEF}_spectrum_dimension"
SPECTRUM_DIMENSION_TRANSFER_LOOP_CATEGORY = (
    f"{SPECTRUM_DIMENSION_LOOP_CATEGORY}_transfer"
)
SPECTRUM_PEAK_LOOP_CATEGORY = f"{NEF}_peak"

SF_CATEGORY = f"{SF}_category"
SF_FRAMECODE = f"{SF}_framecode"
NUM_DIMENSIONS = "num_dimensions"
CHEMICAL_SHIFT_LIST = "chemical_shift_list"
EXPERIMENT_TYPE = "experiment_type"
EXPERIMENT_CLASSIFICATION = "experiment_classification"
CCPN_COMMENT = "ccpn_comment"
CCPN_MERIT = "ccpn_figure_of_merit"

SPECTRUM_FRAME_TAGS = (
    SF_CATEGORY,
    SF_FRAMECODE,
    NUM_DIMENSIONS,
    CHEMICAL_SHIFT_LIST,
    EXPERIMENT_CLASSIFICATION,
    EXPERIMENT_TYPE,
)

DIMENSION_ID = "dimension_id"
AXIS_UNIT = "axis_unit"
AXIS_CODE = "axis_code"

SPECTROMETER_FREQUENCY = "spectrometer_frequency"
SPECTRAL_WIDTH = "spectral_width"
VALUE_FIRST_POINT = "value_first_point"
FOLDING = "folding"
ABSOLUTE_PEAK_POSITIONS = "absolute_peak_positions"
IS_ACQUISITION = "is_acquisition"


DIMENSION_LOOP_TAGS = (
    # mandatory parameters
    DIMENSION_ID,
    AXIS_UNIT,
    AXIS_CODE,
    # # optional parameters
    SPECTROMETER_FREQUENCY,
    SPECTRAL_WIDTH,
    VALUE_FIRST_POINT,
    FOLDING,
    ABSOLUTE_PEAK_POSITIONS,
    IS_ACQUISITION,
)

DIMENSION_INDEX = "dimension_index"
DIMENSION__DIMENSION_INDEX = "dimension_{dimension_index}"
TRANSFER_TYPE = "transfer_type"
IS_INDIRECT = "is_indirect"

ONE_BOND = "onebond"
NEF_PPM = "ppm"

TRANSFER_LOOP_TAGS = [
    # mandatory parameters
    DIMENSION__DIMENSION_INDEX,
    TRANSFER_TYPE,
    # optional parameter
    IS_INDIRECT,
]

CHAIN_CODE = "chain_code"
SEQUENCE_CODE = "sequence_code"
RESIDUE_NAME = "residue_name"
ATOM_NAME = "atom_name"
POSITION = "position"
POSITION_UNCERTAINTY = "position_uncertainty"

CHAIN_CODE__DIMENSION_INDEX = f"{CHAIN_CODE}_{{dimension_index}}"
SEQUENCE_CODE__DIMENSION_INDEX = f"{SEQUENCE_CODE}_{{dimension_index}}"
RESIDUE_NAME__DIMENSION_INDEX = f"{RESIDUE_NAME}_{{dimension_index}}"
ATOM_NAME__DIMENSION_INDEX = f"{ATOM_NAME}_{{dimension_index}}"
POSITION__DIMENSION_INDEX = f"{POSITION}_{{dimension_index}}"
POSITION_UNCERTAINTY__DIMENSION_INDEX = f"{POSITION_UNCERTAINTY}_{{dimension_index}}"


PEAK_ID = "peak_id"
INDEX = "index"

HEIGHT = "height"
HEIGHT_UNCERTAINTY = "height_uncertainty"
VOLUME = "volume"
VOLUME_UNCERTAINTY = "volume_uncertainty"

PEAK_LOOP_TAGS = [
    INDEX,
    PEAK_ID,
    [
        CHAIN_CODE__DIMENSION_INDEX,
        SEQUENCE_CODE__DIMENSION_INDEX,
        RESIDUE_NAME__DIMENSION_INDEX,
        ATOM_NAME__DIMENSION_INDEX,
    ],
    [
        POSITION__DIMENSION_INDEX,
        POSITION_UNCERTAINTY__DIMENSION_INDEX,
    ],
    HEIGHT,
    HEIGHT_UNCERTAINTY,
    VOLUME,
    VOLUME_UNCERTAINTY,
]
