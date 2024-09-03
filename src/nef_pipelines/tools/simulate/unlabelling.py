import sys
from copy import deepcopy
from dataclasses import dataclass, replace
from enum import auto
from pathlib import Path
from typing import Dict, List

import typer
from fyeah import f
from pynmrstar import Entry, Loop, Saveframe
from strenum import StrEnum
from tabulate import tabulate
from uncertainties import ufloat

from nef_pipelines.lib.nef_frames_lib import EXPERIMENT_CLASSIFICATION, EXPERIMENT_TYPE
from nef_pipelines.lib.nef_lib import (
    NEF_PIPELINES_PREFIX,
    UNUSED,
    SelectionType,
    create_nef_save_frame,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
    select_frames_by_name,
)
from nef_pipelines.lib.peak_lib import frame_to_peaks, peaks_to_frame
from nef_pipelines.lib.sequence_lib import sequences_from_frames
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.spectra_lib import (
    EXPERIMENT_CLASSIFICATION_TO_SYNONYM,
    EXPERIMENT_INFO,
    FAKE_SPECTROMETER_FREQUENCY_600,
    SPECTRUM_TYPE_TO_CLASSIFICATION,
    ExperimentType,
)
from nef_pipelines.lib.util import exit_error, parse_comma_separated_options
from nef_pipelines.tools.simulate import simulate_app
from nef_pipelines.tools.simulate.peaks import _make_spectrum

SPECTRUM_TYPE_NHSQC = ExperimentType.N_HSQC


class AminoAcid(StrEnum):
    ALA = auto()
    ARG = auto()
    ASN = auto()
    ASP = auto()
    CYS = auto()
    GLN = auto()
    GLU = auto()
    GLY = auto()
    HIS = auto()
    ILE = auto()
    LEU = auto()
    LYS = auto()
    MET = auto()
    PHE = auto()
    PRO = auto()
    SER = auto()
    THR = auto()
    TRP = auto()
    TYR = auto()
    VAL = auto()
    REF = auto()
    ANY = "*"


ALL_AMINO_ACID_SET = {*AminoAcid.__members__.values()}
ALL_AMINO_ACID_SET.remove(AminoAcid.REF)
ALL_AMINO_ACID_SET.remove(AminoAcid.ANY)
ALL_AMINO_ACID_SET.remove(AminoAcid.PRO)

FULLY_SCRAMBLED_SET = {
    AminoAcid.ASP,
    AminoAcid.GLU,
    AminoAcid.SER,
}

# residues which are not global scramblers
USABLE_UNLABELLING_SET = ALL_AMINO_ACID_SET - FULLY_SCRAMBLED_SET

OBVIOUS_SHIFT_SET = {AminoAcid.ALA, AminoAcid.GLY, AminoAcid.SER, AminoAcid.THR}


SINGLY_SCRAMBLED_SET = {  # GB1   APRATAXIN
    AminoAcid.ALA,  # VAL    VAL
    AminoAcid.GLY,  # TRP    CYS  SER  TRP
    AminoAcid.PHE,  # TYR    TYR
    AminoAcid.TYR,  # PHE                                          ! NOT REALLY UNLABELLED
}

# note residues in brackets are not really scrambled that much
MULTIPLY_SCRAMBLED_SET = {
    # GB1                   APRATAXIN
    AminoAcid.ILE,  # LEU  VAL              LEU  VAL  [ALA]
    AminoAcid.LEU,  # ILE  [VAL]            ILE  VAL  [ALA]
    AminoAcid.THR,  # GLY  TRP              GLY  CYS  SER    [TRP]
    AminoAcid.TRP,  # TYR  PHE              TYR  PHE                ! NOT REALLY UNLABELLED
    AminoAcid.VAL,  # ILE  LEU  [ALA]       ILE  LEU  [ALA]
}

CLEAN_SET = USABLE_UNLABELLING_SET - MULTIPLY_SCRAMBLED_SET - SINGLY_SCRAMBLED_SET
SEMI_CLEAN_SET = USABLE_UNLABELLING_SET - SINGLY_SCRAMBLED_SET

