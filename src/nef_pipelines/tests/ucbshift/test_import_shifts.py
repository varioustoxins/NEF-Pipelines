from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.ucbshift import import_app

runner = CliRunner()
app = import_app


# noinspection PyUnusedLocal
def test_shifts_single_chain():

    EXPECTED = """\
        save_nef_chemical_shift_list_ucbshift
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_ucbshift

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   1   MET   H    8.432     .   H   1
              A   1   MET   HA   4.207     .   H   1
              A   1   MET   C    170.727   .   C   13
              A   1   MET   CA   54.512    .   C   13
              A   1   MET   CB   33.104    .   C   13
              A   1   MET   N    120.882   .   N   15
              A   2   GLN   H    8.928     .   H   1
              A   2   GLN   HA   4.984     .   H   1
              A   2   GLN   C    175.83    .   C   13
              A   2   GLN   CA   54.92     .   C   13
              A   2   GLN   CB   30.66     .   C   13
              A   2   GLN   N    123.822   .   N   15
              A   3   ILE   H    8.347     .   H   1
              A   3   ILE   HA   4.258     .   H   1
              A   3   ILE   C    171.982   .   C   13
              A   3   ILE   CA   59.497    .   C   13
              A   3   ILE   CB   42.071    .   C   13
              A   3   ILE   N    116.238   .   N   15

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    ucbshift_file = path_in_test_data(__file__, "test_shifts.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--frame-name", "ucbshift", ucbshift_file],
        expected_exit_code=0,
    )

    ucbshift_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_ucbshift")

    assert_lines_match(EXPECTED, ucbshift_frame)


def test_shifts_prediction_type_x():
    """Test importing X prediction data"""
    EXPECTED = """\
        save_nef_chemical_shift_list_ucbshift
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_ucbshift

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   1   MET   H    8.234   .   H   1
              A   1   MET   C    55.678  .   C   13
              A   1   MET   N    120.123 .   N   15
              A   2   ALA   H    8.123   .   H   1
              A   2   ALA   C    52.456  .   C   13
              A   2   ALA   N    122.789 .   N   15

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_simple_sequence.nef")
    x_prediction_file = path_in_test_data(__file__, "test_x_prediction.csv")

    result = run_and_report(
        app,
        [
            "shifts",
            "-i",
            sequence_file,
            "--prediction-type",
            "x",
            "--frame-name",
            "ucbshift",
            x_prediction_file,
        ],
        expected_exit_code=0,
    )

    ucbshift_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_ucbshift")
    assert_lines_match(EXPECTED, ucbshift_frame)


def test_shifts_prediction_type_y():
    """Test importing Y prediction data"""
    EXPECTED = """\
        save_nef_chemical_shift_list_ucbshift
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_ucbshift

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   1   MET   H    8.567   .   H   1
              A   1   MET   C    56.123  .   C   13
              A   1   MET   N    119.456 .   N   15
              A   2   ALA   H    8.456   .   H   1
              A   2   ALA   C    51.789  .   C   13
              A   2   ALA   N    123.234 .   N   15

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_simple_sequence.nef")
    y_prediction_file = path_in_test_data(__file__, "test_y_prediction.csv")

    result = run_and_report(
        app,
        [
            "shifts",
            "-i",
            sequence_file,
            "--prediction-type",
            "y",
            "--frame-name",
            "ucbshift",
            y_prediction_file,
        ],
        expected_exit_code=0,
    )

    ucbshift_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_ucbshift")
    assert_lines_match(EXPECTED, ucbshift_frame)


def test_shifts_missing_columns_error():
    """Test error when required columns are missing"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    missing_resname_file = path_in_test_data(__file__, "test_missing_resname.csv")

    result = run_and_report(
        app, ["shifts", "-i", sequence_file, missing_resname_file], expected_exit_code=1
    )

    assert "missing some required columns: RESNAME" in result.stdout


