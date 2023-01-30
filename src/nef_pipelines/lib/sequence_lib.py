import string
from collections import Counter
from dataclasses import replace
from pathlib import Path
from textwrap import dedent
from typing import Dict, Iterable, List, Optional, Tuple, Union

from ordered_set import OrderedSet
from pynmrstar import Entry, Loop, Saveframe

from nef_pipelines.lib.constants import NEF_UNKNOWN
from nef_pipelines.lib.nef_lib import UNUSED, loop_row_namespace_iter

# from nef_pipelines.lib.nef_lib import loop_to_dataframe
from nef_pipelines.lib.structures import AtomLabel, Linking, SequenceResidue
from nef_pipelines.lib.util import (
    chunks,
    exit_error,
    get_display_file_name,
    is_int,
    read_from_file_or_exit,
)

NEF_CHAIN_CODE = "chain_code"
ANY_CHAIN = "_"


def chain_code_iter(
    user_chain_codes: Union[str, List[str]] = "", exclude: Union[str, List[str]] = ()
) -> Iterable[str]:
    """
    split input string into chain codes separated by .s, and yield them.
    Then yield any remaining letters of the upper case alphabet till they run out

    Args:
        user_chain_codes (str):  string of dot separated chain codes
        exclude: chain codes to not include in the iteration

    Returns:
        Iterable[str] single codes
    """

    ascii_uppercase = list(string.ascii_uppercase)

    if isinstance(user_chain_codes, str):
        if "." in user_chain_codes:
            user_chain_codes = user_chain_codes.split(".")

    if isinstance(exclude, str):
        if "." in exclude:
            exclude = exclude.split(".")

    chain_codes = user_chain_codes if user_chain_codes else ascii_uppercase

    seen_codes = set()

    for chain_code in chain_codes:
        seen_codes.add(chain_code)
        if chain_code not in exclude:
            yield chain_code

    for chain_code in ascii_uppercase:
        if chain_code not in seen_codes and chain_code not in exclude:
            yield chain_code

    raise ValueError("run out of chain names!")


def get_linking(
    target_sequence: List[SequenceResidue],
    no_chain_start=List[str],
    no_chain_end=List[str],
) -> List[SequenceResidue]:

    """
    get the correct linking for residue in a standard sequenced chain

    Args:
        target_sequence (List[SequenceResidue]) : the sequence
        no_chain_start (List[str]): if the chain isn't in the list cap it at the start
        no_end (List[str]): if the chain isn't in the list cap it at the end

    Returns:
         List[SequenceResidue]: correctly linked residues
    """

    by_chain = {}
    for residue in target_sequence:
        by_chain.setdefault(residue.chain_code, []).append((residue, "middle"))

    result = []
    for chain, residues_and_linkages in by_chain.items():

        if chain not in no_chain_start:
            residues_and_linkages[0] = (residues_and_linkages[0][0], "start")

        if chain not in no_chain_end:
            residues_and_linkages[-1] = (residues_and_linkages[-1][0], "end")

        result.extend(residues_and_linkages)

    return result


def sequence_to_nef_frame(
    sequences: List[SequenceResidue],
    no_chain_start: Union[List[str], Tuple[str]] = (),
    no_chain_end: Union[List[str], Tuple[str]] = (),
) -> Saveframe:
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

    frame_code = f"{category}"

    nef_frame = Saveframe.from_scratch(frame_code, category)

    nef_frame.add_tag("sf_category", category)
    nef_frame.add_tag("sf_framecode", frame_code)

    nef_loop = Loop.from_scratch("nef_sequence")
    nef_frame.add_loop(nef_loop)

    tags = (
        "index",
        "chain_code",
        "sequence_code",
        "residue_name",
        "linking",
        "residue_variant",
        "cis_peptide",
    )

    nef_loop.add_tag(tags)

    # TODO need tool to set ionisation correctly
    residue_and_linkages = get_linking(sequences, no_chain_start, no_chain_end)

    for index, (sequence_residue, linking) in enumerate(residue_and_linkages):

        nef_loop.add_data_by_tag("index", index + 1)
        nef_loop.add_data_by_tag("chain_code", sequence_residue.chain_code)
        nef_loop.add_data_by_tag("sequence_code", sequence_residue.sequence_code)
        nef_loop.add_data_by_tag("residue_name", sequence_residue.residue_name.upper())
        nef_loop.add_data_by_tag("linking", linking)
        nef_loop.add_data_by_tag("residue_variant", NEF_UNKNOWN)
        nef_loop.add_data_by_tag("cis_peptide", NEF_UNKNOWN)

    return nef_frame


