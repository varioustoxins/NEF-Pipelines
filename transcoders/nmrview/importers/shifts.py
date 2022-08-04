from lib.sequence_lib import chain_code_iter
from lib.typer_utils import get_args
from lib.util import exit_error, process_stream_and_add_frames
from transcoders.nmrview.nmrview_lib import  parse_shifts
from transcoders.nmrview import import_app
from lib.util import cached_file_stream, get_pipe_file
from lib.shift_lib import shifts_to_nef_frame
from pynmrstar import Entry, Saveframe, Loop
import typer
from pathlib import Path
from typing import List, Iterable, Dict, Tuple
from argparse import Namespace
from ordered_set import OrderedSet
from lib.structures import SequenceResidue


app = typer.Typer()

# noinspection PyUnusedLocal
@import_app.command()
def shifts(
    chain_codes: str = typer.Option('A', '--chains', help='chain codes as a list of names spearated by dots',
                                   metavar='<CHAIN-CODES>'),
    entry_name: str = typer.Option('nmrview', help='a name for the entry'),
    pipe: Path = typer.Option(None, metavar='|PIPE|',
                              help='pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]'),
    file_names: List[Path] = typer.Argument(..., help='input files of type nmrview.xpk', metavar='<NMRVIEW-shifts>.out')
):
    """convert nmrview shift file <nmrview-shifts>.out files to NEF"""


    try:
        args = get_args()

        process_shifts(args)
    except Exception as e:
        exit_error(f"reading sequence failed because {e}", e)
#
#
def process_shifts(args: Namespace):
    nmrview_frames = []

    for file_name, chain_code in zip(args.file_names, chain_code_iter(args.chain_codes)):

        with cached_file_stream(file_name) as lines:

            sequence = _get_sequence_or_exit(args)

            chain_seqid_to_type = _sequence_to_residue_type_lookup(sequence)

            nmrview_shifts = parse_shifts(lines, chain_seqid_to_type, chain_code=chain_code)

            frame = shifts_to_nef_frame(nmrview_shifts, args.entry_name)

            nmrview_frames.append(frame)

    entry = process_stream_and_add_frames(nmrview_frames, args)

    print(entry)




def sequence_from_frames(frames: Saveframe) -> List[SequenceResidue]:

    residues = []
    for frame in frames:
        for loop in frame:
            chain_code_index = loop.tag_index('chain_code')
            sequence_code_index = loop.tag_index('sequence_code')
            residue_name_index = loop.tag_index('residue_name')

            for line in loop:
                chain_code = line[chain_code_index]
                sequence_code = int(line[sequence_code_index])
                residue_name = line[residue_name_index]
                residue = SequenceResidue(chain_code, sequence_code, residue_name)
                residues.append(residue)

    return residues


def _get_sequence_or_exit(args):
    sequence_file = None
    if 'sequence' in args:
        sequence_file = args.sequence

    if not sequence_file:
        try:
            stream = get_pipe_file(args)
            entry = Entry.from_file(stream)
            frames = entry.get_saveframes_by_category('nef_molecular_system')
            sequence = sequence_from_frames(frames)

        except Exception as e:
            exit_error(f'failed to read sequence from input stream because {e}', e)


    else:
        with open(sequence_file, 'r') as lines:
            sequence = read_sequence(lines, chain_code=args.chain_code)
    return sequence

def _sequence_to_residue_type_lookup(sequence: List[SequenceResidue]) -> Dict[Tuple[str, int], str]:
    result: Dict[Tuple[str, int], str] = {}
    for residue in sequence:
        result[residue.chain, residue.residue_number] = residue.residue_name
    return result



if __name__ == '__main__':

    typer.run(shifts)