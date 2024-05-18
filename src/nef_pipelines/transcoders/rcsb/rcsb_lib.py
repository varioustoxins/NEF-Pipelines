import random
import re
import string
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from pathlib import Path
from textwrap import dedent
from typing import Dict, Iterable, List, Optional

from fyeah import f
from pdbx import DataContainer
from pdbx.reader import PdbxReader
from strenum import LowercaseStrEnum

from nef_pipelines.lib.structures import LineInfo
from nef_pipelines.lib.util import exit_error


class Atom: ...  # noqa: E701


class Chain: ...  # noqa: E701


class Residue: ...  # noqa: E701


class Model: ...  # noqa: E701


class Structure: ...  # noqa: E701


class Sequence: ...  # noqa: E701


@dataclass
class Atom:  # noqa: F811
    serial: int
    atom_name: str

    x: float
    y: float
    z: float

    alternative_location: str = None

    element: str = None

    temp_fact: float = None
    occupancy: float = 1.0

    residue: Optional[Residue] = None


@dataclass
class Residue:
    sequence_code: int
    residue_name: str
    atoms: List[Atom] = field(default_factory=list)
    chain: Optional[Chain] = None

    def __iter__(self):
        return self.atoms.__iter__()


@dataclass
class Chain:
    residues: List[Residue] = field(default_factory=list)
    chain_code: Optional[str] = None
    segment_id: Optional[str] = None
    sequence: Optional[Sequence] = None
    model: Optional[Model] = None

    def __iter__(self):
        return self.residues.__iter__()


@dataclass
class Model:
    serial: int
    chains: Dict[str, Chain] = field(default_factory=dict)
    structure: Optional[Structure] = None

    def __iter__(self):
        return iter(self.chains.values())


class PdbSecondaryStructureType(IntEnum):
    HELIX_RIGHT_HANDED_ALPHA = auto()
    HELIX_RIGHT_HANDED_OMEGA = auto()
    HELIX_RIGHT_HANDED_PI = auto()
    HELIX_RIGHT_HANDED_GAMMA = auto()
    HELIX_RIGHT_HANDED_3_10 = auto()
    HELIX_LEFT_HANDED_ALPHA = auto()
    HELIX_LEFT_HANDED_OMEGA = auto()
    HELIX_LEFT_HANDED_GAMMA = auto()
    HELIX_RIBBON_HELIX_2_7 = auto()
    HELIX_POLYPROLINE = auto()
    SHEET = auto()


@dataclass
class SecondaryStructureElement:
    chain_code: str
    start_sequence_code: int
    end_sequence_code: int
    alternative_location: str
    secondary_structure_type: PdbSecondaryStructureType

    structure: Optional[Structure] = None


class SequenceSource(Enum):
    SEQRES = auto()
    RESIDUE = auto()


@dataclass
class Sequence:
    id: int
    start_sequence_code: int = 1
    residues: List[str] = field(default_factory=list)
    source: Optional[SequenceSource] = None
    structure: Optional[Structure] = None


@dataclass
class Structure:
    source: str = None
    sequences: Dict[str, Sequence] = field(default_factory=dict)
    secondary_structure: Dict[str, List[SecondaryStructureElement]] = field(
        default_factory=dict
    )

    models: List[Model] = field(default_factory=list)

    def __iter__(self):
        return self.models.__iter__()

    def __getitem__(self, index):
        return self.models[0]


class StructureParseException(Exception):
    pass


current_structure: Optional[Structure] = None
current_model: Optional[Model] = None
current_chain: Optional[Chain] = None
current_residue: Optional[Residue] = None
current_indices: Dict[str, int] = {}
current_lines: List[str]


def _pad_line_to_80(line):
    line_length = len(line)
    if line_length < 80:
        line += " " * (80 - line_length)
    return line


@dataclass
class PDBLineInfo(LineInfo):
    record_type: str


def _convert_to_int_or_exit(
    value_string: str, line_info: PDBLineInfo, field_name: str
) -> int:
    converter = int
    return _convert_to_type_or_exit_error(
        value_string, converter, line_info, field_name
    )


def _convert_to_float_or_exit(
    value_string: str, line_info: PDBLineInfo, field_name: str
) -> int:
    converter = float
    return _convert_to_type_or_exit_error(
        value_string, converter, line_info, field_name
    )


def _convert_to_type_or_exit_error(value_string, converter, line_info, field_name):
    result = None
    try:
        result = converter(value_string)
    except ValueError:
        conversion_type = str(converter).split()[1].strip(">").strip("'")
        _report_bad_conversion(
            value_string,
            conversion_type,
            line_info,
            field_name,
        )
    return result