NO_OBV_CLEAN_SET = CLEAN_SET - OBVIOUS_SHIFT_SET
NO_OBV_SEMI_CLEAN_SET = SEMI_CLEAN_SET - OBVIOUS_SHIFT_SET


LABELING_SETS = {
    "ALL": ALL_AMINO_ACID_SET,
    "USEABLE": USABLE_UNLABELLING_SET,
    "CLEAN": CLEAN_SET,
    "SEMI_CLEAN": SEMI_CLEAN_SET,
    "NO_OBV_CLEAN": NO_OBV_CLEAN_SET,
    "NO_OBV_SEMI_CLEAN": NO_OBV_SEMI_CLEAN_SET,
    "MULTIPLY_SCRAMBLED": MULTIPLY_SCRAMBLED_SET,
    "SINGLY_SCRAMBLED": SINGLY_SCRAMBLED_SET,
    "REMOVE_OBVIOUS": OBVIOUS_SHIFT_SET,
}

LABELING_SET_HELP = {
    "ALL": "All amino acids",
    "USEABLE": "All amino acids excluding those that are uniformly scrambled",
    "CLEAN": "Amino acids that clearly have no scrambling",
    "SEMI_CLEAN": "Amino acids that have no scrambling or a single scambling partner",
    "NO_OBV_CLEAN": "CLEAN set with amino acids with obvious CB shifts removed",
    "NO_OBV_SEMI_CLEAN": "SEMI_CLEAN set with amino acids with obvious CB shifts removed",
    "MULTIPLY_SCRAMBLED": "Amino acids that are scrambled to mutiple partners",
    "SINGLY_SCRAMBLED": "Amino acids that are scrambled to single partners",
    "REMOVE_OBVIOUS": "Causes amino acids with obvious HN, Cα or Cβ chemical shifts to be removed, remove:",
}

ALL_AMINO_ACIDS = [aa.value for aa in AminoAcid if aa.value != "*"]
ALL_AMINO_ACIDS_UPPER = [aa.upper() for aa in ALL_AMINO_ACIDS]


UNLABELLED_SPECTRUM_NAME_TEMPLATE = "synthetic_{spectrum}_unlabelled_{residues}"

UNLABELLED_AMINO_ACIDS_AND_SETS_HELP = """\
    the amino acids or sets of amino acids to use for the unlabelling, to list the available amino acids and sets
    use the --list option. Note the sets are additive except for REMOVE_OBVIOUS_CBETAS which is subtractive.
    The default is NO_CB_CLEAN
"""


FRAME_SELECTORS_HELP = """\
    the names of the frames to use to create the unlabelling, this can be a comma separated list of frame names or
    the option can be called called multiple times. Wild cards are allowed. If no match is found wild cards are checked
    as well  unless --exact is set. Frames can be from any category if --residue-types is used otherwise they should be
    nmr_spetra [aka peak lists]. If no frames are selected and --residue-types is set the default chemical shift list is
    used otherwise all peak lists are used.
"""

NAME_TEMPLATE_HELP = """
    the name template for the new peak lists the placeholders {spectrum} and {residues} will get replaced with the
    spectrum name and the unlabelled residues respectively
"""

RESIDUE_TYPES_HELP = """\
output a residue type list rather than simulated peaks, each residue type will be an anonymous residue with the same
sequence code as the assigned reside i.e.
    A 74 VAL H -> @- @74 '' H.
The format of the residue type list can be printed using the --residue-types-format option
"""

DISPLAY_RESIDUE_TYPES_FORMAT_HELP = (
    "display the NEF format used by the --residue-types option"
)

