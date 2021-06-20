
from pathlib import Path

from argparse import ArgumentParser

from pynmrstar import Entry, Saveframe, Loop

from lib.constants import NEF_PIPELINES, NEF_PIPELINES_VERSION
from lib.util import fixup_metadata, get_pipe_file, script_name, exit_error

from lib.constants import NEF_UNKNOWN



def create_parser():

    result = ArgumentParser(description='convert NMRVIEW file to NEF')
    result.add_argument('--chain', type=str, dest='chain_code', default='A',
                        help='chain code [default= %(default)s]', metavar='<CHAIN-CODE>')
    result.add_argument('--no-chain-end', type=bool, dest='no_chain_start', default=True,
                        help='don\'t include a start of chain link type for the first residue')
    result.add_argument('--no-end', type=bool, dest='no_chain_end', default=True,
                        help='don\'t include a start of chain link type for the last residue')
    result.add_argument('--entry_name', type=str, default='nmrview', dest='entry_name',
                        help='a name for the entry [default: %(default)s)]')
    result.add_argument(action="store", type=str, nargs=1, dest='file_names',
                        help="input file", metavar='<FILE>', )
    result.add_argument('--pipe', type=Path, dest='pipe', metavar='|PIPE|',
                        help='pipe to read NEF data from, for testing overrides stdin !use stdin!')

    return result


def get_linking(target_index, target_sequence, no_start=False, no_end=False):

    result = 'middle'
    if target_index == 0 and not no_start:
        result = 'start'
    if target_index + 1 == len(target_sequence) and not no_end:
        result = 'end'
    return result


def read_sequence(sequence_lines, chain_code='A', sequence_file_name='unknown'):

    start_residue = 1
    result = {}
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
            result[chain_code, start_residue + i] = fields[0]

    return result


def sequence_to_nef(input_sequence, input_args):
    chain = input_args.chain_code

    entry_name = input_args.entry_name.replace(' ', '_')
    nef_entry = Entry.from_scratch(entry_name)

    category = "nef_molecular_system"

    frame_code = f'{category}_{entry_name}'

    nef_frame = Saveframe.from_scratch(frame_code, category)
    nef_entry.add_saveframe(nef_frame)
    nef_frame.add_tag("sf_category", category)
    nef_frame.add_tag("sf_framecode", frame_code)

    nef_loop = Loop.from_scratch('nef_sequence')
    nef_frame.add_loop(nef_loop)

    tags = ('index', 'chain_code', 'sequence_code', 'residue_name', 'linking', 'residue_variant', 'cis_peptide')

    nef_loop.add_tag(tags)

    # TODO need tool to set ionisation correctly
    for index, ((chain_code, sequence_code), residue_name) in enumerate(sorted(input_sequence.items())):
        linking = get_linking(index, sequence)

        nef_loop.add_data_by_tag('index', index + 1)
        nef_loop.add_data_by_tag('chain_code', chain)
        nef_loop.add_data_by_tag('sequence_code', sequence_code)
        nef_loop.add_data_by_tag('residue_name', residue_name.upper())
        nef_loop.add_data_by_tag('linking', linking)
        nef_loop.add_data_by_tag('residue_variant', NEF_UNKNOWN)
        nef_loop.add_data_by_tag('cis_peptide', NEF_UNKNOWN)

    return entry


if __name__ == '__main__':

    parser = create_parser()
    args = parser.parse_args()

    file_name = args.file_names[0]
    with open(file_name, 'r') as lines:
        sequence = read_sequence(lines, chain_code=args.chain_code)

    entry = sequence_to_nef(sequence, args)

    stream = get_pipe_file(args)
    pipe_entry = Entry.from_file(stream) if stream else Entry.from_scratch(args.entry_name)
    fixup_metadata(pipe_entry, NEF_PIPELINES, NEF_PIPELINES_VERSION, script_name(__file__))


    for frame in entry.frame_list:
        pipe_entry.add_saveframe(frame)

    print(pipe_entry)
