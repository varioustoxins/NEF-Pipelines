from pathlib import Path
from sys import stdout
from typing import Dict, List

import typer
from fyeah import f

from nef_pipelines.lib.nef_lib import (
    is_save_frame_name_in_entry,
    molecular_system_from_entry,
    molecular_system_from_entry_or_exit,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    chains_from_frames,
    get_chain_starts,
    sequences_from_frames,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import STDIN, exit_error, in_pytest, smart_open
from nef_pipelines.transcoders.fasta.exporters.sequence import STDOUT
from nef_pipelines.transcoders.nmrview import export_app

app = typer.Typer()

OUTPUT_HELP = """\
Where to write the output to. The default is a set of files with each file is named by a template of the form
"{chain_code}.seq" where {chain_code} is replaced by the chain name. If set to a string containing {chain_code} the
string will be used as a template for the filenames If set to - output will be written to stdout and individual chains
will be written as virtual files with a banner of the form ------------- chain_code.seq ------------- separating them.
A template starting with - will still output to stdout but will use the rest of the string as a template for the
filename
"""


@export_app.command()
def sequences(
    input: Path = typer.Option(
        STDIN, "-i", "--in", help="sequence_text to read input from [- is stdin]"
    ),
    output_destination: str = typer.Option(
        "{chain_code}.seq", "-o", "--out", help=OUTPUT_HELP
    ),
    chain_selectors: List[str] = typer.Argument(
        None,
        help="the names of the chains to export, can be a comma separated"
        " list of chains. Repeated calls add more chains. The default"
        " is to write all chains",
        metavar="<chains>",
    ),
):

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    _exit_if_no_molecular_system_in_entry(entry)

    molecular_system_frame = entry.get_saveframes_by_category("nef_molecular_system")[0]

    chain_selectors = (
        chain_selectors
        if chain_selectors
        else chains_from_frames(molecular_system_frame)
    )

    molecular_system_frame = molecular_system_from_entry_or_exit(entry)

    chain_codes = chains_from_frames(molecular_system_frame)

    _exit_if_chain_selector_not_in_chain_codes(chain_codes, chain_selectors)

    if output_destination == str(STDOUT):
        output_to_stdout = True
        file_name_template = "{chain_code}.seq"
    elif output_destination.startswith("-"):
        output_to_stdout = True
        file_name_template = output_destination[1:]
    else:
        output_to_stdout = False
        file_name_template = output_destination

    if "{chain_code}" not in file_name_template and file_name_template != str(STDOUT):
        msg = f"the file name template {file_name_template} does not contain the string {{chain_code}}"
        exit_error(msg)

    pipe(entry, output_to_stdout, file_name_template, chain_selectors)


def _exit_if_no_molecular_system_in_entry(entry):
    if not is_save_frame_name_in_entry(entry, "nef_molecular_system"):
        msg = f"the entry {entry.entry_id} does not contain a nef_molecular_system saveframe"
        exit_error(msg)


def pipe(entry, output_to_stdout, file_name_template, chain_selectors):

    chains_to_filenames = _build_chains_to_filenames(
        chain_selectors, file_name_template
    )

    chain_sequences = _nmrview_sequences_from_entry(entry, chain_selectors)

    file_banners, final_banner = _make_file_name_banners(chains_to_filenames)

    for chain_code, sequence_text in chain_sequences.items():

        output_file_name = (
            str(STDOUT) if output_to_stdout else chains_to_filenames[chain_code]
        )

        with smart_open(output_file_name) as file_pointer:

            if output_to_stdout and len(file_banners) > 1:
                print(file_banners[chain_code], file=file_pointer)

            print(sequence_text, file=file_pointer)

    if output_to_stdout and len(file_banners) > 1:
        print(final_banner, file=file_pointer)

    stdout_is_atty = stdout.isatty() if not in_pytest() else True
    if not output_to_stdout and not stdout_is_atty:
        print(entry)


def _make_file_name_banners(chains_to_filenames):
    same_width_names = _make_chain_code_to_names_same_width_names(chains_to_filenames)

    file_banners = {
        chain_code: f"------------- {same_width_names[chain_code]} -------------"
        for chain_code, file_name in chains_to_filenames.items()
    }
    banner_lengths = [len(banner) for banner in file_banners.values()]
    max_banner_width = max(banner_lengths)

    final_banner = "-" * max_banner_width

    return file_banners, final_banner


def _exit_if_chain_selector_not_in_chain_codes(chain_codes, chain_selectors):
    for chain_selector in chain_selectors:
        if chain_selector not in chain_codes:
            msg = f"""\
                the chain code {chain_selector} is not in the molecular systems chain codes
                chain selectors:  {', '.join(chain_selectors)}
                chain codes: {', '.join(chain_codes)}
            """
            exit_error(msg)


def _nef_to_nmrview_sequences(
    residues: List[SequenceResidue], chain_codes: List[str]
) -> Dict[str, List[str]]:

    chain_starts = get_chain_starts(residues)

    residues_by_chain = {
        chain_code: [
            residue for residue in residues if residue.chain_code == chain_code
        ]
        for chain_code in chain_codes
    }
    residue_sequences = {
        chain_code: [residue.residue_name for residue in residues_by_chain[chain_code]]
        for chain_code in chain_codes
    }
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
            else:
                line = residue

            sequence_lines.append(line)

        result[chain_code] = "\n".join(sequence_lines)

    return result


def _nmrview_sequences_from_entry(entry, chain_codes):

    molecular_system_frame = molecular_system_from_entry(entry)

    residues = sequences_from_frames(molecular_system_frame)

    return _nef_to_nmrview_sequences(residues, chain_codes)


def _make_chain_code_to_names_same_width_names(names: Dict[str, str]) -> Dict[str, str]:
    max_length = -1
    for name in names.values():
        name_len = len(str(name))
        max_length = max(name_len, max_length)

    return {
        chain_code: str(name).center(max_length) for chain_code, name in names.items()
    }


def _open_for_writing_or_exit(file_name):
    try:
        result = open(file_name, "w")
    except Exception as e:
        msg = f"failed to open {file_name} for writing because {e}"

        exit_error(msg, e)

    return result


def _build_chains_to_filenames(
    chain_codes: List[str], file_name_template: str
) -> Dict[str, str]:

    return {chain_code: f(file_name_template) for chain_code in chain_codes}
