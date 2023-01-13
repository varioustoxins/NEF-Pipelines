import sys
from itertools import zip_longest
from pathlib import Path
from sys import stdout
from typing import Dict, List

import typer

from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.sequence_lib import (
    frame_to_chains,
    get_chain_starts,
    sequence_from_frame,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import STDIN, exit_error, parse_comma_separated_options
from nef_pipelines.transcoders.fasta.exporters.sequence import (
    molecular_system_from_entry_or_exit,
)
from nef_pipelines.transcoders.nmrview import export_app

app = typer.Typer()


@export_app.command()
def sequences(
    file_name_template: str = typer.Option(
        "%s.seq",
        "-t",
        "--template",
        help="the template for the filename to export to %s will get replaced by the name of the chain or a filename if"
        "set with the file-names option",
        metavar="<sequence-file.seq>",
    ),
    input: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read input from [- is stdin]"
    ),
    output_to_stdout: bool = typer.Option(
        False, "-o", "--out", help="write the files to stdout for debugging"
    ),
    file_names: List[str] = typer.Option(
        None,
        "--file-names",
        help="alternative filenames to export to, can be a comma "
        "separated list of filenames. Repeated calls add "
        "more filenames.",
    ),
    chain_selectors: List[str] = typer.Argument(
        None,
        help="the names of the chains to export, can be a comma separated"
        " list of chains. Repeated calls add more chains. The default"
        " is to write all chains",
        metavar="<chains>",
    ),
):
    chain_selectors = parse_comma_separated_options(chain_selectors)

    file_names = parse_comma_separated_options(file_names)

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    molecular_system_frame = molecular_system_from_entry_or_exit(entry)

    chain_selectors = (
        frame_to_chains(molecular_system_frame)
        if not chain_selectors
        else chain_selectors
    )

    chains_to_filenames = _build_chains_to_filenames(
        chain_selectors, file_names, file_name_template
    )

    _exit_if_more_file_names_than_chains(chain_selectors, file_names)

    sequences = _nmrview_sequences_from_entry(molecular_system_frame, chain_selectors)

    same_width_names = _make_names_same_width_dict(chains_to_filenames.values())

    out_width = -1
    for chain_code, file in sequences.items():
        file_name = chains_to_filenames[chain_code]
        if output_to_stdout:
            file_pointer = sys.stdout
        else:
            file_pointer = _open_for_writing_or_exit(file_name)
        out = f"------------- {same_width_names[file_name]} -------------"
        out_width = len(out)
        print(out, file=file_pointer)
        print(file, file=file_pointer)
    print("-" * out_width)

    if not output_to_stdout:
        if not stdout.isatty():
            print(entry)


def _exit_if_more_file_names_than_chains(chain_selectors, file_names):
    if len(file_names) > len(chain_selectors):
        msg = f"""\
            there are more file_names than chains !

            chains = {','.join(chain_selectors)}
            file names: {''.join(file_names)}
        """

        exit_error(msg)


def _nef_to_nmrview_sequences(
    residues: List[SequenceResidue], chain_codes: List[str]
) -> Dict[str, List[str]]:

    chain_starts = get_chain_starts(residues)

    residues_by_chain = {}
    for chain_code in chain_codes:
        residues_by_chain[chain_code] = [
            residue for residue in residues if residue.chain_code == chain_code
        ]

    residue_sequences = {}
    for chain_code in chain_codes:
        residue_sequences[chain_code] = [
            residue.residue_name for residue in residues_by_chain[chain_code]
        ]

    result = {}
    for chain_code, residue_sequence in residue_sequences.items():

        chain_start = chain_starts[chain_code]

        sequence_lines = []
        for i, residue in enumerate(residue_sequence):

            residue = residue.lower()

            if i == 0:
                if chain_start != 1:
                    line = f"{residue} {chain_start}"
            else:
                line = residue

            sequence_lines.append(line)

        result[chain_code] = "\n".join(sequence_lines)

    return result


def _nmrview_sequences_from_entry(molecular_system_frame, chain_codes):

    residues = sequence_from_frame(molecular_system_frame)

    nmrview_sequences = _nef_to_nmrview_sequences(residues, chain_codes)

    return nmrview_sequences


def _make_names_same_width_dict(names: List[str]) -> Dict[str, str]:
    print(names)
    max_length = -1
    for name in names:
        name_len = len(name)
        max_length = name_len if name_len > max_length else max_length

    result = {}
    for name in names:
        result[name] = name.center(max_length)

    return result


def _open_for_writing_or_exit(file_name):
    try:
        result = open(file_name, "w")
    except Exception as e:
        msg = f"failed to open {file_name} for writing because {e}"

        exit_error(msg, e)

    return result


def _build_chains_to_filenames(
    chain_selectors: str, file_names: str, file_name_template: str
) -> Dict[str, str]:

    result = {}

    for chain_selector, file_name in zip_longest(chain_selectors, file_names):
        if file_name:
            result[chain_selector] = file_name
        else:
            result[chain_selector] = file_name_template % chain_selector

    return result