def test_shifts_empty_file_error():
    """Test error with empty CSV file"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    empty_file = path_in_test_data(__file__, "test_empty.csv")

    result = run_and_report(
        app, ["shifts", "-i", sequence_file, empty_file], expected_exit_code=1
    )

    assert "appears to be empty or not in a valid CSV format" in result.stdout


def test_shifts_invalid_resnum_error():
    """Test error when RESNUM is not an integer"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    invalid_resnum_file = path_in_test_data(__file__, "test_invalid_resnum.csv")

    result = run_and_report(
        app, ["shifts", "-i", sequence_file, invalid_resnum_file], expected_exit_code=1
    )

    assert "RESNUM 'not_a_number'" in result.stdout
    assert "is not a valid integer" in result.stdout


def test_shifts_empty_resname_error():
    """Test error when RESNAME is empty"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    empty_resname_file = path_in_test_data(__file__, "test_empty_resname.csv")

    result = run_and_report(
        app, ["shifts", "-i", sequence_file, empty_resname_file], expected_exit_code=1
    )

    assert "RESNAME is missing or empty" in result.stdout


def test_shifts_invalid_shift_value_error():
    """Test error when shift value is not a number"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    invalid_shift_file = path_in_test_data(__file__, "test_invalid_shift.csv")

    result = run_and_report(
        app, ["shifts", "-i", sequence_file, invalid_shift_file], expected_exit_code=1
    )

    assert "'H_UCBShift' value 'not_a_number'" in result.stdout
    assert "is not a valid number" in result.stdout


EXPECTED_MULTI_FILE_SAME_CHAIN_FILE_1 = """
    save_nef_chemical_shift_list_test_file1_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_file1_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         A   1   MET   H   8.234    .   H   1
         A   1   MET   C   55.678   .   C   13
         A   2   ALA   H   8.123    .   H   1
         A   2   ALA   C   52.456   .   C   13

       stop_

    save_
"""

EXPECTED_MULTI_FILE_SAME_CHAIN_FILE_2 = """
    save_nef_chemical_shift_list_test_file2_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_file2_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         A   3   ILE   H   8.567    .   H   1
         A   3   ILE   C   56.789   .   C   13

       stop_

    save_
"""


def test_shifts_multiple_files_same_chain():
    """Test importing multiple files to the same chain creates separate frames"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    file1 = path_in_test_data(__file__, "test_file1.csv")
    file2 = path_in_test_data(__file__, "test_file2.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--chains", "A,A", file1, file2],
        expected_exit_code=0,
    )

    # Each file should create its own frame
    # Check file1 frame contains complete expected data and nothing from file2
    file1_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file1_ucbshift"
    )
    assert_lines_match(file1_frame, EXPECTED_MULTI_FILE_SAME_CHAIN_FILE_1)

    # Check file2 frame contains complete expected data and nothing from file1
    file2_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file2_ucbshift"
    )
    assert_lines_match(file2_frame, EXPECTED_MULTI_FILE_SAME_CHAIN_FILE_2)


EXPECTED_MULTI_FILE_DIFF_CHAINS_FILE_1 = """
    save_nef_chemical_shift_list_test_file1_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_file1_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         A   1   MET   H   8.234    .   H   1
         A   1   MET   C   55.678   .   C   13
         A   2   ALA   H   8.123    .   H   1
         A   2   ALA   C   52.456   .   C   13

       stop_

    save_
"""

EXPECTED_MULTI_FILE_DIFF_CHAINS_FILE_CHAIN_B = """
    save_nef_chemical_shift_list_test_file_chain_b_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_file_chain_b_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         B   1   MET   H   7.111    .   H   1
         B   1   MET   C   44.444   .   C   13
         B   2   GLN   H   7.222    .   H   1
         B   2   GLN   C   55.555   .   C   13

       stop_

    save_
