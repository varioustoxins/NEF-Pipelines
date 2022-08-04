from lib.structures import ShiftList
from pynmrstar import Saveframe, Loop

UNUSED ='.'

def shifts_to_nef_frame(shift_list: ShiftList, entry_name: str):

    category = "nef_chemical_shift_list"

    frame_code = f'{category}_{entry_name}'

    frame = Saveframe.from_scratch(frame_code, category)

    frame.add_tag("sf_category", category)
    frame.add_tag("sf_framecode", frame_code)

    loop = Loop.from_scratch()
    frame.add_loop(loop)

    tags = ('chain_code', 'sequence_code', 'residue_name', 'atom_name', 'value', 'value_uncertainty', 'element',
            'isotope_number')

    loop.set_category(category)
    loop.add_tag(tags)

    for shift in shift_list.shifts:

        loop.add_data_by_tag('chain_code', shift.atom.chain_code)
        loop.add_data_by_tag('sequence_code', shift.atom.sequence_code)
        loop.add_data_by_tag('residue_name', shift.atom.residue_name)
        loop.add_data_by_tag('atom_name', shift.atom.atom_name)
        loop.add_data_by_tag('value', shift.shift)
        if shift.error != None:
            loop.add_data_by_tag('value_uncertainty', shift.error)
        else:
            loop.add_data_by_tag('value_uncertainty', UNUSED)
        loop.add_data_by_tag('element', UNUSED)
        loop.add_data_by_tag('isotope_number', UNUSED)

    return frame