def _report_bad_conversion(
    value: str, conversion_type: str, line_info: PDBLineInfo, field_name: str
):
    msg = f"""
            at line {line_info.line_no} in {line_info.file_name}
            the field {field_name} in a {line_info.record_type} record
            couldn't be converted to a {conversion_type}

            the value of the field {field_name} was |{value}|

                        ruler 10s |         1         2         3         4         5         6         7         8|
                        ruler 1s  |12345678901234567890123456789012345678901234567890123456789012345678901234567890|
            the complete line was |{line_info.line}|

            note all |'s are used to delimit the start and end of lines and values and are not part of the value
        """
    exit_error(msg)


def _as_string_or_none(item):
    if item:
        item = item.strip()
        if not item:
            item = None
    return item


def _as_continuous_string_or_exit(name, line_info: PDBLineInfo, field_name: str):
    name = name.strip()

    if string.whitespace in name:
        _report_bad_conversion(name, "string without spaces", line_info, field_name)

    return name


def _exit_if_no_chain_code_and_no_segment_id(chain_code, segment_id, line_info):
    if not chain_code and not segment_id:
        msg = f"""
            in file {line_info.file_name} at line {line_info.line_no} both the chain code and segment id were
            not present on an ATOM record, one or both must be present

            the line was

            {line_info.line}
        """

        exit_error(msg)


def _parse_atom(line, line_info):
    global current_residue, current_chain, current_model

    serial = line[6:11]
    name = line[12:16]
    alternative_location = line[16]
    residue_name = line[17:20]
    chain_code = line[21]
    sequence_code = line[22:26]
    x = line[30:38]
    y = line[38:46]
    z = line[46:54]
    segment_id = line[72:76]
    element = line[76:78]
    temp_fact = line[60:66]

    serial = _convert_to_int_or_exit(serial, line_info, "serial")
    sequence_code = _convert_to_int_or_exit(sequence_code, line_info, "sequence_code")

    x = _convert_to_float_or_exit(x, line_info, "x")
    y = _convert_to_float_or_exit(y, line_info, "y")
    z = _convert_to_float_or_exit(z, line_info, "z")

    segment_id = _as_string_or_none(segment_id)
    chain_code = _as_string_or_none(chain_code)

    element = _as_string_or_none(element)

    temp_fact = _convert_to_float_or_exit(temp_fact, line_info, "temperature factor")

    name = _as_continuous_string_or_exit(name, line_info, "name")

    alternative_location = _as_string_or_none(alternative_location)

    residue_name = _as_continuous_string_or_exit(
        residue_name, line_info, "residue name"
    )

    current_atom = Atom(
        serial=serial,
        atom_name=name,
        alternative_location=alternative_location,
        x=x,
        y=y,
        z=z,
        element=element,
        temp_fact=temp_fact,
    )

    _exit_if_chain_code_and_segid_are_mismatched(
        current_chain, chain_code, segment_id, line_info
    )

    _exit_if_no_chain_code_and_no_segment_id(chain_code, segment_id, line_info)

    if current_chain:
        new_chain = False
        if (
            current_chain.chain_code and chain_code
        ) and current_chain.chain_code != chain_code:
            new_chain = True

        if (
            current_chain.segment_id
            and segment_id
            and current_chain.segment_id != segment_id
        ):
            new_chain = True

        if new_chain:
            current_chain = None

    if not current_chain:
        chain_segment_key = chain_code if chain_code else segment_id
        current_chain = Chain(chain_code=chain_code, segment_id=segment_id)
        current_model.chains[chain_segment_key] = current_chain

    if current_residue and current_residue.sequence_code != sequence_code:
        current_residue = None

    if not current_residue:
        current_residue = Residue(
            sequence_code=sequence_code, residue_name=residue_name, chain=current_chain
        )
        current_chain.residues.append(current_residue)

    current_atom.residue = current_residue
    current_residue.atoms.append(current_atom)


def _exit_if_chain_code_and_segid_are_mismatched(
    target_chain, chain_code, segment_id, line_info
):
    mismatch = None
    non_mismatch = None

    if (
        target_chain
        and target_chain.chain_code == chain_code
        and chain_code
        and target_chain.segment_id != segment_id
    ):
        mismatch = "segment id"
        non_mismatch = " chain code"

    if (
        target_chain
        and target_chain.segment_id == segment_id
        and segment_id
        and target_chain.chain_code != chain_code
    ):
        mismatch = "chain code"
        non_mismatch = "segment id"

    if mismatch:
        msg = f"""
            while reading a chain from the file {line_info.file_name} at line {line_info.line_no}
            the {mismatch} changed but the {non_mismatch} didn't

            chain code previous: {target_chain.chain_code} current: |{chain_code}|
            segment id previous: {target_chain.segment_id} current: |{segment_id}|

            the current line is

            {line_info.line}

            note |'s are to delimit whitespace in the segment id and are not part of the segment id itself
                 a segment id is always 4 characters long
        """

        exit_error(msg)


