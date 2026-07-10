import typer
from pytest import fixture

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.csv.importers.rdcs import rdcs

app = typer.Typer()
app.command()(rdcs)


@fixture
def INPUT_3A_AB_NEF():
    return read_test_data("3a_ab.neff", __file__)


# noinspection PyUnusedLocal
def test_short_csv(INPUT_3A_AB_NEF):
    csv_path = path_in_test_data(__file__, "short.csv")

    args = [csv_path, "--chain-code", "AAAA"]
    result = run_and_report(app, args, input=INPUT_3A_AB_NEF)

    EXPECTED = """\
        save_nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.sf_category           nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode          nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.restraint_origin      .
           _nef_rdc_restraint_list.tensor_magnitude      .
           _nef_rdc_restraint_list.tensor_rhombicity     .
           _nef_rdc_restraint_list.tensor_chain_code     .
           _nef_rdc_restraint_list.tensor_sequence_code  .
           _nef_rdc_restraint_list.tensor_residue_name   .

           loop_
              _nef_rdc_restraint.index
              _nef_rdc_restraint.restraint_id
              _nef_rdc_restraint.restraint_combination_id
              _nef_rdc_restraint.chain_code_1
              _nef_rdc_restraint.sequence_code_1
              _nef_rdc_restraint.residue_name_1
              _nef_rdc_restraint.atom_name_1
              _nef_rdc_restraint.chain_code_2
              _nef_rdc_restraint.sequence_code_2
              _nef_rdc_restraint.residue_name_2
              _nef_rdc_restraint.atom_name_2
              _nef_rdc_restraint.weight
              _nef_rdc_restraint.target_value
              _nef_rdc_restraint.target_value_uncertainty
              _nef_rdc_restraint.lower_linear_limit
              _nef_rdc_restraint.lower_limit
              _nef_rdc_restraint.upper_limit
              _nef_rdc_restraint.upper_linear_limit
              _nef_rdc_restraint.scale
              _nef_rdc_restraint.distance_dependent

             0   0   .   AAAA   1   ALA   H   AAAA   1   ALA   N   1.0   1.3   .   .   .   .   .   1.0   .
             1   1   .   AAAA   2   ALA   H   AAAA   2   ALA   N   1.0   4.6   .   .   .   .   .   1.0   .
             2   2   .   AAAA   3   ALA   H   AAAA   3   ALA   N   1.0   2.4   .   .   .   .   .   1.0   .

           stop_

        save_

    """

    print(result.stdout)
    result = isolate_frame(result.stdout, "nef_rdc_restraint_list_rdcs")

    assert_lines_match(EXPECTED, result)


def test_short_complete_csv(INPUT_3A_AB_NEF):
    csv_path = path_in_test_data(__file__, "short_complete.csv")

    args = [csv_path]
    result = run_and_report(app, args, input=INPUT_3A_AB_NEF)

    EXPECTED = """\
        save_nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.sf_category           nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode          nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.restraint_origin      .
           _nef_rdc_restraint_list.tensor_magnitude      .
           _nef_rdc_restraint_list.tensor_rhombicity     .
           _nef_rdc_restraint_list.tensor_chain_code     .
           _nef_rdc_restraint_list.tensor_sequence_code  .
           _nef_rdc_restraint_list.tensor_residue_name   .

           loop_
              _nef_rdc_restraint.index
              _nef_rdc_restraint.restraint_id
              _nef_rdc_restraint.restraint_combination_id
              _nef_rdc_restraint.chain_code_1
              _nef_rdc_restraint.sequence_code_1
              _nef_rdc_restraint.residue_name_1
              _nef_rdc_restraint.atom_name_1
              _nef_rdc_restraint.chain_code_2
              _nef_rdc_restraint.sequence_code_2
              _nef_rdc_restraint.residue_name_2
              _nef_rdc_restraint.atom_name_2
              _nef_rdc_restraint.weight
              _nef_rdc_restraint.target_value
              _nef_rdc_restraint.target_value_uncertainty
              _nef_rdc_restraint.lower_linear_limit
              _nef_rdc_restraint.lower_limit
              _nef_rdc_restraint.upper_limit
              _nef_rdc_restraint.upper_linear_limit
              _nef_rdc_restraint.scale
              _nef_rdc_restraint.distance_dependent

             0   0   .   AAAA   1   ALA   HA     AAAA   1   ALA   HN   1.0   1.3   1.0   .   .   .   .   1.0   .
             1   1   .   AAAA   1   ALA   HB     AAAA   1   ALA   HN   1.0   4.6   2.0   .   .   .   .   1.0   .
             2   2   .   AAAA   2   ALA   HG3#   AAAA   2   ALA   HN   1.0   2.4   3.0   .   .   .   .   1.0   .
             3   3   .   AAAA   3   ALA   HA     AAAA   3   ALA   HN   1.0   6.7   4.0   .   .   .   .   1.0   .

           stop_

        save_

    """

    result = isolate_frame(result.stdout, "nef_rdc_restraint_list_rdcs")

    assert_lines_match(EXPECTED, result)