TRANSLATIONS_3_1 = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLU": "E",
    "GLN": "Q",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
}
TRANSLATIONS_1_3 = {value: key for (key, value) in TRANSLATIONS_3_1.items()}


class BadResidue(Exception):
    """
    Bad residue found in a sequence
    """

    pass


def translate_1_to_3(
    sequence: str,
    translations: Dict[str, str] = TRANSLATIONS_1_3,
    unknown: Optional[str] = None,
) -> List[str]:
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
                msg = f"""\
                     unknown residue {residue_name_1let} at residue {i+1}
                     sequence: {sequence}
                               {(' ' * i) + '^'}
                """
                msg = dedent(msg)
                raise BadResidue(msg)

    return result


def translate_3_to_1(
    sequence: List[str], translations: Dict[str, str] = TRANSLATIONS_3_1
) -> List[str]:
    """

    Translate a 3 letter sequence to a 1 letter sequence
    Args:
        sequence (str): 3 letter sequence
        translations (Dict[str, str]): a list of translations for single amino acid codes to 3 letter residue names

    Returns List[str]:
        a list of 1 residue codes

    :param sequence:
    :return:
    """
    result = []
    for i, resn in enumerate(sequence, start=1):
        resn = resn.upper()
        if resn in translations:
            result.append(translations[resn])
        else:
            msg = f"""
            unknown residue {resn}
            in sequence {chunks(' '.join(sequence), 10)}
            at residue number {i}
            """
            exit_error(msg)

    return result


def sequence_3let_to_sequence_residues(
    sequence_3let: List[str], chain_code: str = "A"
) -> List[SequenceResidue]:
    """
    Translate a list of 3 residue sequence codes to SequenceResidues
    Args:
        sequence_3let (List([str]): list of 3 letter residue names
        chain_code (str): the chain code [defaults to A]
        offset (int): the sequence offset [defaults to 0]

    Returns List[SequenceResidue]:
        the sequence as a list of SequenceResidues

    """

    return [
        SequenceResidue(chain_code, i, residue)
        for (i, residue) in enumerate(sequence_3let, start=1)
    ]


def sequence_residues_to_sequence_3let(
    sequence: List[SequenceResidue], chain_code: str = "A"
) -> List[str]:
    """
    Translate a list of SequenceResidues to 3 letter sequence codes t
    Args:
        sequence (List([SequenceResidues]): list of residues
        chain_code (str): the chain code [defaults to A] only residues fromthis chain will be converted

    Returns List[str]:
        the sequence as a list of 3 letter residues

    """
    return [
        residue.residue_name for residue in sequence if residue.chain_code == chain_code
    ]


def frame_to_chains(sequence_frame: Saveframe) -> List[str]:
    """
     a nef molecular systems list the chains found

    :param sequence_frames: a nef molecular system save frame
    :return: a list of chain_codes
    """

    chains = set()
    for loop in sequence_frame.loop_dict.values():
        for row in loop_row_namespace_iter(loop):
            chains.add(row.chain_code)

    if NEF_UNKNOWN in chains:
        chains.remove(NEF_UNKNOWN)

    chains = sorted(chains)

    return chains


def count_residues(sequence_frame: Saveframe, chain_code: str) -> Dict[str, int]:
    """
    given a nef molecular system and a chain list the number of residues of each type in the chain

    :param sequence_frames: a nef molecular system save frame
    :return: a list of chain_codes
    """

    residue_number_to_residue_name = {}
    for row in loop_row_namespace_iter(sequence_frame.loops[0]):
        if row.chain_code == chain_code:
            residue_number_to_residue_name[row.sequence_code] = row.residue_name

    result = Counter()
    for residue_name in sorted(residue_number_to_residue_name.values()):
        result[residue_name] += 1

    return result


