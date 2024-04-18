import typer

from nef_pipelines.lib.nef_lib import NEF_MOLECULAR_SYSTEM
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.rcsb.importers.sequence import sequence

app = typer.Typer()
app.command()(sequence)

HEADER = read_test_data("test_header_entry.txt", __file__)

EXPECTED_3AA = """\
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
"""


# noinspection PyUnusedLocal
def test_3aa():

    path = path_in_test_data(__file__, "3aa.pdb")
    result = run_and_report(app, [path], input=HEADER)

    assert result.exit_code == 0
    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3AA, mol_sys_result)


EXPECTED_3A_AB = """\
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

            1   A    1   ALA   start    .   .
            2   A    2   ALA   middle   .   .
            3   A    3   ALA   end      .   .
            4   B   11   ALA   start    .   .
            5   B   12   ALA   middle   .   .
            6   B   13   ALA   end      .   .

        stop_

    save_
"""


# noinspection PyUnusedLocal
def test_3a_ab():

    path = path_in_test_data(__file__, "3a_ab.pdb")
    result = run_and_report(app, [path], input=HEADER)

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_AB, mol_sys_result)


EXPECTED_3A_CCCC_DDDD = """\
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

            1   CCCC    1   ALA   start    .   .
            2   CCCC    2   ALA   middle   .   .
            3   CCCC    3   ALA   end      .   .
            4   DDDD   11   ALA   start    .   .
            5   DDDD   12   ALA   middle   .   .
            6   DDDD   13   ALA   end      .   .

        stop_

    save_"""


# noinspection PyUnusedLocal
def test_3a_segid_cccc_dddd():

    path = path_in_test_data(__file__, "3a_ab.pdb")
    result = run_and_report(app, ["--segid", path], input=HEADER)

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_CCCC_DDDD, mol_sys_result)


# noinspection PyUnusedLocal
def test_3a_force_segid_cccc_dddd():

    path = path_in_test_data(__file__, "3a_cccc_dddd.pdb")
    result = run_and_report(app, [path], input=HEADER)

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_CCCC_DDDD, mol_sys_result)


# noinspection PyUnusedLocal
def test_3a_test_no_chain_segid():

    path = path_in_test_data(__file__, "3a_no_chain_no_segid.pdb")
    result = run_and_report(app, [path], input=HEADER, expected_exit_code=1)

    assert result.exit_code == 1

    assert "ERROR" in result.stdout
    assert "both the chain code and segment id" in result.stdout
    assert "not present on an ATOM record" in result.stdout