"""


def test_shifts_multiple_files_different_chains():
    """Test importing multiple files to different chains creates separate frames"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    file1 = path_in_test_data(__file__, "test_file1.csv")
    file_chain_b = path_in_test_data(__file__, "test_file_chain_b.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--chains", "A,B", file1, file_chain_b],
        expected_exit_code=0,
    )

    # Each file creates its own frame with different chain codes
    file1_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file1_ucbshift"
    )
    assert_lines_match(file1_frame, EXPECTED_MULTI_FILE_DIFF_CHAINS_FILE_1)

    file_chain_b_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file_chain_b_ucbshift"
    )
    assert_lines_match(file_chain_b_frame, EXPECTED_MULTI_FILE_DIFF_CHAINS_FILE_CHAIN_B)


EXPECTED_ROUNDING_TEST = """
    save_nef_chemical_shift_list_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         A   1   MET   H   8.235     .   H   1
         A   1   MET   C   55.679    .   C   13
         A   1   MET   N   120.123   .   N   15
         A   2   ALA   H   8.123     .   H   1
         A   2   ALA   C   52.457    .   C   13
         A   2   ALA   N   122.789   .   N   15

       stop_

    save_
"""


def test_shifts_rounding_to_3dp():
    """Test that shift values are rounded to 3 decimal places"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    rounding_file = path_in_test_data(__file__, "test_rounding.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--frame-name", "ucbshift", rounding_file],
        expected_exit_code=0,
    )

    ucbshift_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_ucbshift")
    assert_lines_match(ucbshift_frame, EXPECTED_ROUNDING_TEST)


def test_shifts_isotope_and_element_assignment():
    """Test that isotope numbers and elements are correctly assigned"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    rounding_file = path_in_test_data(__file__, "test_rounding.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--frame-name", "ucbshift", rounding_file],
        expected_exit_code=0,
    )

    ucbshift_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_ucbshift")
    # This test validates the complete frame including isotope and element assignments
    assert_lines_match(ucbshift_frame, EXPECTED_ROUNDING_TEST)


def test_frame_name_template_default():
    """Test default frame name template {file_name}_{shift_type}"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    shifts_file = path_in_test_data(__file__, "test_shifts.csv")

    result = run_and_report(
        app, ["shifts", "-i", sequence_file, shifts_file], expected_exit_code=0
    )

    # Should use default template: {file_name}_{shift_type}
    # file_name = test_shifts, shift_type = ucbshift
    assert "save_nef_chemical_shift_list_test_shifts_ucbshift" in result.stdout
    assert (
        "_nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_shifts_ucbshift"
        in result.stdout
    )


def test_frame_name_template_prediction_type_x():
    """Test frame name template with X prediction type"""

    sequence_file = path_in_test_data(__file__, "test_simple_sequence.nef")
    x_file = path_in_test_data(__file__, "test_x_prediction.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--prediction-type", "x", x_file],
        expected_exit_code=0,
    )

    # Default template with X prediction: {file_name}_{shift_type}
    # file_name = test_x_prediction, shift_type = x
    assert "save_nef_chemical_shift_list_test_x_prediction_x" in result.stdout
    assert (
        "_nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_x_prediction_x"
        in result.stdout
    )


def test_frame_name_template_prediction_type_y():
    """Test frame name template with Y prediction type"""

    sequence_file = path_in_test_data(__file__, "test_simple_sequence.nef")
    y_file = path_in_test_data(__file__, "test_y_prediction.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--prediction-type", "y", y_file],
        expected_exit_code=0,
    )

    # Default template with Y prediction: {file_name}_{shift_type}
    # file_name = test_y_prediction, shift_type = y
    assert "save_nef_chemical_shift_list_test_y_prediction_y" in result.stdout
    assert (
        "_nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_y_prediction_y"
        in result.stdout
    )


def test_frame_name_template_custom():
    """Test custom frame name template"""

    sequence_file = path_in_test_data(__file__, "test_simple_sequence.nef")
    shifts_file = path_in_test_data(__file__, "test_rounding.csv")

    result = run_and_report(
        app,
        [
            "shifts",
            "-i",
            sequence_file,
            "--frame-name",
            "custom_{shift_type}_from_{file_name}",
            shifts_file,
        ],
        expected_exit_code=0,
    )

    # Custom template: custom_{shift_type}_from_{file_name}
    # shift_type = ucbshift, file_name = test_rounding
    assert (
        "save_nef_chemical_shift_list_custom_ucbshift_from_test_rounding"
        in result.stdout
    )
    assert (
        "_nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_custom_ucbshift_from_test_rounding"
        in result.stdout
    )


def test_frame_name_template_static():
    """Test static frame name (no template variables)"""

    sequence_file = path_in_test_data(__file__, "test_simple_sequence.nef")
    shifts_file = path_in_test_data(__file__, "test_rounding.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--frame-name", "my_static_frame", shifts_file],
        expected_exit_code=0,
    )

    # Static frame name
    assert "save_nef_chemical_shift_list_my_static_frame" in result.stdout
    assert (
        "_nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_my_static_frame"
        in result.stdout
    )


def test_frame_name_template_multiple_files():
    """Test frame name template with multiple files creates separate frames with individual file names"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    file1 = path_in_test_data(__file__, "test_file1.csv")
    file2 = path_in_test_data(__file__, "test_file2.csv")

    result = run_and_report(
        app,
        [
            "shifts",
            "-i",
            sequence_file,
            "--frame-name",
            "multi_{file_name}_{shift_type}",
            file1,
            file2,
        ],
        expected_exit_code=0,
    )

    # Each file should create its own frame with its own name
    assert "save_nef_chemical_shift_list_multi_test_file1_ucbshift" in result.stdout
    assert (
        "_nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_multi_test_file1_ucbshift"
        in result.stdout
    )

    assert "save_nef_chemical_shift_list_multi_test_file2_ucbshift" in result.stdout
    assert (
        "_nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_multi_test_file2_ucbshift"
        in result.stdout
    )