def _parse_sequence(line: str, _: PDBLineInfo):
    global current_structure
    chain_code = line[11]
    chain_code = _as_string_or_none(chain_code)

    sequence = current_structure.sequences.setdefault(
        chain_code,
        Sequence(id=None, start_sequence_code=1, source=SequenceSource.SEQRES),
    )

    for offset in range(13):
        start = 19 + (offset * 4)
        end = 22 + (offset * 4)

        target_residue = line[start:end].strip()
        if not target_residue:
            break
        sequence.residues.append(target_residue)


def _parse_helix(line: str, line_info: PDBLineInfo):
    global current_structure

    chain_code = line[19]
    alternative_location = line[25]
    first_sequence_code = line[21:25]
    last_sequence_code = line[33:37]
    helix_type = line[38:40]

    chain_code = chain_code.strip()
    alternative_location = _as_string_or_none(alternative_location)
    first_sequence_code = _convert_to_int_or_exit(
        first_sequence_code, line_info, "helix.initial-sequence-number"
    )
    last_sequence_code = _convert_to_int_or_exit(
        last_sequence_code, line_info, "helix.last-sequence-number"
    )
    helix_type_offset = _convert_to_int_or_exit(helix_type, line_info, "helix.class")
    secondary_structure_type = PdbSecondaryStructureType(helix_type_offset)

    secondary_structure_element = SecondaryStructureElement(
        chain_code,
        first_sequence_code,
        last_sequence_code,
        alternative_location,
        secondary_structure_type,
    )

    current_structure.secondary_structure.setdefault(chain_code, []).append(
        secondary_structure_element
    )


def _parse_sheet(line, line_info):
    global current_structure

    chain_code = line[21]
    first_sequence_code = line[22:26]
    alternative_location = line[26]
    last_sequence_code = line[33:37]

    first_sequence_code = _convert_to_int_or_exit(
        first_sequence_code, line_info, "start sequence code"
    )
    last_sequence_code = _convert_to_int_or_exit(
        last_sequence_code, line_info, "end sequence_code"
    )
    alternative_location = _as_string_or_none(alternative_location)

    secondary_structure_element = SecondaryStructureElement(
        chain_code,
        first_sequence_code,
        last_sequence_code,
        alternative_location,
        PdbSecondaryStructureType.SHEET,
    )

    current_structure.secondary_structure.setdefault(chain_code, []).append(
        secondary_structure_element
    )


def _fixup_sequences(current_structure):
    sequences_by_index = {}
    sequence_count = 1

    sequence_residues_set = set()
    for sequence in current_structure.sequences.values():
        sequence_residues = tuple(sequence.residues)
        if sequence_residues not in sequence_residues_set:
            sequences_by_index[sequence_count] = sequence
            sequence_residues_set.add(sequence_residues)
            sequence_count += 1

    for sequence_id, sequence in sequences_by_index.items():
        sequence.id = sequence_id

    current_structure.sequences = sequences_by_index
    for sequence in current_structure.sequences.values():
        sequence.structure = current_structure


def _fixup_secondary_structure(current_structure):
    for secondary_structure_list in current_structure.secondary_structure.values():
        for secondary_structure in secondary_structure_list:
            secondary_structure.structure = current_structure


