
from argparse import Namespace
from typing import Iterable, List, Dict, Tuple

from pynmrstar import Entry, Saveframe, Loop

import lib.constants
from lib import constants
from lib.structures import SequenceResidue
from lib.sequence_lib import sequence_to_nef_frame, chain_code_iter
from lib.typer_utils import get_args

from pathlib import Path

from ..nmrview_lib import AtomLabel,PeakAxis, PeakValues, PeakListData, PeakList
from .sequence import read_sequence

from lib.util import exit_error, process_stream_and_add_frames


from transcoders.nmrview import import_app
import typer

from ..nmrview_lib import parse_tcl, parse_float_list

app = typer.Typer()

# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
        entry_name: str = typer.Option('nmrview', help='a name for the entry'),
        chain_code: str = typer.Option('A', '--chain', help='chain code', metavar='<chain-code>'),
        sequence: str = typer.Option(None, metavar='<nmrview>.seq)', help="seq file for the chain <seq-file>.seq"),
        axis_codes: str = typer.Option('1H.15N', metavar='<axis-codes>',  help='a list of axis codes joined by dots'),
        file_names: List[Path] = typer.Argument(...,help="input peak files", metavar='<peak-file.xpk>')
):
    """convert nmrview peak file <nmrview>.xpk files to NEF"""
    args = get_args()

    import_(args)



# # from sys import stdin
# # from os import isatty
# #
# # is_pipe = not isatty(stdin.fileno())
# from ..lib import AtomLabel, PeakAxis, PeakValues, PeakListData, PeakList
#
#
import itertools
from collections import OrderedDict
#
#
import pyparsing
# from icecream import ic
# from pathlib import Path
#
# from textwrap import dedent
#
# import sys
#
# from pynmrstar import Entry, Saveframe, Loop, definitions
#
# from lib.util import exit_error
#
# definitions.STR_CONVERSION_DICT[''] = None


def find_seq_file_or_exit(shift_file):

    directory = Path(shift_file).parent
    possible_seq_files = []
    for possible_seq_file in directory.iterdir():
        if possible_seq_file.is_file() and possible_seq_file.suffix == '.seq':
            possible_seq_files.append(possible_seq_file)

    num_possible_seq_files = len(possible_seq_files)
    if num_possible_seq_files == 0:
        msg =  f'''# Couldn't find an nmrview sequence [<FILE_NAME>.seq] file in {str(directory)}'''
        exit_error(msg)
    elif num_possible_seq_files != 1:
        file_names = '\n'.join(['# %s' % path.name for path in possible_seq_files])
        msg = f'''# Found more than one possible sequence file
                  # in {str(directory)}
                  # choices are:
                  {file_names}
               '''
        exit_error(msg)


    return possible_seq_files[0] if possible_seq_files else None