RESIDUE_TYPES_FORMAT = """
    The Format of the residue type list is

    save_nefpls_residue_types_default
       _nefpls.sf_category nefpls_residue_types
       _nefpls.sf_framecode nefpls_residue_types_default

       loop_
            _nefpls_residue_type.index
            _nefpls_residue_type.chain_code
            _nefpls_residue_type.sequence_code
            _nefpls_residue_type.residue_type
            _nefpls_residue_type.probability

            1    @-     @1      ALA    0.3
            2    @-     @1      ARG    0.5
            3    @-     @2-1    ASN    .
            4    @-     @2-1    ASP    .
            5    #2     @2      CYS    0.2
            6    #2     @2      LEU    0.8
            7    #2     @3      VAL    0.2
            8    #2     @3      SER    0.8

    In this case default is the name of the list, the list should have a name
    The chain_code and sequence_code should be for unassigned chains and residues, the residue code can include
    a sequence offset
    The labelled_residue flag indicates that the residue
    Probability can be used to give the probability of a particular residue type / . for the default probability
    which would be the 1 / <number-of-residues-in-group> [optional]
    these probabilities should be normalised by the program that uses them.

    note contradictory assignments should cause an error in the program reading the list
"""


@dataclass
class Unlabellinglevel:
    target_residues: AminoAcid
    level: float
    cross_residues: Dict[AminoAcid, float]


# these values are _estimated_ from the graphs in the supplementary material of Bellstedt, P. et al. Resonance
# assignment for a particularly challenging protein based on systematic unlabeling of amino acids to complement
# incomplete NMR data sets. J Biomol Nmr 57, 65 72 (2013).

#
# _RAW_SCRAMBLING_14N_GB1 = {
#     "Ala": (
#         0.0,
#         ("Val", 0.62,),
#         (ANY_RESIDUE, 1.15)
#     ),
#     "Arg": (
#         0.0,
#         (ANY_RESIDUE, 1.10),
#     ),
#     "Asn": (
#         0.0,
#         (ANY_RESIDUE, 0.9)
#     ),
#     "Asp": (
#         0.6,
#         (ANY_RESIDUE, 0.6)  # not included leads to uniform unlabelling
#     ),
#     "Cys": (
#         0.0,
#         (ANY_RESIDUE, 0.95)
#     ),
#
#     "Gln": (
#         0.02,
#         (ANY_RESIDUE, 0.3)
#     ),
#
#     "Glu": (
#         0.45,
#         (ANY_RESIDUE, 0.45)
#     ),
#
#     "Gly": (
#         0.0,
#         ("Trp", 0.5),
#         (ANY_RESIDUE, 0.95)
#     ),
#
#     "His": (
#         0.0,
#         (ANY_RESIDUE, 0.9)
#     ),
#     "Ile": (
#        0.25,
#        ("Leu", 0.4),
#        ("Val", 0.4),
#        (ANY_RESIDUE, 0.95)
#     ),
#     "Leu": (
#         0.19,
#         ('Ile', 0.2),
#         ('Val', 0.3),
#         (ANY_RESIDUE, 0.85)
#     ),
#     "Lys": (
#         0.02,
#         (ANY_RESIDUE, 1.10)
#     ),
#     "Met": (
#         0.0,
#         (ANY_RESIDUE, 1.10)
#     ),
#     "Phe": (
#         0.3,
#         ("Tyr", 0.35),
#         ("Ile", 0.78),
#         ('Leu', 0.8),
#         ('Val', 0.80),
#         (ANY_RESIDUE, 0.9)
#     ),
#     "Pro": (
#         0.0,
#         (ANY_RESIDUE, 0.90)
#     ),
#     "Ser": (
#         0.0,
#         (ANY_RESIDUE, 0.95)
#     ),
#     "Thr": (
#         0.0,
#         ("Gly", 0.0),
#         ("Trp", 0.5),
#         ("Lys", 0.90),
#         ("Tyr", 0.90),
#         (ANY_RESIDUE, 0.80),
#
#     ),
#     "Trp": (
#         0.2,
#         ("Phe", 0.3),
#         ("Tyr", 0.3),
#         (ANY_RESIDUE, 0.7)
#     ),
#     "Tyr": (
#         0.45,
#         ("Phe", 0.55),
#         (ANY_RESIDUE, 0.95)
#     ),
#     "Val": (
#         0.15,
#         ("Ile", 0.5),
#         ("Leu", 0.55),
#         ('Ala', 0.82),
#         (ANY_RESIDUE, 1.00)
#     ),
# }

