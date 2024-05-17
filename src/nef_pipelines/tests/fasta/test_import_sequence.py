from textwrap import dedent

import pytest
import typer
from pynmrstar import Entry
from typer.testing import CliRunner

from nef_pipelines.lib.nef_lib import NEF_MOLECULAR_SYSTEM
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.lib.util import is_int
from nef_pipelines.transcoders.fasta.importers.sequence import sequence

runner = CliRunner()
app = typer.Typer()
app.command()(sequence)


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

save_"""


# noinspection PyUnusedLocal
def test_3aa():

    path = path_in_test_data(__file__, "3aa.fasta")
    result = run_and_report(app, [path])

    assert Entry.from_string(result.stdout).entry_id == "test"
    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3AA, mol_sys_result)


def test_3aa_spaces():

    path = path_in_test_data(__file__, "3aa_spaces.fasta")
    result = run_and_report(app, [path])

    assert Entry.from_string(result.stdout).entry_id == "fasta"
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
     4   B    1   ALA   start    .   .
     5   B    2   ALA   middle   .   .
     6   B    3   ALA   end      .   .

   stop_

save_"""


# noinspection PyUnusedLocal
def test_3aa_x2():

    path = path_in_test_data(__file__, "3aa_x2.fasta")
    result = run_and_report(app, [path])

    assert Entry.from_string(result.stdout).entry_id == "test__test2"
    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_AB, mol_sys_result)


EXPECTED_3A_AB_B_start_11 = """\
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

save_"""


# noinspection PyUnusedLocal
def test_3aa_x2_off_10_b():

    path = path_in_test_data(__file__, "3aa_x2.fasta")
    result = run_and_report(app, ["--starts", "1,11", path])

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_AB_B_start_11, mol_sys_result)


EXPECTED_3AA_HEADER_PARSING = """\
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

     1   thx   -2   ALA   start    .   .
     2   thx   -1   ALA   middle   .   .
     3   thx    0   ALA   end      .   .

   stop_

save_"""


def test_3aa_header_parsing():

    path = path_in_test_data(__file__, "3aa_header.fasta")
    result = run_and_report(app, [path])

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert result.stdout.startswith("data_wibble")
    assert_lines_match(EXPECTED_3AA_HEADER_PARSING, mol_sys_result)


EXPECTED_3AA_X2_HEADER_PARSING = """\
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

     1  X   -2   VAL   start    .   .
     2  X   -1   ILE   middle   .   .
     3  X    0   CYS   middle   .   .
     4  X    1   LYS   middle   .   .
     5  X    2   TYR   end      .   .
     6  Z   10   GLY   start    .   .
     7  Z   11   ALA   middle   .   .
     8  Z   12   ARG   middle   .   .
     9  Z   13   TYR   end      .   .

   stop_

save_"""


def test_3aa_x2_header_parsing():

    path = path_in_test_data(__file__, "3aa_x2_header.fasta")
    result = run_and_report(app, [path])

    assert Entry.from_string(result.stdout).entry_id == "test__test2"
    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3AA_X2_HEADER_PARSING, mol_sys_result)


def test_3aa_x2_chain_repeat_header_parsing():

    file_name = "3aa_x2_header_repeat_chains.fasta"
    path = path_in_test_data(__file__, file_name)
    result = run_and_report(app, [path], expected_exit_code=1)

    assert "some of the input chain codes are repeated" in result.stdout
    assert "Z [2]" in result.stdout
    assert "all chain codes must be unique" in result.stdout
    assert file_name in result.stdout


@pytest.mark.parametrize(
    "header_or_text, expected_or_count",
    [
        (">pdb|4ciw|A", "pdb_4ciw_A"),
        (">CW42", "CW42"),
        (">crab_anapl ALPHA CRYSTALLIN B CHAIN (ALPHA(B)-CRYSTALLIN).", "crab_anapl"),
        (">gnl|mdb|bmrb16965:1 HET-s", "gnl_mdb_bmrb16965_1"),
        ("g", 1024),  # g repeated 1024 times
        (
            ">2DLV_1|Chain A|Regulator of G-protein signaling 18|Homo sapiens (9606)",
            "2DLV_1",
        ),
        (">2SRC_1|Chain A|TYROSINE-PROTEIN KINASE SRC|Homo sapiens (9606)", "2SRC_1"),
        (">H1N1 nucleoprotein, monomeric 416A mutant", "H1N1"),
        (">test NEFPLS | CHAIN: Z | START: 10", "test"),
        ("", "fasta"),
        (">", "fasta"),
    ],
)
def test_headers_2(header_or_text, expected_or_count, tmp_path):

    if is_int(expected_or_count):
        expected_or_count = header_or_text * expected_or_count
        header_or_text = f">{expected_or_count}"

    file_text = f"""
        {header_or_text}
        AAA
    """
    file_text = dedent(file_text)

    tmp_file = tmp_path / "test.fasta"
    with tmp_file.open("w") as fh:
        fh.write(file_text)

    result = run_and_report(app, [str(tmp_file)])

    entry = Entry.from_string(result.stdout)

    assert entry.entry_id == expected_or_count