def _sequence_from_residues_if_no_seqres(structure):

    if not structure.sequences:
        chain_residues = {}
        chain_min_residues = {}
        chain_sequence_valid = {}
        for model in structure.models:
            for chain in model.chains.values():
                for residue in chain.residues:
                    chain_key = (chain.chain_code, chain.segment_id)
                    chain_residues.setdefault(chain_key, {})
                    chain_residues[chain_key].setdefault(
                        residue.sequence_code, set()
                    ).add(residue.residue_name)

        for chain_key in chain_residues:
            min_residue = min(chain_residues[chain_key].keys())
            max_residue = max(chain_residues[chain_key].keys())
            chain_min_residues[chain_key] = min_residue

            chain_sequence_valid[chain_key] = True
            for sequence_code in range(min_residue, max_residue + 1):
                if sequence_code not in chain_residues[chain_key]:
                    chain_sequence_valid[chain_key] = False
                    break
                if len(chain_residues[chain_key][sequence_code]) > 1:
                    chain_sequence_valid[chain_key] = False
                    break

        raw_chain_sequences = {}
        for chain_key in chain_residues:
            if not chain_sequence_valid[chain_key]:
                continue

            current_chain = chain_residues[chain_key]
            for sequence_code in sorted(current_chain):
                residue = current_chain[sequence_code].pop()
                raw_chain_sequences.setdefault(chain_key, []).append(residue)

        chain_sequences = {}
        for chain_id, (chain_key, sequence_residues) in enumerate(
            raw_chain_sequences.items()
        ):
            sequence_start = chain_min_residues[chain_key]

            sequence = Sequence(
                chain_id,
                sequence_start,
                sequence_residues,
                structure,
                SequenceSource.RESIDUE,
            )

            chain_sequences[chain_key] = sequence

        for sequence_chain_key, sequence in chain_sequences.items():
            for model in structure.models:
                for chain in model.chains.values():
                    model_chain_key = (chain.chain_code, chain.segment_id)
                    if sequence_chain_key == model_chain_key:
                        chain.sequence = sequence


def parse_pdb(lines: Iterable[str], source: str = "unknown"):
    global current_model, current_chain, current_residue, current_structure

    current_structure = Structure(source)

    for line_no, line in enumerate(lines, start=1):

        line = line.rstrip("\n")

        line = _pad_line_to_80(line)

        record_type = line[0:6].strip()

        line_info = PDBLineInfo(
            source, line_no=line_no, line=line, record_type=record_type
        )

        if record_type == "ATOM":
            if not current_model:
                current_model = Model(1)
                current_structure.models.append(current_model)
            _parse_atom(line, line_info)

        if record_type == "TER":
            if not current_chain:
                msg = f"""
                    at line {line_info.line_no} in {line_info.file_name}
                    there was a termination line when no chain was bein read

                    the line was

                    {line_info.line}
                """

                exit_error(msg)

            current_chain = None
            current_residue = None

        if record_type == "MODEL":
            model_number = line[10:14]
            model_number = _convert_to_int_or_exit(model_number, line_info, "MODEL")

            if current_model:
                msg = f"""
                    at line {line_info.line_no} in the file {line_info.file_name}
                    a new model started when a model was already open
                    the new model number was {model_number} the old model_numbers was {current_model.serial}

                    the line was

                    |{line_info.line}|

                    note |'s are to delimit whitespace in the line and are not part of the line itself
                """

                exit_error(msg)

            current_model = Model(model_number)
            current_structure.models.append(current_model)

        if record_type == "ENDMDL":
            current_model = None
            current_chain = None
            current_residue = None

        if record_type == "SEQRES":
            _parse_sequence(line, line_info)

        if record_type == "HELIX":
            _parse_helix(line, line_info)

        if record_type == "SHEET":
            _parse_sheet(line, line_info)

    _sequence_from_residues_if_no_seqres(current_structure)

    _fixup_sequences(current_structure)
    _fixup_secondary_structure(current_structure)

    _match_sequences_and_set_offsets(current_structure)

    for secondary_structure_list in current_structure.secondary_structure.values():
        secondary_structure_list.sort(key=lambda x: x.start_sequence_code)

    result = current_structure
    current_structure = None
    current_model = None
    current_chain = None
    current_residue = None

    return result


def _find_last_row_indices(lines, targets):
    result = {}
    for i, line in enumerate(lines):
        for target in targets:
            if target in line:
                result[target] = i

    return result


def _attibute_index_to_name(items, target_index):
    result = None
    for name, index in items.attribute_list_with_order:
        if index == target_index:
            result = name
            break
    return result