_RAW_SCRAMBLING_14N_GB1 = {
    AminoAcid.ALA: (
        0.0,
        (
            AminoAcid.VAL,
            0.62,
        ),
        (AminoAcid.ANY, 1.15),
    ),
    AminoAcid.ARG: (
        0.0,
        (AminoAcid.ANY, 1.10),
    ),
    AminoAcid.ASN: (0.0, (AminoAcid.ANY, 0.9)),
    AminoAcid.ASP: (0.6, (AminoAcid.ANY, 0.6)),
    AminoAcid.CYS: (0.0, (AminoAcid.ANY, 0.95)),
    AminoAcid.GLN: (0.02, (AminoAcid.ANY, 0.3)),
    AminoAcid.GLU: (0.45, (AminoAcid.ANY, 0.45)),
    AminoAcid.GLY: (0.0, (AminoAcid.TRP, 0.5), (AminoAcid.ANY, 0.95)),
    AminoAcid.HIS: (0.0, (AminoAcid.ANY, 0.9)),
    AminoAcid.ILE: (
        0.25,
        (AminoAcid.LEU, 0.4),
        (AminoAcid.VAL, 0.4),
        (AminoAcid.ANY, 0.95),
    ),
    AminoAcid.LEU: (
        0.19,
        (AminoAcid.ILE, 0.2),
        (AminoAcid.VAL, 0.3),
        (AminoAcid.ANY, 0.85),
    ),
    AminoAcid.LYS: (0.02, (AminoAcid.ANY, 1.10)),
    AminoAcid.MET: (0.0, (AminoAcid.ANY, 1.10)),
    AminoAcid.PHE: (
        0.3,
        (AminoAcid.TYR, 0.35),
        (AminoAcid.ILE, 0.78),
        (AminoAcid.LEU, 0.8),
        (AminoAcid.VAL, 0.80),
        (AminoAcid.ANY, 0.9),
    ),
    AminoAcid.PRO: (0.0, (AminoAcid.ANY, 0.90)),
    AminoAcid.SER: (0.0, (AminoAcid.ANY, 0.95)),
    AminoAcid.THR: (
        0.0,
        (AminoAcid.GLY, 0.0),
        (AminoAcid.TRP, 0.5),
        (AminoAcid.LYS, 0.90),
        (AminoAcid.TYR, 0.90),
        (AminoAcid.ANY, 0.80),
    ),
    AminoAcid.TRP: (
        0.2,
        (AminoAcid.PHE, 0.3),
        (AminoAcid.TYR, 0.3),
        (AminoAcid.ANY, 0.7),
    ),
    AminoAcid.TYR: (0.45, (AminoAcid.PHE, 0.55), (AminoAcid.ANY, 0.95)),
    AminoAcid.VAL: (
        0.15,
        (AminoAcid.ILE, 0.5),
        (AminoAcid.LEU, 0.55),
        (AminoAcid.ALA, 0.82),
        (AminoAcid.ANY, 1.00),
    ),
}

SCRAMBLING_14N_GB1 = {
    residue_name: Unlabellinglevel(residue_name, level, dict(cross_residues))
    for residue_name, (level, *cross_residues) in _RAW_SCRAMBLING_14N_GB1.items()
}


