from pathlib import Path
from typing import Dict, List, Tuple

import typer
from pynmrstar import Entry, Saveframe

from nef_pipelines.lib.constants import NEF_PIPELINES
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.sequence_lib import (
    get_chain_code_iter,
    sequence_from_entry_or_exit,
)
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    fixup_metadata,
    get_version,
    parse_comma_separated_options,
    script_name,
)
from nef_pipelines.transcoders.nmrview import import_app
from nef_pipelines.transcoders.nmrview.nmrview_lib import parse_shifts

app = typer.Typer()

# TODO: add a force operation to replace the frame


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def shifts(
    chain_codes: str = typer.Option(
        "A",
        "--chains",
        help="chain codes, can be called multiple times and or be a comma separated list [no spaces!]",
        metavar="<CHAIN-CODES>",
    ),
    frame_name: str = typer.Option(
        "nmrview", "-f", "--frame-name", help="a name for the frame"
    ),
    input_path: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type nmrview.out", metavar="<NMRVIEW-shifts>.out"
    ),
):
    """convert nmrview shift file <nmrview-shifts>.out to NEF"""

    try:
        entry = read_entry_from_file_or_stdin_or_exit_error(input_path)

        chain_codes = parse_comma_separated_options(chain_codes)

        sequence = sequence_from_entry_or_exit(entry)

        pipe(entry, chain_codes, sequence, frame_name, file_names)

    except Exception as e:
        exit_error(f"reading sequence failed because {e}", e)


def pipe(entry, chain_codes, sequence, entry_name, file_names):

    nmrview_frames = []

    chain_code_iter = get_chain_code_iter(chain_codes)
    for file_name, chain_code in zip(file_names, chain_code_iter):

        with open(file_name) as lines:

            chain_seqid_to_type = _sequence_to_residue_type_lookup(sequence)

            nmrview_shifts = parse_shifts(
                lines, chain_seqid_to_type, chain_code=chain_code, file_name=file_name
            )

            frame = shifts_to_nef_frame(nmrview_shifts, entry_name)

            nmrview_frames.append(frame)

    entry = add_frames_to_entry(entry, nmrview_frames)

    print(entry)


def add_frames_to_entry(entry: Entry, frames: List[Saveframe]) -> Entry:
    # TODO deal with merging esp wrt to molecular systems and possibly with other information
    # TODO add frame rename and frame delete
    """
    take a set of save frames and  add them to an Entry and update the NEF metadata header

    Args:
        entry: an entry to add the save frames to
        frames: a set of save frames to add, they must have different names to those present already


    Returns:
        the updated entry containing the frames
    """

    fixup_metadata(entry, NEF_PIPELINES, get_version(), script_name(__file__))

    for frame in frames:

        new_frame_name = frame.name

        frame_in_entry = save_frame_name_in_entry(entry, new_frame_name)

        if frame_in_entry:
            msg = (
                f"the frame named {new_frame_name} already exists in the stream, rename it or delete to add "
                f"the new frame shift frame"
            )
            exit_error(msg)

        entry.add_saveframe(frame)

    return entry


def save_frame_name_in_entry(entry, new_frame_name):
    frame_in_entry = False
    try:
        entry.get_saveframe_by_name(new_frame_name)
    except KeyError:
        frame_in_entry = False

    return frame_in_entry


def sequence_from_frames(frames: Saveframe) -> List[SequenceResidue]:

    residues = []
    for frame in frames:
        for loop in frame:
            chain_code_index = loop.tag_index("chain_code")
            sequence_code_index = loop.tag_index("sequence_code")
            residue_name_index = loop.tag_index("residue_name")

            for line in loop:
                chain_code = line[chain_code_index]
                sequence_code = int(line[sequence_code_index])
                residue_name = line[residue_name_index]
                residue = SequenceResidue(chain_code, sequence_code, residue_name)
                residues.append(residue)

    return residues


def _sequence_to_residue_type_lookup(
    sequence: List[SequenceResidue],
) -> Dict[Tuple[str, int], str]:
    result: Dict[Tuple[str, int], str] = {}
    for residue in sequence:
        result[residue.chain_code, residue.sequence_code] = residue.residue_name
    return result


if __name__ == "__main__":

    typer.run(shifts)
