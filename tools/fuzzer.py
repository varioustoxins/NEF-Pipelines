#!/usr/bin/env python3
#Importing libraries
import sys
import operator

import numpy as np
import pynmrstar
from pynmrstar import Entry
from dataclasses import dataclass
from random import sample
from itertools import tee
import argparse
parser = None



EXIT_ERROR = 1
def exit_error(msg):

        print(f'ERROR: {msg}')
        print('exiting...')
        sys.exit(EXIT_ERROR)


# https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def select_frames(nef_target_data, target_types):

    for frame_name, frame_data in nef_target_data.frame_dict.items():

        for target_type in target_types:
            if frame_name.startswith(target_type):
                yield frame_name, frame_data


def add_random_errors_to_shifts(nef_target_data, atom_type_shift_errors):

    target_types = ['nef_chemical_shift_list']

    for _, frame_data in select_frames(nef_target_data, target_types):

        for loop_name, loop_data in frame_data.loop_dict.items():
            loop_tags = {tag:i for i,tag in enumerate(loop_data.tags)}

            sequence_code_index = loop_tags['sequence_code']
            chain_code_index = loop_tags['chain_code']
            atom_name_index = loop_tags['atom_name']
            shift_index = loop_tags['value']

            print('#')
            print('# fuzzer: adding shift errors ')
            print('#')

            for line_number, line in enumerate(loop_data):
                atom_name = line[atom_name_index]

                if atom_name in atom_type_shift_errors:
                    if atom_type_shift_errors[atom_name] > np.finfo(float).eps:

                        shift = float(line[shift_index])

                        atom_name = line[atom_name_index]

                        name = f'{line[chain_code_index]}.{line[sequence_code_index]}.{line[atom_name_index]}'
                        error = np.random.normal(scale = atom_type_shift_errors[atom_name])[0]

                        new_shift = shift + error

                        print(f'# add error  {error:4.3} to {name} {shift:10.7} -> {new_shift:10.7}')

                        line[shift_index] = "%10.7f" % new_shift




                            
            


# # remove random shifts



def add_random_remove_shifts(nef_target_data, atom_remove_percentage):
    
    target_frames = ['nef_chemical_shift_list']
    for frame_name, frame_data in select_frames(nef_target_data):

        target_type = None
        for target_frame in target_frames:
            if frame_name.startswith(target_frame):
                target_type = target_frame
                break


        if target_type == 'nef_chemical_shift_list':

            for loop_name, loop_data in frame_data.loop_dict.items():
                loop_tags = {tag:i for i,tag in enumerate(loop_data.tags)}

                sequence_code_index = loop_tags['sequence_code']
                chain_code_index = loop_tags['chain_code']
                residue_name_index = loop_tags['residue_name']
                atom_name_index = loop_tags['atom_name']
                shift_index = loop_tags['value']

                possible_lines_for_removal = {}

                for line_number, line in enumerate(loop_data):
                    atom_name = line[atom_name_index]

                    for atom_remove_name in atom_remove_percentage.keys():
                        if atom_remove_name in atom_name:
                            possible_lines_for_removal.setdefault(atom_remove_name,[]).append(line)


                lines_for_removal = []

                for atom_name, values in possible_lines_for_removal.items():
                    pass
                    # pass random.sample(atom_name)
                    # remove = lines_for_removal ??

                for line_for_removal in lines_for_removal:
                    loop_data.remove(line_for_removal)





# # 

def swap_shifts(nef_target_data, atom_swap_shifts_percentage):


    target_frames = ['nef_chemical_shift_list']
    for frame_name, frame_data in nef_target_data.frame_dict.items():


        target_type = None
        for target_frame in target_frames:
            if frame_name.startswith(target_frame):
                target_type = target_frame
                break


        if target_type == 'nef_chemical_shift_list':

            for loop_name, loop_data in frame_data.loop_dict.items():
                loop_tags = {tag:i for i,tag in enumerate(loop_data.tags)}

                sequence_code_index = loop_tags['sequence_code']
                chain_code_index = loop_tags['chain_code']
                residue_name_index = loop_tags['residue_name']
                atom_name_index = loop_tags['atom_name']
                value_index = loop_tags['value']

                possible_lines_for_swapping_shifts = {}

                for line_number, line in enumerate(loop_data):
                    atom_name = line[atom_name_index]

                    for atom_swap_name in atom_swap_shifts_percentage.keys():
                        if atom_swap_name in atom_name:
                            possible_lines_for_swapping_shifts.setdefault(atom_swap_name,[]).append(line)


                lines_for_swapping_shifts = {}

                for atom_name, values in possible_lines_for_swapping_shifts.items():
                    number_to_swap = int(atom_swap_shifts_percentage[atom_name] * len(values))
                    print('#')
                    print(f'# fuzzer number to swap {atom_name}  = {number_to_swap}')
                    print('#')
                    to_swap = sample(values, number_to_swap)

                    for pair in chunks(to_swap, 2):
                        if len(pair) > 1:
                            a, b = pair

                            name_a = f'{a[chain_code_index]} {a[sequence_code_index]} {a[atom_name_index]} {a[residue_name_index]}'
                            name_b = f'{b[chain_code_index]} {b[sequence_code_index]} {b[atom_name_index]} {b[residue_name_index]}'
                            print(f'# fuzzer swapping shift values for {name_a} to {name_b}')
                            a[value_index], b[value_index] = b[value_index], a[value_index]

                    print('#')

def read_args():

    parser = argparse.ArgumentParser(description='Add chemical shift errors to a NEF file')
    parser.add_argument('-a', '--alpha', metavar='ALPHA', type=float, nargs=1, default=0.0, dest='alpha',
                        help='an error in alpha chemical shifts')
    parser.add_argument('-b', '--beta', metavar='BETA', type=float, nargs=1, default=0.0, dest='beta',
                        help='an error in alpha chemical shifts')
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
        add_random_errors_to_shifts(entry, {'CA': args.alpha, 'CB': args.beta})

        print(entry)

    #this is how often you should swap with another residue in % /100 you can define your own values here
    # atom_swap_shifts_percentage =  {'CA' : 0.10, 'CB': 0.05}
    # swap_shifts(nef_target_data, atom_swap_shifts_percentage)
    #
    #
    # # Add errors to shifts....
    # # these are the sd of the errors to add
    # atom_name_errors = {'CA': 0.0, 'CB': 0.1}
    # add_random_errors_to_shifts(nef_file_data, atom_name_errors)
    #
    # #this is how often you should remove a shift in % /100 you can define your own values here
    # atom_remove_percentage =  {'CA' : 0.05, CB: 0.10}
    # add_random_remove_shifts(nef_target_data, atom_remove_percentage)

    # print(nef_file_data)
#  

