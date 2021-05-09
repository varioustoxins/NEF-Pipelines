import string
import sys

from argparse import ArgumentParser

from pynmrstar import Entry, Saveframe, Loop

EXIT_ERROR = 1
UNUSED ='.'
parser = None


def exit_error(msg):

        print(f'ERROR: {msg}')
        print(' exiting...')
        sys.exit(EXIT_ERROR)


def create_parser():

    parser = ArgumentParser(description='convert NMRVIEW file to NEF')
    parser.add_argument('--chain', type=str, dest='chain_code', default='A',
                        help='chain code [default= %(default)s]', metavar='<CHAIN-CODE>')
    parser.add_argument('--no-chain-end', type=bool, dest='no_chain_start', default = True,
                        help='don\'t include a start of chain link type for the first residue')
    parser.add_argument('--no-end', type=bool, dest='no_chain_end', default=True,
                        help='don\'t include a start of chain link type for the last residue')
    parser.add_argument('--entry_name', type=str, default='nmrview', dest='entry_name',
                        help='a name for the entry [default: %(default)s)]')
    parser.add_argument(action="store", type=str, nargs=1, dest='file_names',
                        help="input file", metavar='<FILE>', )

    return parser


def get_linking(target_index, target_sequence, no_start=False, no_end=False):

    result = 'middle'
    if target_index == 0 and not no_start:
        result = 'start'
    if target_index + 1 == len(target_sequence) and not no_end:
        result = 'end'
    return result


def read_sequence(lines, chain_code='A', file_name='unknown'):

    start_residue = 1
    result = {}
    for i, line in enumerate(lines):
        line = line.strip()
        fields = line.split()

        msg = f'''nmview sequences have one residue name per line, 
                     except for the first line which can also contain a starting residue number,
                     at line {i + 1} i got {line} in file {file_name}'''

        if len(fields) > 1 and i != 0:
            exit_error(msg)

        if i == 0 and len(fields) > 2:
            exit_error()

        if i == 0 and len(fields) == 2:
            try:
                start_residue = int(fields[1])
            except ValueError:
                msg = f'''at line {i + 1} in file {file_name} 
                            couldn't convert second field {fields[0]} to an integer'''
                exit_error(msg)

        if len(fields) > 0:
            result[chain_code, start_residue + i] = fields[0]

    return result


if __name__ == '__main__':

    parser = create_parser()
    args = parser.parse_args()

    chain = args.chain_code

    file_name = args.file_names[0]
    with open (file_name,'r') as lines:
        sequence = read_sequence(lines=lines,chain_code=args.chain_code)

    entry_name = args.entry_name.replace(' ','_')
    entry = Entry.from_scratch(entry_name)

    category = "nef_molecular_system"

    frame_code = f'{category}_{entry_name}'

    frame = Saveframe.from_scratch(frame_code, category)
    entry.add_saveframe(frame)
    frame.add_tag("sf_category", category)
    frame.add_tag("sf_framecode", frame_code)

    loop = Loop.from_scratch()
    frame.add_loop(loop)

    tags = ('index', 'chain_code', 'sequence_code', 'residue_name', 'linking', 'residue_variant', 'cis_peptide')

    loop.set_category(category)
    loop.add_tag(tags)

    #TODO need tool to set ionisation correctly
    for index, ((chain_code,sequence_code),residue_name) in enumerate(sorted(sequence.items())):

        linking = get_linking(index,sequence)

        loop.add_data_by_tag('index', index + 1)
        loop.add_data_by_tag('chain_code', args.chain_code)
        loop.add_data_by_tag('sequence_code', sequence_code)
        loop.add_data_by_tag('residue_name', residue_name.upper())
        loop.add_data_by_tag('linking', linking)
        loop.add_data_by_tag('residue_variant', UNUSED)
        loop.add_data_by_tag('cis_peptide', UNUSED)

    print(entry)


