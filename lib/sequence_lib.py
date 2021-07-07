import string
from typing import List, Iterable

from pynmrstar import Saveframe, Loop

from lib.Structures import SequenceResidue
from lib.constants import NEF_UNKNOWN


def chain_code_iter(user_chain_codes: str) -> Iterable[str]:
    """
    split input string into chain codes separated by .s, and yield them.
    Then yield any remaining letters of the alphabet till they run out

    Args:
        user_chain_codes (str):  string of dot separated chain codes

    Returns:
        Iterable[str] single codes
    """
    chain_codes = user_chain_codes.split('.') if user_chain_codes else string.ascii_uppercase.split()

    seen_codes = set()

    for chain_code in chain_codes:
        seen_codes.add(chain_code)
        yield chain_code

    for chain_code in string.ascii_uppercase.split():
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