def test_unknown_residue_warning(INPUT_3A_AB_NEF):
    """Test that unknown residues are handled gracefully with warnings."""
    csv_path = path_in_test_data(__file__, "short_with_unknown.csv")

    args = [csv_path, "--chain-code", "AAAA"]
    result = run_and_report(app, args, input=INPUT_3A_AB_NEF, merge_stderr=False)

    # Unknown residue 99 should have residue_name set to '.'
    EXPECTED_FRAME = """\
        save_nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.sf_category           nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode          nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.restraint_origin      .
           _nef_rdc_restraint_list.tensor_magnitude      .
           _nef_rdc_restraint_list.tensor_rhombicity     .
           _nef_rdc_restraint_list.tensor_chain_code     .
           _nef_rdc_restraint_list.tensor_sequence_code  .
           _nef_rdc_restraint_list.tensor_residue_name   .

           loop_
              _nef_rdc_restraint.index
              _nef_rdc_restraint.restraint_id
              _nef_rdc_restraint.restraint_combination_id
              _nef_rdc_restraint.chain_code_1
              _nef_rdc_restraint.sequence_code_1
              _nef_rdc_restraint.residue_name_1
              _nef_rdc_restraint.atom_name_1
              _nef_rdc_restraint.chain_code_2
              _nef_rdc_restraint.sequence_code_2
              _nef_rdc_restraint.residue_name_2
              _nef_rdc_restraint.atom_name_2
              _nef_rdc_restraint.weight
              _nef_rdc_restraint.target_value
              _nef_rdc_restraint.target_value_uncertainty
              _nef_rdc_restraint.lower_linear_limit
              _nef_rdc_restraint.lower_limit
              _nef_rdc_restraint.upper_limit
              _nef_rdc_restraint.upper_linear_limit
              _nef_rdc_restraint.scale
              _nef_rdc_restraint.distance_dependent

             0   0   .   AAAA   1    ALA   H   AAAA   1    ALA   N   1.0   1.3   .   .   .   .   .   1.0   .
             1   1   .   AAAA   2    ALA   H   AAAA   2    ALA   N   1.0   4.6   .   .   .   .   .   1.0   .
             2   2   .   AAAA   99   .     H   AAAA   99   .     N   1.0   2.4   .   .   .   .   .   1.0   .

           stop_

        save_

    """

    result_frame = isolate_frame(result.stdout, "nef_rdc_restraint_list_rdcs")
    assert_lines_match(EXPECTED_FRAME, result_frame)

    # Should have warning about unknown residue including compact sequence display
    EXPECTED_WARNING = """\
        WARNING: The following residues were not found in the input sequence
        and have been imported with residue_name set to '.' (UNUSED):

        The missing residues were:

        chain AAAA
        99

        The Sequences were:

        chain AAAA
        1 ALA    2 ALA    3 ALA

        chain BBBB
        11 ALA   12 ALA   13 ALA
    """
    assert_lines_match(EXPECTED_WARNING, result.stderr)


