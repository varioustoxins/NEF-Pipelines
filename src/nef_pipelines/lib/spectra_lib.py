from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Tuple, Union

from strenum import LowercaseStrEnum

from nef_pipelines.lib.isotope_lib import Isotope


class NMRMassClass(Enum):
    LOW = auto()
    HIGH = auto()


class ExperimentType(LowercaseStrEnum):
    N_HSQC = auto()
    C_HSQC = auto()

    HNCA = auto()
    HNcoCA = auto()

    HNCACB = auto()
    HNcoCACB = auto()
    CBCAcoNH = auto()

    HNCO = auto()
    HNcaCO = auto()

    TRIPLE = auto()


SPECTRUM_TYPE_TO_CLASSIFICATION = {
    ExperimentType.N_HSQC: "H[N]",
    ExperimentType.C_HSQC: "H[C]",
    ExperimentType.HNCA: "H[N[CA]]",
    ExperimentType.HNcoCA: "H[N[co[CA]]]",
    ExperimentType.HNCACB: "H[N[CA[CB]]]",  # even though you might think of it as H[N[{CA|CB}]]'
    # or H[N[{CA|ca[Cali]}]]]
    # or even H[N[{CA|ca[CB]}]]
    # or even H[N[{CA|ca[C]}]]  ?
    ExperimentType.HNcoCACB: "H[N[co[CA[CB]]]]",  # even though you might think of it related to ones above
    # or 'H[N[co[{CA|ca[C]}]]]
    ExperimentType.CBCAcoNH: "h{CA|Cca}coNH",  # and why is this not h{CA|CBca}coNH
    ExperimentType.HNCO: "H[N[CO]]",
    ExperimentType.HNcaCO: "H[N[ca[CO]]]",
}

TRIPLE_SPECTRA = {
    ExperimentType.N_HSQC,
    ExperimentType.HNCA,
    ExperimentType.HNcoCA,
    ExperimentType.HNCACB,
    ExperimentType.HNcoCACB,
    ExperimentType.HNCO,
    ExperimentType.HNcaCO,
}


@dataclass
class PeakInfo:
    name: str
    atoms: Tuple[Union[str, Tuple[str, ...]], ...]
    dimensions: Tuple[Isotope, ...]
    atom_sets: Tuple[Tuple[Tuple[int, str], ...], ...]
    atom_set_signs: Tuple[int, ...]
    essential_atom_sets: Tuple[int, ...]
    atom_sets_by_mass: Dict[NMRMassClass, Tuple[int, ...]]
    atom_set_names: Tuple[str, ...]
    partners: Tuple[ExperimentType, ...]


@dataclass
class AtomInfo:
    n_field: int
    atom_type: str