def test_shifts_multiple_files_separate_content():
    """Test that multiple files create truly separate frames with isolated content"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    file1 = path_in_test_data(__file__, "test_file1.csv")
    file_chain_b = path_in_test_data(__file__, "test_file_chain_b.csv")

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--chains", "A,B", file1, file_chain_b],
        expected_exit_code=0,
    )

    # Verify complete separation by comparing entire saveframes
    file1_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file1_ucbshift"
    )
    assert_lines_match(file1_frame, EXPECTED_MULTI_FILE_DIFF_CHAINS_FILE_1)

    file_chain_b_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file_chain_b_ucbshift"
    )
    assert_lines_match(file_chain_b_frame, EXPECTED_MULTI_FILE_DIFF_CHAINS_FILE_CHAIN_B)


def test_shifts_no_nef_input_file_creates_default_entry():
    """Test that not providing an input file creates a default 'ucbshift' entry"""

    shifts_file = path_in_test_data(__file__, "test_shifts.csv")

    # Provide empty input via stdin (no -i option)
    result = run_and_report(
        app,
        ["shifts", "--frame-name", "test_frame", shifts_file],
        input="",
        expected_exit_code=0,
    )

    # Should create entry with name 'ucbshift'
    assert "data_ucbshift" in result.stdout

    # Should contain the shifts frame
    assert "save_nef_chemical_shift_list_test_frame" in result.stdout

    # Should contain the nmr metadata frame
    assert "save_nef_nmr_meta_data" in result.stdout


EXPECTED_CHAIN_CODES_FEWER_FILE_1 = """
    save_nef_chemical_shift_list_test_file1_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_file1_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         A   1   MET   H   8.234    .   H   1
         A   1   MET   C   55.678   .   C   13
         A   2   ALA   H   8.123    .   H   1
         A   2   ALA   C   52.456   .   C   13

       stop_

    save_
"""

EXPECTED_CHAIN_CODES_FEWER_FILE_2 = """
    save_nef_chemical_shift_list_test_file2_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_file2_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         B   3   ILE   H   8.567    .   H   1
         B   3   ILE   C   56.789   .   C   13

       stop_

    save_