def test_many_unknown_residues_compact_format(INPUT_3A_AB_NEF):
    """Test compact formatting with many unknown residues."""
    csv_path = path_in_test_data(__file__, "many_unknown.csv")

    args = [csv_path, "--chain-code", "AAAA"]
    result = run_and_report(app, args, input=INPUT_3A_AB_NEF, merge_stderr=False)

    # Verify complete NEF output - should show residue_name = '.' for all unknown residues
    EXPECTED_FRAME = """\
        save_nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.sf_category           nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode          nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.restraint_origin      .
           _nef_rdc_restraint_list.tensor_magnitude      .
           _nef_rdc_restraint_list.tensor_rhombicity     .
           _nef_rdc_restraint_list.tensor_chain_code     .
           _nef_rdc_restraint_list.tensor_sequence_code  .
           _nef_rdc_restraint_list.tensor_residue_name   .

           loop_
              _nef_rdc_restraint.index
              _nef_rdc_restraint.restraint_id
              _nef_rdc_restraint.restraint_combination_id
              _nef_rdc_restraint.chain_code_1
              _nef_rdc_restraint.sequence_code_1
              _nef_rdc_restraint.residue_name_1
              _nef_rdc_restraint.atom_name_1
              _nef_rdc_restraint.chain_code_2
              _nef_rdc_restraint.sequence_code_2
              _nef_rdc_restraint.residue_name_2
              _nef_rdc_restraint.atom_name_2
              _nef_rdc_restraint.weight
              _nef_rdc_restraint.target_value
              _nef_rdc_restraint.target_value_uncertainty
              _nef_rdc_restraint.lower_linear_limit
              _nef_rdc_restraint.lower_limit
              _nef_rdc_restraint.upper_limit
              _nef_rdc_restraint.upper_linear_limit
              _nef_rdc_restraint.scale
              _nef_rdc_restraint.distance_dependent

             0    0   .   AAAA   1    ALA   H   AAAA   1    ALA   N   1.0   1.3   .   .   .   .   .   1.0   .
             1    1   .   AAAA   2    ALA   H   AAAA   2    ALA   N   1.0   4.6   .   .   .   .   .   1.0   .
             2    2   .   AAAA   50   .     H   AAAA   50   .     N   1.0   2.1   .   .   .   .   .   1.0   .
             3    3   .   AAAA   51   .     H   AAAA   51   .     N   1.0   3.2   .   .   .   .   .   1.0   .
             4    4   .   AAAA   52   .     H   AAAA   52   .     N   1.0   4.3   .   .   .   .   .   1.0   .
             5    5   .   AAAA   53   .     H   AAAA   53   .     N   1.0   5.4   .   .   .   .   .   1.0   .
             6    6   .   AAAA   54   .     H   AAAA   54   .     N   1.0   6.5   .   .   .   .   .   1.0   .
             7    7   .   AAAA   55   .     H   AAAA   55   .     N   1.0   7.6   .   .   .   .   .   1.0   .
             8    8   .   AAAA   56   .     H   AAAA   56   .     N   1.0   8.7   .   .   .   .   .   1.0   .
             9    9   .   AAAA   57   .     H   AAAA   57   .     N   1.0   9.8   .   .   .   .   .   1.0   .
             10   10  .   AAAA   58   .     H   AAAA   58   .     N   1.0   10.9  .   .   .   .   .   1.0   .
             11   11  .   AAAA   59   .     H   AAAA   59   .     N   1.0   11.0  .   .   .   .   .   1.0   .
             12   12  .   AAAA   60   .     H   AAAA   60   .     N   1.0   12.1  .   .   .   .   .   1.0   .
             13   13  .   AAAA   61   .     H   AAAA   61   .     N   1.0   13.2  .   .   .   .   .   1.0   .
             14   14  .   AAAA   62   .     H   AAAA   62   .     N   1.0   14.3  .   .   .   .   .   1.0   .
             15   15  .   AAAA   63   .     H   AAAA   63   .     N   1.0   15.4  .   .   .   .   .   1.0   .
             16   16  .   AAAA   64   .     H   AAAA   64   .     N   1.0   16.5  .   .   .   .   .   1.0   .
             17   17  .   AAAA   65   .     H   AAAA   65   .     N   1.0   17.6  .   .   .   .   .   1.0   .
             18   18  .   AAAA   66   .     H   AAAA   66   .     N   1.0   18.7  .   .   .   .   .   1.0   .
             19   19  .   AAAA   67   .     H   AAAA   67   .     N   1.0   19.8  .   .   .   .   .   1.0   .
             20   20  .   AAAA   68   .     H   AAAA   68   .     N   1.0   20.9  .   .   .   .   .   1.0   .
             21   21  .   AAAA   69   .     H   AAAA   69   .     N   1.0   21.0  .   .   .   .   .   1.0   .
             22   22  .   AAAA   70   .     H   AAAA   70   .     N   1.0   22.1  .   .   .   .   .   1.0   .

           stop_

        save_

    """

    result_frame = isolate_frame(result.stdout, "nef_rdc_restraint_list_rdcs")
    assert_lines_match(EXPECTED_FRAME, result_frame)

    # Verify warning shows compact format with overflow
    EXPECTED_WARNING = """\
        WARNING: The following residues were not found in the input sequence
        and have been imported with residue_name set to '.' (UNUSED):

        The missing residues were:

        chain AAAA
        50    51    52    53    54    55    56    57    58    59
        60    61    62    63    64    65    66    67    68    69
        ... and 1 more

        [total of 1 more residues not shown above]

        The Sequences were:

        chain AAAA
        1 ALA    2 ALA    3 ALA

        chain BBBB
        11 ALA   12 ALA   13 ALA
    """
    assert_lines_match(EXPECTED_WARNING, result.stderr)


