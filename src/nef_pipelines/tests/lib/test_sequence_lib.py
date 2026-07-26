from itertools import islice
from textwrap import dedent

import pytest
from pynmrstar import Entry, Saveframe

from nef_pipelines.lib.sequence_lib import (
    AMINO_ACIDS_1LET,
    AMINO_ACIDS_3LET,
    AMINO_ACIDS_RESIDUES,
    BadResidue,
    MoleculeType,
    MoleculeTypes,
    chains_from_frames,
    count_residues_in_chain,
    get_chain_code_iter,
    get_chain_starts,
    guess_molecule_type,
    offset_chain_residues,
    sequence_3let_to_sequence_residues,
    sequences_from_frames,
    translate_1_to_3,
    translate_3_to_1,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.test_lib import path_in_test_data

# Tests for guess_molecule_type (new function)


def test_guess_molecule_type_protein():
    """Test that protein-specific codes are correctly identified."""

    EXPECTED = (MoleculeType.PROTEIN, None)

    # Protein-specific residue codes (R, N, E, Q, etc.)
    protein_codes = ["D", "R", "N", "E", "Q", "H"]

    result = guess_molecule_type(protein_codes)

    assert result == EXPECTED


def test_guess_molecule_type_dna():
    """Test that DNA-specific codes are correctly identified."""

    EXPECTED = (MoleculeType.DNA, None)

    # DNA includes Thymine (T)
    dna_codes = ["A", "C", "G", "T"]

    result = guess_molecule_type(dna_codes)

    assert result == EXPECTED


def test_guess_molecule_type_rna():
    """Test that RNA-specific codes are correctly identified."""

    EXPECTED = (MoleculeType.RNA, None)

    # RNA includes Uracil (U)
    rna_codes = ["A", "C", "G", "U"]

    result = guess_molecule_type(rna_codes)

    assert result == EXPECTED


def test_guess_molecule_type_ambiguous_returns_none():
    """Test that ambiguous codes return None with error message listing possible types."""

    # Only A, C, G - could be protein, DNA, or RNA
    ambiguous_codes = ["A", "C", "G"]

    molecule_type, error_message = guess_molecule_type(ambiguous_codes)

    assert molecule_type is None
    assert error_message is not None
    assert (
        "Cannot determine molecule type from ambiguous residue codes" in error_message
    )
    assert all(code in error_message for code in ["A", "C", "G"])
    assert "Could be: protein, dna, rna" in error_message


def test_guess_molecule_type_mixed_protein_dna():
    """Test that mixed protein/DNA codes return tuple of types with error message."""

    # Mix of protein (D, Q) and DNA (T)
    mixed_codes = ["D", "T", "Q"]

    molecule_types, error_message = guess_molecule_type(mixed_codes)

    assert isinstance(molecule_types, tuple)
    assert MoleculeType.PROTEIN in molecule_types
    assert MoleculeType.DNA in molecule_types
    assert error_message is not None
    assert "Mixed molecule types detected" in error_message
    assert all(code in error_message for code in ["D", "T", "Q"])


def test_guess_molecule_type_ambiguous_includes_codes():
    """Test that ambiguous case includes the problematic residue codes in error message."""

    ambiguous_codes = {"A", "C"}

    molecule_type, error_message = guess_molecule_type(ambiguous_codes)

    assert molecule_type is None
    assert error_message is not None
    assert all(code in error_message for code in ["A", "C"])


# Tests for translate functions (existing tests)


def test_1let_3let():

    assert list(AMINO_ACIDS_3LET) == translate_1_to_3(AMINO_ACIDS_1LET)


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


def test_3let_1let_protein_list():
    """Test translate_3_to_1 with protein sequence as list."""
    sequence = ["ALA", "CYS", "ASP", "GLU", "PHE"]
    result = translate_3_to_1(sequence)
    assert result == ["A", "C", "D", "E", "F"]


def test_3let_1let_protein_single():
    """Test translate_3_to_1 with single protein residue."""
    result = translate_3_to_1("ALA")
    assert result == "A"


def test_3let_1let_case_insensitive():
    """Test translate_3_to_1 is case-insensitive by default."""
    result = translate_3_to_1(["ala", "Cys", "ASP"])
    assert result == ["A", "C", "D"]


def test_3let_1let_case_sensitive():
    """Test translate_3_to_1 with case_sensitive=True requires exact case."""
    result = translate_3_to_1(["ALA", "CYS", "ASP"], case_sensitive=False)
    assert result == ["A", "C", "D"]

    # With case_sensitive=True, lowercase should be unknown
    result = translate_3_to_1(
        ["ala", "CYS", "ASP"], case_sensitive=True, allow_unknown=True
    )
    assert result == ["X", "C", "D"]


def test_1let_3let_case_sensitive():
    """Test translate_1_to_3 with case_sensitive=True requires exact case."""
    result = translate_1_to_3("ACD", case_sensitive=False)
    assert result == ["ALA", "CYS", "ASP"]

    result = translate_1_to_3("acd", case_sensitive=False)
    assert result == ["ALA", "CYS", "ASP"]

    # With case_sensitive=True, lowercase should fail
    result = translate_1_to_3("acd", case_sensitive=True, unknown="UNK")
    assert result == ["UNK", "UNK", "UNK"]


def test_3let_1let_dna():
    """Test translate_3_to_1 with DNA sequence."""
    sequence = ["DG", "DC", "DT", "DA"]
    result = translate_3_to_1(sequence, molecule_type=MoleculeTypes.DNA)
    assert result == ["G", "C", "T", "A"]


def test_3let_1let_rna():
    """Test translate_3_to_1 with RNA sequence."""
    sequence = ["G", "C", "A", "U"]

    result = translate_3_to_1(sequence, molecule_type=MoleculeTypes.RNA)
    assert result == ["G", "C", "A", "U"]


def test_3let_1let_unknown_allowed():
    """Test translate_3_to_1 with unknown residue and allow_unknown=True."""
    sequence = ["ALA", "YYY", "CYS"]
    result = translate_3_to_1(sequence, allow_unknown=True)
    assert result == ["A", "X", "C"]


def test_3let_1let_unknown_custom_code():
    """Test translate_3_to_1 with unknown residue and custom unknown_code."""
    sequence = ["ALA", "XXX", "CYS"]
    result = translate_3_to_1(sequence, allow_unknown=True, unknown_code="?")
    assert result == ["A", "?", "C"]


def test_3let_1let_unknown_not_allowed():
    """Test translate_3_to_1 with unknown residue and allow_unknown=False."""
    # TODO: translate_3_to_1 and translate_1_to_3 should raise proper exceptions instead of SystemExit
    sequence = ["ALA", "XXX", "CYS"]
    with pytest.raises(SystemExit):
        translate_3_to_1(sequence, allow_unknown=False)


def test_3let_sequence_residue():

    sequence_residues = sequence_3let_to_sequence_residues(AMINO_ACIDS_3LET)

    assert sequence_residues == AMINO_ACIDS_RESIDUES


def test_3let_sequence_residue_with_specified_chain():
    sequence_residues = sequence_3let_to_sequence_residues(
        AMINO_ACIDS_3LET, chain_code="B"
    )

    expected = [
        SequenceResidue("B", residue.sequence_code, residue.residue_name)
        for residue in AMINO_ACIDS_RESIDUES
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
        result[chain] = count_residues_in_chain(test_frame, chain)

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
