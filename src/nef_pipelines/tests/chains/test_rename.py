import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.chains.rename import rename

runner = CliRunner()

app = typer.Typer()
app.command()(rename)

RENAME_CHAINS_B_D = ["B", "D"]
RENAME_CHAINS_A_E = ["A", "E"]


# noinspection PyUnusedLocal
def test_rename_basic(clear_cache):

    path = path_in_test_data(__file__, "multi_chain.nef")

    result = run_and_report(app, [*RENAME_CHAINS_B_D], input=open(path))

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

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

         1   A   3   HIS   .   .   .   .   .   Sec5   .
         2   A   4   MET   .   .   .   .   .   Sec5   .
         3   D   5   ARG   .   .   .   .   .   Sec5   .
         4   D   6   GLN   .   .   .   .   .   Sec5   .
         5   C   7   PRO   .   .   .   .   .   Sec5   .

       stop_

    save_

    """

    assert_lines_match(EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_rename_multi_frame(clear_cache):

    path = path_in_test_data(__file__, "multi_chain_shifts.nef")

    result = run_and_report(app, [*RENAME_CHAINS_A_E], input=open(path))

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

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

             1   E   3   HIS   .   .   .   .   .   Sec5   .
             2   E   4   MET   .   .   .   .   .   Sec5   .
             3   B   5   ARG   .   .   .   .   .   Sec5   .
             4   B   6   GLN   .   .   .   .   .   Sec5   .
             5   C   7   PRO   .   .   .   .   .   Sec5   .

           stop_

        save_

        save_ccpn_residue_assignments_test
            _ccpn_residue_assignments_test.sf_category                      ccpn_residue_assignments
            _ccpn_residue_assignments_test.sf_frame_code                    ccpn_residue_assignments_test
            _ccpn_residue_assignments_test.ccpn_assignment_program          mars
            _ccpn_residue_assignments_test.ccpn_assignment_program_version  .
            _ccpn_residue_assignments_test.ccpn_assignment_source           .

           loop_
              _ccpn_residue_assignments_test.serial
              _ccpn_residue_assignments_test.chain_code
              _ccpn_residue_assignments_test.residue_number
              _ccpn_residue_assignments_test.residue_type
              _ccpn_residue_assignments_test.assignment_serial
              _ccpn_residue_assignments_test.assignment
              _ccpn_residue_assignments_test.merit
              _ccpn_residue_assignments_test.fixed

             0   E   1   HIS   .   .    .      .
             1   E   2   MET   0   30   0.2    False
             1   E   2   MET   1   48   0.18   False
             1   B   2   MET   2   50   0.13   False
             1   B   2   MET   3   51   0.15   False
             1   B   2   MET   4   56   0.15   False

           stop_

        save_

    """

    assert_lines_match(EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_rename_select_frame_by_name(clear_cache):

    path = path_in_test_data(__file__, "multi_chain_shifts.nef")

    result = run_and_report(
        app, ["--frame", "test", *RENAME_CHAINS_A_E], input=open(path)
    )

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

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

             1   A   3   HIS   .   .   .   .   .   Sec5   .
             2   A   4   MET   .   .   .   .   .   Sec5   .
             3   B   5   ARG   .   .   .   .   .   Sec5   .
             4   B   6   GLN   .   .   .   .   .   Sec5   .
             5   C   7   PRO   .   .   .   .   .   Sec5   .
           stop_
        save_

        save_ccpn_residue_assignments_test
            _ccpn_residue_assignments_test.sf_category                      ccpn_residue_assignments
            _ccpn_residue_assignments_test.sf_frame_code                    ccpn_residue_assignments_test
            _ccpn_residue_assignments_test.ccpn_assignment_program          mars
            _ccpn_residue_assignments_test.ccpn_assignment_program_version  .
            _ccpn_residue_assignments_test.ccpn_assignment_source           .

            loop_
                _ccpn_residue_assignments_test.serial
                _ccpn_residue_assignments_test.chain_code
                _ccpn_residue_assignments_test.residue_number
                _ccpn_residue_assignments_test.residue_type
                _ccpn_residue_assignments_test.assignment_serial
                _ccpn_residue_assignments_test.assignment
                _ccpn_residue_assignments_test.merit
                _ccpn_residue_assignments_test.fixed

                 0   E   1   HIS   .   .    .      .
                 1   E   2   MET   0   30   0.2    False
                 1   E   2   MET   1   48   0.18   False
                 1   B   2   MET   2   50   0.13   False
                 1   B   2   MET   3   51   0.15   False
                 1   B   2   MET   4   56   0.15   False
           stop_
        save_

    """

    assert_lines_match(EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_rename_select_frame_by_category(clear_cache):

    path = path_in_test_data(__file__, "multi_chain_shifts.nef")
    input = open(path).read()

    command = [*RENAME_CHAINS_A_E, "--frame", "mol", "--selector-type", "category"]

    result = run_and_report(app, command, input=input)

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

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

             1   E   3   HIS   .   .   .   .   .   Sec5   .
             2   E   4   MET   .   .   .   .   .   Sec5   .
             3   B   5   ARG   .   .   .   .   .   Sec5   .
             4   B   6   GLN   .   .   .   .   .   Sec5   .
             5   C   7   PRO   .   .   .   .   .   Sec5   .
           stop_
        save_

        save_ccpn_residue_assignments_test
            _ccpn_residue_assignments_test.sf_category                      ccpn_residue_assignments
            _ccpn_residue_assignments_test.sf_frame_code                    ccpn_residue_assignments_test
            _ccpn_residue_assignments_test.ccpn_assignment_program          mars
            _ccpn_residue_assignments_test.ccpn_assignment_program_version  .
            _ccpn_residue_assignments_test.ccpn_assignment_source           .

            loop_
                _ccpn_residue_assignments_test.serial
                _ccpn_residue_assignments_test.chain_code
                _ccpn_residue_assignments_test.residue_number
                _ccpn_residue_assignments_test.residue_type
                _ccpn_residue_assignments_test.assignment_serial
                _ccpn_residue_assignments_test.assignment
                _ccpn_residue_assignments_test.merit
                _ccpn_residue_assignments_test.fixed

                 0   A  1   HIS   .   .    .      .
                 1   A   2   MET   0   30   0.2    False
                 1   A   2   MET   1   48   0.18   False
                 1   B   2   MET   2   50   0.13   False
                 1   B   2   MET   3   51   0.15   False
                 1   B   2   MET   4   56   0.15   False
           stop_
        save_

    """

    assert_lines_match(EXPECTED, result.stdout)
