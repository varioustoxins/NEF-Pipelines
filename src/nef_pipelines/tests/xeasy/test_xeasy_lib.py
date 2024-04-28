import pytest

from nef_pipelines.lib.sequence_lib import sequence_to_residue_name_lookup
from nef_pipelines.lib.structures import (
    AtomLabel,
    DimensionInfo,
    NewPeak,
    Residue,
    SequenceResidue,
    ShiftData,
)
from nef_pipelines.lib.test_lib import path_in_test_data, read_test_data
from nef_pipelines.transcoders.xeasy.xeasy_lib import (
    parse_peaks,
    parse_sequence,
    parse_shifts,
)

EXPECTED_SEQUENCE = [
    SequenceResidue(*residue.split())
    for residue in [
        "A 1 HIS",
        "A 2 MET",
        "A 3 ARG",
        "A 4 GLN",
        "A 5 THR",
        "A 6 MET",
        "A 7 LEU",
        "A 8 VAL",
        "A 9 THR",
    ]
]


def test_sequence_basic():
    sequence = read_test_data("basic.seq", __file__).split("\n")

    result = parse_sequence(sequence)
    assert result == EXPECTED_SEQUENCE


def test_sequence_basic_commented():
    sequence = read_test_data("basic.seq", __file__).split("\n")
    sequence = ["#a comment", *sequence]

    result = parse_sequence(sequence)
    assert result == EXPECTED_SEQUENCE


def test_sequence_basic_commented_two_lines_bad():
    with open(path_in_test_data(__file__, "basic.seq")) as fh:
        sequence = fh.readlines()

    with pytest.raises(SystemExit) as e:
        sequence = ["#a comment", "# a bad comment", *sequence]
        parse_sequence(sequence)

    assert e.type == SystemExit
    assert e.value.code == 1


EXPECTED_DIMENSIONS = [
    DimensionInfo(*dimension.split())
    for dimension in ["H1  HN ppm", "H1  H  ppm", "N15 N  ppm"]
]

EXPECTED_PEAKS = [
    NewPeak(
        [
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "2",
                        "MET",
                    ),
                    "H",
                ),
                8.731,
            ),
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "3",
                        "ARG",
                    ),
                    "H",
                ),
                8.723,
            ),
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "4",
                        "GLN",
                    ),
                    "N",
                ),
                115.265,
            ),
        ],
        id=1,
        volume=5.5,
        volume_uncertainty=0.0,
        comment="MAP    403",
    ),
    NewPeak(
        [
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        ".",
                        ".",
                        ".",
                    ),
                    ".",
                ),
                8.731,
            ),
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        ".",
                        ".",
                        ".",
                    ),
                    ".",
                ),
                4.610,
            ),
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        ".",
                        ".",
                        ".",
                    ),
                    ".",
                ),
                115.275,
            ),
        ],
        id=2,
        volume=5.5,
        volume_uncertainty=0.0,
        comment=None,
    ),
    NewPeak(
        [
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "5",
                        "THR",
                    ),
                    "H",
                ),
                8.732,
            ),
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "6",
                        "MET",
                    ),
                    "HA2",
                ),
                4.192,
            ),
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "7",
                        "LEU",
                    ),
                    "N",
                ),
                115.254,
            ),
        ],
        id=3,
        volume=5.5,
        volume_uncertainty=0.0,
        comment="MAP    404",
    ),
    NewPeak(
        [
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "5",
                        "THR",
                    ),
                    "H",
                ),
                8.732,
            ),
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "6",
                        "MET",
                    ),
                    "HA3",
                ),
                4.192,
            ),
            ShiftData(
                AtomLabel(
                    SequenceResidue(
                        "A",
                        "7",
                        "LEU",
                    ),
                    "N",
                ),
                115.254,
            ),
        ],
        id=3,
        volume=5.5,
        volume_uncertainty=0.0,
        comment="MAP    405",
    ),
]


def test_basic_peaks():
    with open(path_in_test_data(__file__, "basic.peaks")) as fh:
        peaks = fh.readlines()

    lookup = sequence_to_residue_name_lookup(EXPECTED_SEQUENCE)
    spectrum_type, dimension_info, peaks = parse_peaks(
        peaks, source="unknown", residue_name_lookup=lookup
    )

    assert spectrum_type == "N15TOCSY"
    assert dimension_info == EXPECTED_DIMENSIONS

    assert peaks == EXPECTED_PEAKS


EXPECTED_SHIFTS = [
    ShiftData(
        atom=AtomLabel(
            residue=Residue(chain_code="A", sequence_code="1", residue_name="HIS"),
            atom_name="N",
            element=None,
            isotope_number=None,
        ),
        value="112.794",
        value_uncertainty="0.010",
        line_width=None,
        line_width_uncertainty=None,
    ),
    ShiftData(
        atom=AtomLabel(
            residue=Residue(chain_code="A", sequence_code="1", residue_name="HIS"),
            atom_name="HE1",
            element=None,
            isotope_number=None,
        ),
        value="7.955",
        value_uncertainty="0.010",
        line_width=None,
        line_width_uncertainty=None,
    ),
    ShiftData(
        atom=AtomLabel(
            residue=Residue(chain_code="A", sequence_code="2", residue_name="MET"),
            atom_name="N",
            element=None,
            isotope_number=None,
        ),
        value="113.996",
        value_uncertainty="0.000",
        line_width=None,
        line_width_uncertainty=None,
    ),
    ShiftData(
        atom=AtomLabel(
            residue=Residue(chain_code="A", sequence_code="2", residue_name="MET"),
            atom_name="QE",
            element=None,
            isotope_number=None,
        ),
        value="3.778",
        value_uncertainty="0.010",
        line_width=None,
        line_width_uncertainty=None,
    ),
    ShiftData(
        atom=AtomLabel(
            residue=Residue(chain_code="A", sequence_code="2", residue_name="MET"),
            atom_name="CE",
            element=None,
            isotope_number=None,
        ),
        value="27.054",
        value_uncertainty="0.010",
        line_width=None,
        line_width_uncertainty=None,
    ),
    ShiftData(
        atom=AtomLabel(
            residue=Residue(chain_code="A", sequence_code="3", residue_name="ARG"),
            atom_name="HD2",
            element=None,
            isotope_number=None,
        ),
        value="3.133",
        value_uncertainty="0.000",
        line_width=None,
        line_width_uncertainty=None,
    ),
    ShiftData(
        atom=AtomLabel(
            residue=Residue(chain_code="A", sequence_code="3", residue_name="ARG"),
            atom_name="HD3",
            element=None,
            isotope_number=None,
        ),
        value="3.134",
        value_uncertainty="0.000",
        line_width=None,
        line_width_uncertainty=None,
    ),
    ShiftData(
        atom=AtomLabel(
            residue=Residue(chain_code="A", sequence_code="3", residue_name="ARG"),
            atom_name="HE",
            element=None,
            isotope_number=None,
        ),
        value="4.378",
        value_uncertainty="0.010",
        line_width=None,
        line_width_uncertainty=None,
    ),
]


def test_basic_shifts():

    with open(path_in_test_data(__file__, "basic_shifts.prot")) as fh:
        shifts = fh.readlines()

    lookup = sequence_to_residue_name_lookup(EXPECTED_SEQUENCE)
    shifts = parse_shifts(shifts, source="unknown", residue_lookup=lookup)

    assert shifts == EXPECTED_SHIFTS
