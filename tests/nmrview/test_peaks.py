import traceback
from pathlib import Path

import lib
import pytest

from typer.testing import CliRunner
from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

MOLECULAR_SYSTEM_NMRVIEW = 'nef_spectrum_nmrview'
NMRVIEW_IMPORT_PEAKS= ['nmrview', 'import', 'peaks']

runner = CliRunner()


@pytest.fixture
def using_nmrview():
    # register the module under test
    import transcoders.nmrview

EXPECTED_4AA = '''\
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

     1   ppm   1H    800.133   8810.5    .   circular   true   .    
     2   ppm   1H    800.133   8849.49   .   circular   true   .    
     3   ppm   15N   81.076    6639.53   .   circular   true   .    

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

     1   0   0.38    .   0.38    .   10.405   .   8.796   .   132.49   .   A   1   ala   HE1   A   3   ala   HN   .   .   .   .    
     2   1   1.298   .   1.298   .   10.408   .   7.139   .   132.49   .   .   .   .     .     .   .   .     .    .   .   .   .    
     4   3   0.319   .   0.319   .   10.408   .   5.542   .   132.49   .   A   2   ala   HE1   A   3   ala   HA   .   .   .   .    

   stop_

save_
'''

# noinspection PyUnusedLocal
def test_3peaks(typer_app, using_nmrview, monkeypatch):

    # reading stdin doesn't work in pytest so for a clean header
    #TODO move to conftest.py
    monkeypatch.setattr(lib.util, 'get_pipe_file', lambda x: None)
    peaks_path = path_in_test_data(__file__, '4peaks.xpk')
    sequence_path = path_in_test_data(__file__, '4peaks.seq')
    result = runner.invoke(typer_app, [*NMRVIEW_IMPORT_PEAKS, '--sequence', sequence_path,  '--axis-codes', '1H.1H.15N', peaks_path])
    assert result.exit_code == 0

    result = isolate_frame(result.stdout, 'nef_nmr_spectrum_simnoe')

    assert_lines_match(EXPECTED_4AA, result)


if __name__ == '__main__':
    pytest.main([__file__, '-vv'])
