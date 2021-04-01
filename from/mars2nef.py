#!/usr/bin/env python3
import argparse
import os
import sys
import pathlib
import re
from dataclasses import dataclass
from pynmrstar import Loop, Saveframe, Entry

EXIT_ERROR = 1
UNUSED ='.'

def exit_error(msg):

        print(f'ERROR: {msg}')
        print(' exiting...')
        sys.exit(EXIT_ERROR)

# https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]



@dataclass
class Assignment:
    assignment: int
    fixed: bool = False
    merit: float = 0.0


def mars_to_nef(lines, args):

    pseudo_residue_re = re.compile('[a-zA-Z@]+_([0-9]+)')
    assignment_sets = {}
    residue_types = {}

    for line_number, line in enumerate(lines):
        line = line.strip()
        fields = line.split()

        residue_type, residue_number = fields[0].split('_')
        residue_number = int(residue_number)

        residue_types[residue_number] = residue_type

        assignment_sets[residue_number] = []
        for assignment_data in chunks(fields[1:], 2):

            residue, raw_merit = assignment_data
            residue_matches = pseudo_residue_re.search(residue).groups()

            if len(residue_matches) != 1:
                msg = """couldn't find residue number in pseudo residue
                         line number: {line number}
                         line value: {line}

                         expected a pseudo residue of the form <alpha>_<number>
                         alpha a-z, A-Z or @
                      """

                exit_error(msg)

            pseudo_residue_number = int(residue_matches[0])

            FIXED_MERIT = '(F)'
            fixed = raw_merit == FIXED_MERIT

            if fixed:
                merit = None
            else:
                merit = raw_merit.strip('()')
                try:
                    merit = float(merit) / 100.0
                except ValueError:
                    msg = """ couldn't convert merit to float
                              line number: {line number}
                              line value: {line}
                          """
                    exit_error(msg)

            assignment = Assignment(pseudo_residue_number, fixed, merit)

            assignment_sets[residue_number].append(assignment)

    loop = Loop.from_scratch('ccpn_residue_assignment_default')
    loop.add_tag(
        ['serial', 'chain_code', 'residue_number', 'residue_type', 'assignment_serial', 'assignment', 'merit', 'fixed'])
    data = []
    UNUSED_4 = [UNUSED, ] * 4

    chain = args.chain
    for serial, residue_number in enumerate(sorted(assignment_sets)):
        assignments = assignment_sets[residue_number]

        out_residue_number = residue_number + args.offset
        if assignments:
            for assignment_serial, assignment in enumerate(assignments):
                line = [serial, chain, out_residue_number, residue_types[residue_number],
                        assignment_serial, assignment.assignment, assignment.merit, assignment.fixed]
                data.append(line)
        else:
            line = [serial, chain, out_residue_number, residue_types[residue_number], *UNUSED_4]
            data.append(line)
    loop.data = data
    save_frame = Saveframe.from_scratch("ccpn_residue_assignments", "ccpn_residue_assignments")
    FIXED_TAGS = (('ccpn_assignment_program', 'mars'),
                  ('ccpn_assignment_program_version', UNUSED),
                  ('ccpn_assignment_source', UNUSED),
                  ('sf_category', 'ccpn_residue_assignments'),
                  ('sf_ftame_code', 'ccpn_residue_assignments_default')
                  )
    for tag, value in FIXED_TAGS:
        save_frame.add_tag(tag, value)
    save_frame.add_loop(loop)
    entry = Entry.from_scratch('test')
    entry.add_saveframe(save_frame)

    return entry

def read_args():
    global parser
    parser = argparse.ArgumentParser(description='convert MARS assigmnent_AAs.out to ccpn NEF assignment file')
    parser.add_argument('-o', '--offset', metavar='OFFSET', type=int, default=0, dest='offset',
                        help='offset to add to residue numbers')
    parser.add_argument('-c', '--chain', metavar='CHAIN', type=str, default='A', dest='chain',
                        help='chain to use for assignment')
    parser.add_argument(metavar='assignments_AAs.out', nargs=1, dest='file')

    return parser.parse_args()

if __name__ == '__main__':

    args = read_args()

    path = pathlib.Path(args.file[0])

    print('*', path, os.getcwd())
    if not path.is_file():
        exit_error(f'I need an input file, path was {file_name}')

    if (file_name := path.name) != 'assignment_AAs.out':
        exit_error(f'I need a mars output file [assignment_AAs.out] i got {file_name}')

    with open(path) as fh:
        entry = mars_to_nef(fh, args)

        print(entry)





 

    

