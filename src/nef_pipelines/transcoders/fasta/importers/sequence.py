from collections import Counter
from dataclasses import dataclass
from itertools import chain, cycle, islice
from pathlib import Path
from typing import Iterable, List

import typer
from fastaparser import Reader
from ordered_set import OrderedSet
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    BadResidue,
    MoleculeType,
    get_chain_code_iter,
    offset_chain_residues,
    sequence_3let_to_res,
    sequence_to_nef_frame,
    translate_1_to_3,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import (
    NEWLINE,
    STDIN,
    exit_error,
    is_int,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.fasta import import_app

CHAIN_STARTS_HELP = """first residue number of sequences can be a comma separated list or added multiple times
                       note the offsets are applied on top of any chain starts present in the file headers unless
                       the option --no-header is used"""

NO_HEADER_HELP = """don't read the NEF-Pipelines sequence header if present
                    the format of the header is >{entry_name} CHAIN: {chain} | START RESIDUE: {chain_start}
                    an example would be >test CHAIN: A | START: -2 for the entry test where chain A starts at -2
                   """

app = typer.Typer()

NO_CHAIN_START_HELP = """don't include the start chain link type on a chain for the first residue [linkage will be
                         middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                         option multiple times to set chain starts for multiple chains"""
NO_CHAIN_END_HELP = """don't include the end chain link type on a chain for the last residue [linkage will be
                       middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                       option multiple times to set chain ends for multiple chains"""


# todo add comment to other sequences etc
@import_app.command()
def sequence(
    chain_codes: List[str] = typer.Option(
        [],
        "--chains",
        help="chain codes to use for the imported chains, can be a a comma separated list or can be called "
        "multiple times",
        metavar="<CHAIN-CODES>",
    ),
    starts: List[str] = typer.Option(
        [],
        "--starts",
        help=CHAIN_STARTS_HELP,
        metavar="<START>",
    ),
    no_chain_starts: List[str] = typer.Option(
        [], "--no-chain-start", help=NO_CHAIN_START_HELP
    ),
    no_chain_ends: List[str] = typer.Option(
        [], "--no-chain-end", help=NO_CHAIN_END_HELP
    ),
    # TODO: unused inputs!
    entry_name: str = typer.Option(None, help="a name for the entry if required"),
    in_file: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [- is stdin]",
    ),
    molecule_types: List[MoleculeType] = typer.Option(
        [
            MoleculeType.PROTEIN,
        ],
        "--molecule-type",
        help="molecule type one of protein, dna, rna or  carbohydrate",
    ),
    no_header: bool = typer.Option(False, "--no-header", help=NO_HEADER_HELP),
    file_names: List[Path] = typer.Argument(
        ..., help="the file to read", metavar="<FASTA-FILE>"
    ),
):
    """- convert fasta sequence to nef"""

    file_names = parse_comma_separated_options(file_names)

    chain_codes = parse_comma_separated_options(chain_codes)
    if not chain_codes:
        chain_codes = [
            "A",
        ]

    no_chain_starts = parse_comma_separated_options(no_chain_starts)
    if not no_chain_starts:
        no_chain_starts = [
            False,
        ]

    no_chain_ends = parse_comma_separated_options(no_chain_ends)
    if no_chain_ends:
        no_chain_ends = [
            False,
        ]

    starts = [int(elem) for elem in parse_comma_separated_options(starts)]
    if not starts:
        starts = [
            1,
        ]

    molecule_types = parse_comma_separated_options(molecule_types)
    if not molecule_types:
        molecule_types = [
            MoleculeType.PROTEIN,
        ]

    entry = read_or_create_entry_exit_error_on_bad_file(in_file)

    entry = pipe(
        entry,
        chain_codes,
        starts,
        no_chain_starts,
        no_chain_ends,
        molecule_types,
        no_header,
        file_names,
        entry_name,
    )

    print(entry)