# _RAW_SCRAMBLING_14N_APRAYAXIN = {
#     "Ala": (
#         0.0,
#         ("Val", 0.50,),
#         (ANY_RESIDUE, 0.85)
#     ),
#     "Arg": (
#         0.0,
#         (ANY_RESIDUE, 0.95),
#     ),
#     "Asn": (
#         0.0,
#         (ANY_RESIDUE, 0.88)
#     ),
#     "Asp": (
#         0.45,
#         (ANY_RESIDUE, 0.45)  # not included leads to uniform unlabelling
#     ),
#     "Cys": (
#         0.0,
#         ("Ala", 0.3),
#         ("Arg", 0.7),
#         ("Lys", 0.55),
#         ("Thr", 0.75),
#         ("Trp", 0.85),
#         ("Val", 0.85),
#         (ANY_RESIDUE, 0.95)
#     ),
#     "Gln": (
#         0.05,
#         (ANY_RESIDUE, 0.25)
#     ),
#     "Glu": (
#         0.45,
#         (ANY_RESIDUE, 0.45)
#     ),
#     "Gly": (
#         0.0,
#         ("Ala", 0.85),
#         ("Cys", 0.0),
#         ("Ser", 0.0),
#         ("Trp", 0.60),
#         (ANY_RESIDUE, 0.95),
#     ),
#     "His": (
#         0.0,
#         (ANY_RESIDUE, 0.85)
#     ),
#     "Ile": (
#         0.20,
#         ("Ala", 0.65),
#         ("Leu", 0.325),
#         ("Val", 0.35),
#         (ANY_RESIDUE, 0.80)
#     ),
#     'Leu': (
#         0.20,
#         ('Ala', 0.65),
#         ('Ile', 0.20),
#         ('Val', 0.35),
#         (ANY_RESIDUE, 0.80)
#     ),
#     "Lys": (
#         0.02,
#         (ANY_RESIDUE, 0.90)
#     ),
#     "Met": (
#         0.3,
#         ("Phe", 0.80),
#         ("Tyr", 0.80),
#         (ANY_RESIDUE, 0.90)
#     ),
#     "Pro": (
#         0.0,
#         (ANY_RESIDUE, 0.70)
#     ),
#     "Ser": (
#         0.55,
#         (ANY_RESIDUE, 0.55)
#     ),
#     "Thr": (
#         0.0,
#         ("Cys", 0.25),
#         ("Gly", 0.0),
#         ("Ser", 0.05),
#         ("Trp", 0.70),
#         (ANY_RESIDUE, 0.90)
#     ),
#     "Trp": (
#         0.45,
#         ("Phe", 0.6),
#         ("Tyr", 0.3),
#         (ANY_RESIDUE, 0.80)
#     ),
#     "Tyr": (
#         0.50,
#         ("Phe", 0.65),
#         ("Trp", 0.7),
#         (ANY_RESIDUE, 0.80)
#     ),
#     "Val": (
#         0.15,
#         ("Ala", 0.65),
#         ("Ile", 0.45),
#         ("Leu", 0.50),
#         (ANY_RESIDUE, 0.85)
#     ),
# }

_RAW_SCRAMBLING_14N_APRAYAXIN = {
    AminoAcid.ALA: (
        0.0,
        (
            AminoAcid.VAL,
            0.50,
        ),
        (AminoAcid.ANY, 0.85),
    ),
    AminoAcid.ARG: (
        0.0,
        (AminoAcid.ANY, 0.95),
    ),
    AminoAcid.ASN: (0.0, (AminoAcid.ANY, 0.88)),
    AminoAcid.ASP: (
        0.45,
        (AminoAcid.ANY, 0.45),  # not included leads to uniform unlabelling
    ),
    AminoAcid.CYS: (
        0.0,
        (AminoAcid.ALA, 0.3),
        (AminoAcid.ARG, 0.7),
        (AminoAcid.LYS, 0.55),
        (AminoAcid.THR, 0.75),
        (AminoAcid.TRP, 0.85),
        (AminoAcid.VAL, 0.85),
        (AminoAcid.ANY, 0.95),
    ),
    AminoAcid.GLN: (0.05, (AminoAcid.ANY, 0.25)),
    AminoAcid.GLU: (0.45, (AminoAcid.ANY, 0.45)),
    AminoAcid.GLY: (
        0.0,
        (AminoAcid.ALA, 0.85),
        (AminoAcid.CYS, 0.0),
        (AminoAcid.SER, 0.0),
        (AminoAcid.TRP, 0.60),
        (AminoAcid.ANY, 0.95),
    ),
    AminoAcid.HIS: (0.0, (AminoAcid.ANY, 0.85)),
    AminoAcid.ILE: (
        0.20,
        (AminoAcid.ALA, 0.65),
        (AminoAcid.LEU, 0.325),
        (AminoAcid.VAL, 0.35),
        (AminoAcid.ANY, 0.80),
    ),
    AminoAcid.LEU: (
        0.20,
        (AminoAcid.ALA, 0.65),
        (AminoAcid.ILE, 0.20),
        (AminoAcid.VAL, 0.35),
        (AminoAcid.ANY, 0.80),
    ),
    AminoAcid.LYS: (0.02, (AminoAcid.ANY, 0.90)),
    AminoAcid.MET: (
        0.3,
        (AminoAcid.PHE, 0.80),
        (AminoAcid.TYR, 0.80),
        (AminoAcid.ANY, 0.90),
    ),
    AminoAcid.PRO: (0.0, (AminoAcid.ANY, 0.70)),
    AminoAcid.SER: (0.55, (AminoAcid.ANY, 0.55)),
    AminoAcid.THR: (
        0.0,
        (AminoAcid.CYS, 0.25),
        (AminoAcid.GLY, 0.0),
        (AminoAcid.SER, 0.05),
        (AminoAcid.TRP, 0.70),
        (AminoAcid.ANY, 0.90),
    ),
    AminoAcid.TRP: (
        0.45,
        (AminoAcid.PHE, 0.6),
        (AminoAcid.TYR, 0.3),
        (AminoAcid.ANY, 0.80),
    ),
    AminoAcid.TYR: (
        0.50,
        (AminoAcid.PHE, 0.65),
        (AminoAcid.TRP, 0.7),
        (AminoAcid.ANY, 0.80),
    ),
    AminoAcid.VAL: (
        0.15,
        (AminoAcid.ALA, 0.65),
        (AminoAcid.ILE, 0.45),
        (AminoAcid.LEU, 0.50),
        (AminoAcid.ANY, 0.85),
    ),
}