def test_two_chains_all_missing(INPUT_3A_AB_NEF):
    """Test formatting with 2 chains of 20 residues each, all missing (40 total)."""
    csv_path = path_in_test_data(__file__, "two_chains_all_missing.csv")

    args = [csv_path]
    result = run_and_report(app, args, input=INPUT_3A_AB_NEF, merge_stderr=False)

    # Verify complete NEF output with all 40 entries showing residue_name = '.'
    result_frame = isolate_frame(result.stdout, "nef_rdc_restraint_list_rdcs")

    EXPECTED_FRAME = """\
        save_nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.sf_category           nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode          nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.restraint_origin      .
           _nef_rdc_restraint_list.tensor_magnitude      .
           _nef_rdc_restraint_list.tensor_rhombicity     .
           _nef_rdc_restraint_list.tensor_chain_code     .
           _nef_rdc_restraint_list.tensor_sequence_code  .
           _nef_rdc_restraint_list.tensor_residue_name   .

           loop_
              _nef_rdc_restraint.index
              _nef_rdc_restraint.restraint_id
              _nef_rdc_restraint.restraint_combination_id
              _nef_rdc_restraint.chain_code_1
              _nef_rdc_restraint.sequence_code_1
              _nef_rdc_restraint.residue_name_1
              _nef_rdc_restraint.atom_name_1
              _nef_rdc_restraint.chain_code_2
              _nef_rdc_restraint.sequence_code_2
              _nef_rdc_restraint.residue_name_2
              _nef_rdc_restraint.atom_name_2
              _nef_rdc_restraint.weight
              _nef_rdc_restraint.target_value
              _nef_rdc_restraint.target_value_uncertainty
              _nef_rdc_restraint.lower_linear_limit
              _nef_rdc_restraint.lower_limit
              _nef_rdc_restraint.upper_limit
              _nef_rdc_restraint.upper_linear_limit
              _nef_rdc_restraint.scale
              _nef_rdc_restraint.distance_dependent

             0    0   .   AAAA   100   .   H   AAAA   100   .   N   1.0   1.1   .   .   .   .   .   1.0   .
             1    1   .   AAAA   101   .   H   AAAA   101   .   N   1.0   1.2   .   .   .   .   .   1.0   .
             2    2   .   AAAA   102   .   H   AAAA   102   .   N   1.0   1.3   .   .   .   .   .   1.0   .
             3    3   .   AAAA   103   .   H   AAAA   103   .   N   1.0   1.4   .   .   .   .   .   1.0   .
             4    4   .   AAAA   104   .   H   AAAA   104   .   N   1.0   1.5   .   .   .   .   .   1.0   .
             5    5   .   AAAA   105   .   H   AAAA   105   .   N   1.0   1.6   .   .   .   .   .   1.0   .
             6    6   .   AAAA   106   .   H   AAAA   106   .   N   1.0   1.7   .   .   .   .   .   1.0   .
             7    7   .   AAAA   107   .   H   AAAA   107   .   N   1.0   1.8   .   .   .   .   .   1.0   .
             8    8   .   AAAA   108   .   H   AAAA   108   .   N   1.0   1.9   .   .   .   .   .   1.0   .
             9    9   .   AAAA   109   .   H   AAAA   109   .   N   1.0   2.0   .   .   .   .   .   1.0   .
             10   10  .   AAAA   110   .   H   AAAA   110   .   N   1.0   2.1   .   .   .   .   .   1.0   .
             11   11  .   AAAA   111   .   H   AAAA   111   .   N   1.0   2.2   .   .   .   .   .   1.0   .
             12   12  .   AAAA   112   .   H   AAAA   112   .   N   1.0   2.3   .   .   .   .   .   1.0   .
             13   13  .   AAAA   113   .   H   AAAA   113   .   N   1.0   2.4   .   .   .   .   .   1.0   .
             14   14  .   AAAA   114   .   H   AAAA   114   .   N   1.0   2.5   .   .   .   .   .   1.0   .
             15   15  .   AAAA   115   .   H   AAAA   115   .   N   1.0   2.6   .   .   .   .   .   1.0   .
             16   16  .   AAAA   116   .   H   AAAA   116   .   N   1.0   2.7   .   .   .   .   .   1.0   .
             17   17  .   AAAA   117   .   H   AAAA   117   .   N   1.0   2.8   .   .   .   .   .   1.0   .
             18   18  .   AAAA   118   .   H   AAAA   118   .   N   1.0   2.9   .   .   .   .   .   1.0   .
             19   19  .   AAAA   119   .   H   AAAA   119   .   N   1.0   3.0   .   .   .   .   .   1.0   .
             20   20  .   CCCC   100   .   H   CCCC   100   .   N   1.0   3.1   .   .   .   .   .   1.0   .
             21   21  .   CCCC   101   .   H   CCCC   101   .   N   1.0   3.2   .   .   .   .   .   1.0   .
             22   22  .   CCCC   102   .   H   CCCC   102   .   N   1.0   3.3   .   .   .   .   .   1.0   .
             23   23  .   CCCC   103   .   H   CCCC   103   .   N   1.0   3.4   .   .   .   .   .   1.0   .
             24   24  .   CCCC   104   .   H   CCCC   104   .   N   1.0   3.5   .   .   .   .   .   1.0   .
             25   25  .   CCCC   105   .   H   CCCC   105   .   N   1.0   3.6   .   .   .   .   .   1.0   .
             26   26  .   CCCC   106   .   H   CCCC   106   .   N   1.0   3.7   .   .   .   .   .   1.0   .
             27   27  .   CCCC   107   .   H   CCCC   107   .   N   1.0   3.8   .   .   .   .   .   1.0   .
             28   28  .   CCCC   108   .   H   CCCC   108   .   N   1.0   3.9   .   .   .   .   .   1.0   .
             29   29  .   CCCC   109   .   H   CCCC   109   .   N   1.0   4.0   .   .   .   .   .   1.0   .
             30   30  .   CCCC   110   .   H   CCCC   110   .   N   1.0   4.1   .   .   .   .   .   1.0   .
             31   31  .   CCCC   111   .   H   CCCC   111   .   N   1.0   4.2   .   .   .   .   .   1.0   .
             32   32  .   CCCC   112   .   H   CCCC   112   .   N   1.0   4.3   .   .   .   .   .   1.0   .
             33   33  .   CCCC   113   .   H   CCCC   113   .   N   1.0   4.4   .   .   .   .   .   1.0   .
             34   34  .   CCCC   114   .   H   CCCC   114   .   N   1.0   4.5   .   .   .   .   .   1.0   .
             35   35  .   CCCC   115   .   H   CCCC   115   .   N   1.0   4.6   .   .   .   .   .   1.0   .
             36   36  .   CCCC   116   .   H   CCCC   116   .   N   1.0   4.7   .   .   .   .   .   1.0   .
             37   37  .   CCCC   117   .   H   CCCC   117   .   N   1.0   4.8   .   .   .   .   .   1.0   .
             38   38  .   CCCC   118   .   H   CCCC   118   .   N   1.0   4.9   .   .   .   .   .   1.0   .
             39   39  .   CCCC   119   .   H   CCCC   119   .   N   1.0   5.0   .   .   .   .   .   1.0   .

           stop_

        save_

    """
    assert_lines_match(EXPECTED_FRAME, result_frame)

    # Verify warning shows both chains with 20 residues each
    EXPECTED_WARNING = """\
        WARNING: The following residues were not found in the input sequence
        and have been imported with residue_name set to '.' (UNUSED):

        The missing residues were:

        chain AAAA
        100   101   102   103   104   105   106   107   108   109
        110   111   112   113   114   115   116   117   118   119

        chain CCCC
        100   101   102   103   104   105   106   107   108   109
        110   111   112   113   114   115   116   117   118   119

        The Sequences were:

        chain AAAA
        1 ALA    2 ALA    3 ALA

        chain BBBB
        11 ALA   12 ALA   13 ALA
    """
    assert_lines_match(EXPECTED_WARNING, result.stderr)


