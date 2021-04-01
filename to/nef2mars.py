#!/usr/bin/env python3
from pynmrstar import Entry
import json
from string import digits
import sys
from tabulate import tabulate
import argparse

parser = None

def nef2mars(entry):

    code = entry['nef_chemical_shift_list_default']
    code_json_x = code.get_json()
    code_json = json.loads(code_json_x)
    loop = code_json['loops'][0]

    offsets = {}

    for index, tag in enumerate(loop['tags']):
        offsets[tag]=index
    chain_offset = offsets['chain_code']
    code_offset = offsets['sequence_code']
    atom_offset = offsets['atom_name']
    value_offset = offsets['value']


    new_fields = {}
    for line in loop['data']:
        code = str(line[code_offset])
        chain = str(line[chain_offset])

        if not (code.startswith('@') and chain.startswith('@')):
            continue

        sequence_code = (str(code).strip('@'))

        fields = sequence_code.split('-')
        atom_name = str(line[atom_offset])
        remove_digits = str.maketrans('', '', digits)
        atom_name = atom_name.replace('@','').translate(remove_digits)
        value = float(line[value_offset])
        if len(fields) == 1:
           fields.append('0')
        for i, field in enumerate(fields):
           fields [i] = int(field)
        fields.insert(1, atom_name)
        fields = tuple(fields)
        new_fields[fields] = value


    headings = (('H', ('H',0)), ('N',  ('N',0)), ('Ca', ('CA',0)), ('Ca-1',  ('CA', 1)), ('Cb', ('CB',0)), ('Cb-1', ('CB', 1)), ('CO',  ('C',0)), ('CO-1', ('C',1)))
    headers = (' ', 'H', 'N', 'CA', 'CA-1', 'CB', 'CB-1', 'CO', 'CO-1')

    residue_nums = set()
    for key in new_fields:
        residue_nums.add(key[0])

    lines = []
    for residue_num in sorted(residue_nums):
        line = []
        lines.append(line)

        line.append('PR_'+ str(residue_num))

        for heading, heading_key in headings:
            key = (residue_num, *heading_key)
            if key in new_fields:
                line.append('%-7.3f    ' % new_fields[key])
            else:
                line.append('-         ')

    print(tabulate(lines, headers=headers, tablefmt='plain'))

EXIT_ERROR = 1
def exit_error(msg):

        print(f'ERROR: {msg}')
        print('exiting...')
        sys.exit(EXIT_ERROR)

def read_args():
    global parser
    parser = argparse.ArgumentParser(description='Read a NEF File and create a MARS chemical shifts file')
    parser.add_argument(metavar='FILES', nargs=argparse.REMAINDER, dest='files')

    return parser.parse_args()


if __name__ == '__main__':

    args = read_args()

    is_tty = sys.stdin.isatty()

    if is_tty and len(args.files) == 0:
        parser.print_help()
        print()
        msg = """I require at least 1 argument or input stream with a chemical_shift_list frame"""
        
        exit_error(msg)

    entries = []
    try:
        if len(args.files) == 0:
            lines = sys.stdin.read()
            entries.append(Entry.from_string(lines))
        else:
            for file in args.files:
                entries.append(Entry.from_file(file))
    except OSError as e:
        msg = f"couldn't open target nef file because {e}"
        exit_error(msg)

    for entry in entries:
        nef2mars(entry)

