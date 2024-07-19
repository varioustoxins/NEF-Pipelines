from dataclasses import dataclass, field
from enum import auto
from typing import Dict, List, Optional, Union

from strenum import LowercaseStrEnum, StrEnum

# TODO: to avoid circular import, move to constants
UNUSED = "."


class Linking(StrEnum):
    START = auto()
    MIDDLE = auto()
    END = auto()
    FREE = auto()


class SequenceResidue: ...  # noqa: E701


class Residue: ...  # noqa: E701


# something like this migh be nice
# but we would need updates...
# class ResidueAssignmentState(StrEnum):
#     UNASSIGNED = auto()
#     ASSIGNED = auto()
#     OFFSET_OR_PREFIX = auto()
#     LABEL = auto()


@dataclass(frozen=True, order=True)
class Residue:
    chain_code: str
    sequence_code: Union[int, str]
    residue_name: str
    sequence_code_prefix: str = ""
    offset: int = 0
    # assignmnet_state:ResidueAssignmentState  add as property

    @staticmethod
    def from_sequence_residue(sequence_residue: SequenceResidue) -> Residue:
        return Residue(
            sequence_residue.chain_code,
            sequence_residue.sequence_code,
            sequence_residue.residue_name,
        )


@dataclass(frozen=True, order=True)
class SequenceResidue(Residue):

    is_cis: bool = False
    linking: Optional[Linking] = None
    variants: List[str] = ()


# should contain a residue and have constructors?
@dataclass(frozen=True, order=True)
class AtomLabel:
    residue: Residue
    atom_name: str
    element: str = None
    isotope_number: int = None

    def is_unassigned(self):
        residue_unassigned = (
            self.residue.chain_code == UNUSED
            and self.residue.sequence_code == UNUSED
            and self.residue.residue_name == UNUSED
        )
        return residue_unassigned and self.atom_name == UNUSED


UNASSIGNED_ATOM = AtomLabel(Residue(UNUSED, UNUSED, UNUSED), UNUSED)


@dataclass
class PeakAxis:
    atom_labels: List[AtomLabel]
    ppm: float
    merit: str
    # comment: str


@dataclass
class DistanceRestraint:
    atom_list_1: List[AtomLabel]
    atom_list_2: List[AtomLabel]

    target_distance: float
    distance_minus: float
    distance_plus: float

    comment: str = None


@dataclass
class DihedralRestraint:
    atom_1: AtomLabel
    atom_2: AtomLabel
    atom_3: AtomLabel
    atom_4: AtomLabel

    merit: float = None
    name: str = None
    remark: str = None

    target_value: float = None  # use one or the  of target_value and error
    target_value_error: float = None

    lower_limit: float = None  # or upper and lower limits
    upper_limit: float = None


@dataclass
class PeakValues:
    serial: int

    height: Optional[float] = None
    height_uncertainty: Optional[float] = None

    volume: Optional[float] = None
    volume_uncertainty: Optional[float] = None

    deleted: Optional[bool] = False
    comment: Optional[str] = ""

    width: Optional[float] = None  # HWHH ppm
    # bound: float

    # merit: Optional[str] = None

    # flag0: str


# assignment has a tuple of dimensions


@dataclass
class Assignments:
    assignments: Dict[str, List[AtomLabel]]


@dataclass
class Peak:
    id: int
    values: PeakValues

    # move these to axis_values?
    positions: Dict[str, float]

    # assignment has a list of one or more assignments
    # each Assignment will have one value for each axis this maybe be either
    # 0. a list with no AtomLabels - unassigned
    # 1. a list with a single AtomLabel -  this axis is definitively assigned
    # 2. a list with multiple AtomLabels - this axis has multiple putative assignments
    # Note if there are multiple unique assignments each of these is should be a top level
    # assignment of the peak
    assignments: List[Assignments]

    position_uncertainties: Optional[Dict[str, float]] = None


@dataclass
class PeakListData:
    num_axis: int
    axis_labels: List[str]
    # isotopes: List[str]
    data_set: str
    sweep_widths: List[float]
    spectrometer_frequencies: List[float]


# TODO: are axes indexed by names or by integer...
@dataclass
class PeakList:
    peak_list_data: PeakListData
    peaks: List[Dict[Union[int, str], Peak]]


@dataclass
class LineInfo:
    file_name: str
    line_no: int
    line: str


@dataclass(frozen=True, order=True)
class ShiftData:
    atom: AtomLabel
    value: float  # TODO: should be position
    value_uncertainty: Optional[float] = None  # TODO: should be position_uncertainty
    line_width: Optional[float] = None  # line width in Hz
    line_width_uncertainty: Optional[float] = None  # uncertainty of line width in Hz

    frame_name: Optional[str] = ""
    frame_row: Optional[int] = None
    frame_line: Optional[str] = None


@dataclass
class ShiftList:
    shifts: List[ShiftData]


@dataclass(order=True)
class RdcRestraint:
    atom_1: AtomLabel
    atom_2: AtomLabel
    value: float
    value_uncertainty: float
    weight: Optional[float] = None


class PeakFitMethod(LowercaseStrEnum):
    GAUSSIAN = auto()
    LORENTZIAN = auto()
    SPLINE = auto()