class ComputedLineInfo:
    def __init__(self, lines: List[str], file_name: str, search_window=10):
        self._lines: List[str] = lines
        self.file_name = file_name
        self._container_offset = None
        self._line_number = None
        self._search_window = search_window
        self._search_terms = None

    def set_container(self, container: str):
        for line_number, line in enumerate(self._lines, start=1):

            if line.strip().startswith(f"_{container}."):
                self._container_offset = line_number
                self._line_number = f"close to / below {self._container_offset}"

    def set_container_row(self, offset):
        self._line_number = self._container_offset + offset + 1
        self._search_terms = None

    @property
    def line(self):
        return (
            self._lines[self._line_number]
            if self._line_number
            else "value of line unknown"
        )

    @property
    def line_no(self):

        result = self._line_number

        test_line = self._line_number if self._line_number else None

        if self._search_terms:

            start = test_line - self._search_window
            end = test_line + self._search_window
            scores = self.score_lines(end, start)

            failed = self._scores_good(scores)

            if failed:
                start = self._container_offset
                end = len(self._lines) - 1
                scores = self._score_lines(start, end)

            failed = self._scores_good(scores)

            if not failed:
                result = scores.most_common()[0][0]

        return result

    def _scores_good(self, scores):
        failed = False
        if len(scores) > 1:
            failed = False
            if scores.most_common()[0][1] == scores.most_common()[1][1]:
                failed = True

            if scores.most_common()[0][1] != len(self._search_terms):
                failed = True
        return failed

    def score_lines(self, end, start):
        scores = Counter()
        for i, search_line_line_number in enumerate(range(start, end)):

            if search_line_line_number > 0 and search_line_line_number < (
                len(self._lines) - 1
            ):
                fields = self._lines[search_line_line_number].split()
                for search_term in self._search_terms:
                    print(
                        i,
                        search_line_line_number,
                        str(search_term) in fields,
                        search_term,
                        fields,
                    )
                    if str(search_term) in fields:
                        scores[search_line_line_number + 1] += 1
        return scores

    def set_search_terms(self, *args):
        self._search_terms = list(args)


def _parse_cif_atoms(data: DataContainer, line_info: ComputedLineInfo) -> Structure:
    global current_structure, current_model, current_chain, current_residue

    atoms = data.get_object("atom_site")
    line_info.set_container("atom_site")

    record_type_index = atoms.get_attribute_index("group_PDB")
    atom_id_index = atoms.get_attribute_index("id")
    element_index = atoms.get_attribute_index("type_symbol")

    seq_code_index = _get_attribute_index_favour_auth(atoms, "{source}_seq_id")
    residue_name_index = _get_attribute_index_favour_auth(atoms, "{source}_comp_id")
    chain_code_index = _get_attribute_index_favour_auth(atoms, "{source}_asym_id")
    atom_name_index = _get_attribute_index_favour_auth(atoms, "{source}_atom_id")

    alternative_location_index = atoms.get_attribute_index("pdbx_PDB_ins_code")

    model_index = atoms.get_attribute_index("pdbx_PDB_model_num")
    occupancy_index = atoms.get_attribute_index("occupancy")
    x_index = atoms.get_attribute_index("Cartn_x")
    y_index = atoms.get_attribute_index("Cartn_y")
    z_index = atoms.get_attribute_index("Cartn_z")
    B_iso_or_equiv_index = atoms.get_attribute_index("B_iso_or_equiv")

    current_model = None
    for i, row in enumerate(atoms, start=1):
        line_info.set_container_row(i)
        line_info.set_search_terms(*row)

        record_type = row[record_type_index]

        if record_type == "ATOM":
            atom_id = row[atom_id_index]
            element = row[element_index]
            chain_code = row[chain_code_index]
            atom_name = row[atom_name_index]
            sequence_code = row[seq_code_index]
            alternative_location = row[alternative_location_index]
            residue_name = row[residue_name_index]
            model_number = row[model_index]
            occupancy = row[occupancy_index]
            x = row[x_index]
            y = row[y_index]
            z = row[z_index]
            b_iso_or_equiv = row[B_iso_or_equiv_index]

            seq_code_attribute_name = _attibute_index_to_name(atoms, seq_code_index)

            # use correct line info and correct name in conversion of sequence_id
            atom_id = _convert_to_int_or_exit(atom_id, None, "atom_id")
            element = _as_string_or_none(element)
            sequence_code = _convert_to_int_or_exit(
                sequence_code,
                line_info,
                f"sequence atom_id [{seq_code_attribute_name}]",
            )
            alternative_location = _as_string_or_none(alternative_location)
            model_number = _convert_to_int_or_exit(model_number, line_info, "model")
            occupancy = _convert_to_float_or_exit(occupancy, line_info, "occupancy")
            x = _convert_to_float_or_exit(x, line_info, "x")
            y = _convert_to_float_or_exit(y, line_info, "y")
            z = _convert_to_float_or_exit(z, line_info, "z")

            b_iso_or_equiv = _as_string_or_none(b_iso_or_equiv)
            if b_iso_or_equiv:
                b_iso_or_equiv = _convert_to_float_or_exit(
                    b_iso_or_equiv, line_info, "b value"
                )

            if not current_model or model_number != current_model.serial:
                current_model = Model(model_number, structure=current_structure)
                current_structure.models.append(current_model)
                current_chain = None

            if current_chain and current_chain.chain_code != chain_code:
                current_chain = None
                current_residue = None

            sequence = (
                current_structure.sequences[sequence_code]
                if sequence_code in current_structure.sequences
                else None
            )

            if not current_chain:
                current_chain = Chain(
                    chain_code=chain_code, sequence=sequence, model=current_model
                )
                current_model.chains[chain_code] = current_chain

            if current_residue and current_residue.sequence_code != sequence_code:
                current_residue = None

            if not current_residue:
                current_residue = Residue(
                    sequence_code, residue_name, chain=current_chain
                )
                current_chain.residues.append(current_residue)

            current_atom = Atom(
                atom_id,
                atom_name,
                x,
                y,
                z,
                alternative_location,
                element,
                b_iso_or_equiv,
                occupancy,
                current_residue,
            )

            current_residue.atoms.append(current_atom)

    current_model = None
    current_chain = None
    current_residue = None

    result = current_structure
    current_structure = None

    return result