def test_edge_case_sequence_numbers(INPUT_3A_AB_NEF):
    """Test formatting with negative, zero, and large (3-4 digit) sequence numbers."""
    csv_path = path_in_test_data(__file__, "edge_case_sequences.csv")

    args = [csv_path]
    result = run_and_report(app, args, input=INPUT_3A_AB_NEF, merge_stderr=False)

    # Verify complete NEF output handles edge case sequence numbers
    EXPECTED_FRAME = """\
        save_nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.sf_category           nef_rdc_restraint_list
           _nef_rdc_restraint_list.sf_framecode          nef_rdc_restraint_list_rdcs
           _nef_rdc_restraint_list.restraint_origin      .
           _nef_rdc_restraint_list.tensor_magnitude      .
           _nef_rdc_restraint_list.tensor_rhombicity     .
           _nef_rdc_restraint_list.tensor_chain_code     .
           _nef_rdc_restraint_list.tensor_sequence_code  .
           _nef_rdc_restraint_list.tensor_residue_name   .

           loop_
              _nef_rdc_restraint.index
              _nef_rdc_restraint.restraint_id
              _nef_rdc_restraint.restraint_combination_id
              _nef_rdc_restraint.chain_code_1
              _nef_rdc_restraint.sequence_code_1
              _nef_rdc_restraint.residue_name_1
              _nef_rdc_restraint.atom_name_1
              _nef_rdc_restraint.chain_code_2
              _nef_rdc_restraint.sequence_code_2
              _nef_rdc_restraint.residue_name_2
              _nef_rdc_restraint.atom_name_2
              _nef_rdc_restraint.weight
              _nef_rdc_restraint.target_value
              _nef_rdc_restraint.target_value_uncertainty
              _nef_rdc_restraint.lower_linear_limit
              _nef_rdc_restraint.lower_limit
              _nef_rdc_restraint.upper_limit
              _nef_rdc_restraint.upper_linear_limit
              _nef_rdc_restraint.scale
              _nef_rdc_restraint.distance_dependent

             0   0   .   AAAA   -5     .   H   AAAA   -5     .   N   1.0   1.1   .   .   .   .   .   1.0   .
             1   1   .   AAAA   -4     .   H   AAAA   -4     .   N   1.0   1.2   .   .   .   .   .   1.0   .
             2   2   .   AAAA   0      .   H   AAAA   0      .   N   1.0   1.5   .   .   .   .   .   1.0   .
             3   3   .   AAAA   999    .   H   AAAA   999    .   N   1.0   2.1   .   .   .   .   .   1.0   .
             4   4   .   AAAA   1000   .   H   AAAA   1000   .   N   1.0   2.2   .   .   .   .   .   1.0   .

           stop_

        save_

    """

    result_frame = isolate_frame(result.stdout, "nef_rdc_restraint_list_rdcs")
    assert_lines_match(EXPECTED_FRAME, result_frame)

    # Verify warning shows proper right-alignment for edge cases
    EXPECTED_WARNING = """\
        WARNING: The following residues were not found in the input sequence
        and have been imported with residue_name set to '.' (UNUSED):

        The missing residues were:

        chain AAAA
        -5    -4     0   999  1000

        The Sequences were:

        chain AAAA
        1 ALA    2 ALA    3 ALA

        chain BBBB
        11 ALA   12 ALA   13 ALA
    """
    assert_lines_match(EXPECTED_WARNING, result.stderr)