def pipe(
    entry: Entry,
    chain_codes: List[str],
    starts: List[int],
    no_chain_starts: List[bool],
    no_chain_ends: List[bool],
    molecule_types: List[MoleculeType],
    no_header: bool,
    file_names,
    entry_name: str,
):
    fasta_frames = []

    fasta_residues, read_entry_name = _read_sequences(
        file_names, chain_codes, molecule_types, not no_header
    )

    if read_entry_name and not entry_name:
        entry_name = "__".join(read_entry_name)
        if not entry_name:
            entry_name = "fasta"
        entry.entry_id = entry_name
    elif entry_name:
        entry.entry_id = entry_name
    else:
        entry.entry_id = "fasta"

    read_chain_codes = residues_to_chain_codes(fasta_residues)

    offsets = _get_sequence_offsets(read_chain_codes, starts)

    fasta_residues = offset_chain_residues(fasta_residues, offsets)

    fasta_residues = sorted(fasta_residues)

    fasta_frames.append(
        sequence_to_nef_frame(fasta_residues, no_chain_starts, no_chain_ends)
    )

    entry = add_frames_to_entry(entry, fasta_frames)

    return entry


def _get_sequence_offsets(chain_codes: List[str], starts: List[int]):

    offsets = [start - 1 for start in starts]
    cycle_starts = chain(
        offsets,
        cycle(
            [
                0,
            ]
        ),
    )
    offsets = list(islice(cycle_starts, len(chain_codes)))

    return {chain_code: offset for chain_code, offset in zip(chain_codes, offsets)}


def residues_to_chain_codes(residues: List[SequenceResidue]) -> List[str]:
    return list(OrderedSet([residue.chain_code for residue in residues]))


@dataclass
class Sequence:
    entry_id: str
    comment: str
    sequence: List[str]
    chain_code: str = None
    starts: int = 1


# could do with taking a list of offsets
# noinspection PyUnusedLocal
#
def _parse_fasta(fasta_sequence, parse_header: bool = True) -> Sequence:
    definition = fasta_sequence.formatted_definition_line()
    bar_count = definition.count("|")
    last_part = definition.split()[-1]
    is_bracketed = last_part.startswith("(") and last_part.endswith(")")
    is_last_field_number = last_part.strip("()").isdigit()

    chain_code = None
    start = 1

    if fasta_sequence.description.startswith("NEFPLS") and parse_header:
        fields = fasta_sequence.description.split("|")
        for field in fields:

            field = field.strip()

            if field.startswith("CHAIN:"):
                chain_code = field.split()[-1]

            if field.startswith("START:"):
                if is_int(field[-1]):
                    start = int(field.split()[-1])

        entry_id, comment = fasta_sequence.id, fasta_sequence.description

    elif bar_count == 3 and is_bracketed and is_last_field_number:
        fields = definition.split("|")
        entry_id = fields[0].lstrip(">")
        comment = "__".join(fields[1:])
    else:
        sequence_id = "".join([c if c.isalnum() else "_" for c in fasta_sequence.id])
        entry_id, comment = sequence_id, fasta_sequence.description

    letters = [letter_code.letter_code for letter_code in fasta_sequence.sequence]
    return Sequence(entry_id, comment, letters, chain_code, start)


@dataclass
class SequenceInfo:
    entry_id: str
    chain_code: str
    start: int


def _exit_if_there_are_file_and_input_chain_codes(
    file_chain_codes, input_chain_codes, file_paths
):
    input_chain_codes = [
        chain_code for chain_code in input_chain_codes if chain_code is not None
    ]
    file_chain_codes = [
        chain_code for chain_code in file_chain_codes if chain_code is not None
    ]
    if file_chain_codes and input_chain_codes:
        msg = f"""
            there are chain codes in the files and input arguments
            the chain codes in the files are {','.join(file_chain_codes)}
            the chain codes in the input arguments are {','.join(input_chain_codes)}
            the files are
            {NEWLINE.join([str(file_path) for file_path in file_paths])}
            chain codes must come from files or inputs not both!
            """
        exit_error(msg)


def _exit_if_there_are_gaps_in_file_chain_codes(file_chain_codes, file_paths):

    file_chain_codes = [
        chain_code for chain_code in file_chain_codes if chain_code is not None
    ]
    if len(file_chain_codes) != len(file_chain_codes):
        msg = f"""
            there are sequences without chain codes in the files
            {NEWLINE.join([str(file_path) for file_path in file_paths])}
            either all sequences in files must have a chain code or none
            """
        exit_error(msg)