def _get_attribute_index_favour_auth(atoms, attribute_template):
    auth_attribute_name = attribute_template.format(source="auth")
    label_attribute_name = attribute_template.format(source="label")
    if atoms.has_attribute(auth_attribute_name):
        result = atoms.get_attribute_index(auth_attribute_name)
    else:
        result = atoms.get_attribute_index(label_attribute_name)

    return result


def _parse_cif_helix(data, line_info):
    global current_structure

    if helices := data.get_object("struct_conf"):
        line_info.set_container("struct_conf")

        chain_code_index = _get_attribute_index_favour_auth(
            helices, "beg_{source}_asym_id"
        )
        secondary_start_index = _get_attribute_index_favour_auth(
            helices, "beg_{source}_seq_id"
        )
        secondary_end_index = _get_attribute_index_favour_auth(
            helices, "end_{source}_seq_id"
        )
        alternative_location_index = helices.get_attribute_index(
            "pdbx_beg_PDB_ins_code"
        )
        helix_type_index = helices.get_attribute_index("pdbx_PDB_helix_class")

        for i, line in enumerate(helices):
            line_info.set_container_row(i)
            line_info.set_search_terms(*line)

            chain_code = line[chain_code_index]
            alternative_location = line[alternative_location_index]
            first_sequence_code = line[secondary_start_index]
            last_sequence_code = line[secondary_end_index]
            helix_type = line[helix_type_index]

            alternative_location = _as_string_or_none(alternative_location)
            first_sequence_code = _convert_to_int_or_exit(
                first_sequence_code, line_info, "helix.initial-sequence-number"
            )
            last_sequence_code = _convert_to_int_or_exit(
                last_sequence_code, line_info, "helix.last-sequence-number"
            )
            helix_type_offset = _convert_to_int_or_exit(
                helix_type, line_info, "helix.class"
            )
            secondary_structure_type = PdbSecondaryStructureType(helix_type_offset)

            secondary_structure_element = SecondaryStructureElement(
                chain_code,
                first_sequence_code,
                last_sequence_code,
                alternative_location,
                secondary_structure_type,
                structure=current_structure,
            )

            current_structure.secondary_structure.setdefault(chain_code, []).append(
                secondary_structure_element
            )


def _parse_cif_sheet(data, line_info):
    global current_structure

    if sheets := data.get_object("struct_sheet_range"):
        line_info.set_container("struct_sheet_range")

        chain_code_index = _get_attribute_index_favour_auth(
            sheets, "beg_{source}_asym_id"
        )
        secondary_start_index = _get_attribute_index_favour_auth(
            sheets, "beg_{source}_seq_id"
        )
        secondary_end_index = _get_attribute_index_favour_auth(
            sheets, "end_{source}_seq_id"
        )
        alternative_location_index = sheets.get_attribute_index("pdbx_beg_PDB_ins_code")

        for i, line in enumerate(sheets):
            line_info.set_container_row(i)
            line_info.set_search_terms(line)
            chain_code = line[chain_code_index]
            first_sequence_code = line[secondary_start_index]
            last_sequence_code = line[secondary_end_index]
            alternative_location = line[alternative_location_index]

            first_sequence_code = _convert_to_int_or_exit(
                first_sequence_code, None, "start sequence code"
            )
            last_sequence_code = _convert_to_int_or_exit(
                last_sequence_code, None, "end sequence_code"
            )
            alternative_location = _as_string_or_none(alternative_location)

            secondary_structure_element = SecondaryStructureElement(
                chain_code,
                first_sequence_code,
                last_sequence_code,
                alternative_location,
                PdbSecondaryStructureType.SHEET,
            )

            current_structure.secondary_structure.setdefault(chain_code, []).append(
                secondary_structure_element
            )


