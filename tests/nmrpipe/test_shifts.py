from lib.structures import  ShiftList, ShiftData, AtomLabel
from textwrap import dedent
from transcoders.nmrpipe.nmrpipe_lib import read_db_file_records , read_shift_file

def test_lib_parse_shifts():

    EXPECTED = ShiftList(
        shifts=[
            ShiftData(atom=AtomLabel(chain_code='A', sequence_code=1, residue_name='ALA', atom_name='N'), shift=125.74, error=None),
            ShiftData(atom=AtomLabel(chain_code='A', sequence_code=2, residue_name='GLY', atom_name='HN'), shift=8.31, error=None)
        ]
    )


    test_data = '''
        VARS   RESID RESNAME ATOMNAME SHIFT
        FORMAT %4d %1s %4s %8.2f

        1   ALA   N   125.74
        2   GLY   HN   8.31

    '''

    test_data = dedent(test_data)

    test_records = read_db_file_records(test_data.split('\n'))

    shifts = read_shift_file(test_records)
    assert shifts == EXPECTED

