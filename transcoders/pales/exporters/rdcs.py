from dataclasses import replace
from fnmatch import fnmatch
from typing import List, Tuple, Dict

import tabulate
from pynmrstar import Entry, Saveframe, Loop
from transcoders.pales import export_app
import typer

from lib.sequence_lib import get_sequence_or_exit

from lib.sequence_lib import sequence_residues_to_sequence_3let, translate_3_to_1
from lib.util import chunks, exit_error, read_float_or_exit

from lib.structures import SequenceResidue, RdcRestraint, AtomLabel

from lib.nef_lib import loop_to_dataframe, select_frames_by_name

from lib.util import cached_stdin

app = typer.Typer()

#TODO: name translations
#TODO: correct weights
#TODO: move utuilities to lib
#TODO: support multiple chains

# noinspection PyUnusedLocal
@export_app.command()
def rdcs(
    chains: str = typer.Option([], '-c', '--chain', help="chains to export, to add mutiple chains use repeated calls  [default: 'A']", metavar='<CHAIN-CODE>'),
    raw_weights: List[str] = typer.Option([], '-w', '--weight', help='weights for rdcs as a comma separated triple of 2 atom names and a weight [no spaces e.g HN,N,1.0], multiple weights may be added by repeated calls, efault is HN,N,1.0'),
    frame_selectors: List[str] = typer.Option('*', '-f', '--frame', help='selector for the rdc restraint frame to use, can be called multiple times and include wild cards')
):
    """- convert nef rdc restraints to pales"""

    if not chains:
        chains=['A']
    weights = _parse_weights(raw_weights)
    sequence = get_sequence_or_exit()

    sequence_3_let = sequence_residues_to_sequence_3let(sequence)

    sequence_1_let = translate_3_to_1(sequence_3_let)

    NEF_RDC_CATEGORY = 'nef_rdc_restraint_list'

    entry = _create_entry_from_stdin_or_exit()
    rdc_frames = entry.get_saveframes_by_category(NEF_RDC_CATEGORY)

    if frame_selectors is None:
        frame_selectors = ['']
    frames = select_frames_by_name(rdc_frames, frame_selectors)

    restaints = _rdc_restraints_from_frames(frames, chains, weights)

    restaints = _translate_atom_names(restaints, 'xplor')

    print(f'REMARK NEF CHAIN {", ".join(chains)}')
    print(f'REMARK NEF START RESIDUE {sequence[0].sequence_code}')
    print()
    _print_pipe_sequence(sequence_1_let)
    print()
    _print_restraints(restaints, weights)


def _create_entry_from_stdin_or_exit():

    try:
        entry = Entry.from_string(''.join(cached_stdin()))
    except Exception as e:
        exit_error(f"failed to read nef entry from stdin because {e}", e)

    return entry


def _translate_atom_names(restraints: list[RdcRestraint], naming_scheme='iupac')-> List[RdcRestraint]:
    result =[]
    for restraint in restraints:
        atom_1 = restraint.atom_1
        atom_2 = restraint.atom_2

        if atom_1.atom_name == 'H':
            restraint.atom_1 = replace(atom_1, atom_name='HN')

        if atom_2.atom_name == 'H':
            restraint.atom_1 = replace(atom_2, atom_name='HN')

        result.append(restraint)

    return result


def _select_frames_by_name(frames: List[Saveframe], name_selectors: List[str]) -> List[str]:
    result = {}

    for frame in frames:
        for selector in name_selectors:
            matcher = f'*{selector}*'
            if fnmatch(frame.name, f'*{selector}*'):
                result[frame.name] = frame
    return list(result.values())


def _loop_row_dict_iter(loop: Loop):
    for row in loop:
        yield {tag: value for tag, value in zip(loop.tags,row)}


def _rdc_restraints_from_frames(frames: List[Saveframe], chains: List[str], weights: Dict[Tuple[str, str], float]):
    result = []
    for frame in frames:
        for row in _loop_row_dict_iter(frame.loops[0]):

            atom_1 = AtomLabel(row['chain_code_1'], int(row['sequence_code_1']), row['residue_name_1'], row['atom_name_1'])
            atom_2 = AtomLabel(row['chain_code_2'], int(row['sequence_code_2']), row['residue_name_2'], row['atom_name_2'])

            weight_key = _build_weights_key(row['atom_name_1'], row['atom_name_2'])
            # this should be
            weight =  weights[weight_key] if weight_key in weights else 1.0
            rdc = RdcRestraint(atom_1, atom_2, row['target_value'], row['target_value_uncertainty'], weight)

            result.append(rdc)

    return sorted(result)




def _parse_weights(raw_weights):

    result  = {}
    for raw_weight in raw_weights:

        raw_weight_fields = raw_weight.split(',')

        if len(raw_weight_fields) != 3:
            exit_error(f'bad weight {raw_weight} weights should have 3 fields separated by commas [no spaces] atom_1,atom_2,weight. e.g HN,N,1.0')

        atom_1, atom_2, raw_rdc_weight =  raw_weight_fields

        rdc_weight = read_float_or_exit(raw_rdc_weight, message=f'weights should have 3 fields separated by commas [no spaces] atom_1,atom_2,weight weight should be a float i got {raw_weight} for field feild [{raw_rdc_weight}] which is not a float')

        key = _build_weights_key(atom_1, atom_2)
        result[key] = rdc_weight

    # it not possibe to add default weights?
    HN_N_key = _build_weights_key('HN', 'N')
    if not HN_N_key in result:
        result[HN_N_key] = 1.0

    return result

def _build_weights_key(atom_1, atom_2):
    return tuple(sorted([atom_1, atom_2]))

def _print_restraints(restraints: List[RdcRestraint], weights: Dict[Tuple[str, str], float]):
    VARS = 'VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D DD W'.split()
    FORMAT = 'FORMAT %5d     %6s       %6s        %5d     %6s    %6s %9.3f %9.3f %.2f'.split()

    table = [VARS, FORMAT]

    for i, restraint in enumerate(restraints):
        atom_1 = restraint.atom_1
        atom_2 = restraint.atom_2

        weights_key = _build_weights_key(atom_1.atom_name, atom_2.atom_name)
        weight = weights[weights_key]
        row = ['', atom_1.sequence_code, atom_1.residue_name, atom_1.atom_name,
               atom_2.sequence_code, atom_2.residue_name, atom_2.atom_name, restraint.rdc, restraint.rdc_error, weight]
        table.append(row)

    print(tabulate.tabulate(table, tablefmt='plain'))


def _print_pipe_sequence(sequence_1_let: List[str]):

    rows = chunks(sequence_1_let, 100)

    for row in rows:
        row_chunks = list(chunks(row, 10))
        row_strings = [''.join(chunk) for chunk in row_chunks]
        print(f'DATA SEQUENCE {" ".join(row_strings)}')