def read_peaks(lines, chain_code, sequence):

    line = next(lines)
    headers = line.strip().split()

    header_items = ['label', 'dataset', 'sw', 'sf']
    if len(header_items) != 4:
        msg = f'''this doesn't look like an nmrview xpk file,
                  i expected a header containing 4 items on the first line: {','.join(header_items)}
                  i got {line} at line 1'''
        exit_error(msg)

    for name in header_items:
        if not name in headers:
            msg  = f'''this doesn't look like an nmrview xpk file,
                       i expected a header containing the values: {', '.join(header_items)}
                       i got '{line}' at line 1'''
            exit_error(msg)

    axis_labels = None
    data_set = None
    sweep_widths = []
    spectrometer_frequencies = []
    num_axis = None
    for header_no, header_type in enumerate(headers):
        line = next(lines)
        if header_type == 'label':
            axis_labels = line.strip().split()
            num_axis = len(axis_labels)
        elif header_type == 'dataset':
            data_set = line.strip()
        elif header_type == 'sw':
            line_no = header_no+2
            sweep_widths = parse_float_list(line, line_no)
            check_num_fields(sweep_widths,num_axis,"sweep widths",line,line_no)
        elif header_type == 'sf':
            line_no = header_no + 2
            spectrometer_frequencies = parse_float_list(line, line_no)
            check_num_fields(spectrometer_frequencies, num_axis, "spectrometer frequencies", line, line_no)

    peak_list_data = PeakListData(num_axis,axis_labels,data_set,sweep_widths,spectrometer_frequencies)
    line = next(lines)
    raw_headings = line.split()

    heading_indices = OrderedDict({'index': 0})
    for axis_index,axis in enumerate(axis_labels):
        for axis_field in list('LPWBEJU'):
            header = f'{axis}.{axis_field}'
            if header in raw_headings:
                heading_indices[header]=raw_headings.index(header)+1
    # ic(heading_indices)
    for peak_item in ['vol','int','stat','comment','flag0']:
        if peak_item in raw_headings:
            heading_indices[peak_item] = raw_headings.index(peak_item)+1
    # ic(heading_indices)
    peaks = []
    field = None
    for line_no, raw_line in enumerate(lines):
        if not len(raw_line.strip()):
            continue
        try:
            peak = {}
            line = parse_tcl(raw_line)
            #TODO validate and report errors
            peak_index = int(line[0])


            for axis_index, axis in enumerate(axis_labels):
                axis_values = []
                for axis_field in list('LPWBEJU'):
                    header = f'{axis}.{axis_field}'
                    field_index = heading_indices[header]
                    value = line[field_index]

                    if axis_field == 'L':
                        label = value[0] if value else '?'
                        if label =='?':

                            residue_number = None
                            atom_name = ''
                        else:
                            residue_number, atom_name = label.split('.')
                            residue_number = int(residue_number)


                        if residue_number:
                            residue_type = sequence.setdefault((chain_code, residue_number), None)
                        else:
                            residue_type = ''

                        if residue_number:
                            atom = AtomLabel(chain_code,residue_number,residue_type,atom_name.upper())
                        else:
                            atom = AtomLabel('', None, '', atom_name.upper())
                        axis_values.append(atom)

                    elif axis_field == 'P':
                        shift = float(value)
                        axis_values.append(shift)
                    elif axis_field in 'WJU':
                        pass
                    elif axis_field == 'E':
                        merit = value
                        axis_values.append(merit)

                # ic(axis_index, axis_values)
                peak[axis_index] = PeakAxis(*axis_values)

            peak_values = []

            for field in ['vol','int','stat','comment','flag0']:
                field_index = heading_indices[field]
                value = line[field_index]

                if field == 'vol':
                    # ic(value)
                    peak_values.append(float(value))
                elif field == 'int':
                    peak_values.append(float(value))
                elif field == 'stat':
                    peak_values.append(int(value))
                elif field == 'comment':

                    comment = value[0].strip("'") if value else ''
                    peak_values.append(comment)
                elif field == 'flag0':
                    pass

            peak['values'] = PeakValues(peak_index, *peak_values)

            peaks.append(peak)
        except Exception as e:
            field = str(field) if field else 'unknown'
            msg = f"failed to parse file a line {line_no} with input: '{raw_line.strip()}' field: {field}  axis: {axis_field} exception: {e}"
            print(msg)
            raise e


    return PeakList(peak_list_data, peaks)


def check_num_fields(fields, number, field_type, line, line_no):
    if len(fields) != number:
        msg = f'Expected {number} {field_type} got {len(fields)} for line: {line} at line {line_no}'
        exit_error(msg)




def _sequence_to_residue_type_lookup(sequence: List[SequenceResidue]) -> Dict[Tuple[str,int], SequenceResidue]:
    result: Dict[Tuple[str,int], SequenceResidue] = {}
    for residue in sequence:
        result[residue.chain, residue.residue_number] = residue.residue_name
    return result


def _get_isotope_code_or_exit(axis, axis_codes):
    if axis >= len(axis_codes):
        msg = f"can't find isotope code for axis {axis + 1} got axis codes {','.join(axis_codes)}"
        exit_error(msg)
    axis_code = axis_codes[axis]
    return axis_code


def get_sequecne_or_exit(args):
    seq_file = args.sequence
    if not seq_file:
        raise ('read from stdin')
    else:
        with open(seq_file, 'r') as lines:
            sequence = read_sequence(lines, chain_code=args.chain_code)
    return sequence


