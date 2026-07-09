"""
    Core dataclasses shared across system,
    eg: AtomLabel, SequenceResidue, ShiftData, NewPeak, selector results, etc
"""

import math
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Dict, List, Optional, Tuple, Union

from pynmrstar import Loop, Saveframe
from strenum import LowercaseStrEnum, StrEnum


class EntryPart(Flag):
    """Identifies which structural level of a NEF entry an item belongs to.

    Flag enum — values can be combined with | for use in expand_frame_loop_and_tag_wildcards.
    """

    Entry = auto()
    Saveframe = auto()
    Loop = auto()
    FrameTag = auto()
    LoopTag = auto()


@dataclass(frozen=True)
class EntryPartValues:
    """\
    Location of one item within a NEF saveframe hierarchy.

    entry_part is derived automatically from loop_category and tag_name:
        neither set  → Saveframe
        tag_name only → FrameTag
        loop_category only → Loop
        both set → LoopTag

    Attributes:
        frame_name: Saveframe name
        frame_category: Saveframe category
        loop_category: Loop category — set for Loop and LoopTag, None otherwise
        tag_name: Tag or column name — set for FrameTag and LoopTag, None otherwise
        entry_part: Derived from loop_category/tag_name (not a constructor argument)
    """

    frame_name: str
    frame_category: str
    loop_category: Optional[str] = None
    tag_name: Optional[str] = None
    entry_part: EntryPart = field(init=False)

    def __post_init__(self):
        """Derive entry_part from the combination of loop_category and tag_name."""
        if self.loop_category is None and self.tag_name is None:
            ep = EntryPart.Saveframe
        elif self.loop_category is None:
            ep = EntryPart.FrameTag
        elif self.tag_name is None:
            ep = EntryPart.Loop
        else:
            ep = EntryPart.LoopTag
        object.__setattr__(self, "entry_part", ep)


class NEFPipelinesException(Exception): ...  # noqa: E701


class NEFPipelinesInternalError(NEFPipelinesException):
    """Exception raised when an internal invariant is violated.

    This indicates a programming error, not a user error.
    These exceptions should never occur in correct code.
    """

    ...


class NEFBadLoopSelectionException(NEFPipelinesException):
    """Exception raised when a loop selection is incorrectly defined
    in FrameLoopAndTags.
    """

    ...


# TODO: to avoid circular import, move to constants
UNUSED = "."
PSEUDO_PREFIX = "@"
CCPN_UNSASSIGNED_CHAIN = "-"


class Linking(StrEnum):
    START = auto()
    MIDDLE = auto()
    END = auto()
    FREE = auto()


class SequenceResidue: ...  # noqa: E701


class Residue: ...  # noqa: E701


# something like this might be nice
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
    chain_code_prefix: str = ""
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

    is_cis: Optional[bool] = None  # None is equivalent to .
    linking: Optional[Linking] = None
    variants: List[str] = ()


@dataclass(frozen=True)
class SaveframeNameParts:
    """\
    Parsed components of a NEF framecode.

    Framecodes follow the grammar:
        framecode ::= category ["_" identity] [suffix]
        category  ::= namespace "_" type
        qualifier ::= index | suffix   (* mutually exclusive *)
        index                ::= "`" integer "`"
        suffix               ::= "." token       (* folds into identity in parser *)

    Example: nef_nmr_spectrum_k_ubi_hnco`1`
        namespace: "nef"
        type:      "nmr_spectrum"
        identity:  "k_ubi_hnco"
        index:     "1"

    Singleton: framecode with no identity and no suffix (framecode == category).

    When used as a target specification for rename operations, all fields follow the
    same two-sentinel rule:
      None → inherit this field from the source frame
      ""   → explicitly absent (no namespace prefix, no identity, no index)
      "v"  → use this exact value
    """

    namespace: Optional[str] = None
    type: Optional[str] = None
    identity: Optional[str] = None
    index: Optional[str] = None

    @property
    def is_singleton(self) -> bool:
        return not self.identity and not self.index

    @property
    def full_name(self) -> str:
        """\
        Reconstruct full framecode from parts.

        Includes namespace prefix if present. Empty string namespace means no prefix.
        Raises ValueError if type is None.
        """
        if self.type is None:
            msg = f"""
                cannot compute full_name: type is None!
                values are:
                    namespace: {self.namespace}
                    type: None
                    identity: {self.identity}
                    index: {self.index}
            """
            raise ValueError(msg)

        # category (in grammar sense) = namespace + type
        if self.namespace:
            category_with_namespace = f"{self.namespace}_{self.type}"
        else:
            category_with_namespace = self.type

        # Build base name
        if not self.identity:
            base = category_with_namespace
        else:
            base = f"{category_with_namespace}_{self.identity}"

        # Add index if present
        if self.index:
            return f"{base}`{self.index}`"
        return base


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
            or self.residue.sequence_code_prefix == PSEUDO_PREFIX
            or self.residue.chain_code_prefix == PSEUDO_PREFIX
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
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    bond_length: Optional[float] = None


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