def get_sequence_or_exit(
    file_name: Path = Path("-"),
) -> Optional[List[SequenceResidue]]:
    """
    read a sequence from a nef molecular system on a file or stdin or exit, return a list of residues

    file_name: a path to read the nef from Path('-') read from stdin
    :return: a list of parsed residues and chains, in the order they were read
    """
    try:
        result = get_sequence(file_name)
    except Exception as e:
        msg = "couldn't read sequence from nef input stream, either no stream or no nef molecular system frame"
        exit_error(msg, e)

    if len(result) == 0:
        msg = "no sequence read from nef molecular system in nef input stream"
        exit_error(msg)

    return result


def get_sequence(file_name: Path = Path("-")) -> List[SequenceResidue]:
    """
    read a sequence from a nef molecular system on stdin and return a list of residues

    file_name: a path to read the nef from Path('-') read from stdin
    can raise Exceptions

    :return:a list of parsed residues and chains, in the order they were read
    """

    text = read_from_file_or_exit(file_name, "sequence from NEF molecular system")

    display_file_name = get_display_file_name(file_name)

    try:
        entry = Entry.from_string(text)
    except Exception as e:
        msg = f"couldn't parse text in {display_file_name} as NEF data"
        exit_error(msg, e)

    return sequence_from_entry(entry)


def sequence_from_entry_or_exit(entry: Entry) -> List[SequenceResidue]:
    sequence = sequence_from_entry(entry)

    if not sequence:
        msg = "did you read a sequence? a sequence is required and was not read"
        exit_error(msg)

    return sequence


def sequence_from_entry(entry) -> List[SequenceResidue]:

    result = []
    if entry is not None:
        frames = entry.get_saveframes_by_category("nef_molecular_system")

        if frames:
            result = sequence_from_frame(frames[0])
    return result


def sequence_from_frame(
    frame: Saveframe, chain_codes_to_select: Union[str, List[str]] = ANY_CHAIN
) -> List[SequenceResidue]:

    """
    read sequences from a nef molecular system save frame
    can raise Exceptions

    :param frame: the save frame to read residues from, must have category nef molecular system
    :param chain_code_to_select: the chain codes to select,t this can be either a string or list of strings,
                                 any chain is selected using the instance of the constant string ANY_CHAIN [default]
    :return: a list of parsed residues and chains, in the order they were read
    """

    if chain_codes_to_select is not ANY_CHAIN and isinstance(
        chain_codes_to_select, str
    ):
        chain_codes_to_select = set(
            [
                chain_codes_to_select,
            ]
        )
    elif chain_codes_to_select is not ANY_CHAIN:
        chain_codes_to_select = set(chain_codes_to_select)

    residues = OrderedSet()

    if frame.category != "nef_molecular_system":
        raise Exception(
            f"sequences can only be read from nef molecular system frames, the category of the provided frame "
            f"was {frame.category}"
        )

    loop = frame.loops[0]

    chain_code_index = loop.tag_index("chain_code")
    sequence_code_index = loop.tag_index("sequence_code")
    residue_name_index = loop.tag_index("residue_name")
    linking_index = loop.tag_index("linking")

    for line in loop:
        chain_code = line[chain_code_index]
        if chain_codes_to_select is ANY_CHAIN or chain_code in chain_codes_to_select:
            sequence_code = line[sequence_code_index]
            residue_name = line[residue_name_index]
            linking = (
                Linking[line[linking_index].upper()]
                if line[linking_index] != NEF_UNKNOWN
                else None
            )
            residue = SequenceResidue(
                chain_code=chain_code,
                sequence_code=sequence_code,
                residue_name=residue_name,
                linking=linking,
            )
            residues.append(residue)

    return list(residues)


def sequence_3let_to_res(
    sequence_3_let: List[str], chain_code: str, start: int = 1
) -> List[SequenceResidue]:
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


def get_chain_starts(residues: List[SequenceResidue]) -> Dict[str, int]:
    """
    from a list of residues get the lowest residue number for each chain ignoring any sequence codes that
    can't be converted to an integer

    :param residues:  a list of residues from one ore more chains
    :return: a dictionary of chain starts by chain_code
    """

    chain_residue_numbers = {}

    for residue in residues:

        if is_int(residue_number := residue.sequence_code):
            chain_residue_numbers.setdefault(residue.chain_code, []).append(
                residue_number
            )

    return {
        chain_code: min(residue_numbers)
        for chain_code, residue_numbers in chain_residue_numbers.items()
    }