SCRAMBLING_14N_APRATAXIN = {
    residue_name: Unlabellinglevel(residue_name, level, dict(cross_residues))
    for residue_name, (level, *cross_residues) in _RAW_SCRAMBLING_14N_APRAYAXIN.items()
}


@simulate_app.command()
def unlabelling(
    context: typer.Context,
    input: Path = typer.Option(
        Path("-"),
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="where to read NEF data from either a file or stdin '-'",
    ),
    frame_selectors: List[str] = typer.Option(
        None, "--peak-selected_frames", metavar=None, help=FRAME_SELECTORS_HELP
    ),
    exact: bool = typer.Option(False, "--exact", help="match the frame names exactly"),
    name_template: str = typer.Option(
        UNLABELLED_SPECTRUM_NAME_TEMPLATE, help=NAME_TEMPLATE_HELP
    ),
    list_sets: bool = typer.Option(
        False, "--list", help="list the available amino acid sets"
    ),
    residue_types: bool = typer.Option(
        False, "--residue-types", help=RESIDUE_TYPES_HELP
    ),
    display_residue_types_format: bool = typer.Option(
        False, "--residue-type-format", help=DISPLAY_RESIDUE_TYPES_FORMAT_HELP
    ),
    unlabelled_amino_acids_and_sets: List[str] = typer.Argument(
        None, help=UNLABELLED_AMINO_ACIDS_AND_SETS_HELP
    ),
):
    """-  make a set of synthetic peaks for a 14N/15N unlabelling experiment NMR using input shifts or peaks
    data from Bellstedt et al. J. Biomol. Nmr 57, 65-72 (2013) doi:10.1007/s10858-013-9768-0
    """

    _list_labeling_sets_and_exit_if_list_true(list_sets)

    _display_residue_types_format_and_exit_if_format_true(display_residue_types_format)

    unlabelled_amino_acids_and_sets = parse_comma_separated_options(
        unlabelled_amino_acids_and_sets
    )

    unlabelled_amino_acids_and_sets = _expand_labelling_sets(
        unlabelled_amino_acids_and_sets
    )

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    all_unknown_amino_acids = {
        amino_acid
        for amino_acid in unlabelled_amino_acids_and_sets
        if amino_acid.upper() not in ALL_AMINO_ACIDS
    }

    _exit_if_residues_are_unknown(all_unknown_amino_acids)

    if not unlabelled_amino_acids_and_sets:
        unlabelled_amino_acids_and_sets = NO_OBV_CLEAN_SET

    if not frame_selectors:
        # TODO exact is not used here!
        if residue_types:
            selected_frames = select_frames(
                entry, "nef_chemical_shift_list_default", SelectionType.NAME
            )
        else:
            selected_frames = select_frames(
                entry, "nef_nmr_spectrum", SelectionType.CATEGORY
            )

    else:
        selected_frames = select_frames_by_name(entry, frame_selectors, exact=exact)

        msg = f"""
            using the selectors {', '.join(frame_selectors)} and with residue_types {residue_types}
            I couldn't find any frames to use in the entry {entry.entry_id}
        """
        exit_error(msg)

    entry = pipe(
        entry,
        selected_frames,
        unlabelled_amino_acids_and_sets,
        name_template,
        output_residue_typing=residue_types,
    )

    print(entry)


