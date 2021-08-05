import string
from textwrap import dedent
from typing import List, Iterable, Dict

from pynmrstar import Saveframe, Loop

from lib.structures import SequenceResidue
from lib.constants import NEF_UNKNOWN


def chain_code_iter(user_chain_codes: str = '') -> Iterable[str]:
    """
    split input string into chain codes separated by .s, and yield them.
    Then yield any remaining letters of the alphabet till they run out

    Args:
        user_chain_codes (str):  string of dot separated chain codes

    Returns:
        Iterable[str] single codes
    """

    ascii_uppercase = list(string.ascii_uppercase)
    chain_codes = user_chain_codes.split('.') if user_chain_codes else ascii_uppercase

    seen_codes = set()

    for chain_code in chain_codes:
        seen_codes.add(chain_code)
        yield chain_code

    for chain_code in ascii_uppercase:
        if chain_code not in seen_codes:
            yield chain_code

    raise ValueError('run out of chain names!')


def get_linking(target_index, target_sequence: List[SequenceResidue], no_start=False, no_end=False) -> str:

    """
        get the correct linking for residue in a standard sequenced chain

        Args:
            target_index (int):  index in the sequence
            target_sequence (List[SequenceResidue]) : the sequence
            no_start (bool): if true don't cap the chain start
            no_end (bool): if true don't cap the chain end

        Returns:
            str: a linkage
    """

    result = 'middle'
    if target_index == 0 and not no_start:
        result = 'start'
    if target_index + 1 == len(target_sequence) and not no_end:
        result = 'end'
    return result


def sequence_to_nef_frame(input_sequence: List[SequenceResidue], entry_name: str) -> Saveframe:
    """

    Args:
        input_sequence (List[SequenceResidue]): the sequence
        entry_name (str): the name of the entry

    Returns:
        Saveframe: a NEF saveframe
    """

    category = "nef_molecular_system"

    frame_code = f'{category}_{entry_name}'

    nef_frame = Saveframe.from_scratch(frame_code, category)

    nef_frame.add_tag("sf_category", category)
    nef_frame.add_tag("sf_framecode", frame_code)

    nef_loop = Loop.from_scratch('nef_sequence')
    nef_frame.add_loop(nef_loop)

    tags = ('index', 'chain_code', 'sequence_code', 'residue_name', 'linking', 'residue_variant', 'cis_peptide')

    nef_loop.add_tag(tags)

    # TODO need tool to set ionisation correctly
    for index, sequence_residue in enumerate(input_sequence):
        linking = get_linking(index, input_sequence)

        nef_loop.add_data_by_tag('index', index + 1)
        nef_loop.add_data_by_tag('chain_code', sequence_residue.chain)
        nef_loop.add_data_by_tag('sequence_code', sequence_residue.residue_number)
        nef_loop.add_data_by_tag('residue_name', sequence_residue.residue_name.upper())
        nef_loop.add_data_by_tag('linking', linking)
        nef_loop.add_data_by_tag('residue_variant', NEF_UNKNOWN)
        nef_loop.add_data_by_tag('cis_peptide', NEF_UNKNOWN)

    return nef_frame

TRANSLATIONS_3_1 = {
    'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D',
    'CYS': 'C', 'GLU': 'E', 'GLN': 'Q', 'GLY': 'G', 'HIS': 'H',
    'ILE': 'I', 'LEU': 'L', 'LYS': 'K', 'MET': 'M',
    'PHE': 'F', 'PRO': 'P', 'SER': 'S', 'THR': 'T',
    'TRP': 'W', 'TYR': 'Y', 'VAL': 'V'
}
TRANSLATIONS_1_3 = {value: key for (key, value) in TRANSLATIONS_3_1.items()}


class BadResidue(Exception):
    """
    Bad residue found in a sequence
    """
    pass


def translate_1_to_3(sequence: str, translations: Dict[str, str] = TRANSLATIONS_1_3) -> List[str]:
    """
    Translate a 1 letter sequence to a 3 letter sequence
    Args:
        sequence (str): 1 letter sequence
        translations (Dict[str, str]): a list of translations for single amino acid codes to 3 letter residue names

    Returns List[str]:
        a list of 3 residue codes

    """
    result = []
    for i, residue_name_1let in enumerate(sequence):
        residue_name_1let = residue_name_1let.upper()
        if residue_name_1let in translations:
            result.append(translations[residue_name_1let])
        else:
            msg = f'''\
                 unknown residue {residue_name_1let} at residue {i+1}
                 sequence: {sequence}
                           {(' ' * i) + '^'}      
            '''
            msg = dedent(msg)
            raise BadResidue(msg)

    return result


def sequence_3let_to_sequence_residues(sequence_3let: List[str], chain_code: str = 'A', offset: int = 0) -> List[SequenceResidue]:
    """
    Translate a list of 3 residue sequence codes to SequenceResidues
    Args:
        sequence_3let (List([str]): list of 3 letter residue names
        chain_code (str): the chain code [defaults to A]
        offset (int): the sequence offset [defaults to 0]

    Returns List[SequenceResidue]:
        the sequence as a list of SequenceResidues

    """
    return [SequenceResidue(chain_code, i + 1 + offset, residue) for (i, residue) in enumerate(sequence_3let)]
