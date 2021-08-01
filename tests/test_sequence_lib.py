from textwrap import dedent

import pytest

from lib.sequence_lib import translate_1_to_3, sequence_3let_to_sequence_residues, BadResidue
from lib.structures import SequenceResidue

ABC_SEQUENCE_1LET = 'acdefghiklmnpqrstvwy'
ABC_SEQUENCE_3LET = (
        'ALA',
        'CYS',
        'ASP',
        'GLU',
        'PHE',
        'GLY',
        'HIS',
        'ILE',
        'LYS',
        'LEU',
        'MET',
        'ASN',
        'PRO',
        'GLN',
        'ARG',
        'SER',
        'THR',
        'VAL',
        'TRP',
        'TYR'
)

ABC_SEQUENCE_RESIDUES = [SequenceResidue('A', i+1, residue) for (i, residue) in enumerate(ABC_SEQUENCE_3LET)]


def test_1let_3let():

    assert len(ABC_SEQUENCE_1LET) == 20
    assert len(ABC_SEQUENCE_3LET) == 20

    assert list(ABC_SEQUENCE_3LET) == translate_1_to_3(ABC_SEQUENCE_1LET)


def test_bad_1let_3let():
    BAD_SEQUENCE = 'acdefghiklmonpqrstvwy'

    msgs = '''\
              unknown residue O
              at residue 12
              sequence: acdefghiklmonpqrstvwy
              ^
              '''

    msgs = dedent(msgs)
    msgs = msgs.split('\n')

    with pytest.raises(BadResidue) as exc_info:
        translate_1_to_3(BAD_SEQUENCE)

    for msg in msgs:
        assert msg in exc_info.value.args[0]


def test_3let_sequence_residue():

    sequence_residues = sequence_3let_to_sequence_residues(ABC_SEQUENCE_3LET)

    assert sequence_residues == ABC_SEQUENCE_RESIDUES


def test_3let_sequence_residue_diff_chain():
    sequence_residues = sequence_3let_to_sequence_residues(ABC_SEQUENCE_3LET, chain_code='B')

    expected = [SequenceResidue('B', residue.residue_number, residue.residue_name) for residue in ABC_SEQUENCE_RESIDUES]

    assert sequence_residues == expected


def test_3let_sequence_residue_offset():
    sequence_residues = sequence_3let_to_sequence_residues(ABC_SEQUENCE_3LET, offset=-10)

    expected = [SequenceResidue(residue.chain, residue.residue_number-10, residue.residue_name) for residue in ABC_SEQUENCE_RESIDUES]

    assert sequence_residues == expected


if __name__ == '__main__':
    pytest.main([f'{__file__}', '-vv'])