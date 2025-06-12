import os
import string
from collections import Counter
from dataclasses import replace
from enum import auto
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from ordered_set import OrderedSet
from pynmrstar import Entry, Loop, Saveframe
from strenum import LowercaseStrEnum

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
    strip_characters_right,
)


class MoleculeType(LowercaseStrEnum):
    PROTEIN = auto()
    RNA = auto()
    DNA = auto()
    CARBOHYDRATE = auto()


NEF_CHAIN_CODE = "chain_code"
ANY_CHAIN = "_"


class ChainCodeIterable:

    ASCII_UPPERCASE = list(string.ascii_uppercase)

    def __init__(self, user_chain_codes: List[str], exclude: List[str] = ()):

        self._index = 0
        self._chain_codes = []

        seen_codes = set()
        self._chain_codes = []
        for user_chain_code in user_chain_codes:
            seen_codes.add(user_chain_code)
            if user_chain_code not in exclude:
                self._chain_codes.append(user_chain_code)

        for chain_code in self.ASCII_UPPERCASE:
            if chain_code not in seen_codes and chain_code not in exclude:
                self._chain_codes.append(chain_code)

    def __iter__(self):
        return self

    def __next__(self):
        if self._index < len(self._chain_codes):
            result = self._chain_codes[self._index]
            self._index += 1
            return result
        else:
            raise StopIteration("run out of chain names!")


def get_chain_code_iter(
    user_chain_codes: List[str] = "", exclude: List[str] = ()
) -> Iterator[str]:
    """
    return an iterator they will yield chain codes in user chain codes and
    once exhausted yield any remaining letters of the upper case alphabet
    till they run out. A list of chain codes to not use can be provided...

    Args:
        user_chain_codes (str):  string of dot separated chain codes or a list of chain codes
        exclude: chain codes to not include in the iteration

    Returns:
        Iterable[str] single codes
    """

    return ChainCodeIterable(user_chain_codes, exclude).__iter__()


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

        data = [
            {
                "index": index + 1,
                "chain_code": sequence_residue.chain_code,
                "sequence_code": sequence_residue.sequence_code,
                "residue_name": sequence_residue.residue_name.upper(),
                "linking": linking,
                "residue_variant": NEF_UNKNOWN,
                "cis_peptide": NEF_UNKNOWN,
            }
        ]
        nef_loop.add_data(data)

    return nef_frame


class MoleculeTypes(LowercaseStrEnum):
    PROTEIN = auto()
    DNA = auto()
    RNA = auto()
    CARBOH = auto()
    LIGAND = auto()
    OTHER = auto()


TRANSLATIONS_3_1_DNA = {"DG": "G", "DC": "C", "DT": "T", "DA": "A"}
TRANSLATIONS_1_3_DNA = {value: key for (key, value) in TRANSLATIONS_3_1_DNA.items()}

TRANSLATIONS_3_1_RNA = {"G": "G", "C": "C", "A": "A", "U": "U", "I": "I"}
TRANSLATIONS_1_3_RNA = {value: key for (key, value) in TRANSLATIONS_3_1_RNA.items()}