@dataclass(frozen=True, order=True)
class NewPeak:
    # TODO: support multiple assignments
    shifts: List[
        ShiftData
    ]  # multiple assignments  we support this by having mutiple shifts with the same value?

    id: Optional[int] = None
    height: Optional[float] = None
    height_uncertainty: Optional[float] = None
    volume: Optional[float] = None
    volume_uncertainty: Optional[float] = None
    peak_fit_method: Optional[Union[str, PeakFitMethod]] = None
    figure_of_merit: Optional[float] = None
    comment: str = ""


@dataclass
class DimensionInfo:
    axis_code: str  # this is the isotope code for us...
    axis_name: str = None
    axis_unit: Optional[str] = "ppm"


class RelaxationModelParameter(StrEnum):
    S2 = auto()
    S2_FAST = auto()
    S2_SLOW = auto()
    TAU_E = auto()
    TAU_FAST = auto()
    TAU_SLOW = auto()
    R_EXCHANGE = auto()
    J_0 = auto()
    J_OMEGA_1 = auto()
    J_OMEGA_2 = auto()
    J_OMEGA_1_87 = auto()
    J_OMEGA_2_87 = auto()
    RHO_1 = auto()
    RHO_2 = auto()


class RelaxationModelType(StrEnum):
    MODEL_FREE = auto()
    REDUCED_SPECTRAL_DENSITY = auto()


class RelaxationUnit(StrEnum):
    UNITLESS = auto()
    PICO_SECOND = auto()
    NANO_SECOND = auto()
    MICRO_SECOND = auto()
    MILLI_SECOND = auto()
    PER_SECOND = auto()
    SECOND = auto()


class RelaxationDataSource(StrEnum):
    SIMULATION = auto()
    ESTIMATE = auto()
    EXPERIMENTAL = auto()


@dataclass(frozen=True, order=True)
class RelaxationValue:
    atom: AtomLabel
    value: float
    value_type: RelaxationModelParameter
    value_error: float = None
    unit: RelaxationUnit = None
    dipole_atom: AtomLabel = None


class DiffusionModel(StrEnum):
    SPHERE = auto()
    SPHEROID_PROLATE = auto()
    SPHEROID_OBLATE = auto()
    ELLIPSOID = auto()


@dataclass(frozen=True)
class TensorFrame:
    d_iso: float = None

    d_x: float = None
    d_y: float = None
    d_z: float = None

    d_anisotropic: float = None
    d_rhombic: float = None

    alpha: float = None
    beta: float = None
    gamma: float = None

    theta: float = None
    phi: float = None


@dataclass(frozen=True)
class RelaxationData:
    model_type: RelaxationModelType
    data_source: RelaxationDataSource
    values: List[RelaxationValue] = field(default_factory=list)
    tauM: float = None
    tauM_error: float = None

    field_strengths: List[float] = None

    diffusion_model: DiffusionModel = None
    tensor_frame: TensorFrame = None
    tensor_frame_error: TensorFrame = None
    structure_name: str = None


# fmt: off
# TODO: this is an initial attempt some more work needed on turn types and other analysis programs
class SecondaryStructureType(LowercaseStrEnum):
    #                                         DSSP |  SST |  comment
    ALPHA_HELIX = auto()                    # H    |  H   |  right-handed
    ALPHA_HELIX_LEFT_HANDED = auto()        # .    |  h
    THREE_TEN_HELIX = auto()                # G    |  G   |  right-handed
    THREE_TEN_HELIX_LEFT_HANDED = auto()    # .    |  g
    BETA_SHEET = auto()                     # E    |  E
    BETA_BRIDGE = auto()                    # B    |
    PI_HELIX = auto()                       # I    |  I   |  right-handed, aka a 5 helix
    PI_HELIX_LEFT_HANDED = auto()           # .    |  i
    TURN = auto()                           # T    |  T   |  hydrogen bonded turn, subclasses listed below
    ALPHA_TURN = auto()                     # .    |  4   |  4 bonds, ALPHA-like TURN (right/left-handed)
    BETA_TURN = auto()                      # .    |  3   |  3 bonds sub classes are listed below
    #                                              |      |  3_10-like  TURN (right/left-handed)
    BETA_I_TURN = auto()
    BETA_II_TURN = auto()
    BETA_I_PRIME_TURN = auto()
    BETA_II_PRIME_TURN = auto()
    BETA_IV_TURN = auto()
    BETA_VIA1_TURN = auto()
    BETA_VIA2_TURN = auto()
    BETA_VIB_TURN = auto()
    BETA_VII_TURN = auto()
    GAMMA_TURN = auto()                     # .    |      |  2 bonds
    DELTA_TURN = auto()                     # .    |      |  1 bond - sterically unlikley
    PI_TURN = auto()                        # .    |   5  |  5 bonds
    BEND = auto()                           # S    |      |
    COIL = auto()                           # .    |      |  either disordered or a loop but unknown which
    LOOP = auto()                           # .    |      |  well-defined structure but not one of the
    #                                              |      |  standard dssp types also called an omega loop
    DISORDERED = auto()                     # .    |      |  a region without ordered secondary structure
    UNKNOWN = auto()                        # .    |   -  |  the program wasn't able to determine secondary
    #                                              |      |  structure type (None?)
# fmt: on


@dataclass
class SecondaryStructure:
    residue: Residue
    secondary_structure: SecondaryStructureType
    merit: float  # typically between 0 and 1
    comment: str = ""