def _read_sequences(
    file_paths: List[Path],
    chain_codes: Iterable[str],
    molecule_types: List[MoleculeType],
    parse_header=False,
) -> List[SequenceResidue]:

    sequence_records = []

    for file_path in file_paths:
        try:
            with open(file_path) as handle:
                try:
                    reader = Reader(handle)
                    for fasta_sequence in reader:
                        sequence_records.append(
                            _parse_fasta(fasta_sequence, parse_header)
                        )

                except Exception as e:
                    # check if relative to os.getcwd
                    exit_error(f"Error reading fasta file {str(file_path)}", e)
        except IOError as e:
            exit_error(f"couldn't open {file_path} because:\n{e}", e)

    number_sequences = len(sequence_records)
    number_molecule_types = len(molecule_types)

    if number_molecule_types == 1:
        molecule_types = molecule_types * number_sequences
    elif number_molecule_types == 0 or number_molecule_types < number_sequences:
        msg = f"""
            number molecule types [{number_molecule_types}] is different from number of chains {number_sequences}
        """
        exit_error(msg)

    residues = OrderedSet()
    # read as many chain codes as there are sequences
    # https://stackoverflow.com/questions/16188270/get-a-fixed-number-of-items-from-a-generator

    file_chain_codes = [
        sequence_record.chain_code for sequence_record in sequence_records
    ]

    _exit_if_there_are_gaps_in_file_chain_codes(file_chain_codes, file_paths)

    # this keeps the default input chain code as A
    file_chain_codes = [
        chain_code for chain_code in file_chain_codes if chain_code is not None
    ]
    if file_chain_codes and chain_codes == ["A"]:
        chain_codes = []

    _exit_if_there_are_file_and_input_chain_codes(
        file_chain_codes, chain_codes, file_paths
    )

    _exit_if_there_are_replicate_chain_codes_from_files(
        file_chain_codes, chain_codes, file_paths
    )

    chain_codes = file_chain_codes if file_chain_codes else chain_codes

    chain_code_iter = get_chain_code_iter(chain_codes)
    for sequence_record, chain_code, molecule_type in zip(
        sequence_records, chain_code_iter, molecule_types
    ):

        try:
            sequence_3_let = translate_1_to_3(
                sequence_record.sequence, molecule_type=molecule_type
            )
        except BadResidue as e:
            exit_error(
                f"Error translating sequence {sequence_record} to 3 letter code {e}",
                e,
            )

        chain_code = (
            sequence_record.chain_code if sequence_record.chain_code else chain_code
        )
        chain_residues = sequence_3let_to_res(sequence_3_let, chain_code)

        chain_residues = offset_chain_residues(
            chain_residues,
            {sequence_record.chain_code: sequence_record.starts - 1},
        )

        residues.update(chain_residues)

    entry_names = [
        sequence_record.entry_id
        for sequence_record in sequence_records
        if sequence_record.entry_id
    ]

    return residues, entry_names


def _exit_if_there_are_replicate_chain_codes_from_files(
    file_chain_codes, input_chain_codes, file_paths
):

    file_chain_counts = Counter(file_chain_codes)
    file_chain_replicates = {
        chain_code: count
        for chain_code, count in file_chain_counts.items()
        if count > 1 and chain_code is not None
    }
    input_chain_counts = Counter(input_chain_codes)
    input_chain_replicates = {
        chain_code: count
        for chain_code, count in input_chain_counts.items()
        if count > 1
    }

    if file_chain_replicates:
        repeats = " ".join(
            [
                f"{chain_code} [{count}]"
                for chain_code, count in file_chain_replicates.items()
            ]
        )

        msg = f"""
                some of the input chain codes are repeated: {repeats}
                {NEWLINE.join([str(file_path) for file_path in file_paths])}
                all chain codes must be unique
            """
        exit_error(msg)

    if input_chain_replicates:
        msg = f"""
            some of the chain codes: {','.join(input_chain_replicates.keys())}
            are repeated in the input each chain must have a unique chain code
        """

        exit_error(msg)

    all_chain_counts = Counter(file_chain_codes + input_chain_codes)
    all_chain_replicates = {
        chain_code: count
        for chain_code, count in all_chain_counts.items()
        if count > 1 and chain_code is not None
    }
    if all_chain_replicates:
        msg = f"""
                some of the chain codes are repeated: {','.join(all_chain_replicates.keys())}
                the chain codes come from a combination of the input arguments and the files
                {NEWLINE.join([str(file_paths) for file_path in file_paths])}
                all chain_codes_must_be_unique
            """
        exit_error(msg)
