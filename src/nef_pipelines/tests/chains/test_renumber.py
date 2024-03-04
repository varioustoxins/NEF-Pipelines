import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.chains.renumber import renumber

runner = CliRunner()

app = typer.Typer()
app.command()(renumber)

OFFSET_CHAINS_A_10 = ["A", "10"]
OFFSET_CHAINS_A_10_B_5 = ["A", "10", "B", "5"]
OFFSET_CHAINS_MISSING_OFFSET = ["A", "10", "B"]
OFFSET_CHAINS_BAD_OFFSET = ["A", "10", "B", "B5"]
SET_CHAIN_STARTS_A_0_B_10 = ["--starts", "A", "0", "B", "10"]
SET_CHAIN_STAR_A_SHIFTS = ["--starts", "A", "10", "--frames", "nef_nmr_spectrum"]


# noinspection PyUnusedLocal
def test_renumber_basic():

    path = path_in_test_data(__file__, "tailin_seq_short.nef")

    result = run_and_report(app, [*OFFSET_CHAINS_A_10], input=open(path))

    EXPECTED = """\
        data_talin1

        save_nef_molecular_system
           _nef_molecular_system.sf_category   nef_molecular_system
           _nef_molecular_system.sf_framecode  nef_molecular_system

           loop_
              _nef_sequence.index
              _nef_sequence.chain_code
              _nef_sequence.sequence_code
              _nef_sequence.residue_name
              _nef_sequence.linking
              _nef_sequence.residue_variant
              _nef_sequence.cis_peptide

             1    A   20   GLU   start    .   .
             2    A   21   TYR   middle   .   .
             3    A   22   ALA   middle   .   .
             4    A   23   GLN   middle   .   .
             5    A   24   PRO   middle   .   .
             6    A   25   ARG   middle   .   .
             7    A   26   LEU   middle   .   .
             8    A   27   ARG   middle   .   .
             9    A   28   LEU   middle   .   .
             10   A   29   GLY   middle   .   .
             11   A   30   PHE   middle   .   .
             12   A   31   GLU   middle   .   .
             13   A   32   ASP   end      .   .

           stop_

        save_
    """

    assert_lines_match(EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_renumber_multi_chain_two_chains():
    path = path_in_test_data(__file__, "multi_chain.nef")

    result = run_and_report(app, [*OFFSET_CHAINS_A_10_B_5], input=open(path))

    EXPECTED = """\
        data_test

        save_nef_molecular_system
           _nef_molecular_system.sf_category   nef_molecular_system
           _nef_molecular_system.sf_framecode  nef_molecular_system

            loop_
                _nef_sequence.index
                _nef_sequence.chain_code
                _nef_sequence.sequence_code
                _nef_sequence.residue_name
                _nef_sequence.linking
                _nef_sequence.residue_variant
                _nef_sequence.cis_peptide
                _nef_sequence.ccpn_comment
                _nef_sequence.ccpn_chain_role
                _nef_sequence.ccpn_compound_name
                _nef_sequence.ccpn_chain_comment
                1   A   13   HIS   .   .   .   .   .   Sec5   .
                2   A   14   MET   .   .   .   .   .   Sec5   .
                3   B   10   ARG   .   .   .   .   .   Sec5   .
                4   B   11   GLN   .   .   .   .   .   Sec5   .
                5   C   7    PRO   .   .   .   .   .   Sec5   .
            stop_

        save_
    """

    assert_lines_match(EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_renumber_no_offset():
    path = path_in_test_data(__file__, "multi_chain.nef")

    result = run_and_report(
        app, [*OFFSET_CHAINS_MISSING_OFFSET], input=open(path), expected_exit_code=1
    )

    assert "ERROR" in result.stdout
    assert "there must be an offset/start for each chain" in result.stdout


# noinspection PyUnusedLocal
def test_renumber_bad_offset():
    path = path_in_test_data(__file__, "multi_chain.nef")

    result = run_and_report(
        app, [*OFFSET_CHAINS_BAD_OFFSET], input=open(path), expected_exit_code=1
    )

    assert "ERROR" in result.stdout
    assert "B5" in result.stdout
    assert "2nd" in result.stdout
    assert "can't be converted to an int" in result.stdout


def test_renumber_no_chain_or_offset():
    path = path_in_test_data(__file__, "multi_chain.nef")

    result = run_and_report(app, [], input=open(path), expected_exit_code=1)

    assert "ERROR" in result.stdout
    assert "you didn't provide any chains and offsets/starts" in result.stdout


# noinspection PyUnusedLocal
def test_set_starts_two_chains():
    path = path_in_test_data(__file__, "multi_chain.nef")

    result = run_and_report(app, [*SET_CHAIN_STARTS_A_0_B_10], input=open(path))

    EXPECTED = """\
        data_test

        save_nef_molecular_system
           _nef_molecular_system.sf_category   nef_molecular_system
           _nef_molecular_system.sf_framecode  nef_molecular_system

           loop_
              _nef_sequence.index
              _nef_sequence.chain_code
              _nef_sequence.sequence_code
              _nef_sequence.residue_name
              _nef_sequence.linking
              _nef_sequence.residue_variant
              _nef_sequence.cis_peptide
              _nef_sequence.ccpn_comment
              _nef_sequence.ccpn_chain_role
              _nef_sequence.ccpn_compound_name
              _nef_sequence.ccpn_chain_comment

             1   A   0    HIS   .   .   .   .   .   Sec5   .
             2   A   1    MET   .   .   .   .   .   Sec5   .
             3   B   10   ARG   .   .   .   .   .   Sec5   .
             4   B   11   GLN   .   .   .   .   .   Sec5   .
             5   C   7    PRO   .   .   .   .   .   Sec5   .

           stop_

        save_

    """

    assert_lines_match(EXPECTED, result.stdout)


def test_renumber_shifts_chain_a_only():
    path = path_in_test_data(__file__, "nef_3_peaks.nef")

    result = run_and_report(app, [*SET_CHAIN_STAR_A_SHIFTS], input=open(path))

    NOQUA_E501 = "# noqa E501"
    EXPECTED = """# noqa E501
        data_nmrview

        save_nef_molecular_system
           _nef_molecular_system.sf_category   nef_molecular_system
           _nef_molecular_system.sf_framecode  nef_molecular_system

           loop_
              _nef_sequence.index
              _nef_sequence.chain_code
              _nef_sequence.sequence_code
              _nef_sequence.residue_name
              _nef_sequence.linking
              _nef_sequence.residue_variant
              _nef_sequence.cis_peptide

             1   A   1   ALA   start    .   .
             2   A   2   ALA   middle   .   .
             3   A   3   ALA   end      .   .

           stop_

        save_

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

             1   0   0.38    .   0.38    .   10.405   .   8.796   .   132.49   .   A   10   ala   HE1   A   12   ala   HN   A   10   ala   N
             2   1   1.298   .   1.298   .   10.408   .   7.139   .   132.49   .   .   .    .     .     .   .    .     .    .   .    .     .
             3   3   0.319   .   0.319   .   10.408   .   5.542   .   132.49   .   A   11   ala   HE1   A   12   ala   HA   .   .    .     .

           stop_

        save_


    """.replace(
        NOQUA_E501, ""
    )

    assert_lines_match(EXPECTED, result.stdout)


def test_renumber_chain_in_first_column():
    test_data = """
        data_chain

        save_chain_test
           _nef_molecular_system.sf_category   chain_test
           _nef_molecular_system.sf_framecode  chain_test

           loop_
              _nef_sequence.chain_code
              _nef_sequence.sequence_code


             A   1
             A   2
             A   3

           stop_
        save_
    """

    result = run_and_report(app, [*OFFSET_CHAINS_A_10], input=test_data)

    EXPECTED = """
        data_chain

        save_chain_test
           _nef_molecular_system.sf_category   chain_test
           _nef_molecular_system.sf_framecode  chain_test

           loop_
              _nef_sequence.chain_code
              _nef_sequence.sequence_code


             A   11
             A   12
             A   13

           stop_
        save_
    """

    assert_lines_match(EXPECTED, result.stdout)
