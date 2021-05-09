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


def read_args():
    global parser
    parser = ArgumentParser(description='convert NMRVIEW file to NEF')
    parser.add_argument('--start-chain', type=str, dest='start_chain', default='A',
                        help='the starting chain code [should be in A-Z currently]', metavar='<CHAIN-CODE>')
    parser.add_argument('--no-chain-end', type=bool, dest='no_chain_start', default = True,
                        help='don\'t include a start of chain link type for the first residue')
    parser.add_argument('--no-end', type=bool, dest='no_chain_end', default=True,
                        help='don\'t include a start of chain link type for the last residue')
    parser.add_argument('--entry_name', type=str, default='nmrview', dest='entry_name',
                        help='a name for the entry [default: %(default)s)]')
    parser.add_argument(action="store", type=str, nargs='+', dest='files',
                        help="input file(s)", metavar='<FILE>', )


    return parser.parse_args()

def pos_to_char(pos):
    return chr(pos + 65)

def char_position(letter):
    return ord(letter) - 65


def get_linking(target_index, target_sequence, no_start=False, no_end=False):

    result = 'middle'
    if target_index == 0 and not no_start:
        result = 'start'
    if target_index + 1 == len(target_sequence) and not no_end:
        result = 'end'
    return result


if __name__ == '__main__':

    args = read_args()

    start_chain = args.start_chain.upper()
    if len(start_chain) > 1:
        exit_error(f'A chain code should be a single letter [currently] got {start_chain}')

    chain_start_index = char_position(start_chain)

    num_files = len(args.files)
    remaining_indices = len(string.ascii_uppercase) - chain_start_index
    if num_files > remaining_indices:
        exit_error(f'I can only cope with a maximum of {remaining_indices} files you gave {num_files} and firsst chain {start_chain}')

    if (args.no_chain_start or args.nochain_end) and num_files > 1:
        exit_error(f"you can only use --no-chain-start or no-chain-end with a single chain, i got {num_files} chains")

    for file_index, file_name in enumerate(args.files):
        start_residue = 1
        sequence = []
        with open (file_name,'r') as lines:
            for i, line in enumerate(lines):
                line = line.strip()
                fields = line.split()

                msh = f'''nmview sequences have one residue name per line, 
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
                        msg = f'''at line {i+1} in file {file_name} 
                                couldn't convert second field {fields[0]} to an integer'''
                        exit_error(msg)

                if len(fields) > 0:
                    sequence.append(fields[0])
        entry_name = args.entry_name.replace(' ','_')
        entry = Entry.from_scratch(entry_name)

        category = "nef_molecular_system"
        frame_index = ''
        if len(args.files) > 1:
            frame_index = f'_{file_index+1}'

        frame_code = f'{category}_{entry_name}{frame_index}'

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
        for index, residue_name in enumerate(sequence):

            linking = get_linking(index,sequence)

            loop.add_data_by_tag('index', index + 1)
            loop.add_data_by_tag('chain_code', pos_to_char(chain_start_index + file_index))
            loop.add_data_by_tag('sequence_code', start_residue + index)
            loop.add_data_by_tag('residue_name', residue_name.upper())
            loop.add_data_by_tag('linking', linking)
            loop.add_data_by_tag('residue_variant', UNUSED)
            loop.add_data_by_tag('cis_peptide', UNUSED)

    print(entry)


