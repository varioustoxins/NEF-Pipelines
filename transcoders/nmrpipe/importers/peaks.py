import math
import re
import sys
import traceback
from collections import OrderedDict
from enum import Enum, IntEnum
from textwrap import dedent
from typing import List, Dict, Tuple

from icecream import ic
from ordered_set import OrderedSet
from pynmrstar import Entry, Saveframe, Loop

from lib.constants import NEF_UNKNOWN
from lib import constants
from lib.sequence_lib import chain_code_iter, translate_1_to_3
from lib.structures import SequenceResidue

from lib.typer_utils import get_args

from pathlib import Path

from lib.structures import AtomLabel, PeakAxis, PeakValues, PeakListData, PeakList
from .sequence import read_sequence

from lib.util import exit_error, process_stream_and_add_frames, get_pipe_file, cached_file_stream, is_int

import itertools




from transcoders.nmrpipe import import_app
import typer

from ..nmrpipe_lib import read_db_file_records, select_records, VARS, VALUES
from ...nmrview.importers.peaks import create_spectrum_frame

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
        entry_name: str = typer.Option('nmrpipe', help='a name for the entry'),
        chain_code: str = typer.Option('A', '--chain', help='chain code', metavar='<chain-code>'),
        sequence: str = typer.Option(None, metavar='<nmrpipe>.seq)',
                                     help="seq file for the chain <seq-file>.tab, the value '!internal!' will read from the peak file"),
        axis_codes: str = typer.Option('1H.15N', metavar='<axis-codes>',  help='a list of axis codes joined by dots'),
        filter_noise: bool = typer.Option(True, help='remove peaks labelled as noise'),
        file_names: List[Path] = typer.Argument(..., help="input peak files", metavar='<peak-file.xpk>')
):
    """convert nmrview peak file <nmrview>.xpk files to NEF"""


    exception_message = ''
    try:
        args = get_args()

        sequence = _get_sequence_or_exit(args)


        # frames =
        peak_list = _read_nmrpipe_peaks(args, sequence)
        frames = create_spectrum_frame(args, entry_name, peak_list)



    except Exception as e:

        traceback.print_exc()


        print(exception_message)

    entry = process_stream_and_add_frames([frames, ], args)

    print(entry)



def _get_sequence_or_exit(args):
    sequence_file = None
    if 'sequence' in args:
        sequence_file = args.sequence

    if not sequence_file:

        try:
            stream = get_pipe_file(args)
            entry = Entry.from_file(stream)
            frames = entry.get_saveframes_by_category('nef_molecular_system')
            sequence = sequence_from_frames(frames)

        except Exception as e:
            exit_error(f'failed to read sequence from input stream because {e}')

    else:
        if sequence_file == '!internal!':
            sequence = _read_sequence_internal(args.file_names)
        else:
            with open(sequence_file, 'r') as lines:
                sequence = read_sequence(lines, chain_code=args.chain_code)

    if not sequence:
        exit_error(f'''no sequence read with args: {sys.argv[1:]}''')
    return sequence


def _read_sequence_internal(file_names):
    sequence = []

    for (file_name, chain_code) in zip(file_names, chain_code_iter()):
        file_h = cached_file_stream(file_name)
        sequence.extend(read_sequence(file_h, chain_code=chain_code))

    return sequence


def _get_column_indices(gdb_file):
    return {column: index-1 for index, column in enumerate(_get_gdb_columns(gdb_file)) if column != 'INDEX'}


def _propagate_assignments(assignments):

    current = []
    result = []
    for assignment in assignments:
        fields = re.split(r'(\d+)', assignment)
        if len(fields) == 3:
            current = fields[:2]
        elif len(fields) == 1:
            fields = [*current, *fields]

        result.append(fields)

    return result


class PEAK_TYPES(IntEnum):
   PEAK = 1
   NOISE = 2
   SINC_WIGGLE = 3

# NMRPIPE VARS https://spin.niddk.nih.gov/NMRPipe/doc2new/
#
# INDEX = 'INDEX'  # REQUIRED      - The unique peak ID number.
# X_AXIS = 'X_AXIS'  # REQUIRED      - Peak position: in points in 1st dimension, from left of spectrum limit
# Y_AXIS = 'Y_AXIS'  # REQUIRED      - Peak position: in points in 2nd dimension, from bottom of spectrum limit
# DX = 'DX'  # NOT REQUIRED  - Estimate of the error in peak position due to random noise, in points.
# DY = 'DY'  # NOT REQUIRED  - Estimate of the error in peak position due to random noise, in points.
# X_PPM = 'X_PPM'  # NOT REQUIRED  - Peak position: in ppm in 1st dimension
# Y_PPM = 'Y_PPM'  # NOT REQUIRED  - Peak position: in ppm in 2nd dimension
# X_HZ = 'X_HZ'  # NOT REQUIRED  - Peak position: in Hz in 1st dimension
# Y_HZ = 'Y_HZ'  # NOT REQUIRED  - Peak position: in Hz in 2nd dimension
# XW = 'XW'  # REQUIRED      - Peak width: in points in 1st dimension
# YW = 'YW'  # REQUIRED      - Peak width: in points in 2nd dimension
# XW_HZ = 'XW_HZ'  # REQUIRED      - Peak width: in points in 1st dimension
# YW_HZ = 'YW_HZ'  # REQUIRED      - Peak width: in points in 2nd dimension
# X1 = 'X1'  # NOT REQUIRED  - Left border of peak in 1st dim, in points
# X3 = 'X3'  # NOT REQUIRED  - Right border of peak in 1st dim, in points
# Y1 = 'Y1'  # NOT REQUIRED  - Left border of peak in 2nd dim, in points
# Y3 = 'Y3'  # NOT REQUIRED  - Right border of peak in 2nd, in points
# HEIGHT = 'HEIGHT'  # NOT REQUIRED  - Peak height
# DHEIGHT = 'DHEIGHT'  # NOT REQUIRED  - Peak height error
# VOL = 'VOL'  # NOT REQUIRED  - Peak volume
# PCHI2 = 'PCHI2'  # NOT REQUIRED  - the Chi-square probability for the peak (i.e. probability due to the noise)
# TYPE = 'TYPE'  # NOT REQUIRED  - the peak classification; 1=Peak, 2=Random Noise, 3=Truncation artifact.
# ASS = 'ASS'  # REQUIRED      - Peak assignment
# CLUSTID = 'CLUSTID'  # REQUIRED      - Peak cluster id. Peaks with the same CLUSTID value are the overlapped.
# MEMCNT = 'MEMCNT'  # REQUIRED      - the total number of peaks which are in a given peak's cluster
# (i.e. peaks which have the same CLUSTID value)