# when we get beyond 3.9 support this should change to
# Vector3D: TypeAlias = Tuple[float, float, float]
# and when we get beyon 3.11 support this should change to
# type Vector3D = Tuple[float, float, float]
Vector3D = Tuple[float, float, float]


@dataclass(frozen=True)
class RdcTensorFrameData:
    da: float
    dr: float

    eigen_vector_x: Vector3D
    eigen_vector_y: Vector3D
    eigen_vector_z: Vector3D

    def is_defined(self):
        da_ok = not math.isnan(self.da)
        dr_ok = not math.isnan(self.dr)
        eigen_x_ok = not any(math.isnan(elem) for elem in self.eigen_vector_x)
        eigen_y_ok = not any(math.isnan(elem) for elem in self.eigen_vector_y)
        eigen_z_ok = not any(math.isnan(elem) for elem in self.eigen_vector_z)
        eigen_ok = eigen_x_ok and eigen_y_ok and eigen_z_ok

        return da_ok and dr_ok and eigen_ok


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


@dataclass
class ChainOffset:
    chain_code: str
    offset: int


@dataclass
class ResiduePair:
    start_residue: Optional[Union[str, int]] = None
    end_residue: Optional[Union[str, int]] = None


@dataclass
class ChainCode:
    chain_code: str = None


@dataclass
class ResidueRange(ResiduePair, ChainCode):
    pass


class ResidueRangeParsingException(NEFPipelinesException):
    """Exception raised when parsing a residue range specifications fails."""

    pass


@dataclass
class ChainStartAndEnds:
    chain_code: Union[int, str]
    has_start: bool
    has_end: bool


@dataclass
class RangeOffset(ResidueRange):
    """Represents a chain offset operation with optional range specification."""

    offset: int = 0


class ChainOffsetSyntaxParsingError(Exception):
    """Exception raised when parsing the new chain offset syntax fails."""

    def __init__(
        self, message: str, bad_value: str = "", all_arguments: List[str] = None
    ):
        super().__init__(message)
        self.bad_value = bad_value
        self.all_arguments = all_arguments or []


@dataclass
class FrameLoopAndTagSelectors:
    frame_name: str
    loop_name: Optional[str]
    frame_tags: List[str] = field(default_factory=list)
    loop_tags: List[str] = field(default_factory=list)


@dataclass
class FrameLoopsAndTags:
    """One item per matched frame; multiple loops live in `loops`.

    Tag selection (three-state convention):
        []        — no selection (command decides what to render)
        ['*']     — explicit wildcard (note: only present when no namespace filtering)
        [n1, n2]  — specific named tags (may include fnmatch wildcards)
    """

    frame: Saveframe
    loops: List[Loop] = field(default_factory=list)
    frame_tags: List[str] = field(default_factory=list)
    loop_tags: Dict[str, List[str]] = field(default_factory=dict)

    def __str__(self):
        loops_str = (
            "[\n"
            + "".join(f"        {loop.category},\n" for loop in self.loops)
            + "    ]"
        )
        loop_tags_str = (
            "{\n"
            + "".join(
                f"        {cat}: [{', '.join(tags)}],\n"
                for cat, tags in self.loop_tags.items()
            )
            + "    }"
        )
        return (
            f"FrameLoopsAndTags(\n"
            f"    frame={self.frame.name},\n"
            f"    loops={loops_str},\n"
            f"    frame_tags={self.frame_tags},\n"
            f"    loop_tags={loop_tags_str},\n"
            f")"
        )


@dataclass
class PaperType:
    """Paper formatting configuration for plotting."""

    paper_size: str  # a4, letter, legal, a3, tabloid
    orientation: str  # landscape, portrait


@dataclass
class PlotInfo:
    """Plot layout configuration."""

    paper_type: PaperType
    rows: int
    cols: int
    output_template: str
    common_y_scale: bool = False
    page_margin: float = 0.05  # Page edge margin as % of page width/height
    spacing: float = 0.03  # Spacing between plots as % of page width/height
    debug_grid: bool = False  # Show colored backgrounds for debugging grid layout


@dataclass
class FittedRate:
    """Fitted exponential decay parameters."""

    amplitude: float  # I0 - initial intensity
    rate: float  # R - decay rate constant
    rate_error: float  # Error on rate constant
    data_id: int  # Link to data ID


@dataclass
class SeriesData:
    """Time-series relaxation data for a single data_id."""

    data_id: int
    variable_values: List[float]  # Time points
    data_values: List[float]  # Intensity values
    variable_errors: List[Optional[float]]
    value_errors: List[Optional[float]]
    noise_estimate: Optional[float] = None


class MeasurementType(StrEnum):
    HEIGHT = auto()
    VOLUME = auto()