def import_(args):

    sequence = get_sequecne_or_exit(args)

    sequence = _sequence_to_residue_type_lookup(sequence)


    with open(args.file_names[0], 'r') as lines:
        peaks_list = read_peaks(lines, args.chain_code, sequence)

    entry_name = peaks_list.peak_list_data.data_set.replace(' ', '_')
    entry_name = entry_name.removesuffix('.nv')
    entry_name = entry_name.replace('.','_')
    entry = Entry.from_scratch(entry_name)

    category = "nef_nmr_spectrum"

    frame_code = f'{category}_{entry_name}'

    frame = Saveframe.from_scratch(frame_code, category)
    entry.add_saveframe(frame)
    frame.add_tag("sf_category", category)
    frame.add_tag("sf_framecode", frame_code)
    frame.add_tag("num_dimensions", peaks_list.peak_list_data.num_axis)
    frame.add_tag("chemical_shift_list", constants.NEF_UNKNOWN)

    loop = Loop.from_scratch(f'nef_spectrum_dimension')
    frame.add_loop(loop)

    list_tags = ('dimension_id',

            'axis_unit',
            'axis_code',

            'spectrometer_frequency',
            'spectral_width',

            'value_first_point',
            'folding',
            'absolute_peak_positions',
            'is_acquisition'
    )


    loop.add_tag(list_tags)

    list_data = peaks_list.peak_list_data

    for i in range(list_data.num_axis):
        for tag in list_tags:
            if tag == 'dimension_id':
                loop.add_data_by_tag(tag, i+1)
            elif tag == 'axis_unit':
                loop.add_data_by_tag(tag, 'ppm')
            elif tag == 'axis_code':
                axis_codes = args.axis_codes.split('.')
                loop.add_data_by_tag(tag, axis_codes[i])
            elif tag == 'spectrometer_frequency':
                loop.add_data_by_tag(tag, list_data.spectrometer_frequencies[i])
            elif tag == 'spectral_width':
                # ic(tag, list_data.sweep_widths[i])
                loop.add_data_by_tag(tag, list_data.sweep_widths[i])
            elif tag == 'folding':
                loop.add_data_by_tag(tag, 'circular')
            elif tag == 'absolute_peak_positions':
                loop.add_data_by_tag(tag, 'true')
            else:
                loop.add_data_by_tag(tag,lib.constants.NEF_UNKNOWN)

    loop = Loop.from_scratch('nef_spectrum_dimension_transfer')
    frame.add_loop(loop)

    transfer_dim_tags = (
        'dimension_1',
        'dimension_2',
        'transfer_type'
    )

    loop.add_tag(transfer_dim_tags)

    loop = Loop.from_scratch('nef_peak')
    frame.add_loop(loop)

    peak_tags = [
         'index',
         'peak_id',
         'volume',
         'volume_uncertainty',
         'height',
         'height_uncertainty'
    ]

    position_tags = [(f'position_{i+1}', f'position_uncertainty_{i+1}') for i in range(list_data.num_axis)]
    position_tags = itertools.chain(*position_tags)

    atom_name_tags = [(f'chain_code_{i+1}',f'sequence_code_{i+1}',f'residue_name_{i+1}',f'atom_name_{i+1}')
                       for i in range(list_data.num_axis)]
    atom_name_tags = itertools.chain(*atom_name_tags)

    tags = [*peak_tags, *position_tags, *atom_name_tags]

    loop.add_tag(tags)

    for i, peak in enumerate(peaks_list.peaks):
        peak_values = peak['values']
        if peak_values.status < 0:
            continue
        for tag in tags:

            if tag == 'index':
                loop.add_data_by_tag(tag, i+1)
            elif tag == 'peak_id':
                loop.add_data_by_tag(tag, peak_values.index)
            elif tag == 'volume':
                loop.add_data_by_tag(tag, peak_values.volume)
            elif tag == 'height':
                loop.add_data_by_tag(tag, peak_values.intensity)
            elif tag.split('_')[0] == 'position' and len(tag.split('_')) == 2:
                index = int(tag.split('_')[-1])-1
                loop.add_data_by_tag(tag, peak[index].ppm)
            elif tag.split('_')[:2] == ['chain','code']:
                index = int(tag.split('_')[-1]) - 1
                chain_code = peak[index].atom_labels.chain_code
                chain_code = chain_code if chain_code != None else args.chain_code
                chain_code = chain_code if chain_code else '.'
                loop.add_data_by_tag(tag, chain_code)
            elif tag.split('_')[:2] == ['sequence','code']:
                index = int(tag.split('_')[-1]) - 1
                sequence_code  = peak[index].atom_labels.sequence_code
                sequence_code = sequence_code if sequence_code else '.'
                loop.add_data_by_tag(tag, sequence_code)
            elif tag.split('_')[:2] == ['residue','name']:
                index = int(tag.split('_')[-1]) - 1

                residue_name =  peak[index].atom_labels.residue_name
                residue_name = residue_name if residue_name else '.'
                loop.add_data_by_tag(tag, residue_name)
            elif tag.split('_')[:2] == ['atom','name']:
                index = int(tag.split('_')[-1]) - 1

                atom_name = peak[index].atom_labels.atom_name
                atom_name = atom_name if atom_name else '.'
                loop.add_data_by_tag(tag, atom_name)
            else:
                loop.add_data_by_tag(tag, constants.NEF_UNKNOWN)

    print(entry)


