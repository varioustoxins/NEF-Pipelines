from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Tuple, Union

from strenum import StrEnum

from nef_pipelines.lib.isotope_lib import Isotope

FAKE_SPECTROMETER_FREQUENCY_600 = 600.12345678


class NMRMassClass(Enum):
    IDP = auto()
    LOW = auto()
    HIGH = auto()


class ExperimentType(StrEnum):
    N_HSQC = auto()
    C_HSQC = auto()

    HNCA = auto()
    HNcoCA = auto()

    HNCACB = auto()
    HNcoCACB = auto()
    CBCAcoNH = auto()

    HNCO = auto()
    HNcaCO = auto()

    # for transfer pathways in 13C detected spectra see
    # Kosol s. et. al Molecules 2013, 18, 10802-10828; doi:10.3390/molecules180910802 [in references]
    # Felli I.C. et. al. Chem. Rev. 2022, 122, 9468−9496 doi:10.1021/acs.chemrev.1c00871

    CON = auto()
    NCO = auto()
    CAN = auto()
    CACO = auto()
    CBCACO = auto()
    CACON = auto()
    CBCACON = auto()
    caNCO = auto()
    CANCO = auto()
    COCON = auto()
    NcaNCO = auto()
    CBCANCO = auto()
    COCA = auto()

    # NcaNCO = auto()

    CDETECT = auto()
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
    ExperimentType.CON: "CON",
    ExperimentType.NCO: "NCO",
    ExperimentType.CAN: "CAN",
    ExperimentType.CACO: "CACO",
    ExperimentType.CBCACO: "CBCACO",
    ExperimentType.CACON: "CACON",
    ExperimentType.CBCACON: "CBCACON",
    ExperimentType.caNCO: "caNCO",
    ExperimentType.CANCO: "CANCO",
    ExperimentType.COCON: "CO_CO[N].Jcoupling",  # is this right
    ExperimentType.COCA: "COCA",
    ExperimentType.NcaNCO: "hNcaNCO",
    ExperimentType.CBCANCO: "CBCANCO",  # not actually defined
}

# a subset of the synonyms produced by lib/experiments/prototypes from the ccpn v2 experiment prototypes
# just for triple reoenance spectra, carbon dectected spectra and hsqcs
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
    "CON": "CON",
    "NCO": "NCO",
    "CAN": "CAN",
    "CACO": "CACO",
    "CBCACO": "CBCACO",
    "CACON": "CACON",
    "CBCACON": "CBCACON",
    "COCON": "CO_CO[N].Jcoupling",
    "COCA": "COCA",
    "caNCO": "caNCO",
    "CANCO": "CANCO",
    "NcaNCO": "hNcaNCO",
    "CBCANCO": "CBCANCO",  # not actually defined
}

EXPERIMENT_CLASSIFICATION_TO_SYNONYM = {
    synonym: spectrum_type
    for spectrum_type, synonym in EXPERIMENT_SYNONYM_TO_CLASSIFICATION.items()
}

