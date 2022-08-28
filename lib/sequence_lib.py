import string
import sys
from dataclasses import replace
from textwrap import dedent
from typing import List, Iterable, Dict, Optional, Tuple, Union

from ordered_set import OrderedSet
from pynmrstar import Saveframe, Loop, Entry

from lib.structures import SequenceResidue, Linking
from lib.constants import NEF_UNKNOWN
from lib.nef_lib import loop_to_dataframe

import pandas as pd


from lib.util import get_pipe_file, cached_stdin, exit_error, chunks, running_in_pycharm, is_int

NEF_CHAIN_CODE = 'chain_code'


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


def get_linking(target_sequence: List[SequenceResidue], no_chain_start=List[str], no_chain_end=List[str]) -> List[SequenceResidue]:

    """
        get the correct linking for residue in a standard sequenced chain

        Args:
            target_index (int):  index in the sequence
            target_sequence (List[SequenceResidue]) : the sequence
            no_chain_start (List[str]): if the chain isn't in the list cap it at the start
            no_end (List[str]): if the chain isn't in the list cap it at the end

        Returns:
             List[SequenceResidue]: correctly linked residues
    """

    by_chain = {}
    for residue in target_sequence:
        by_chain.setdefault(residue.chain_code, []).append((residue,'middle'))

    result = []
    for chain, residues_and_linkages in by_chain.items():

        if chain not in no_chain_start:
            residues_and_linkages[0] = (residues_and_linkages[0][0], 'start')

        if chain not in no_chain_end:
            residues_and_linkages[-1] = (residues_and_linkages[-1][0], 'end')

        result.extend(residues_and_linkages)

    return result


def sequence_to_nef_frame(sequences: List[SequenceResidue], no_chain_start: Union[List[str],Tuple[str]]=(), no_chain_end: Union[List[str],Tuple[str]]=()) -> Saveframe:
    """

    Args:
        sequences (List[SequenceResidue]): the sequence as a list of sequence residues [will be sorted]
        no_chain_start (List[str]): if the chain isn't in the list cap it at the start
        no_chain_end (List[str]): if the chain isn't in the list cap it at the end

    Returns:
        Saveframe: a NEF saveframe
    """

    sequences = sorted(sequences)

    category = "nef_molecular_system"

    frame_code = f'{category}'

    nef_frame = Saveframe.from_scratch(frame_code, category)

    nef_frame.add_tag("sf_category", category)
    nef_frame.add_tag("sf_framecode", frame_code)

    nef_loop = Loop.from_scratch('nef_sequence')
    nef_frame.add_loop(nef_loop)

    tags = ('index', 'chain_code', 'sequence_code', 'residue_name', 'linking', 'residue_variant', 'cis_peptide')

    nef_loop.add_tag(tags)

    # TODO need tool to set ionisation correctly
    residue_and_linkages = get_linking(sequences, no_chain_start, no_chain_end)

    for index, (sequence_residue, linking) in enumerate(residue_and_linkages):

        nef_loop.add_data_by_tag('index', index + 1)
        nef_loop.add_data_by_tag('chain_code', sequence_residue.chain_code)
        nef_loop.add_data_by_tag('sequence_code', sequence_residue.sequence_code)
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


def translate_1_to_3(sequence: str, translations: Dict[str, str] = TRANSLATIONS_1_3, unknown: Optional[str] = None) -> List[str]:
    """
    Translate a 1 letter sequence to a 3 letter sequence
    Args:
        sequence (str): 1 letter sequence
        translations (Dict[str, str]): a list of translations for single amino acid codes to 3 letter residue names
        unknown (Optional[str]): optional name for residues if they are unknown, if set no error is raised if a
                                 1 letter residue name is not recognised
    Returns List[str]:
        a list of 3 residue codes

    """
    result = []
    for i, residue_name_1let in enumerate(sequence):
        residue_name_1let = residue_name_1let.upper()
        if residue_name_1let in translations:
            result.append(translations[residue_name_1let])
        else:
            if unknown:
                result.append(unknown)
            else:
                msg = f'''\
                     unknown residue {residue_name_1let} at residue {i+1}
                     sequence: {sequence}
                               {(' ' * i) + '^'}      
                '''
                msg = dedent(msg)
                raise BadResidue(msg)

    return result

def translate_3_to_1(sequence: List[str], translations: Dict[str, str] = TRANSLATIONS_3_1) -> List[str]:
    '''

    Translate a 3 letter sequence to a 1 letter sequence
    Args:
        sequence (str): 3 letter sequence
        translations (Dict[str, str]): a list of translations for single amino acid codes to 3 letter residue names

    Returns List[str]:
        a list of 1 residue codes

    :param sequence:
    :return:
    '''
    result = []
    for i, resn in enumerate(sequence, start=1):
        resn = resn.upper()
        if resn in translations:
            result.append(translations[resn])
        else:
            msg  = f"""
            unknown residue {resn} 
            in sequence {chunks(' '.join(sequence), 10)}
            at residue number {i}
            """
            exit_error(f'unknown residue {resn} in sequence')

    return result

