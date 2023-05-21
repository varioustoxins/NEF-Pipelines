import pytest

from nef_pipelines.lib.sequence_lib import residues_to_residue_name_lookup
from nef_pipelines.lib.structures import (
    AtomLabel,
    DimensionInfo,
    NewPeak,
    SequenceResidue,
    ShiftData,
)
from nef_pipelines.lib.test_lib import path_in_test_data
from nef_pipelines.transcoders.xeasy.xeasy_lib import parse_peaks, parse_sequence

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
    sequence = open(path_in_test_data(__file__, "basic.seq")).readlines()

    result = parse_sequence(sequence)
    assert result == EXPECTED_SEQUENCE


def test_sequence_basic_commented():
    sequence = open(path_in_test_data(__file__, "basic.seq")).readlines()
    sequence = ["#a comment", *sequence]

    result = parse_sequence(sequence)
    assert result == EXPECTED_SEQUENCE


def test_sequence_basic_commented_two_lines_bad():
    sequence = open(path_in_test_data(__file__, "basic.seq")).readlines()

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
    peaks = open(path_in_test_data(__file__, "basic.peaks")).readlines()

    lookup = residues_to_residue_name_lookup(EXPECTED_SEQUENCE)
    spectrum_type, dimension_info, peaks = parse_peaks(
        peaks, source="unknown", residue_name_lookup=lookup
    )

    assert spectrum_type == "N15TOCSY"
    assert dimension_info == EXPECTED_DIMENSIONS

    assert peaks == EXPECTED_PEAKS
