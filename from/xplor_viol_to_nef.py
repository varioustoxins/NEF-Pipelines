#!/usr/bin/env python3
import argparse
import string

from tabulate import tabulate
import sys
import pathlib
import re

from pynmrstar import Entry, Saveframe, Loop


EXIT_ERROR = 1
UNUSED ='.'
filename_matcher=re.compile('fold_([0-9]+).sa.viols')
parser = None
range_split = re.compile('\.\.').split

def exit_error(msg):

        print(f'ERROR: {msg}')
        print(' exiting...')
        sys.exit(EXIT_ERROR)

def read_args():
    global parser
    parser = argparse.ArgumentParser(description='convert xplor nOe violations to NEF')

    parser.add_argument(metavar='<XPLOR>.viols', action='extend', nargs='+', dest='files')

    parser.add_argument('-o', '--output-file', dest='output_file', default=None)

    return parser.parse_args()

def collapse_names(names, depth=2):

    if len(names) == 1:
        result=names[0]
    else:
        digit_by_depth = {}
        for target in names:
            for i in range(1, depth+1):

                if target[-i].isdigit():
                    digit_by_depth.setdefault(-i,set()).add(target[-i])

                else:
                    break

        name_list = list(list(names)[0])
        for depth, unique_digits in digit_by_depth.items():
            if len(unique_digits) > 1:
                name_list[depth] = '%'
        result = ''.join(name_list)

        result = collapse_right_repeated_string(result)
    return result


def collapse_right_repeated_string(target, repeating='%'):

    orig_length = len(target)

    result = target.rstrip(repeating)

    if len(result) < orig_length:
        result = result + repeating

    return result


def viol_to_nef(file_handle, model, file_path, args):
    in_data = False
    results = {}

    for line in file_handle:

        if 'NOE restraints in potential term' in line:
            restraint_number = None
            sub_restraint_id = 0
            pair_number = 0
            current_selections = None
            current_fields = None
            index = 0

            frame_name = line.split(':')[1].split('(')[0].strip()
            in_data = True
            lines = {}
            results[frame_name] = lines

            while not line.startswith('-----'):
                line = next(file_handle)
            line = next(file_handle)

        if in_data and line.startswith('number of restraints'):
            in_data = False
            restraint_number = None
            pair_number = None
            index = 0

        if in_data and len(line.strip()) == 0:
            continue

        if in_data and '-- OR --' in line:
            sub_restraint_id += 1
            pair_number = 0
            continue

        if in_data:
            line = line.strip()

            line = _remove_violated_mark_if_present(line)

            new_restraint_number = _get_id(line, restraint_number)

            pair_number = 0 if new_restraint_number != restraint_number else pair_number
            current_pair_number = pair_number
            pair_number = pair_number+1

            sub_restraint_id = 0 if new_restraint_number != restraint_number else sub_restraint_id
            restraint_number = new_restraint_number
            line = _remove_id(line)

            selections = _get_selections(line, 2, current_selections)
            current_selections = selections
            line = _remove_selections(line, 2)

            line = ' '.join(line.split('!'))
            fields = line.split()
            if not fields:
                fields = current_fields
            current_fields = fields

            calculated = float(fields[0])
            min_bound = float(range_split(fields[1])[0])
            max_bound = float(range_split(fields[1])[1])

            violation = 0.0
            if calculated < min_bound:
                violation = calculated - min_bound
            elif calculated > max_bound:
                violation = calculated - max_bound


            key = (index, model, new_restraint_number, sub_restraint_id, current_pair_number)
            comment = fields[3]
            restraint_list = comment.rstrip(string.digits)
            restraint_identifier = comment[len(restraint_list):]
            result = {'selection-1': selections[0],
                      'selection-2': selections[1],
                      'probability': '.',
                      'calc': calculated,
                      'min': min_bound,
                      'max': max_bound,
                      'dist': calculated,
                      'viol': violation,
                      'restraint-list': restraint_list,
                      'restraint-number': restraint_identifier,
                      'comment': fields[3],
                      'violation-file': file_path.parts[-1],
                      'structure-file': f'{file_path.stem}.cif'

            }

            lines[key] = result
            index += 1


            # print(line.strip().split([')','(']))
            # while((fields:=line.strip().partition(')'))[2:] !=('','')):
            #     line=fields[-1]
            #     print(fields)
            # return
    args.next_index = index
    return results

def _get_id(line, current_id):
    putative_id = line.split()[0].strip()

    result = current_id
    if not putative_id.startswith('('):
        result = int(putative_id)

    return result


def _remove_violated_mark_if_present(line):

    result = line.strip().lstrip('*').strip()
    return result


def _remove_id(line):
    return line.lstrip('0123456789').strip()


def _line_active(line):
    fields = line.split()
    return fields[0] != '*'


def _get_selections(line, count, current_selections):

    results = []
    line = line.strip()
    for i in range(count):
        value, _, line = line.partition(')')
        results.append(value)
        line = line.strip()

    results = [selection.lstrip('(') for selection in results]
    selections = []
    for i, result in enumerate(results):
        selection = []

        if len(result.strip()):
            selections.append(selection)
            segid = result[:4]
            selection.append(segid)
            result = result[4:]
            selection.extend(result.split())
        else:
            selections.append(current_selections[i])

    return selections


def _remove_selections(line,count):

    line = line.strip()
    for i in range(count):
        value, _, line = line.partition(')')
        line = line.strip()

    return line