def pipe(
    entry: Entry,
    selected_frames: List[Saveframe],
    unlabelled_residues: List[str],
    name_template_string: str,
    output_residue_typing: bool = False,
) -> Entry:

    # this could be almost anyting that has a sequence code and a residue name
    shift_frames = [
        frame
        for frame in selected_frames
        if frame.category in {"nef_chemical_shift_list", "nef_molecular_system"}
    ]
    peak_frames = [
        frame for frame in selected_frames if frame.category == "nef_nmr_spectrum"
    ]

    if not shift_frames and not peak_frames:
        exit_error("working with peak frames not implemented yet..., bug gary!")

    frames = []

    if output_residue_typing:
        if peak_frames:
            msg = """
                I can't output residue types from peak frames currently (bug gary!)
            """
            exit_error(msg)

        frames.append(_make_residue_typing_table(shift_frames, unlabelled_residues))

    else:
        if shift_frames:
            # TODO different naming for peaks and shifts frame functions
            shifts = nef_frames_to_shifts(shift_frames)

            shifts = [shift for shift in shifts if shift.atom.atom_name in ["H", "N"]]

            shifts = _average_equivalent_shifts(shifts)

            spectrum_info = EXPERIMENT_INFO[SPECTRUM_TYPE_NHSQC]

            peaks = _make_spectrum(shifts, spectrum_info)

        elif peak_frames:

            peaks = frame_to_peaks(peak_frames)
        else:
            msg = """
                No peaks or frames were selected to base the ¹H-¹⁵N HSQC to unlabelled spectrum on
            """
            exit_error(msg)

        # todo check there are some 1H 15N pairs

        if peaks:
            for target_residue in unlabelled_residues:
                # for template expansion
                residues = target_residue  # noqa: F841
                spectrum = entry.entry_id  # noqa: F841
                frame_name = f(name_template_string)

                frames.append(
                    _make_spectrum_frame(
                        peaks, target_residue, spectrum_info, frame_name
                    )
                )
        else:

            cause = "shifts" if shift_frames else "peaks"

            exit_error(
                f"couldn't build a ¹H-¹⁵N HSQC to unlabel because i couldn't find any {cause}"
            )

    for frame in frames:
        entry.add_saveframe(frame)

    return entry


def _make_residue_typing_table(selected_frames, unlabelled_residues):

    frame = create_nef_save_frame(f"{NEF_PIPELINES_PREFIX}_residue_types", "default")

    loop = Loop.from_scratch(f"{NEF_PIPELINES_PREFIX}_residue_type")

    for tag in ["index", "chain_code", "sequence_code", "residue_type", "probability"]:
        loop.add_tag(tag)

    frame.add_loop(loop)
    sequence = sequences_from_frames(selected_frames)
    residues_to_list = []

    for residue in sequence:
        if residue.residue_name in unlabelled_residues:
            residues_to_list.append(residue)

    for index, residue in enumerate(residues_to_list, start=1):
        row = {
            "index": index,
            "chain_code": residue.chain_code,
            "sequence_code": residue.sequence_code,
            "residue_type": residue.residue_name,
            "probability": UNUSED,
        }
        loop.add_data(
            [
                row,
            ]
        )

    return frame


