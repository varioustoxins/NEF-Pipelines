from itertools import islice
from textwrap import dedent

import pytest
from pynmrstar import Entry, Saveframe

from nef_pipelines.lib.sequence_lib import (
    BadResidue,
    chains_from_frames,
    count_residues,
    get_chain_code_iter,
    get_chain_starts,
    offset_chain_residues,
    sequence_3let_to_sequence_residues,
    sequences_from_frames,
    translate_1_to_3,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.test_lib import path_in_test_data

ABC_SEQUENCE_1LET = "acdefghiklmnpqrstvwy"
ABC_SEQUENCE_3LET = (
    "ALA",
    "CYS",
    "ASP",
    "GLU",
    "PHE",
    "GLY",
    "HIS",
    "ILE",
    "LYS",
    "LEU",
    "MET",
    "ASN",
    "PRO",
    "GLN",
    "ARG",
    "SER",
    "THR",
    "VAL",
    "TRP",
    "TYR",
)

ABC_SEQUENCE_RESIDUES = [
    SequenceResidue("A", i, residue)
    for (i, residue) in enumerate(ABC_SEQUENCE_3LET, start=1)
]


def test_1let_3let():

    assert len(ABC_SEQUENCE_1LET) == 20
    assert len(ABC_SEQUENCE_3LET) == 20

    assert list(ABC_SEQUENCE_3LET) == translate_1_to_3(ABC_SEQUENCE_1LET)


def test_bad_1let_3let():
    BAD_SEQUENCE = "acdefghiklmonpqrstvwy"

    msgs = """\
              unknown residue o
              at residue 12
              sequence:
              acdefghiklmonpqrstvwy
              ^
              """

    msgs = dedent(msgs)
    msgs = msgs.split("\n")

    with pytest.raises(BadResidue) as exc_info:
        translate_1_to_3(BAD_SEQUENCE)

    for msg in msgs:
        assert msg in str(exc_info.value)


def test_3let_sequence_residue():

    sequence_residues = sequence_3let_to_sequence_residues(ABC_SEQUENCE_3LET)

    assert sequence_residues == ABC_SEQUENCE_RESIDUES


def test_3let_sequence_residue_diff_chain():
    sequence_residues = sequence_3let_to_sequence_residues(
        ABC_SEQUENCE_3LET, chain_code="B"
    )

    expected = [
        SequenceResidue("B", residue.sequence_code, residue.residue_name)
        for residue in ABC_SEQUENCE_RESIDUES
    ]

    assert sequence_residues == expected


TEST_DATA_MULTI_CHAIN = """
    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide
          _nef_sequence.ccpn_comment
          _nef_sequence.ccpn_chain_role
          _nef_sequence.ccpn_compound_name
          _nef_sequence.ccpn_chain_comment

         1    A   3    HIS   .   .   .   .   .   Sec5   .
         2    A   4    MET   .   .   .   .   .   Sec5   .
         3    B   5    ARG   .   .   .   .   .   Sec5   .
         4    B   6    GLN   .   .   .   .   .   Sec5   .
         5    C   7    PRO   .   .   .   .   .   Sec5   .

       stop_

    save_

    """


def test_list_chains():

    test_frame = Saveframe.from_string(TEST_DATA_MULTI_CHAIN)
    chains = chains_from_frames(test_frame)

    assert chains == list(["A", "B", "C"])


def test_list_chains_no_chains():
    TEST_DATA = """
    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide
          _nef_sequence.ccpn_comment
          _nef_sequence.ccpn_chain_role
          _nef_sequence.ccpn_compound_name
          _nef_sequence.ccpn_chain_comment

         1    .   3    HIS   .   .   .   .   .   Sec5   .

       stop_

    save_

    """
    test_frame = Saveframe.from_string(TEST_DATA)
    chains = chains_from_frames(test_frame)

    assert chains == list([])


CHAIN_STARTS_TEST_DATA = [
    SequenceResidue(chain_code="A", sequence_code=-1, residue_name="ALA"),
    SequenceResidue(chain_code="A", sequence_code=2, residue_name="ALA"),
    SequenceResidue(chain_code="A", sequence_code="z", residue_name="ALA"),
    SequenceResidue(chain_code="B", sequence_code=2, residue_name="ALA"),
    SequenceResidue(chain_code="B", sequence_code=2, residue_name="ALA"),
    SequenceResidue(chain_code="B", sequence_code=3, residue_name="ALA"),
    SequenceResidue(chain_code="c", sequence_code="y", residue_name="ALA"),
]


def test_count_chains():
    test_frame = Saveframe.from_string(TEST_DATA_MULTI_CHAIN)

    result = {}
    for chain in "ABC":
        result[chain] = count_residues(test_frame, chain)

    EXPECTED = {"A": {"HIS": 1, "MET": 1}, "B": {"ARG": 1, "GLN": 1}, "C": {"PRO": 1}}
    assert result == EXPECTED


def test_get_chain_starts():

    EXPECTED = {
        "A": -1,
        "B": 2,
    }

    assert EXPECTED == get_chain_starts(CHAIN_STARTS_TEST_DATA)


def test_offset_chains():

    EXPECTED = [
        SequenceResidue(chain_code="A", sequence_code=1, residue_name="ALA"),
        SequenceResidue(chain_code="A", sequence_code=4, residue_name="ALA"),
        SequenceResidue(chain_code="A", sequence_code="z", residue_name="ALA"),
        SequenceResidue(chain_code="B", sequence_code=0, residue_name="ALA"),
        SequenceResidue(chain_code="B", sequence_code=0, residue_name="ALA"),
        SequenceResidue(chain_code="B", sequence_code=1, residue_name="ALA"),
        SequenceResidue(chain_code="c", sequence_code="y", residue_name="ALA"),
    ]

    offsets = {"A": 2, "B": -2, "C": 1, "D": 3}

    result = offset_chain_residues(CHAIN_STARTS_TEST_DATA, offsets)

    for pair in zip(EXPECTED, result):
        print(pair)

    assert EXPECTED == result


def test_chain_code_iter_basic():
    chain_code_iter = get_chain_code_iter()
    result = [chain_code for chain_code in islice(chain_code_iter, 3)]

    EXPECTED = list("ABC")

    assert EXPECTED == result


def test_chain_code_iter_with_user():
    chain_code_iter = get_chain_code_iter("DE")
    result = [chain_code for chain_code in islice(chain_code_iter, 3)]

    EXPECTED = list("DEA")

    assert EXPECTED == result


def test_chain_code_iter_with_exclude():
    chain_code_iter = get_chain_code_iter(exclude="BC")
    result = [chain_code for chain_code in islice(chain_code_iter, 3)]

    EXPECTED = list("ADE")

    assert EXPECTED == result


def test_sequence_from_frame():
    path = path_in_test_data(__file__, "multi_chain.nef")

    frames = Entry.from_file(path).get_saveframes_by_category("nef_molecular_system")

    sequence = sequences_from_frames(frames[0], chain_codes_to_select=["B", "C"])

    EXPECTED = [
        SequenceResidue(chain_code="B", sequence_code=5, residue_name="ARG"),
        SequenceResidue(chain_code="B", sequence_code=6, residue_name="GLN"),
        SequenceResidue(chain_code="C", sequence_code=7, residue_name="PRO"),
    ]

    assert sequence == EXPECTED


def test_sequence_from_frame_empty():
    path = path_in_test_data(__file__, "multi_chain.nef")

    frames = Entry.from_file(path).get_saveframes_by_category("nef_molecular_system")

    sequence = sequences_from_frames(frames[0], chain_codes_to_select=["D", "E"])

    EXPECTED = []

    assert sequence == EXPECTED


def test_sequence_from_frame_all():
    path = path_in_test_data(__file__, "multi_chain.nef")

    frames = Entry.from_file(path).get_saveframes_by_category("nef_molecular_system")

    sequence = sequences_from_frames(frames[0])

    EXPECTED = [
        SequenceResidue(chain_code="A", sequence_code=3, residue_name="HIS"),
        SequenceResidue(chain_code="A", sequence_code=4, residue_name="MET"),
        SequenceResidue(chain_code="B", sequence_code=5, residue_name="ARG"),
        SequenceResidue(chain_code="B", sequence_code=6, residue_name="GLN"),
        SequenceResidue(chain_code="C", sequence_code=7, residue_name="PRO"),
    ]

    assert sequence == EXPECTED
