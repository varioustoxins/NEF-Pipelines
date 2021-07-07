
from argparse import Namespace
from typing import Iterable, List

from lib.sequence_lib import sequence_to_nef_frame, chain_code_iter
from lib.typer_utils import get_args

from pathlib import Path

from lib.Structures import SequenceResidue
from lib.util import exit_error, process_stream_and_add_frames


from transcoders.nmrview import import_app
import typer

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command()
def sequence(
    chain_codes: str = typer.Option('A', '--chains', help='chain codes as a list of names spearated by dots',
                                   metavar='<CHAIN-CODES>'),
    no_chain_start: bool = typer.Option(False, '--no-chain-start/',
                                        help="don't include a start of chain link type for the first residue"),
    no_chain_end: bool = typer.Option(False, '--no-chain-end/',
                                      help="don't include an end of chain link type for the last residue"),
    entry_name: str = typer.Option('nmrview', help='a name for the entry'),
    pipe: Path = typer.Option(None, metavar='|PIPE|',
                              help='pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]'),
    file_names: List[Path] = typer.Argument(..., help='input files of type nmrview.seq', metavar='<SEQ-FILE>')
):
    """convert nmrview sequence file <NMRVIEW_SEQUENCE>.seq files to NEF"""
    args = get_args()

    process_sequence(args)


def read_sequence(sequence_lines: Iterable[str], chain_code: str = 'A', sequence_file_name: str = 'unknown') \
                  -> List[SequenceResidue]:

    start_residue = 1
    result = []
    for i, line in enumerate(sequence_lines):
        line = line.strip()
        fields = line.split()

        msg = f'''nmview sequences have one residue name per line, 
                  except for the first line which can also contain a starting residue number,
                  at line {i + 1} i got {line} in file {sequence_file_name}
                  line was: {line}'''

        if len(fields) > 1 and i != 0:
            exit_error(msg)

        if i == 0 and len(fields) > 2:
            exit_error(f'''at the first line the should be one 3 letter code and an optional residue number
                           in file {sequence_file_name} at line {i+1} got {len(fields)} fields 
                           line was: {line}''')

        if i == 0 and len(fields) == 2:
            try:
                start_residue = int(fields[1])
            except ValueError:
                msg = f'''couldn't convert second field {fields[0]} to an integer
                          at line {i + 1} in file {sequence_file_name} 
                          line was: {line}
                        '''
                exit_error(msg)

        if len(fields) > 0:
            result.append(SequenceResidue(chain_code, start_residue + i, fields[0]))

    return result


def process_sequence(args: Namespace):
    nmrview_frames = []

    for file_name, chain_code in zip(args.file_names, chain_code_iter(args.chain_codes)):
        with open(file_name, 'r') as lines:
            nmrview_sequence = read_sequence(lines, chain_code=chain_code)

            frame = sequence_to_nef_frame(nmrview_sequence, args.entry_name)

            nmrview_frames.append(frame)

    entry = process_stream_and_add_frames(nmrview_frames, args)

    print(entry)


if __name__ == '__main__':

    typer.run(sequence)