C_DETECT_SPECTRA = {
    ExperimentType.CON,
    ExperimentType.NCO,
    ExperimentType.CAN,
    ExperimentType.CACO,
    ExperimentType.CBCACO,
    ExperimentType.CACON,
    ExperimentType.CBCACON,
    ExperimentType.COCON,
    ExperimentType.caNCO,
    ExperimentType.CANCO,
    ExperimentType.COCON,
    ExperimentType.NcaNCO,
    ExperimentType.CBCANCO,
    ExperimentType.COCA,
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

EXPERIMENT_GROUPS = {
    ExperimentType.CDETECT: C_DETECT_SPECTRA,
    ExperimentType.TRIPLE: TRIPLE_SPECTRA,
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
    # C'-i Ni
    ExperimentType.CON: PeakInfo(
        name="CON",
        atoms=("N", "C"),
        dimensions=(Isotope.N15, Isotope.C13),
        atom_sets=(((-1, "C"), (0, "N")),),
        atom_set_signs=(1,),
        essential_atom_sets=(1,),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("C-1",),
        partners=(),
    ),
    # Ni C'-i
    ExperimentType.NCO: PeakInfo(
        name="NCO",
        atoms=("N", "C"),
        dimensions=(Isotope.N15, Isotope.C13),
        atom_sets=(((0, "N"), (-1, "C")),),
        atom_set_signs=(1,),
        essential_atom_sets=(1,),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("C-1",),
        partners=(),
    ),
    ExperimentType.CAN: PeakInfo(
        name="CAN",
        atoms=("N", "CA"),
        dimensions=(Isotope.N15, Isotope.C13),
        atom_sets=(((0, "N"), (0, "CA")),),
        atom_set_signs=(1,),
        essential_atom_sets=(1,),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("CA",),
        partners=(),
    ),
    ExperimentType.CACO: PeakInfo(
        name="CACO",
        atoms=("C", "CA"),
        dimensions=(Isotope.C13, Isotope.C13),
        atom_sets=(((0, "CA"), (0, "C")),),
        atom_set_signs=(1,),
        essential_atom_sets=(1,),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("CA",),
        partners=(),
    ),
    ExperimentType.CBCACO: PeakInfo(
        name="CBCACO",
        atoms=(("CA", "CB"), "C"),
        dimensions=(Isotope.C13, Isotope.C13),
        atom_sets=(
            ((0, "CA"), (0, "C")),
            ((0, "CB"), (0, "C")),
        ),
        atom_set_signs=(1, 1),
        essential_atom_sets=(0, 1),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("CA", "CB"),
        partners=(),
    ),
    # Cαi-C'i-Ni+1
    ExperimentType.CACON: PeakInfo(
        name="CACON",
        atoms=("CA", "C", "N"),
        dimensions=(Isotope.C13, Isotope.C13, Isotope.N15),
        atom_sets=(((-1, "CA"), (-1, "C"), (0, "N")),),
        atom_set_signs=(1,),
        essential_atom_sets=(1,),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("CA"),
        partners=(),
    ),
    # Cαi-1 C'i-1-Ni, Cßi-1-C'i-1-Ni
    ExperimentType.CBCACON: PeakInfo(
        name="CBCACON",
        atoms=(("CA", "CB"), "C", "N"),
        dimensions=(Isotope.C13, Isotope.C13, Isotope.N15),
        atom_sets=(
            ((-1, "CA"), (-1, "C"), (0, "N")),
            ((-1, "CB"), (-1, "C"), (0, "N")),
        ),
        atom_set_signs=(1, 1),
        essential_atom_sets=(0, 1),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("CA", "CB"),
        partners=(),
    ),
    # Ni-Ni-C'i-1, Ni+1-Ni-C'i-1
    ExperimentType.caNCO: PeakInfo(
        name="caNCO",
        atoms=("N", "C"),
        dimensions=(Isotope.N15, Isotope.N15, Isotope.C13),
        atom_sets=(((0, "N"), (0, "N"), (-1, "C")), ((1, "N"), (0, "N"), (-1, "C"))),
        atom_set_signs=(1, 1),
        essential_atom_sets=(0, 1),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("Ndiag", "N+1"),
        partners=(),
    ),
    # Cai, C’i, Ni+1 and C’i, Ni+1 ,Cai+1
    ExperimentType.CANCO: PeakInfo(
        name="CANCO",
        atoms=("CA", "N", "C"),
        dimensions=(Isotope.C13, Isotope.C13, Isotope.N15),
        atom_sets=(((0, "CA"), (1, "N"), (0, "C")), ((1, "CA"), (1, "N"), (0, "C"))),
        atom_set_signs=(1, 1),
        essential_atom_sets=(0, 1),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("Ndiag", "N+1"),
        partners=(),
    ),
    # C'-i-C'-i-Ni, C'i-1,-C'i-Ni+1, C'i+1 -C'i -Ni+1
    ExperimentType.COCON: PeakInfo(
        name="COCON",
        atoms=("N", "C"),
        dimensions=(Isotope.C13, Isotope.C13, Isotope.N15),
        atom_sets=(
            ((-1, "C"), (-1, "C"), (0, "N")),
            ((-1, "C"), (0, "C"), (1, "N")),
            ((1, "C"), (0, "C"), (1, "N")),
        ),
        atom_set_signs=(1, 1, 1),
        essential_atom_sets=(0, 1, 2),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("C-1diag", "C-1", "C+1"),
        partners=(),
    ),
    # Ni-Ni-C'i-1, Ni+1-Ni-Ci-1, Ni-1-Ni-C'i-1
    ExperimentType.NcaNCO: PeakInfo(
        name="NcaNCO",
        atoms=("N", "C"),
        dimensions=(Isotope.N15, Isotope.N15, Isotope.C13),
        atom_sets=(
            ((0, "N"), (0, "N"), (-1, "C")),
            ((1, "N"), (0, "N"), (-1, "C")),
            ((-1, "N"), (0, "N"), (-1, "C")),
        ),
        atom_set_signs=(1, 1, 1),
        essential_atom_sets=(0, 1, 2),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("N", "N+1", "N-1"),
        partners=(),
    ),
    # Cαi-C'i-1-Ni, Cßi-C'i-1-Ni, Cßi-C'i-Ni+1, Cαi- C'i-Ni+1
    ExperimentType.CBCANCO: PeakInfo(
        name="CBCANCO",
        atoms=("N", "C", ("CA", "CB")),
        dimensions=(Isotope.C13, Isotope.C13, Isotope.N15),
        atom_sets=(
            ((0, "CA"), (0, "C"), (0, "N")),
            ((0, "CB"), (0, "C"), (0, "N")),
            ((0, "CA"), (0, "C"), (1, "N")),
            ((0, "CB"), (0, "C"), (1, "N")),
        ),
        atom_set_signs=(1, 1, 1, 1),
        essential_atom_sets=(0, 1, 2, 3),
        atom_sets_by_mass={NMRMassClass.IDP: (0)},
        atom_set_names=("CAN", "CBN", "CAN+1", "CBN+1"),
        partners=(),
    ),
}