def sequence_to_chains(residues: List[SequenceResidue]) -> List[str]:
    """
    from a list of residues get chain_codes

    :param residues:  a list of residues from one ore more chains
    :return: a list of chain_codes
    """

    chain_codes = set()

    for residue in residues:

        chain_codes.add(residue.chain_code)

    return sorted(tuple(chain_codes))


def offset_chain_residues(
    residues: List[SequenceResidue], chain_residue_offsets: Dict[str, int]
) -> List[SequenceResidue]:
    """
    take a list of residues and offset residue sequence_codes by any offsets in chains if the
    sequence_code can be converted to an integer and the chain_code matches

    :param residues:  a list of residues from one ore more chains
    :return: a list of residues
    """

    result = []
    for residue in residues:
        if residue.chain_code in chain_residue_offsets and is_int(
            residue.sequence_code
        ):
            offset = chain_residue_offsets[residue.chain_code]
            result.append(
                replace(residue, sequence_code=residue.sequence_code + offset)
            )
        else:
            result.append(residue)

    return result


def make_chunked_sequence_1let(
    sequence_1_let: List[str], sub_chunk: int = 10, line_length: int = 100
) -> List[str]:
    """
    convert a list of strings into a chunked list of strings with (by de]fault) every 100 sting being
    separated by a new line [line_length] and sequences of strings being separated by a space
    :param sequence_1_let: a list of strings typically 1 single letter
    :param sub_chunk: how often to separate strings by a space
    :param line_length: how many strings need to be seen before a new line is added
    :return: a list of formatted strings one per line
    """

    rows = chunks(sequence_1_let, 100)

    row_strings = []
    for row in rows:
        row_chunks = list(chunks(row, 10))
        row_string = ["".join(chunk) for chunk in row_chunks]
        row_strings.append(" ".join(row_string))

    return row_strings


def residues_to_residue_name_lookup(
    sequence: List[SequenceResidue],
) -> Dict[Tuple[str, str], str]:
    return {
        (residue.chain_code, str(residue.sequence_code)): residue.residue_name
        for residue in sequence
    }


def replace_chain_in_atom_labels(
    atom_labels: List[AtomLabel], chain_code: str
) -> List[AtomLabel]:
    """
    replace the chain in a list of AtomLabels, not this operation is not inplace new AtomLabels are returned

    :param atom_labels: a list of AtomLabels
    :param chain_code: the new chain_code
    :return: the updated AtomLabels
    """
    result = []

    for selection in atom_labels:
        new_residue = replace(selection.residue, chain_code=chain_code)
        result.append(replace(selection, residue=new_residue))

    return result


def get_residue_name_from_lookup(
    chain_code: str,
    sequence_code: Union[str, int],
    lookup_table: Dict[Union[str, int], str],
) -> str:
    """
    get a residue name from a chain_code and sequence_code, using the provided lookup table. The sequence code is
    treated being as either  a string or an int, strs are checked first
    :param chain_code: the chain code
    :param sequence_code: the residue code treated as both an int and a string
    :param lookup_table: the table of residues names indexed by chain_code_sequence_code
    :return:
    """

    seq_key = chain_code, str(sequence_code)

    residue_name = lookup_table.get(seq_key, None)

    if not residue_name:
        if is_int(sequence_code):
            seq_key = chain_code, int(sequence_code)

    residue_name = lookup_table.get(seq_key, UNUSED)

    if residue_name is not None:
        residue_name = residue_name.upper()

    return residue_name


def sequence_to_residue_type_lookup(
    sequence: List[SequenceResidue],
) -> Dict[Tuple[str, int], str]:

    """
    build a lookup table from sequence_code, chain_code to residue_type from a list of sequence residues
    :param sequence: a list of sequence residues
    :return: the lookup table
    """
    result: Dict[Tuple[str, int], str] = {}
    for residue in sequence:
        result[residue.chain_code, residue.sequence_code] = residue.residue_name
    return result
