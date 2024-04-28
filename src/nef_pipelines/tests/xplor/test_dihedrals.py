import typer

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.xplor.importers.dihedrals import dihedrals

app = typer.Typer()
app.command()(dihedrals)


# noinspection PyUnusedLocal
def test_2_dihedrals():
    sequence_path = path_in_test_data(__file__, "3a_ab.neff")
    dihedrals_path = path_in_test_data(__file__, "test_2_dihedrals.tbl")

    with open(sequence_path, "r") as fh:
        nef_sequence = fh.read()

    args = [dihedrals_path]
    result = run_and_report(app, args, input=nef_sequence)

    EXPECTED = """\
        save_nef_dihedral_restraint_list_test_2_dihedrals                               # noqa: E501
            _nef_dihedral_restraint_list.sf_category     nef_dihedral_restraint_list
            _nef_dihedral_restraint_list.sf_framecode    nef_dihedral_restraint_list_test_2_dihedrals
            _nef_dihedral_restraint_list.potential_type  undefined

            loop_
                _nef_dihedral_restraint.index
                _nef_dihedral_restraint.restraint_id
                _nef_dihedral_restraint.restraint_combination_id
                _nef_dihedral_restraint.chain_code_1
                _nef_dihedral_restraint.sequence_code_1
                _nef_dihedral_restraint.residue_name_1
                _nef_dihedral_restraint.atom_name_1
                _nef_dihedral_restraint.chain_code_2
                _nef_dihedral_restraint.sequence_code_2
                _nef_dihedral_restraint.residue_name_2
                _nef_dihedral_restraint.atom_name_2
                _nef_dihedral_restraint.chain_code_3
                _nef_dihedral_restraint.sequence_code_3
                _nef_dihedral_restraint.residue_name_3
                _nef_dihedral_restraint.atom_name_3
                _nef_dihedral_restraint.chain_code_4
                _nef_dihedral_restraint.sequence_code_4
                _nef_dihedral_restraint.residue_name_4
                _nef_dihedral_restraint.atom_name_4
                _nef_dihedral_restraint.weight
                _nef_dihedral_restraint.target_value
                _nef_dihedral_restraint.lower_limit
                _nef_dihedral_restraint.upper_limit

                1   1   .   AAAA   1   .   C   AAAA   2   .   N    AAAA   2   .   CA   AAAA   2   .   C   1.0   -45.7   -166.2   74.8
                2   2   .   AAAA   2   .   N   AAAA   2   .   CA   AAAA   2   .   C    AAAA   3   .   N   1.0   65.4    -55.3    186.1

            stop_
        save_
    """.replace(
        NOQA_E501, ""
    )

    result = isolate_frame(
        result.stdout, "nef_dihedral_restraint_list_test_2_dihedrals"
    )

    assert_lines_match(EXPECTED, result)


def test_2_dihedrals_bad():
    sequence_path = path_in_test_data(__file__, "3a_ab.neff")
    dihedrals_path = path_in_test_data(__file__, "test_2_dihedrals_bad.tbl")

    with open(sequence_path, "r") as fh:
        nef_sequence = fh.read()

    args = [dihedrals_path]
    result = run_and_report(app, args, input=nef_sequence, expected_exit_code=1)

    assert "ERROR" in result.stdout
    assert "failed to read dihedral restraints" in result.stdout