def _make_spectrum_frame(
    peaks,
    target_residue,
    spectrum_info,
    frame_name,
    spectrometer_frequency=FAKE_SPECTROMETER_FREQUENCY_600,
):
    if target_residue == AminoAcid.REF:
        peaks = deepcopy(peaks)
    else:
        peaks = _unlabel_peaks(
            deepcopy(peaks),
            target_residue,
            [SCRAMBLING_14N_APRATAXIN, SCRAMBLING_14N_GB1],
        )

    dimensions = [{"axis_code": dimension} for dimension in spectrum_info.dimensions]
    spectrum_classification = SPECTRUM_TYPE_TO_CLASSIFICATION[ExperimentType.N_HSQC]
    extra_tags = {
        EXPERIMENT_CLASSIFICATION: spectrum_classification,
        EXPERIMENT_TYPE: EXPERIMENT_CLASSIFICATION_TO_SYNONYM[spectrum_classification],
    }
    return peaks_to_frame(
        peaks, dimensions, spectrometer_frequency, frame_name, extra_tags=extra_tags
    )


def _average_equivalent_shifts(shifts):

    shifts_by_atom = {}

    for shift in shifts:
        atom = shift.atom

        shifts_by_atom.setdefault(atom, []).append(shift)

    for atom, shifts in shifts_by_atom.items():
        if len(shifts) > 1:
            shifts = [ufloat(shift.value, shift.value_uncertainty) for shift in shifts]
            mean_shift = sum(shift) / len(shifts)

            new_shift = replace(
                shifts[0],
                value=mean_shift.nominal_value,
                uncertainty=mean_shift.std_dev,
            )

            shifts_by_atom[atom] = [
                new_shift,
            ]

    return [shift[0] for shift in shifts_by_atom.values()]


def _unlabel_peaks(peaks, unlabeled_residue, unlabelling_patterns):

    pattern_for_residue = None
    for pattern in unlabelling_patterns:
        if unlabeled_residue in pattern:
            pattern_for_residue = pattern[unlabeled_residue]

    cross_residues = pattern_for_residue.cross_residues
    general_modulation = pattern_for_residue.cross_residues[AminoAcid.ANY]

    modulated_peaks = []
    for peak in peaks:
        residue_names = set([shift.atom.residue.residue_name for shift in peak.shifts])

        if len(residue_names) != 1:
            exit_error(
                "INTERNAL ERROR: unlabelling is only supported for peaks with a single residue type"
            )

        residue = residue_names.pop()

        height = peak.height
        volume = peak.volume
        if residue == unlabeled_residue:
            height *= pattern_for_residue.level
            volume *= pattern_for_residue.level
        else:
            modulation = (
                cross_residues[residue]
                if residue in cross_residues
                else general_modulation
            )
            height *= modulation
            volume *= modulation

        modulated_peaks.append(replace(peak, height=height, volume=volume))

    return modulated_peaks


def _exit_if_residues_are_unknown(all_unknown_amino_acids):
    if all_unknown_amino_acids:
        msg = f"""\
            I don't have unlabelling information for the following residues:
            {', '.join(all_unknown_amino_acids)}
        """
        exit_error(msg)


def _display_residue_types_format_and_exit_if_format_true(format: bool):
    if format:
        print(RESIDUE_TYPES_FORMAT, file=sys.stderr)
        print()
        print("exiting...")
        sys.exit(0)


def _expand_labelling_sets(unlabelled_amino_acids_and_sets):
    expanded_unlabelled_amino_acids_and_sets = set()
    for residue_or_set in unlabelled_amino_acids_and_sets:
        if residue_or_set in LABELING_SETS:
            if residue_or_set == "REMOVE_OBVIOUS":
                expanded_unlabelled_amino_acids_and_sets -= OBVIOUS_SHIFT_SET
            else:
                expanded_unlabelled_amino_acids_and_sets.update(
                    LABELING_SETS[residue_or_set]
                )
        else:
            expanded_unlabelled_amino_acids_and_sets.add(residue_or_set)
    return expanded_unlabelled_amino_acids_and_sets


def _list_labeling_sets_and_exit_if_list_true(list: bool):
    if list:
        table = []
        for name, description in LABELING_SET_HELP.items():
            table.append([name, description])
            amino_acids = [value.name for value in LABELING_SETS[name]]
            table.append(["", ", ".join(amino_acids)])
            table.append(["", ""])
        print()
        print(tabulate(table, headers=["Name", "Description"]))
        print("\nexiting...")
        sys.exit(0)