TRANSLATIONS_3_1_PROTEIN = {
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
TRANSLATIONS_1_3_PROTEIN = {
    value: key for (key, value) in TRANSLATIONS_3_1_PROTEIN.items()
}

TRANSLATIONS_1_3 = {
    MoleculeTypes.PROTEIN: TRANSLATIONS_1_3_PROTEIN,
    MoleculeTypes.DNA: TRANSLATIONS_1_3_DNA,
    MoleculeTypes.RNA: TRANSLATIONS_1_3_RNA,
    MoleculeTypes.CARBOH: None,
    MoleculeTypes.OTHER: None,
    MoleculeTypes.LIGAND: None,
}
TRANSLATIONS_3_1 = {
    MoleculeTypes.PROTEIN: TRANSLATIONS_3_1_PROTEIN,
    MoleculeTypes.DNA: TRANSLATIONS_3_1_DNA,
    MoleculeTypes.RNA: TRANSLATIONS_3_1_RNA,
    MoleculeTypes.CARBOH: None,
    MoleculeTypes.OTHER: None,
    MoleculeTypes.LIGAND: None,
}


class BadResidue(Exception):
    """
    Bad residue found in a sequence
    """

    def __init__(self, residue_name, error_pos, sequence_string):

        self.residue_name = residue_name
        self.sequence_string = sequence_string
        self.error_pos = error_pos

    def __str__(self):
        try:
            terminal_width = os.get_terminal_size().columns
        except OSError:
            terminal_width = 80

        error_pos_string = [
            " ",
        ] * len(self.sequence_string)
        error_pos_string[self.error_pos] = "^"
        error_pos_string = "".join(error_pos_string)

        msg = f"""\
        unknown residue {self.residue_name}
        at residue {self.error_pos+1}
        sequence:
        """
        msg = dedent(msg)
        sequence_string_chunks = list(chunks(self.sequence_string, terminal_width - 10))
        pos_string_chunks = list(chunks(error_pos_string, terminal_width - 10))
        for sequence_chunk, pos_chunk in zip(sequence_string_chunks, pos_string_chunks):
            msg += f"{''.join(sequence_chunk)}\n"
            msg += f"{''.join(pos_chunk)}\n"

        return msg


def translate_1_to_3(
    sequence: str, molecule_type=MoleculeTypes.PROTEIN, unknown: Optional[str] = None
) -> List[str]:
    """
    Translate a 1 letter sequence to a 3 letter sequence
    Args:
        sequence (str): 1 letter sequence
        molecule_type (MoleculeTypes): type of molecule to translate residue types
        unknown (Optional[str]): optional name for residues if they are unknown, if set no error is raised if a
                                 1 letter residue name is not recognised
    Returns List[str]:
        a list of 3 residue codes
        :param type:

    """

    translations = TRANSLATIONS_1_3[molecule_type]

    result = []
    for i, residue_name_1let in enumerate(sequence):
        if residue_name_1let == " ":
            continue
        original_residue_name_1let = residue_name_1let
        residue_name_1let = residue_name_1let.upper()
        if translations is None:
            result.append(residue_name_1let)
        elif residue_name_1let in translations:
            result.append(translations[residue_name_1let])
        else:
            if unknown:
                result.append(unknown)
            else:
                raise BadResidue(original_residue_name_1let, i, sequence)

    return result


def translate_3_to_1(
    sequence: Union[str, List[str]], molecule_type=MoleculeTypes.PROTEIN
) -> List[str]:
    """

    Translate a 3 letter sequence to a 1 letter sequence. If a single string is supplied it
    is trabnslated and returned as a sinle residue
    Args:
        sequence (str|List[str]): 3 letter sequence code or 3 letter sequence
        molecule_type (MoleculeTypes): type of molecule to translate residue types

    Returns str|List[str]:
        a list of 1 residue codes or a single 1 letter residue code

    :param sequence:
    :return:
    """

    single_aa = False
    if isinstance(sequence, str):
        sequence = [
            str,
        ]
        single_aa = True

    translations = TRANSLATIONS_3_1[molecule_type]

    result = []
    for i, residue_name in enumerate(sequence, start=1):
        residue_name = residue_name.upper()
        if translations is None:
            if len(residue_name) == 1:
                result.append(residue_name)
            else:
                msg = f"""
                    it isn't possible to translate the residue name {residue_name} to a 1 letter code
                    the molecule type {molecule_type} doesn't have one letter codes and the residue name: {residue_name}
                    is longer than one letter and so can't be passed through
                """
                exit_error(msg)
        if residue_name in translations:
            result.append(translations[residue_name])
        else:
            msg = f"""
            unknown residue {residue_name}
            in sequence {chunks(' '.join(sequence), 10)}
            at residue number {i}
            """
            exit_error(msg)

    if single_aa:
        result = result[0]

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
        chain_code (str): the chain code [defaults to A] only residues from this chain will be converted

    Returns List[str]:
        the sequence as a list of 3 letter residues

    """
    return [
        residue.residue_name for residue in sequence if residue.chain_code == chain_code
    ]


def chains_from_frames(
    sequence_frame_or_frames: Union[Saveframe, List[Saveframe]]
) -> List[str]:
    """
     a nef molecular systems list the chains found

    :param sequence_frames: a nef molecular system save frame
    :return: a list of chain_codes
    """
    if isinstance(sequence_frame_or_frames, Saveframe):
        sequence_frames = [
            sequence_frame_or_frames,
        ]
    else:
        sequence_frames = sequence_frame_or_frames

    chains = set()
    for sequence_frame in sequence_frames:
        sequences = sequences_from_frames(sequence_frame)
        for residue in sequences:
            chains.add(residue.chain_code)

    if NEF_UNKNOWN in chains:
        chains.remove(NEF_UNKNOWN)

    if None in chains:
        chains.remove(None)

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
            result = sequences_from_frames(frames[0])
    return result


# TODO: check how this deals with sequences with repeats e.g. a sequence with A.3.ALA amd A.3.GLY etc
def sequences_from_frames(
    frame_or_frames: Union[Saveframe, List[Saveframe]],
    chain_codes_to_select: Union[str, List[str]] = ANY_CHAIN,
) -> List[SequenceResidue]:
    """
    read sequences from a nef save frame with the maximal information content about the residues

    :param frame: the save frame to read residues from, must have category nef molecular system
    :param chain_code_to_select: the chain codes to select this can be either a string or list of strings,
                                 any chain is selected using the instance of the constant string ANY_CHAIN [default]
    :return: a list of parsed residues and chains, in the order they were read
    """

    # TODO: check chain code for validity
    if chain_codes_to_select is not ANY_CHAIN and isinstance(
        chain_codes_to_select, str
    ):
        chain_codes_to_select = [
            chain_codes_to_select,
        ]

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

    if isinstance(frame_or_frames, Saveframe):
        frame_or_frames = [
            frame_or_frames,
        ]

    residues = OrderedSet()
    for frame in frame_or_frames:
        for loop in frame.loops:
            residues.update(_parse_loops_residues(loop, chain_codes_to_select))

    return select_best_residues_by_info_content(residues)


def select_best_residues_by_info_content(residues):
    """
    given a list of residues select the best residue definition for each chain code and sequence code
    this removes formally unassigned residues [contain # or @ in sequence_code or chain_code] and favours a residue
    with a residue name, the priority is then cis peptide > residue variants > linking though this shouldn't have an
    effect unless there are errors in the definition of a molecular system

    note if there are multiple residues with the same residue name they are both added...

    :param residues: a list of residues

    :return: a list of residues with the best description possible
    """
    residues = _filter_partially_or_unassigned_residues(residues)

    residues_by_chain_code_sequence_code = {}
    for residue in residues:
        key = residue.chain_code, residue.sequence_code
        residues_by_chain_code_sequence_code.setdefault(key, []).append(residue)

    new_residues = []
    for i, equivalent_residues in enumerate(
        residues_by_chain_code_sequence_code.values()
    ):

        residues_and_scores = {}
        score = 0
        for equivalent_residue in equivalent_residues:
            # somewhat arbitrary scoring system to pick the best residue
            # TODO should we merge if there is missing info...
            if equivalent_residue.residue_name not in (None, UNUSED):
                score += 100000
            if equivalent_residue.is_cis not in (None, UNUSED):
                score += 10000
            if equivalent_residue.variants not in (None, UNUSED):
                score += 1000
            if equivalent_residue.linking not in (None, UNUSED):
                score += 100
            residues_and_scores[score] = equivalent_residue

        equivalent_residues = [
            residues_and_scores[score] for score in sorted(residues_and_scores)
        ]

        new_equivalent_residues = []
        if len(equivalent_residues) > 1:

            seen_residue_names = set()
            for equivalent_residue in equivalent_residues:
                if equivalent_residue.residue_name not in (None, UNUSED):
                    if equivalent_residue.residue_name not in seen_residue_names:
                        new_equivalent_residues.append(equivalent_residue)
                        seen_residue_names.add(equivalent_residue.residue_name)

            if new_equivalent_residues:
                new_equivalent_residues = [
                    equivalent_residues[0],
                ]
        else:
            new_equivalent_residues = [
                equivalent_residues[0],
            ]

        new_residues.extend(new_equivalent_residues)
    return new_residues


def _filter_partially_or_unassigned_residues(residues):

    result = []
    for residue in residues:
        if residue.chain_code in (None, UNUSED):
            continue
        if residue.sequence_code in (None, UNUSED):
            continue
        if isinstance(residue.chain_code, str) and residue.chain_code[0] in ("#", "@"):
            continue
        if isinstance(residue.sequence_code, str) and residue.sequence_code[0] in (
            "#",
            "@",
        ):
            continue
        result.append(residue)
    return result


def _parse_loops_residues(loop, chain_codes_to_select):

    offsets = [f"_{index}" for index in range(1, 16)]
    offsets.insert(0, "")
    index_sets = []
    for offset in offsets:
        if offset == "":
            linking_tag = f"linking{offset}"
            linking_index = (
                loop.tag_index(linking_tag) if linking_tag in loop.tags else None
            )

            residue_variant_tag = f"residue_variant{offset}"
            residue_variant_index = (
                loop.tag_index(residue_variant_tag)
                if residue_variant_tag in loop.tags
                else None
            )

            cis_peptide_tag = f"cis_peptide{offset}"
            cis_peptide_index = (
                loop.tag_index(cis_peptide_tag)
                if cis_peptide_tag in loop.tags
                else None
            )

        chain_code_tag = f"chain_code{offset}"
        chain_code_index = (
            loop.tag_index(chain_code_tag) if chain_code_tag in loop.tags else None
        )

        sequence_code_tag = f"sequence_code{offset}"
        sequence_code_index = (
            loop.tag_index(sequence_code_tag)
            if sequence_code_tag in loop.tags
            else None
        )

        residue_name_tag = f"residue_name{offset}"
        residue_name_index = (
            loop.tag_index(residue_name_tag) if residue_name_tag in loop.tags else None
        )

        if chain_code_index is None and sequence_code_index is None:
            continue

        index_set = {
            "chain_code_index": chain_code_index,
            "sequence_code_index": sequence_code_index,
            "residue_name_index": residue_name_index,
            "linking_index": linking_index,
            "residue_variant_index": residue_variant_index,
            "cis_peptide_index": cis_peptide_index,
        }

        index_sets.append(index_set)

    residues = []
    for line in loop:

        for index_set in index_sets:
            chain_code_index = index_set["chain_code_index"]
            sequence_code_index = index_set["sequence_code_index"]
            residue_name_index = index_set["residue_name_index"]
            linking_index = index_set["linking_index"]
            residue_variant_index = index_set["residue_variant_index"]
            cis_peptide_index = index_set["cis_peptide_index"]

            if chain_code_index is not None:
                chain_code = line[chain_code_index]
                if chain_code == UNUSED:
                    continue

                if not (
                    chain_codes_to_select is ANY_CHAIN
                    or chain_code in chain_codes_to_select
                ):
                    continue
            else:
                continue

            if sequence_code_index is not None:
                sequence_code = line[sequence_code_index]
                sequence_code = (
                    int(sequence_code) if is_int(sequence_code) else sequence_code
                )
            else:
                sequence_code = None

            residue_name = line[residue_name_index] if residue_name_index else None

            if linking_index is not None:
                linking = (
                    Linking[line[linking_index].upper()]
                    if line[linking_index] != NEF_UNKNOWN
                    else None
                )
            else:
                linking = None

            if cis_peptide_index is not None:
                cis_peptide = line[cis_peptide_index]
                if cis_peptide == UNUSED:
                    cis_peptide = False
                elif cis_peptide.lower() == "true":
                    cis_peptide = True
                elif cis_peptide.lower() == "false":
                    cis_peptide = False
                else:
                    cis_peptide = False
            else:
                cis_peptide = False

            if residue_variant_index is not None:
                residue_variants = line[residue_variant_index].split(",")
                residue_variants = (
                    ()
                    if residue_variants
                    == [
                        UNUSED,
                    ]
                    else tuple(residue_variants)
                )
            else:
                residue_variants = ()

            residue = SequenceResidue(
                chain_code=chain_code,
                sequence_code=sequence_code,
                residue_name=residue_name,
                linking=linking,
                is_cis=cis_peptide,
                variants=residue_variants,
            )
            if residue.chain_code and residue.sequence_code:
                residues.append(residue)

    return residues


def sequence_3let_to_res(
    sequence_3_let: List[str], chain_code: str, start: int = 1
) -> List[SequenceResidue]:
    """
    convert a list of 3 letter residue names to a list of sequence residues
    :param sequence_3_let: 3 letter names
    :param chain_code: chain code to use
    :param start:  start of the chain [default is 1]
    :return: a list of sequence residues
    """
    result = set()
    for res_number, residue_name in enumerate(sequence_3_let, start=start):
        result.add(SequenceResidue(chain_code, res_number, residue_name))

    return list(result)


def get_chain_starts(residues: List[SequenceResidue]) -> Dict[str, int]:
    """
    from a list of residues get the lowest residue number for each chain ignoring any sequence codes that
    can't be converted to an integer

    :param residues:  a list of residues from one or more chains
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


def get_chain_ends(residues: List[SequenceResidue]) -> Dict[str, int]:
    """
    from a list of residues get the highest residue number for each chain ignoring any sequence codes that
    can't be converted to an integer

    :param residues:  a list of residues from one or more chains
    :return: a dictionary of chain starts by chain_code
    """

    chain_residue_numbers = {}

    for residue in residues:

        if is_int(residue_number := residue.sequence_code):
            chain_residue_numbers.setdefault(residue.chain_code, []).append(
                residue_number
            )

    return {
        chain_code: max(residue_numbers)
        for chain_code, residue_numbers in chain_residue_numbers.items()
    }


def get_chain_starts_and_ends(
    residues: List[SequenceResidue],
) -> Dict[str, Tuple[int, int]]:
    """
    from a list of residues get the lowest highest residue number for each chain ignoring any sequence codes that
    can't be converted to an integer

    :param residues:  a list of residues from one or more chains
    :return: a dictionary of chain starts and ends as a tuple by chain_code
    """

    chain_starts = get_chain_starts(residues)
    chain_ends = get_chain_ends(residues)

    result = {}
    for chain in chain_starts:
        result[chain] = (chain_starts[chain], chain_ends[chain])

    return result


def sequence_to_chains(residues: List[SequenceResidue]) -> List[str]:
    """
    from a list of residues get chain_codes

    :param residues:  a list of residues from one or more chains
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

    :param residues:  a list of residues from one or more chains
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


def sequence_3let_list_from_sequence(
    sequence: List[SequenceResidue], count: int = 10, chain_code="A"
) -> List[str]:
    """
    convert a list of Residues to a set of lines containing space separated residue names
    [default 10] per line

    :param sequence: a sequence
    :param count: number of residues names to display per line
    :return: a list of lines as strings
    """

    residue_names = [
        residue.residue_name for residue in sequence if residue.chain_code == chain_code
    ]
    rows = chunks(residue_names, count)

    row_strings = []
    for row in rows:
        row_strings.append(" ".join(row))

    return row_strings


def make_chunked_sequence_1let(
    sequence_1_let: List[str], sub_chunk: int = 10, line_length: int = 100
) -> List[str]:
    """
    convert a list of strings into a chunked list of strings with (by default) every 100 sting being
    separated by a new line [line_length] and sequences of strings being separated by a space
    :param sequence_1_let: a list of strings typically 1 single letter
    :param sub_chunk: how often to separate strings by a space
    :param line_length: how many strings need to be seen before a new line is added
    :return: a list of formatted strings one per line
    """

    rows = chunks(sequence_1_let, line_length)

    row_strings = []
    for row in rows:
        row_chunks = list(chunks(row, sub_chunk))
        row_string = ["".join(chunk) for chunk in row_chunks]
        row_strings.append(" ".join(row_string))

    return row_strings


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
) -> Optional[str]:
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


# TODO sequence codes should be ints if they look like ints (currently fails tests)
def sequence_to_residue_name_lookup(
    sequence: List[SequenceResidue],
) -> Dict[Tuple[str, int], str]:
    """
    build a lookup table from sequence_code, chain_code to residue_type from a list of sequence residues
    :param sequence: a list of sequence residues
    :return: the lookup table
    """

    result: Dict[Tuple[str, int], str] = {}
    if len(sequence) > 0:
        result = {
            (residue.chain_code, str(residue.sequence_code)): residue.residue_name
            for residue in sequence
        }

    return result


def atom_sort_key(item: AtomLabel) -> Tuple[Any, ...]:
    """

    key based sorter for atom labels that enables them to be sorted in a sensible order including sequence codes
    which are not numeric...

    :param item: an atom label
    :return: a tuple based on the atom label which gives the correct sort order
    """

    try:
        items = []
        residue = item.residue
        chain_code = residue.chain_code.strip()
        prefix, numbers = strip_characters_right(chain_code, string.digits)

        if numbers == "":
            numbers = 0, ""
        if is_int(numbers):
            numbers = int(numbers), ""
        else:
            numbers = 0, numbers

        if UNUSED in prefix:
            order = 2
        elif "@" in prefix or "#" in prefix:
            order = 1
        else:
            order = 0

        items.append([order, prefix, *numbers])

        sequence_code = str(residue.sequence_code).strip()
        prefix, numbers = strip_characters_right(sequence_code, (string.digits + "+-"))

        if is_int(numbers):
            numbers = [int(numbers), "", 0]
        elif "+" in numbers or "-" in numbers:
            for splitter in "+-":
                if splitter in numbers:
                    numbers = numbers.rsplit(splitter, maxsplit=1)
                    numbers = [numbers[0], splitter, numbers[1]]
                    break
            if is_int(numbers[0]) and is_int(numbers[-1]):
                numbers[0] = int(numbers[0])
                numbers[-1] = int(numbers[-1])
        else:
            numbers = [0, numbers, 0]

        if UNUSED in prefix:
            order = 2
        elif "@" in prefix or "#" in prefix:
            order = 1
        else:
            order = 0

        items.append([order, prefix, *numbers])

        items.append(residue.residue_name.lower())
        items.append(item.atom_name.lower())
    except Exception as e:
        msg = f"""
            I can't sort {item} because it doesn't seem to be behaving like an AtomLabel...
            [{e}]
        """
        raise ValueError(msg)

    return items


def exit_if_chain_not_in_entrys_sequence(chain_code: str, entry: Entry):

    nef_sequence = sequence_from_entry(entry)

    _exit_if_chain_not_in_sequence(chain_code, nef_sequence, entry)


def _exit_if_chain_not_in_sequence(
    chain_code: str,
    nef_sequence: List[SequenceResidue],
    entry: Entry,
):
    file_name = f"{entry.source} [stdin]" if entry.source == "-" else entry.source

    nef_chain_codes = sequence_to_chains(nef_sequence)
    if chain_code and chain_code not in nef_chain_codes:
        msg = f"""
            The chain code {chain_code} was not found in the input chain codes in the nef stream
            with entry name {entry.entry_id}  in file {file_name}
            the chain codes found were {','.join(nef_chain_codes)}
        """

        exit_error(msg)