def _read_nmrpipe_peaks(args, sequence):
    for file_name in args.file_names:
        file_h = cached_file_stream(file_name)
        gdb_file = read_db_file_records(file_h, file_name=file_name)

        _check_is_peak_file_or_exit(gdb_file)

        data = select_records(gdb_file, VALUES)

        dimensions = _get_peak_list_dimension(gdb_file)

        column_indices = _get_column_indices(gdb_file)

        axis_labels = _get_axis_labels(gdb_file)

        spectrometer_frequencies = [[] for _ in range(dimensions)]

        raw_peaks  = []
        for index, line in enumerate(data, start=1):
            ic(index,line)
            peak = {}
            raw_peaks.append(peak)
            peak_type = line.values[column_indices['TYPE']]
            if args.filter_noise and peak_type != PEAK_TYPES.PEAK:
                continue

            assignment = line.values[column_indices['ASS']]
            assignments = assignment.split('-')
            assignments = _propagate_assignments(assignments)
            assignments = _assignments_to_atom_labels(assignments, dimensions)


            height = line.values[column_indices['HEIGHT']]
            height_error = line.values[column_indices['DHEIGHT']]
            height_percentage_error  = height_error / height
            volume = line.values[column_indices['VOL']]
            volume_error = volume * height_percentage_error


            peak_values = PeakValues(index=index, volume=volume, intensity=height, status=True, comment = '')
            peak['values'] = peak_values


            for i, dimension in enumerate('X Y Z A'.split()[:dimensions]):

                shift = line.values[column_indices['%s_PPM' % dimension]]


                point_error = line.values[column_indices['D%s' % dimension]]

                point = line.values[column_indices['%s_AXIS' % dimension]]
                error = point_error / point * shift

                pos_hz = line.values[column_indices['%s_HZ' % dimension]]

                axis = PeakAxis(atom_labels=assignments[i], ppm=shift, merit=1)

                peak[i] = axis

                sf = pos_hz / shift

                # atom_label = AtomLabel(chain_code=args.chain_code, sequence_code)

                spectrometer_frequencies[i].append(sf)


        spectrometer_frequencies = [_mean(frequencies) for frequencies in spectrometer_frequencies]
        header_data = PeakListData(num_axis=dimensions, axis_labels=axis_labels, data_set=None, sweep_widths=None,
                                      spectrometer_frequencies=spectrometer_frequencies)


        peak_list = PeakList(header_data, raw_peaks)

        return peak_list



def _mean(values):
    return sum(values) / len(values)


def _get_peak_list_dimension(gdb_file):

    return len(_get_axis_labels(gdb_file))


def _assignments_to_atom_labels(assignments, dimensions, chain_code = 'A'):
    result = []

    for assignment in assignments:
        chain_code = chain_code

        residue_name = None
        len_assignment = len(assignment)
        if len_assignment > 0:
            residue_name = translate_1_to_3(assignment[0], unknown='.')[0]

        sequence_code = None
        if len_assignment > 1:
            raw_sequence_code = assignment[1]
            if is_int(raw_sequence_code):
                sequence_code = int(raw_sequence_code)

        atom_name = None
        if len_assignment > 2:
            atom_name = assignment[2]

        result.append(AtomLabel(chain_code, sequence_code, residue_name, atom_name))

    len_result = len(result)
    if len_result < dimensions:
        for i in (len_result-dimensions):
            result.append(AtomLabel(None, None, None, None))
    return result


def _get_axis_labels(gdb_file):
    columns = _get_gdb_columns(gdb_file)

    result = []
    for var in columns:
        if var.endswith('_AXIS'):
            result.append(var.split('_')[0])
    return result


def _get_gdb_columns(gdb_file):
    return select_records(gdb_file, VARS)[0].values


def _check_is_peak_file_or_exit(gdb_file):
    columns = set(_get_gdb_columns(gdb_file))
    expected_fields = set('X_AXIS XW XW_HZ ASS CLUSTID MEMCNT'.split())
    if not expected_fields.issubset(columns):
        msg = f'''\
            this gdb file doesn't appear to contain all the columns expected for a peak file
            expected: {','.join(expected_fields)}
            got {','.join(columns & expected_fields)}
            file: {gdb_file.file_name}
            '''
        msg = dedent(msg)
        exit_error(msg)