"""


def test_shifts_chain_codes_fewer_than_files():
    """Test providing fewer chain codes than files uses iterator to fill missing codes"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    file1 = path_in_test_data(__file__, "test_file1.csv")
    file2 = path_in_test_data(__file__, "test_file2.csv")

    # Only provide one chain code for two files
    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--chains", "A", file1, file2],
        expected_exit_code=0,
    )

    # First file should get A, second file should get B (from iterator)
    file1_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file1_ucbshift"
    )
    assert_lines_match(file1_frame, EXPECTED_CHAIN_CODES_FEWER_FILE_1)

    file2_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file2_ucbshift"
    )
    assert_lines_match(file2_frame, EXPECTED_CHAIN_CODES_FEWER_FILE_2)


def test_shifts_frame_name_template_invalid_variable():
    """Test frame name template with invalid variable provides helpful error message"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    shifts_file = path_in_test_data(__file__, "test_shifts.csv")

    # Use invalid template variable - should fail with helpful error
    result = run_and_report(
        app,
        [
            "shifts",
            "-i",
            sequence_file,
            "--frame-name",
            "frame_{invalid_var}",
            shifts_file,
        ],
        expected_exit_code=1,
    )

    # Should fail with helpful error message showing invalid variable and available ones
    assert "invalid template variable 'invalid_var'" in result.stdout
    assert "frame_{invalid_var}" in result.stdout  # Shows the template
    assert "Available variables are:" in result.stdout
    assert "file_name" in result.stdout  # Shows available variables
    assert "shift_type" in result.stdout


EXPECTED_OVERLAPPING_FILE_1 = """
    save_nef_chemical_shift_list_test_file1_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_file1_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         A   1   MET   H   8.234    .   H   1
         A   1   MET   C   55.678   .   C   13
         A   2   ALA   H   8.123    .   H   1
         A   2   ALA   C   52.456   .   C   13

       stop_

    save_
"""

EXPECTED_OVERLAPPING_CONFLICTING = """
    save_nef_chemical_shift_list_test_conflicting_file_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_conflicting_file_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

         A   1   MET   H   8.999    .   H   1
         A   1   MET   C   44.111   .   C   13
         A   2   ALA   H   7.888    .   H   1
         A   2   ALA   C   33.222   .   C   13

       stop_

    save_
"""


def test_shifts_overlapping_residues_same_chain():
    """Test multiple files with overlapping residue numbers in same chain"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    file1 = path_in_test_data(__file__, "test_file1.csv")  # has residues 1,2
    conflicting_file = path_in_test_data(
        __file__, "test_conflicting_file.csv"
    )  # also has residues 1,2

    result = run_and_report(
        app,
        ["shifts", "-i", sequence_file, "--chains", "A,A", file1, conflicting_file],
        expected_exit_code=0,
    )

    # Each file should create its own frame, so overlapping residues are OK
    file1_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_file1_ucbshift"
    )
    assert_lines_match(file1_frame, EXPECTED_OVERLAPPING_FILE_1)

    conflicting_frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_conflicting_file_ucbshift"
    )
    assert_lines_match(conflicting_frame, EXPECTED_OVERLAPPING_CONFLICTING)


EXPECTED_NO_VALID_SHIFTS = """
    save_nef_chemical_shift_list_test_no_shifts_ucbshift
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_test_no_shifts_ucbshift

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty
          _nef_chemical_shift.element
          _nef_chemical_shift.isotope_number

       stop_

    save_
"""


def test_shifts_no_valid_shifts_in_file():
    """Test file that has valid structure but no actual shift data"""

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    no_shifts_file = path_in_test_data(__file__, "test_no_shifts.csv")

    result = run_and_report(
        app, ["shifts", "-i", sequence_file, no_shifts_file], expected_exit_code=0
    )

    # Should create frame but with no shift data - validate complete empty frame
    frame = isolate_frame(
        result.stdout, "nef_chemical_shift_list_test_no_shifts_ucbshift"
    )
    assert_lines_match(frame, EXPECTED_NO_VALID_SHIFTS)
