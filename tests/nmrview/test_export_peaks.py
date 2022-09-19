
import lib
import pytest

from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data, clear_cache, run_and_report

from transcoders.nmrview.exporters.peaks import _make_names_unique, _row_to_peak

from lib.structures import Peak, PeakValues, AtomLabel, SequenceResidue

NMRVIEW_EXPORT_PEAKS= ['nmrview', 'export', 'peaks']



@pytest.fixture
def using_nmrview():
    # register the module under test
    import transcoders.nmrview

EWXPECTED = '''\
save_nef_nmr_spectrum_simnoe
   _nef_nmr_spectrum.sf_category          nef_nmr_spectrum
   _nef_nmr_spectrum.sf_framecode         nef_nmr_spectrum_simnoe
   _nef_nmr_spectrum.num_dimensions       3
   _nef_nmr_spectrum.chemical_shift_list  .

   loop_
      _nef_spectrum_dimension.dimension_id
      _nef_spectrum_dimension.axis_unit
      _nef_spectrum_dimension.axis_code
      _nef_spectrum_dimension.spectrometer_frequency
      _nef_spectrum_dimension.spectral_width
      _nef_spectrum_dimension.value_first_point
      _nef_spectrum_dimension.folding
      _nef_spectrum_dimension.absolute_peak_positions
      _nef_spectrum_dimension.is_acquisition

     1   ppm   1H    800.133   11.0113   .   circular   true   .    
     2   ppm   1H    800.133   11.0600   .   circular   true   .    
     3   ppm   15N   81.076    81.8927   .   circular   true   .    

   stop_

   loop_
      _nef_spectrum_dimension_transfer.dimension_1
      _nef_spectrum_dimension_transfer.dimension_2
      _nef_spectrum_dimension_transfer.transfer_type


   stop_

   loop_
      _nef_peak.index
      _nef_peak.peak_id
      _nef_peak.volume
      _nef_peak.volume_uncertainty
      _nef_peak.height
      _nef_peak.height_uncertainty
      _nef_peak.position_1
      _nef_peak.position_uncertainty_1
      _nef_peak.position_2
      _nef_peak.position_uncertainty_2
      _nef_peak.position_3
      _nef_peak.position_uncertainty_3
      _nef_peak.chain_code_1
      _nef_peak.sequence_code_1
      _nef_peak.residue_name_1
      _nef_peak.atom_name_1
      _nef_peak.chain_code_2
      _nef_peak.sequence_code_2
      _nef_peak.residue_name_2
      _nef_peak.atom_name_2
      _nef_peak.chain_code_3
      _nef_peak.sequence_code_3
      _nef_peak.residue_name_3
      _nef_peak.atom_name_3

     1   0   0.38    .   0.38    .   10.405   .   8.796   .   132.49   .   A   1   ala   HE1   A   3   ala   HN   A   1   ala   N    
     2   1   1.298   .   1.298   .   10.408   .   7.139   .   132.49   .   .   .   .     .     .   .   .     .    .   .   .     .    
     4   3   0.319   .   0.319   .   10.408   .   5.542   .   132.49   .   A   2   ala   HE1   A   3   ala   HA   .   .   .     .    

   stop_

save_
'''

EXPECTED_AXES = ['1H_1','1H_2','15N']

def test_make_names_unique():
    TEST = ['1H','1H','15N']

    result = _make_names_unique(TEST)

    assert result == EXPECTED_AXES

def test_row_to_peak():
    TEST_ROW = {
        'index': 1,
        'peak_id': 0,
        'volume': 0.38,
        'volume_uncertainty': '.',
        'height': 0.38,
        'height_uncertainty': '.',
        'position_1': 10.405,
        'position_uncertainty_1': '.',
        'position_2': 8.796,
        'position_uncertainty_2': '.',
        'position_3': 132.49,
        'position_uncertainty_3': '.',
        'chain_code_1': 'A',
        'sequence_code_1': 1,
        'residue_name_1': 'ala',
        'atom_name_1': 'HE1',
        'chain_code_2': 'A',
        'sequence_code_2': 3,
        'residue_name_2': 'ala',
        'atom_name_2': 'HN',
        'chain_code_3': 'A',
        'sequence_code_3': 1,
        'residue_name_3': 'ala',
        'atom_name_3': 'N'
    }

    result = _row_to_peak(EXPECTED_AXES, TEST_ROW)

    assignments = {
        '15N': [AtomLabel(SequenceResidue(chain_code='A', sequence_code=1, residue_name='ala'), atom_name='N')],
        '1H_1': [AtomLabel(SequenceResidue(chain_code='A', sequence_code=1, residue_name='ala'), atom_name='HE1')],
        '1H_2': [AtomLabel(SequenceResidue(chain_code='A', sequence_code=3, residue_name='ala'), atom_name='HN')]
    }
    positions = {
        '1H_1' : 10.405,
        '1H_2': 8.796,
        '15N': 132.49
    }

    EXPECTED_PEAK = Peak(id=0, positions=positions, assignments=assignments, values=PeakValues(serial=1, volume=0.38, height=0.38))


    assert result == EXPECTED_PEAK

EXPECTED ="""\
label dataset sw sf
1H_1 1H_2 15N
unknown.nv
{8810.505} {8849.471} {6639.533}
{800.133} {800.133} {81.076}
   1H_1.L          1H_1.P       1H_1.W    1H_1.B    1H_1.E  1H_1.J  1H_1.U  1H_2.L  1H_2.P  1H_2.W  1H_2.B  1H_2.E  1H_2.J  1H_2.U  15N.L  15N.P  15N.W  15N.B  15N.E  15N.J  15N.U  vol  int  stat  comment  flag0
0  {A.1.HE1}   10.405   0.024   0.051   ++   0.000   {?}   {A.3.HN}   8.796   0.024   0.051   ++   0.000   {?}   {A.1.N}   132.490   0.024   0.051   ++   0.000   {?}  0.380 0.380 0 {?} 0
1  {?}         10.408   0.024   0.051   ++   0.000   {?}   {?}        7.139   0.024   0.051   ++   0.000   {?}   {?}       132.490   0.024   0.051   ++   0.000   {?}  1.298 1.298 0 {?} 0
3  {A.2.HE1}   10.408   0.024   0.051   ++   0.000   {?}   {A.3.HA}   5.542   0.024   0.051   ++   0.000   {?}   {?}       132.490   0.024   0.051   ++   0.000   {?}  0.319 0.319 0 {?} 0 
"""

# noinspection PyUnusedLocal
def test_3peaks(typer_app, using_nmrview, clear_cache, monkeypatch):

    # # # reading stdin doesn't work in pytest so for a clean header
    # # #TODO move to conftest.py
    # # monkeypatch.setattr(lib.util, 'get_pipe_file', lambda x: None)
    STREAM =  open(path_in_test_data(__file__, 'nef_3_peaks.nef', local=True)).read()

    args = [*NMRVIEW_EXPORT_PEAKS]
    result = run_and_report(typer_app, args, input=STREAM)

    assert_lines_match(EXPECTED, result.stdout)
