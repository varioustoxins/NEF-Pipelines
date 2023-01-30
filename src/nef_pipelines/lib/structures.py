from dataclasses import dataclass
from enum import auto
from typing import Dict, List, Optional, Union

from strenum import StrEnum


class Linking(StrEnum):
    START = (auto(),)
    MIDDLE = auto()
    END = auto()


@dataclass(frozen=True, order=True)
class SequenceResidue:
    chain_code: str
    sequence_code: Union[int, str]
    residue_name: str
    is_cis: bool = False
    linking: Optional[Linking] = None
    variant: Optional[str] = None


# should contain a residue and have constructors?
@dataclass(frozen=True, order=True)
class AtomLabel:
    residue: SequenceResidue
    atom_name: str
    element: str = None
    isotope_number: int = None


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


@dataclass
class DihedralRestraint:
    atom_1: AtomLabel
    atom_2: AtomLabel
    atom_3: AtomLabel
    atom_4: AtomLabel

    target_angle: float
    lower_limit: float
    upper_limit: float


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


@dataclass
class ShiftData:
    atom: AtomLabel
    value: float
    value_uncertainty: Optional[float] = None


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