def tabulate_data(data):
    for restraint_table in data:
        print(restraint_table)
        print('-' * len(restraint_table))
        print()



        table = []
        non_index_headings = ['probability', 'calc', 'min',
                    'max', 'dist', 'viol', 'restraint-list', 'restraint-number', 'comment']
        selections = ['selection-1', 'selection-2' ]

        for indices, datum in data[restraint_table].items():

            line = []
            table.append(line)

            have_path_ids = len(indices) == 5
            if have_path_ids:
                (index, model, id, sub_id,path_id) = indices
            else:
                (index, model, id, sub_id) = indices

            line.append(index+1)
            line.append(model)
            line.append(int(id)+1)
            line.append(sub_id+1)
            if have_path_ids:
                line.append(path_id + 1)
            line.append('.'.join(datum['selection-1']))
            line.append('.'.join(datum['selection-2']))

            for elem in non_index_headings:
                line.append(datum[elem])

        if have_path_ids:
            headings = ['index', 'model', 'id', 'sub id', 'path_id', *selections, *non_index_headings]
        else:
            headings = ['index', 'model', 'id', 'sub id', *selections, *non_index_headings]

        print(tabulate(table, headers=headings))
        print()


def _collapse_pairs(nef_entries):

    result = {}
    for entry_name, data in nef_entries.items():

        pair_selections = {}
        unique_entry_data = {}

        for i,(key, entry) in enumerate(data.items()):

            new_key = key[1:-1]

            pair_selections.setdefault(new_key, []).append((entry['selection-1'],entry['selection-2']))
            unique_entry_data[new_key] = entry

        new_entry = {}
        for i, (new_key, selection_data) in enumerate(pair_selections.items()):

            atoms_1 = set()
            atoms_2 = set()
            for selection_1, selection_2 in selection_data:
                atoms_1.add(selection_1[-1])
                atoms_2.add(selection_2[-1])

            selection_1 = selection_data[0][0]
            selection_2 = selection_data[0][1]

            nef_atom_name_1 = collapse_names(atoms_1)
            nef_atom_name_2 = collapse_names(atoms_2)

            selection_1[-1] = nef_atom_name_1
            selection_2[-1] = nef_atom_name_2

            unique_entry_data[new_key]['selection-1'] = selection_1
            unique_entry_data[new_key]['selection-2'] = selection_2



            new_entry[new_key] = unique_entry_data[new_key]

        result[entry_name] = new_entry


    # ic(result)
    return result


def data_as_nef(overall_result):

    entry = Entry.from_scratch('default')

    for table_name, table_data in overall_result.items():

        category = "ccpn_distance_restraint_violation_list"
        frame_code = f'{category}_{table_name}'
        frame = Saveframe.from_scratch(frame_code, category)
        entry.add_saveframe(frame)

        frame.add_tag("sf_category", category)
        frame.add_tag("sf_framecode", frame_code)
        frame.add_tag("nef_spectrum", f"nef_nmr_spectrum_{list(table_data.values())[0]['restraint-list']}")
        frame.add_tag("nef_restraint_list", f"nef_distance_restraint_list_{list(table_data.values())[0]['restraint-list']}")
        frame.add_tag("program", 'Xplor-NIH')
        frame.add_tag("program_version", UNUSED)
        frame.add_tag("protocol", 'marvin/pasd,refine')
        frame.add_tag("protocol_version", UNUSED)
        frame.add_tag("protocol_parameters", UNUSED)



        lp = Loop.from_scratch()

        tags = ('index', 'model_id', 'restraint_id', 'restraint_sub_id',
                'chain_code_1','sequence_code_1', 'residue_name_1', 'atom_name_1',
                'chain_code_2', 'sequence_code_2', 'residue_name_2', 'atom_name_2',
                'weight', 'probability', 'lower_limit', 'upper_limit', 'distance', 'violation',
                'violation_file', 'structure_file', 'structure_index','nef_peak_id', 'comment'
                )

        lp.set_category('ccpn_restraint_violation')
        lp.add_tag(tags)

        for index, (indices, line_data) in enumerate(table_data.items()):


            indices = list(indices)
            indices = [index,*indices]

            indices[0] += 1
            indices[2] += 1
            indices[3] += 1

            #TODO: conversion of SEGID to chain ID maybe too crude
            selection_1 = line_data['selection-1']
            selection_1[0] = selection_1[0].strip()
            selection_2 = line_data['selection-2']
            selection_2[0] = selection_2[0].strip()

            data = [*indices, *selection_1, *selection_2,
                    1.0, line_data['probability'], line_data['min'], line_data['max'],
                    # GST: this removes trailing rounding errors without loss of accuracy
                    round(line_data['dist'], 10),
                    round(line_data['viol'],10),
                    line_data['violation-file'],line_data['structure-file'], 1,
                    line_data['restraint-number'], line_data['comment']
                    ]

            lp.add_data(data)

        frame.add_loop(lp)

    return str(entry)


if __name__ == '__main__':

    args = read_args()

    overall_result = {}

    for name in args.files:
        path = pathlib.Path(name)

        try:
            model_number = int(filename_matcher.match(path.parts[-1]).group(1))
        except:
            exit_error(f"Couldn't find a model number in {path.parts[-1]} using matcher {filename_matcher.pattern}")

        if not path.is_file():
            exit_error(f'I need an input file, path was {path}')

        with open(path) as fh:
            entries = viol_to_nef(fh, model_number, path, args)

            entries = _collapse_pairs(entries)

            for entry_name, entry in entries.items():
                overall_result.setdefault(entry_name, {}).update(entry)


    #tabulate_data(overall_result)

    result = data_as_nef(overall_result)
    if args.output_file:
        with open(args.output_file,'w') as fh:
            fh.write(result)
    else:
        print(result)

