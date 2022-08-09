from lib.structures import  ShiftList, ShiftData, AtomLabel
from textwrap import dedent
from transcoders.nmrview.nmrview_lib import  parse_shifts
import pytest
from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

from typer.testing import CliRunner
runner = CliRunner()

SHIFTS_NMRPIPE = 'nef_chemical_shift_list_nmrview'
METADATA_NMRVIEW ='nef_nmr_meta_data'
NMRVIEW_IMPORT_SHIFTS = ['nmrview', 'import', 'shifts']

HEADER = open(path_in_test_data(__file__,'test_header_entry.txt', local=False)).read()


@pytest.fixture
def using_nmrview():
    # register the module under test
    import transcoders.nmrview


def test_lib_parse_shifts():


    EXPECTED = ShiftList(
        shifts=[
            ShiftData(atom=AtomLabel(chain_code='A', sequence_code=1, residue_name='ASP', atom_name='CA'), shift=52.00, error=None),
            ShiftData(atom=AtomLabel(chain_code='A', sequence_code=1, residue_name='ASP', atom_name='HA'), shift=4.220, error=None),
            ShiftData(atom=AtomLabel(chain_code='A', sequence_code=2, residue_name='VAL', atom_name='CG2'), shift=19.300, error=None),
            ShiftData(atom=AtomLabel(chain_code='A', sequence_code=2, residue_name='VAL', atom_name='HG21'), shift=0.814, error=None),
            ShiftData(atom=AtomLabel(chain_code='A', sequence_code=2, residue_name='VAL', atom_name='HG22'), shift=0.814, error=None),
            ShiftData(atom=AtomLabel(chain_code='A', sequence_code=3, residue_name='GLN', atom_name='N'), shift=125.058, error=None)
        ]
    )


    test_data = '''\
          1.CA      52.000 1
          1.HA       4.220 1
          2.CG2     19.300 1
          2.HG21     0.814 1
          2.HG22     0.814 1
          3.N      125.058 1
    '''

    chain_seqid_to_type = {
        ('A', 1) : 'ASP',
        ('A', 2): 'VAL',
        ('A', 3): 'GLN'
    }

    test_data = dedent(test_data)

    shifts = parse_shifts(test_data.split('\n'), chain_seqid_to_type)

    assert shifts == EXPECTED
#
EXPECTED_PPM_OUT_SHORT = '''\
save_nef_chemical_shift_list_nmrview
   _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
   _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_nmrview

   loop_
      _nef_chemical_shift_list.chain_code
      _nef_chemical_shift_list.sequence_code
      _nef_chemical_shift_list.residue_name
      _nef_chemical_shift_list.atom_name
      _nef_chemical_shift_list.value
      _nef_chemical_shift_list.value_uncertainty
      _nef_chemical_shift_list.element
      _nef_chemical_shift_list.isotope_number

     A   1   .   CA     52.0      .   .   .    
     A   1   .   HA     4.22      .   .   .    
     A   2   .   CG2    19.3      .   .   .    
     A   2   .   HG21   0.814     .   .   .    
     A   2   .   HG22   0.814     .   .   .    
     A   3   .   N      125.058   .   .   .    

   stop_

save_
'''

# # noinspection PyUnusedLocal
def test_ppm_out_short(typer_app, using_nmrview, monkeypatch):

    monkeypatch.setattr('sys.stdin.isatty', lambda: False)

    path = path_in_test_data(__file__, 'ppm_short.out')
    result = runner.invoke(typer_app, [*NMRVIEW_IMPORT_SHIFTS, path], input=HEADER)

    if result.exit_code != 0:
        print('INFO: stdout from failed read:\n',result.stdout)

    assert result.exit_code == 0
    mol_sys_result = isolate_frame(result.stdout, '%s' % SHIFTS_NMRPIPE)

    assert_lines_match(EXPECTED_PPM_OUT_SHORT, mol_sys_result)