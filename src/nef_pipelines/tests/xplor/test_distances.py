import typer

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.xplor.importers.distances import distances

app = typer.Typer()
app.command()(distances)


# noinspection PyUnusedLocal
def test_2_distances():
    sequence_path = path_in_test_data(__file__, "3a_ab.neff")
    dihedrals_path = path_in_test_data(__file__, "test_2_distances.tbl")

    with open(sequence_path, "r") as fh:
        nef_sequence = fh.read()

    args = [dihedrals_path]
    result = run_and_report(app, args, input=nef_sequence)

    EXPECTED = """\
        save_nef_distance_restraint_list_test_2_distances                               # noqa: E501
            _nef_distance_restraint_list.sf_category     nef_distance_restraint_list
            _nef_distance_restraint_list.sf_framecode    nef_distance_restraint_list_test_2_distances
            _nef_distance_restraint_list.potential_type  undefined

            loop_
                _nef_distance_restraint.index
                _nef_distance_restraint.restraint_id
                _nef_distance_restraint.restraint_combination_id
                _nef_distance_restraint.chain_code_1
                _nef_distance_restraint.sequence_code_1
                _nef_distance_restraint.residue_name_1
                _nef_distance_restraint.atom_name_1
                _nef_distance_restraint.chain_code_2
                _nef_distance_restraint.sequence_code_2
                _nef_distance_restraint.residue_name_2
                _nef_distance_restraint.atom_name_2
                _nef_distance_restraint.weight
                _nef_distance_restraint.target_value
                _nef_distance_restraint.lower_limit
                _nef_distance_restraint.upper_limit
                1   1   .   AAAA   1   .   HN   AAAA   2   .   HDA#   1.0   2.6   0.6   5.6
                2   2   .   AAAA   2   .   HN   AAAA   3   .   HD1#   1.0   4.5   1.5   6.2

           stop_
        save_
    """.replace(
        NOQA_E501, ""
    )

    result = isolate_frame(
        result.stdout, "nef_distance_restraint_list_test_2_distances"
    )

    assert_lines_match(EXPECTED, result)


def test_2_distances_bad():
    sequence_path = path_in_test_data(__file__, "3a_ab.neff")
    distances_path = path_in_test_data(__file__, "test_2_distances_bad.tbl")

    with open(sequence_path, "r") as fh:
        nef_sequence = fh.read()

    args = [distances_path]
    result = run_and_report(app, args, input=nef_sequence, expected_exit_code=1)

    assert "ERROR" in result.stdout
    assert "failed to read distance restraints" in result.stdout


def test_2_dihstances_no_segids():
    sequence_path = path_in_test_data(__file__, "3a_ab.neff")
    distances_path = path_in_test_data(__file__, "test_2_distances_no_segids.tbl")

    with open(sequence_path, "r") as fh:
        nef_sequence = fh.read()

    args = [distances_path, "--chains", "AAAA"]
    result = run_and_report(app, args, input=nef_sequence)

    EXPECTED = """\
        save_nef_distance_restraint_list_test_2_distances_no_segids                               # noqa: E501
            _nef_distance_restraint_list.sf_category     nef_distance_restraint_list
            _nef_distance_restraint_list.sf_framecode    nef_distance_restraint_list_test_2_distances_no_segids
            _nef_distance_restraint_list.potential_type  undefined

            loop_
                _nef_distance_restraint.index
                _nef_distance_restraint.restraint_id
                _nef_distance_restraint.restraint_combination_id
                _nef_distance_restraint.chain_code_1
                _nef_distance_restraint.sequence_code_1
                _nef_distance_restraint.residue_name_1
                _nef_distance_restraint.atom_name_1
                _nef_distance_restraint.chain_code_2
                _nef_distance_restraint.sequence_code_2
                _nef_distance_restraint.residue_name_2
                _nef_distance_restraint.atom_name_2
                _nef_distance_restraint.weight
                _nef_distance_restraint.target_value
                _nef_distance_restraint.lower_limit
                _nef_distance_restraint.upper_limit
                1   1   .   AAAA   1   .   HN   AAAA   2   .   HDA#   1.0   2.6   0.6   5.6
                2   2   .   AAAA   2   .   HN   AAAA   3   .   HD1#   1.0   4.5   1.5   6.2

           stop_
        save_
    """.replace(
        NOQA_E501, ""
    )

    result = isolate_frame(
        result.stdout, "nef_distance_restraint_list_test_2_distances_no_segids"
    )

    assert_lines_match(EXPECTED, result)


def test_2_distances_overriding_segids():
    sequence_path = path_in_test_data(__file__, "3a_ab.neff")
    distances_path = path_in_test_data(__file__, "test_2_distances.tbl")

    with open(sequence_path, "r") as fh:
        nef_sequence = fh.read()

    args = [distances_path, "--chains", "BBBB", "--use-chains"]
    result = run_and_report(app, args, input=nef_sequence)

    EXPECTED = """\
        save_nef_distance_restraint_list_test_2_distances                               # noqa: E501
            _nef_distance_restraint_list.sf_category     nef_distance_restraint_list
            _nef_distance_restraint_list.sf_framecode    nef_distance_restraint_list_test_2_distances
            _nef_distance_restraint_list.potential_type  undefined

            loop_
                _nef_distance_restraint.index
                _nef_distance_restraint.restraint_id
                _nef_distance_restraint.restraint_combination_id
                _nef_distance_restraint.chain_code_1
                _nef_distance_restraint.sequence_code_1
                _nef_distance_restraint.residue_name_1
                _nef_distance_restraint.atom_name_1
                _nef_distance_restraint.chain_code_2
                _nef_distance_restraint.sequence_code_2
                _nef_distance_restraint.residue_name_2
                _nef_distance_restraint.atom_name_2
                _nef_distance_restraint.weight
                _nef_distance_restraint.target_value
                _nef_distance_restraint.lower_limit
                _nef_distance_restraint.upper_limit
                1   1   .   BBBB   1   .   HN   BBBB   2   .   HDA#   1.0   2.6   0.6   5.6
                2   2   .   BBBB   2   .   HN   BBBB   3   .   HD1#   1.0   4.5   1.5   6.2

           stop_
        save_
    """.replace(
        NOQA_E501, ""
    )

    result = isolate_frame(
        result.stdout, "nef_distance_restraint_list_test_2_distances"
    )

    assert_lines_match(EXPECTED, result)