def test_2_dihedrals_no_segids():
    sequence_path = path_in_test_data(__file__, "3a_ab.neff")
    dihedrals_path = path_in_test_data(__file__, "test_2_dihedrals_no_segids.tbl")

    with open(sequence_path, "r") as fh:
        nef_sequence = fh.read()

    args = [dihedrals_path, "--chains", "AAAA"]
    result = run_and_report(app, args, input=nef_sequence)

    EXPECTED = """\
        save_nef_dihedral_restraint_list_test_2_dihedrals_no_segids                              # noqa: E501
            _nef_dihedral_restraint_list.sf_category     nef_dihedral_restraint_list
            _nef_dihedral_restraint_list.sf_framecode    nef_dihedral_restraint_list_test_2_dihedrals_no_segids
            _nef_dihedral_restraint_list.potential_type  undefined

            loop_
                _nef_dihedral_restraint.index
                _nef_dihedral_restraint.restraint_id
                _nef_dihedral_restraint.restraint_combination_id
                _nef_dihedral_restraint.chain_code_1
                _nef_dihedral_restraint.sequence_code_1
                _nef_dihedral_restraint.residue_name_1
                _nef_dihedral_restraint.atom_name_1
                _nef_dihedral_restraint.chain_code_2
                _nef_dihedral_restraint.sequence_code_2
                _nef_dihedral_restraint.residue_name_2
                _nef_dihedral_restraint.atom_name_2
                _nef_dihedral_restraint.chain_code_3
                _nef_dihedral_restraint.sequence_code_3
                _nef_dihedral_restraint.residue_name_3
                _nef_dihedral_restraint.atom_name_3
                _nef_dihedral_restraint.chain_code_4
                _nef_dihedral_restraint.sequence_code_4
                _nef_dihedral_restraint.residue_name_4
                _nef_dihedral_restraint.atom_name_4
                _nef_dihedral_restraint.weight
                _nef_dihedral_restraint.target_value
                _nef_dihedral_restraint.lower_limit
                _nef_dihedral_restraint.upper_limit

                1   1   .   AAAA   1   .   C   AAAA   2   .   N    AAAA   2   .   CA   AAAA   2   .   C   1.0   -45.7   -166.2   74.8
                2   2   .   AAAA   2   .   N   AAAA   2   .   CA   AAAA   2   .   C    AAAA   3   .   N   1.0   65.4    -55.3    186.1

            stop_
        save_
    """.replace(
        NOQA_E501, ""
    )

    result = isolate_frame(
        result.stdout, "nef_dihedral_restraint_list_test_2_dihedrals_no_segids"
    )

    assert_lines_match(EXPECTED, result)


def test_2_dihedrals_overriding_segids():
    sequence_path = path_in_test_data(__file__, "3a_ab.neff")
    dihedrals_path = path_in_test_data(__file__, "test_2_dihedrals.tbl")

    with open(sequence_path, "r") as fh:
        nef_sequence = fh.read()

    args = [dihedrals_path, "--chains", "BBBB", "--use-chains"]
    result = run_and_report(app, args, input=nef_sequence)

    EXPECTED = """\
        save_nef_dihedral_restraint_list_test_2_dihedrals                                     # noqa: E501
            _nef_dihedral_restraint_list.sf_category     nef_dihedral_restraint_list
            _nef_dihedral_restraint_list.sf_framecode    nef_dihedral_restraint_list_test_2_dihedrals
            _nef_dihedral_restraint_list.potential_type  undefined

            loop_
                _nef_dihedral_restraint.index
                _nef_dihedral_restraint.restraint_id
                _nef_dihedral_restraint.restraint_combination_id
                _nef_dihedral_restraint.chain_code_1
                _nef_dihedral_restraint.sequence_code_1
                _nef_dihedral_restraint.residue_name_1
                _nef_dihedral_restraint.atom_name_1
                _nef_dihedral_restraint.chain_code_2
                _nef_dihedral_restraint.sequence_code_2
                _nef_dihedral_restraint.residue_name_2
                _nef_dihedral_restraint.atom_name_2
                _nef_dihedral_restraint.chain_code_3
                _nef_dihedral_restraint.sequence_code_3
                _nef_dihedral_restraint.residue_name_3
                _nef_dihedral_restraint.atom_name_3
                _nef_dihedral_restraint.chain_code_4
                _nef_dihedral_restraint.sequence_code_4
                _nef_dihedral_restraint.residue_name_4
                _nef_dihedral_restraint.atom_name_4
                _nef_dihedral_restraint.weight
                _nef_dihedral_restraint.target_value
                _nef_dihedral_restraint.lower_limit
                _nef_dihedral_restraint.upper_limit

                1   1   .   BBBB   1   .   C   BBBB   2   .   N    BBBB   2   .   CA   BBBB   2   .   C   1.0   -45.7   -166.2   74.8
                2   2   .   BBBB   2   .   N   BBBB   2   .   CA   BBBB   2   .   C    BBBB   3   .   N   1.0   65.4    -55.3    186.1

            stop_
        save_
    """.replace(
        NOQA_E501, ""
    )

    result = isolate_frame(
        result.stdout, "nef_dihedral_restraint_list_test_2_dihedrals"
    )

    assert_lines_match(EXPECTED, result)
