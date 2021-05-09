from pathlib import Path

from textwrap import dedent

import string
import sys

from argparse import ArgumentParser
from nmview_seq import read_sequence
from icecream import ic

from pynmrstar import Entry, Saveframe, Loop

from xplor_viol_to_nef import collapse_names

EXIT_ERROR = 1
UNUSED ='.'
parser = None


def exit_error(msg):

        print(f'ERROR: {dedent(msg)}')
        print(' exiting...')
        sys.exit(EXIT_ERROR)

def find_seq_file_or_warning(shift_file):

    directory = Path(shift_file).parent
    possible_seq_files = []
    for possible_seq_file in directory.iterdir():
        if possible_seq_file.is_file() and possible_seq_file.suffix == '.seq':
            possible_seq_files.append(possible_seq_file)

    num_possible_seq_files = len(possible_seq_files)
    if num_possible_seq_files == 0:
        msg =  f'''# Couldn't find an nmrview sequence [<FILE_NAME>.seq] file in {str(directory)}'''
        print(msg, file=sys.stderr)
    elif num_possible_seq_files != 1:
        file_names = '\n'.join(['# %s' % path.name for path in possible_seq_files])
        msg = f'''# Found more than one possible sequence file 
                  # in {str(directory)}
                  # choices are:
                  {file_names}
               '''
        exit_error(msg)

    return possible_seq_files[0]



def read_args():
    global parser
    parser = ArgumentParser(description='convert NMRVIEW file to NEF')
    parser.add_argument('--entry_name', type=str, default='nmrview', dest='entry_name',
                        help='a name for the entry [default: %(default)s)]')
    parser.add_argument('--chain-code', type=str, dest='chain_code', default='A',
                        help='the chain_code', metavar='<CHAIN-CODE>')
    parser.add_argument('--shifts-file', type=str, dest='seq_file', metavar='<FILE_NAME>.seq',
                        default=None,
                        help="seq file for the chain <SEQ-FILE>.seq, assumed to be in the same folder as the shift file")
    parser.add_argument(action="store", type=str, nargs=1, dest='file_name',
                        help="input file(s)", metavar='<FILE>', )

    return parser.parse_args()


def read_shifts(lines, chain_code, sequence):

    result = {}
    for i, line in enumerate(lines):

        line = line.strip()
        fields = line.split()
        num_fields = len(fields)
        if num_fields != 3:
            msg = f'''An nmrview ppm.out file should have 3 fields per line
                    i got{num_fields} at line {i + 1} 
                    with data: {line}'''
            exit_error(msg)

        shift, stereo_specificty_code = fields[1:]

        atom_fields = fields[0].split('.')
        num_atom_fields = len(atom_fields)
        if num_atom_fields != 2:
            msg = f'''An nmrview ppm.out file should have atom specfiers of the form '1.CA'
                                        i got{num_atom_fields} at line {i + 1} 
                                        with data: {line}'''
            exit_error(msg)
        residue_number, atom = atom_fields

        try:
            residue_number = int(residue_number)
        except ValueError:
            msg = f'''An nmrview residue number should be an integer
                      i got {residue_number} at line {i + 1}'''
            exit_error(msg)

        try:
            shift = float(shift)
        except ValueError:
            msg = f'''A chemical shift should be a float
                      i got {shift} at line {i + 1}'''
            exit_error(msg)

        try:
            stereo_specificty_code = int(stereo_specificty_code)
        except ValueError:
            msg = f'''An nmrview stereo specificty code should be an integer
                      i got {stereo_specificty_code} at line {i + 1}'''
            exit_error(msg)

        if not stereo_specificty_code in [1, 2, 3]:
            msg = f'''An nmrview stereo specificty code should be an integer between 1 and 3,
                      i got {stereo_specificty_code} at line {i + 1}'''
            exit_error(msg)

        # ic(sequence,residue_number,chain_code)

        seq_key = chain_code,residue_number
        residue_name = sequence.setdefault(seq_key,UNUSED).upper()

        key = chain_code, residue_number, residue_name, atom
        result[key] = (shift, stereo_specificty_code)
    return result

def collapse_shifts(shifts):
    result = {}
    for residue_key, atom_shifts in shifts_by_residue(shifts).items():
        shifts_by_atom = shifts_by_common_shift(atom_shifts)
        for atom_name, shift in shifts_by_atom.items():
            new_atom_key = (*residue_key, atom_name)
            result[new_atom_key] = shift

    return result

def shifts_by_residue(shifts):
    result = {}
    for key,value in shifts.items():
        chain,sequence,res_type,atom =  key

        key = chain,sequence,res_type
        result.setdefault(key,{})[atom] = value

    return result

def group_by_stem(names):
    stemmed = {}
    for name in names:
        stem = name.rstrip('0123456789')
        stemmed.setdefault(stem, []).append(name)

    ic(stemmed)
    return list(stemmed.values())


def shifts_by_common_shift(residue_shifts):

    result = {}

    by_shift = {}
    for atom, data in residue_shifts.items():
        by_shift.setdefault(data[0],[]).append(atom)

    for shift, names in by_shift.items():
        name_sets = group_by_stem(names)
        for name_set in name_sets:
            result[collapse_names(name_set)] = shift

    return result


if __name__ == '__main__':

    args = read_args()

    seq_file = args.seq_file
    if not seq_file:
        seq_file = find_seq_file_or_warning(args.file_name[0])

    with open (seq_file,'r') as lines:
        sequence = read_sequence(lines, chain_code=args.chain_code)

    with open(args.file_name[0], 'r') as lines:
        shifts = read_shifts(lines, args.chain_code, sequence)

    shifts = collapse_shifts(shifts)

    entry_name = args.entry_name.replace(' ', '_')
    entry = Entry.from_scratch(entry_name)

    category = "nef_chemical_shift_list"

    frame_code = f'{category}_{entry_name}'

    frame = Saveframe.from_scratch(frame_code, category)
    entry.add_saveframe(frame)
    frame.add_tag("sf_category", category)
    frame.add_tag("sf_framecode", frame_code)

    loop = Loop.from_scratch()
    frame.add_loop(loop)

    tags = ('chain_code', 'sequence_code', 'residue_name', 'atom_name', 'value', 'value_uncertainty', 'element', 'isotope_number')

    loop.set_category(category)
    loop.add_tag(tags)

    for key, data in shifts.items():
        chain_code, residue_number, residue_name, atom_name = key
        loop.add_data_by_tag('chain_code', chain_code)
        loop.add_data_by_tag('sequence_code', residue_number)
        loop.add_data_by_tag('residue_name', residue_name)
        loop.add_data_by_tag('atom_name', atom_name)
        loop.add_data_by_tag('value', data)
        loop.add_data_by_tag('value_uncertainty', UNUSED)
        loop.add_data_by_tag('element', UNUSED)
        loop.add_data_by_tag('isotope_number', UNUSED)

    print(entry)