def parse_cif(lines: Iterable[str], source: str = "unknown") -> Structure:
    global current_structure, current_indices

    current_lines = [line for line in lines]

    current_indices = _find_last_row_indices(
        current_lines,
        [
            "_atom_site",
        ],
    )

    current_structure = Structure(source)

    reader = PdbxReader(current_lines)
    data = []
    reader.read(data)
    data = data[0]

    line_info = ComputedLineInfo(current_lines, file_name=source)

    _parse_cif_sequence(data, line_info)
    _parse_cif_helix(data, line_info)
    _parse_cif_sheet(data, line_info)
    structure = _parse_cif_atoms(data, line_info)

    _fixup_cif_sequences(structure)

    _match_sequences_and_set_offsets(structure)

    for secondary_structure_list in structure.secondary_structure.values():
        secondary_structure_list.sort(key=lambda x: x.start_sequence_code)

    return structure


def _fixup_cif_sequences(structure):
    sequence_id_map = {}
    for new_sequence_id, (original_sequence_id, sequence) in enumerate(
        structure.sequences.items(), start=1
    ):
        sequence_id_map[original_sequence_id] = new_sequence_id
    for old_sequence_id, new_sequence_id in sequence_id_map.items():
        sequence = structure.sequences.pop(old_sequence_id)
        sequence.id = new_sequence_id
        structure.sequences[new_sequence_id] = sequence


def _get_lenght_longest_residue_name(structure):

    residue_names = set()
    for sequence in structure.sequences.values():
        residue_names.update(sequence.residues)

    for model in structure.models:
        for chain in model.chains.values():
            residue_names.update([residue.residue_name for residue in chain])

    name_lengths = [len(residue_name) for residue_name in residue_names]

    return max(name_lengths)


def _match_sequences_and_set_offsets(structure):
    if structure.sequences:
        max_residue_name_length = _get_lenght_longest_residue_name(structure)
        chain_matches = {}
        chain_offsets = {}
        chain_sequence_starts = {}
        for chain in structure.models[0].chains.values():
            chain_segment_id_key = chain.chain_code, chain.segment_id

            chain_residues = {}
            chain_sequence_starts[chain_segment_id_key] = chain.residues[
                0
            ].sequence_code

            for residue in chain.residues:
                chain_residues[residue.sequence_code] = residue.residue_name

            min_residue = min(chain_residues.keys())
            max_residue = max(chain_residues.keys())

            match_residues = []
            wildcard = "." * max_residue_name_length
            for i in range(min_residue, max_residue + 1):

                match_residue = (
                    chain_residues[i].ljust(max_residue_name_length, "-")
                    if i in chain_residues
                    else wildcard
                )
                match_residues.append(match_residue)
            match_residues = "".join(match_residues)

            for index, sequence in structure.sequences.items():
                sequence_residues = [
                    residue.ljust(max_residue_name_length, "-")
                    for residue in sequence.residues
                ]
                sequence_residues = "".join(sequence_residues)

                match = re.search(match_residues, sequence_residues)

                chain_key = chain.chain_code, chain.segment_id
                if match:
                    chain_offsets[chain_key] = int(
                        match.start() / max_residue_name_length
                    )
                    chain_matches[chain_key] = sequence.id
                    continue

        sequence_start_counts = {}
        chain_sequence_id_and_start = {}
        for chain_key, chain_start in chain_sequence_starts.items():
            if chain_key in chain_offsets:
                sequence_start = chain_start - chain_offsets[chain_key]
                sequence_id = chain_matches[chain_key]
                sequence_start_counts.setdefault(sequence_id, Counter())[
                    sequence_start
                ] += 1
                chain_sequence_id_and_start[chain_key] = (sequence_id, sequence_start)

        for sequence_id, sequence_starts in sequence_start_counts.items():
            if len(sequence_starts) > 1:
                bad_chains = [
                    chain_key
                    for chain_key, (chain_sequence_id, _) in chain_sequence_id_and_start
                    if sequence_id == chain_sequence_id
                ]
                bad_chains = [
                    f"chain_code: {chain_key[0]} sequence_code: {chain_key[1]}"
                    for chain_key in bad_chains
                ]
                bad_chains = "\n".join(bad_chains)  # noqua: E999
                msg = """
                    for sequence {sequence_id} there were multiple possible sequence starts
                    derived from the sequences of the chains
                    {bad_chains}
                """
                msg = dedent(msg)
                msg = f(msg)
                raise StructureParseException(msg)

        sequences_by_id = {
            sequence.id: sequence for sequence in structure.sequences.values()
        }
        chains_by_chain_key = {
            (chain.chain_code, chain.segment_id): chain
            for chain in structure.models[0].chains.values()
        }

        for chain_key, (sequence_id, _) in chain_sequence_id_and_start.items():
            sequence = sequences_by_id[sequence_id]
            chain = chains_by_chain_key[chain_key]
            chain.sequence = sequence


