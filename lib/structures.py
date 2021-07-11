from dataclasses import dataclass
from typing import NamedTuple, List


class SequenceResidue(NamedTuple):
    chain: str
    residue_number: int
    residue_name: str

@dataclass
class AtomLabel:
    chain_code: str
    sequence_code: int
    residue_name: str
    atom_name: str


@dataclass
class PeakAxis:
    atom_labels: List[AtomLabel]
    ppm: float
    # width: float
    # bound: float
    merit: str
    # j: float
    # U: str


@dataclass
class PeakValues:
    index: int
    volume: float
    intensity: float
    status: bool
    comment: str
    # flag0: str


@dataclass
class PeakListData:
    num_axis: int
    axis_labels: List[str]
    # isotopes: List[str]
    data_set: str
    sweep_widths: List[float]
    spectrometer_frequencies: List[float]


@dataclass
class PeakList:
    peak_list_data: PeakListData
    peaks: dict