def sequence_3let_to_sequence_residues(sequence_3let: List[str], chain_code: str = 'A') -> List[SequenceResidue]:
    """
    Translate a list of 3 residue sequence codes to SequenceResidues
    Args:
        sequence_3let (List([str]): list of 3 letter residue names
        chain_code (str): the chain code [defaults to A]
        offset (int): the sequence offset [defaults to 0]

    Returns List[SequenceResidue]:
        the sequence as a list of SequenceResidues

    """


    return [SequenceResidue(chain_code, i, residue) for (i, residue) in enumerate(sequence_3let, start=1)]

def sequence_residues_to_sequence_3let(sequence: List[SequenceResidue], chain_code: str = 'A') -> List[str]:
    """
    Translate a list of SequenceResidues to 3 letter sequence codes t
    Args:
        sequence (List([SequenceResidues]): list of residues
        chain_code (str): the chain code [defaults to A] only residues fromthis chain will be converted

    Returns List[str]:
        the sequence as a list of 3 letter residues

    """
    return [residue.residue_name for residue in sequence if residue.chain_code == chain_code]

def frame_to_chains(sequence_frame: Saveframe) -> List[str]:
    """
    given a list of nef molecular systems list the chains found

    :param sequence_frames: list of nef molecular system save frames
    :return: a list of chain_codes
    """

    chains = set()
    for loop in sequence_frame.loop_dict.values():
        data_frame = loop_to_dataframe(loop)
        chains.update(data_frame[NEF_CHAIN_CODE] .unique())

    if NEF_UNKNOWN in chains:
        chains.remove(NEF_UNKNOWN)

    chains = sorted(chains)

    return chains

def count_residues(sequence_frame: Saveframe, chain_code: str) -> Dict[str, int]:
    """
    given a nef molecular system list and a chain list the number of residues

    :param sequence_frames: list of nef molecular system save frames
    :return: a list of chain_codes
    """

    result = {}
    sequence_dataframe = loop_to_dataframe(list(sequence_frame.loop_dict.values())[0])

    rows_with_chain = sequence_dataframe[sequence_dataframe.chain_code == chain_code]
    residues = rows_with_chain.residue_name.unique()

    for residue in sorted(residues):
        residue_selector = rows_with_chain.residue_name == residue
        count = rows_with_chain.residue_name[residue_selector].count()
        result[residue] = count

    return result

def get_sequence_or_exit() -> Optional[List[SequenceResidue]]:
    """
    read a sequence from a nef molecular system on stdin or exit

    :return: a list of parsed residues and chains, in the order they were read
    """
    try:
        result = get_sequence()
    except Exception as e:
        msg = "couldn't read sequence from nef input stream, either no stream or no nef molecular system frame"
        exit_error(msg, e)

    if len(result) == 0 :
        msg = "no sequence read from nef molecular system in nef input stream"
        exit_error(msg)

    return result

def get_sequence() -> List[SequenceResidue]:
    """
    read a sequence from a nef molecular system on stdin and return a list of residues

    can raise Exceptions

    :return:a list of parsed residues and chains, in the order they were read
    """

    result = []

    if sys.stdin.isatty():
        exit_error('trying to read sequence from stdin but stdin is not a stream [did you forget to add a nef file to your pipeline?]')

    if running_in_pycharm():
        exit_error("reading from stdin doesn't work in pycharm debug environment as there is no shell...")

    stream = cached_stdin()

    if stream:
        text = ''.join(stream)

        entry = Entry.from_string(text)

        if entry != None:
            frames = entry.get_saveframes_by_category('nef_molecular_system')

            if frames:
                result = sequence_from_frame(frames[0])


    return result


def sequence_from_frame(frame: Saveframe) -> List[SequenceResidue]:

    """
    read sequences from a nef molecular system save frame
    can raise Exceptions

    :param frame: the save frame to read residues from, must have category nef molecular system
    :return: a list of parsed residues and chains, in the order they were read
    """
    residues = OrderedSet()

    if frame.category != 'nef_molecular_system':
        raise Exception(f'sequences can only be read from nef molecular system frames, the category of the provided frame was {frame.category}')

    loop = frame.loops[0]

    chain_code_index = loop.tag_index('chain_code')
    sequence_code_index = loop.tag_index('sequence_code')
    residue_name_index = loop.tag_index('residue_name')
    linking_index = loop.tag_index('linking')

    for line in loop:
        chain_code = line[chain_code_index]
        sequence_code = line[sequence_code_index]
        residue_name = line[residue_name_index]
        linking = Linking[line[linking_index].upper()] if line[linking_index] != NEF_UNKNOWN else None
        residue = SequenceResidue(chain_code, sequence_code, residue_name, linking)
        residues.append(residue)

    return list(residues)

def sequence_3let_to_res(sequence_3_let: List[str], chain_code: str, start:int =1) -> List[SequenceResidue]:
    """
    convert a list of 3 letter residue names to a list of sequence residues
    :param sequence_3_let: 3 letter names
    :param chain_code: chain code to use
    :param start:  start of the chain [default is 1]
    :return: a list of sequeence residues
    """
    result = set()
    for res_number, residue_name in enumerate(sequence_3_let, start=start):
        result.add(SequenceResidue(chain_code, res_number, residue_name))

    return list(result)