# TODO much of this is ugly!
EXPERIMENT_INFO = {
    ExperimentType.N_HSQC: PeakInfo(
        name="N-HSQC",
        atoms=("N", "H"),
        dimensions=(Isotope.N15, Isotope.H1),
        atom_sets=(((0, "N"), (0, "H")),),
        atom_set_signs=(1,),
        essential_atom_sets=(0,),
        atom_sets_by_mass={NMRMassClass.LOW: (0,), NMRMassClass.HIGH: (0,)},
        atom_set_names=("HN",),
        partners=(),
    ),
    # SpectraTypes.C_HSQC: ShiftInfo(
    #     atoms={'H', 'C'},
    #     dimensions= (Isotope.H1, Isotope.N15),
    #     atom_sets=[[(1, 'H'), (1, 'C')],],
    #     atom_set_signs=[1]
    # ),
    ExperimentType.HNCA: PeakInfo(
        name="HNCA",
        atoms=(("CA",), "N", "H"),
        dimensions=(Isotope.C13, Isotope.N15, Isotope.H1),
        atom_sets=(
            ((0, "CA"), (0, "N"), (0, "H")),
            ((-1, "CA"), (0, "N"), (0, "H")),
        ),
        atom_set_signs=(1, 1),
        essential_atom_sets=(0, 1),
        atom_sets_by_mass={NMRMassClass.LOW: (0, 1), NMRMassClass.HIGH: (0, 1)},
        atom_set_names=("CA", "CA-1"),
        partners=(ExperimentType.HNcoCA,),
    ),
    ExperimentType.HNcoCA: PeakInfo(
        name="HNcoCA",
        atoms=("H", "N", ("CA",)),
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=(((0, "H"), (0, "N"), (-1, "CA")),),
        atom_set_signs=(1,),
        essential_atom_sets=(0,),
        atom_sets_by_mass={NMRMassClass.LOW: (0,), NMRMassClass.HIGH: (0,)},
        atom_set_names=("CA-1",),
        partners=(ExperimentType.HNCA,),
    ),
    ExperimentType.HNCACB: PeakInfo(
        name="HNCACB",
        atoms=("H", "N", ("CA", "CB")),
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=(
            ((0, "H"), (0, "N"), (0, "CA")),
            ((0, "H"), (0, "N"), (-1, "CA")),
            ((0, "H"), (0, "N"), (0, "CB")),
            ((0, "H"), (0, "N"), (-1, "CB")),
        ),
        atom_set_signs=(1, 1, -1, -1),
        essential_atom_sets=(0, 2),
        atom_sets_by_mass={
            NMRMassClass.LOW: (0, 1, 2, 3),
            NMRMassClass.HIGH: (0, 1, 2),
        },
        atom_set_names=("CA", "CA-1", "CB", "CB-1"),
        partners=(ExperimentType.HNcoCACB, ExperimentType.CBCAcoNH),
    ),
    ExperimentType.HNcoCACB: PeakInfo(
        name="HNcoCACB",
        atoms=("H", "N", ("CA", "CB")),
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=(
            ((0, "H"), (0, "N"), (-1, "CA")),
            ((0, "H"), (0, "N"), (-1, "CB")),
        ),
        atom_set_signs=(1, -1),
        essential_atom_sets=(1,),
        atom_sets_by_mass={NMRMassClass.LOW: (0, 1), NMRMassClass.HIGH: (0, 1)},
        atom_set_names=("CA-1", "CA-1"),
        partners=(ExperimentType.HNCACB,),
    ),
    ExperimentType.CBCAcoNH: PeakInfo(
        name="CBCAcoNH",
        atoms=("H", "N", ("CA", "CB")),
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=(
            ((0, "H"), (0, "N"), (-1, "CA")),
            ((0, "H"), (0, "N"), (-1, "CB")),
        ),
        atom_set_signs=(1, 1),
        essential_atom_sets=(1,),
        atom_sets_by_mass={NMRMassClass.LOW: (0, 1), NMRMassClass.HIGH: (0, 1)},
        atom_set_names=("CA-1", "CB-1"),
        partners=(ExperimentType.HNCACB,),
    ),
    ExperimentType.HNCO: PeakInfo(
        name="HNCO",
        atoms=("H", "N", ("C",)),
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=(((0, "H"), (0, "N"), (-1, "C")),),
        atom_set_signs=(1,),
        essential_atom_sets=(0,),
        atom_sets_by_mass={NMRMassClass.LOW: (0,), NMRMassClass.HIGH: (0,)},
        atom_set_names=("C-1",),
        partners=(ExperimentType.HNcaCO,),
    ),
    ExperimentType.HNcaCO: PeakInfo(
        name="HNcaCO",
        atoms=("H", "N", ("C",)),
        dimensions=(Isotope.H1, Isotope.N15, Isotope.C13),
        atom_sets=(
            ((0, "H"), (0, "N"), (0, "C")),
            ((0, "H"), (0, "N"), (-1, "C")),
        ),
        atom_set_signs=(1, 1),
        essential_atom_sets=(1,),
        atom_sets_by_mass={NMRMassClass.LOW: (0, 1), NMRMassClass.HIGH: (1,)},
        atom_set_names=("C", "C-1"),
        partners=(ExperimentType.HNCO,),
    ),
}

# a subset of the synonyms produced by lib/experiments/prototypes from the ccpn v2 experiment prototypes
# just for tipe reoenance spectra and hsqcs
EXPERIMENT_SYNONYM_TO_CLASSIFICATION = {
    "15N HSQC/HMQC": "H[N]",
    "13C HSQC/HMQC": "H[C]",
    "H-detected HNcoCA": "H[N[co[CA]]]",
    "HNCA": "H[N[CA]]",
    "H-detected HNCACB": "H[N[CA[CB]]]",
    "H-detected HNcoCACB": "H[N[co[CA[CB]]]]",
    "hbCB/haCAcoNNH": "h{CA|Cca}coNH",
    "HNCO": "H[N[CO]]",
    "H-detected HNcaCO": "H[N[ca[CO]]]",
}

EXPERIMENT_CLASSIFICATION_TO_SYNONYM = {
    synonym: spectrum_type
    for spectrum_type, synonym in EXPERIMENT_SYNONYM_TO_CLASSIFICATION.items()
}
