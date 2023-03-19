SPECTRUM_FRAME_CATEGORY = "nef_nmr_spectrum"
SPECTRUM_DIMENSION_LOOP_CATEGORY = "nef_spectrum_dimension"
SPECTRUM_DIMENSION_TRANSFER_LOOP_CATEGORY = (
    f"{SPECTRUM_DIMENSION_LOOP_CATEGORY}_transfer"
)
SPECTRUM_PEAK_LOOP_CATEGORY = "nef_peak"

SF_CATEGORY = "sf_category"
SF_FRAMECODE = "sf_framecode"
NUM_DIMENSIONS = "num_dimensions"
CHEMICAL_SHIFT_LIST = "chemical_shift_list"
EXPERIMENT_TYPE = "experiment_type"
EXPERIMENT_CLASSIFICATION = "experiment_classification"

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

CHAIN_CODE__DIM_INDEX = f"{CHAIN_CODE}_{{dim_index}}"
SEQUENCE_CODE__DIM_INDEX = f"{SEQUENCE_CODE}_{{dim_index}}"
RESIDUE_NAME__DIM_INDEX = f"{RESIDUE_NAME}_{{dim_index}}"
ATOM_NAME__DIM_INDEX = f"{ATOM_NAME}_{{dim_index}}"
POSITION__DIM_INDEX = f"{POSITION}_{{dim_index}}"
POSITION_UNCERTAINTY__DIM_INDEX = f"{POSITION_UNCERTAINTY}_{{dim_index}}"


PEAK_LOOP_TAGS = [
    CHAIN_CODE__DIM_INDEX,
    SEQUENCE_CODE__DIM_INDEX,
    RESIDUE_NAME__DIM_INDEX,
    ATOM_NAME__DIM_INDEX,
    POSITION__DIM_INDEX,
    POSITION_UNCERTAINTY__DIM_INDEX,
]

PEAK_ID = "peak_id"
INDEX = "index"

PEAK_LOOP_TAGS = [
    INDEX,
    PEAK_ID,
]

HEIGHT = "height"
HEIGHT_UNCERTAINTY = "height_uncertainty"
VOLUME = "volume"
VOLUME_UNCERTAINTY = "volume_uncertainty"