def _parse_cif_sequence(data, line_info):
    global current_structure, current_indices

    sequence = data.get_object("entity_poly_seq")
    line_info.set_container("entity_poly_seq")

    entity_id_index = sequence.get_attribute_index("entity_id")
    monomer_id_index = sequence.get_attribute_index("mon_id")

    for i, row in enumerate(sequence.row_list, start=1):
        line_info.set_container_row(i)
        line_info.set_search_terms(*row)

        entity_id = row[entity_id_index]
        monomer_id = row[monomer_id_index]
        current_structure.sequences.setdefault(
            entity_id,
            Sequence(
                entity_id,
                None,
                structure=current_structure,
                source=SequenceSource.SEQRES,
            ),
        )

        current_structure.sequences[entity_id].residues.append(monomer_id)


PDB_RECORD_IDS = set(
    [
        "HEADER",
        "OBSLTE",
        "TITLE",
        "SPLT",
        "CAVEAT",
        "COMPND",
        "SOURCE",
        "KEYWDS",
        "EXPDTA",
        "NUMMDL",
        "MDLTYP",
        "AUTHOR",
        "REVDAT",
        "SPRSDE",
        "JRNL",
        "REMARKS",
        "DBREF",
        "DBREF1",
        "DBREF2",
        "SEQADV",
        "SEQRES",
        "MODRES",
        "HET",
        "FORMUL",
        "HETNAM",
        "HETSYN",
        "HELIX",
        "SHEET",
        "SSBOND",
        "LINK",
        "CISPEP",
        "SITE" "CRYST1",
        "MTRIXn",
        "ORIGXn",
        "SCALEn",
        "MODEL",
        "ANISOU",
        "TER",
        "ENDMDL",
        "CONECT",
        "MASTER",
        "END",
    ]
)


class RCSBFileType(LowercaseStrEnum):
    PDB = (auto(),)
    CIF = (auto(),)
    UNKNOWN = auto()


def guess_cif_or_pdb(lines: Iterable[str], file_name: str = "", test_length: int = 100):

    pdb = 0
    cif = 0

    file_path = Path(file_name)

    if file_path.suffix.lower() in (".cif", ".mmcif", ".pdbx"):
        cif = 1
    elif file_path.suffix.lower() == ".pdb":
        pdb = 1
    else:
        for line in lines[:test_length]:
            fields = line.strip().split()
            if fields[0] in PDB_RECORD_IDS:
                pdb += 1
            if (
                fields[0].startswith("data_")
                or fields[0][0] in ("_", ";")
                or fields[0] == "loop_"
            ):
                cif += 1

    if pdb > cif:
        result = RCSBFileType.PDB
    elif cif > pdb:
        result = RCSBFileType.CIF
    else:
        result = RCSBFileType.UNKNOWN

    return result


if __name__ == "__main__":
    root = Path(
        "/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines/tests/rcsb/test_data/"
    )
    file_name = random.choice(
        [
            root / Path("1l2y_short.cif"),
            root / Path("1l2y_short.pdb"),
        ]
    )
    file_path = Path(file_name)
    fh = open(file_path)

    file_name = file_path.parts[-1]
    if file_path.suffix == ".cif":
        structure = parse_cif(fh, file_name)
    else:
        structure = parse_pdb(fh, file_name)

    print(structure.sequences)
    print(structure.secondary_structure)
    for model in structure.models:
        print(len(model.chains))
        for chain in model.chains:
            for residue in chain.residues:
                for atom in residue:
                    print(
                        model.serial,
                        "|",
                        chain.chain_code,
                        chain.segment_id,
                        "|",
                        residue.sequence_code,
                        residue.residue_name,
                        "|",
                        atom.serial,
                        atom.atom_name,
                        atom.alternative_location,
                        atom.x,
                        atom.y,
                        atom.z,
                        atom.element,
                        atom.temp_fact,
                        atom.occupancy,
                    )
    print(structure.secondary_structure)
    print(structure.sequences)
