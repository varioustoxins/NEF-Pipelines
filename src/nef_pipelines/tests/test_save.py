import os
from pathlib import Path

import typer
from pynmrstar import Entry

from nef_pipelines.lib.test_lib import (
    assert_frame_category_exists,
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.save import save

app = typer.Typer()
app.command()(save)

EXPECTED = """
-------------------------------------------------- xplor --------------------------------------------------
data_xplor

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

     1   AAAA   1    ALA   start    .   .
     2   AAAA   2    ALA   middle   .   .
     3   AAAA   3    ALA   end      .   .
     4   BBBB   11   ALA   start    .   .
     5   BBBB   12   ALA   middle   .   .
     6   BBBB   13   ALA   end      .   .

   stop_

save_

-------------------------------------------------- test --------------------------------------------------
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

----------------------------------------------------------------------------------------------------------
"""


EXPECTED_XPLOR = """
data_xplor

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

     1   AAAA   1    ALA   start    .   .
     2   AAAA   2    ALA   middle   .   .
     3   AAAA   3    ALA   end      .   .
     4   BBBB   11   ALA   start    .   .
     5   BBBB   12   ALA   middle   .   .
     6   BBBB   13   ALA   end      .   .

   stop_

save_
"""

EXPECTED_TEST = """
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
"""


# noinspection PyUnusedLocal
def test_save_multi_stream_stdout():
    data = read_test_data(
        "multi.nef",
        __file__,
    )
    result = run_and_report(app, ["-"], input=data)

    assert_lines_match(EXPECTED, result.stdout)


def test_save_multi_stream_stdout_single_file():
    data = read_test_data(
        "multi.nef",
        __file__,
    )
    result = run_and_report(app, "--single-file -".split(), input=data)

    assert_lines_match(EXPECTED, result.stdout)


EXPECTED_NO_HEADER = "\n".join(
    [line for line in EXPECTED.splitlines() if not line.startswith("--")]
)


def test_save_multi_stream_stdout_no_header():
    data = read_test_data(
        "multi.nef",
        __file__,
    )
    result = run_and_report(app, "--no-header -".split(), input=data)

    assert_lines_match(EXPECTED_NO_HEADER, result.stdout)


def test_save_multi_stream_to_directory(tmp_path):
    data = read_test_data(
        "multi.nef",
        __file__,
    )

    result = run_and_report(
        app,
        [
            str(tmp_path),
        ],
        input=data,
    )

    assert_lines_match(result.stdout, data)

    assert Path(tmp_path / "xplor.nef").exists()
    assert Path(tmp_path / "test.nef").exists()

    assert_lines_match(EXPECTED_XPLOR, Path(tmp_path / "xplor.nef").read_text())
    assert_lines_match(EXPECTED_TEST, Path(tmp_path / "test.nef").read_text())


def test_save_multi_stream_to_single_file(tmp_path):
    data = read_test_data(
        "multi.nef",
        __file__,
    )

    test_file_path = tmp_path / "test_all.nef"
    result = run_and_report(
        app,
        [
            "--single-file",
            str(test_file_path),
        ],
        input=data,
    )

    assert_lines_match(result.stdout, data)

    assert Path(tmp_path / "test_all.nef").exists()

    assert_lines_match(EXPECTED, Path(tmp_path / "test_all.nef").read_text())


def test_save_multi_stream_to_directory_files_exist(tmp_path):
    data = read_test_data(
        "multi.nef",
        __file__,
    )

    (tmp_path / "xplor.nef").write_text("existing file")

    result = run_and_report(
        app,
        [
            str(tmp_path),
        ],
        input=data,
        expected_exit_code=1,
    )

    assert "when trying to write the file" in result.stdout
    assert "it already exists" in result.stdout


def test_save_multi_stream_to_directory_files_exist_force(tmp_path):
    data = read_test_data(
        "multi.nef",
        __file__,
    )

    (tmp_path / "xplor.nef").write_text("existing file")

    result = run_and_report(
        app,
        [
            "--force",
            str(tmp_path),
        ],
        input=data,
    )

    assert_lines_match(result.stdout, data)

    assert Path(tmp_path / "xplor.nef").exists()
    assert Path(tmp_path / "test.nef").exists()

    assert_lines_match(EXPECTED_XPLOR, Path(tmp_path / "xplor.nef").read_text())
    assert_lines_match(EXPECTED_TEST, Path(tmp_path / "test.nef").read_text())


def test_save_multi_stream_to_files(tmp_path):
    data = read_test_data(
        "multi.nef",
        __file__,
    )

    test_path_1 = tmp_path / "test_1.nef"
    test_path_2 = tmp_path / "test_2.nef"

    result = run_and_report(
        app, f"{str(test_path_1)} {str(test_path_2)}".split(), input=data
    )

    assert_lines_match(result.stdout, data)

    assert test_path_1.exists()
    assert test_path_2.exists()

    assert_lines_match(EXPECTED_XPLOR, test_path_1.read_text())
    assert_lines_match(EXPECTED_TEST, test_path_2.read_text())


def test_save_multi_stream_to_too_few_files(tmp_path):
    data = read_test_data(
        "multi.nef",
        __file__,
    )

    test_path_1 = tmp_path / "test_1.nef"

    result = run_and_report(
        app, f"{str(test_path_1)}".split(), input=data, expected_exit_code=1
    )

    assert test_path_1.exists()
    assert_lines_match(EXPECTED_XPLOR, test_path_1.read_text())

    assert "Number of entries does not match number of file paths" in result.stdout
    assert "i ran out of file paths to write to" in result.stdout


def test_save_no_stream(tmp_path):

    test_path_1 = tmp_path / "test_1.nef"

    result = run_and_report(app, f"{str(test_path_1)}".split(), expected_exit_code=1)

    assert (
        "you must provide at least one entry to write, did you input a NEF file stream?"
        in result.stdout
    )


def test_save_multi_stream_to_no_files(tmp_path):
    data = read_test_data(
        "multi.nef",
        __file__,
    )

    os.chdir(tmp_path)

    result = run_and_report(app, [], input=data, expected_exit_code=0)

    assert_lines_match(result.stdout, data)

    assert Path(tmp_path / "xplor.nef").exists()
    assert Path(tmp_path / "test.nef").exists()

    assert_lines_match(EXPECTED_XPLOR, Path(tmp_path / "xplor.nef").read_text())
    assert_lines_match(EXPECTED_TEST, Path(tmp_path / "test.nef").read_text())


def test_save_single_file_to_directory_error(tmp_path):

    result = run_and_report(
        app, f"--single-file {str(tmp_path)}".split(), expected_exit_code=1
    )

    assert (
        "you must provide at least one entry to write, did you input a NEF file stream?"
        in result.stdout
    )


def test_save_single_file_to_multipe_files_error(tmp_path):

    data = read_test_data(
        "multi.nef",
        __file__,
    )

    test_path_1 = tmp_path / "test_1.nef"
    test_path_2 = tmp_path / "test_2.nef"

    result = run_and_report(
        app,
        f"--single-file {str(test_path_1)} {test_path_2}".split(),
        input=data,
        expected_exit_code=1,
    )

    assert (
        "the single file option is incompatible with multiple file paths, there were 2 file paths"
        in result.stdout
    )
    assert str(test_path_1) in result.stdout
    assert str(test_path_2) in result.stdout


def test_save_single_stream_stdout():
    data = read_test_data(
        "header.nef",
        __file__,
    )

    result = run_and_report(
        app,
        ["-"],
        input=data,
    )

    assert "--------" not in result.stdout
    assert_frame_category_exists(result.stdout, "nef_nmr_meta_data")


def test_multi_line_string():
    data = read_test_data(
        "header_globals.nef",
        __file__,
    )

    result = run_and_report(
        app,
        ["-"],
        input=data,
    )

    Entry.from_string(result.stdout)
    # no exceptions is all that is needed


def test_globals_cleanup():
    data = read_test_data(
        "header_globals.nef",
        __file__,
    )

    result = run_and_report(
        app,
        ["-"],
        input=data,
    )

    assert_frame_category_exists(result.stdout, "nefpls_globals", count=0)


def test_globals_cleanup_off():
    data = read_test_data(
        "header_globals.nef",
        __file__,
    )

    result = run_and_report(
        app,
        ["--no-globals-cleanup", "-"],
        input=data,
    )

    assert_frame_category_exists(result.stdout, "nefpls_globals", count=1)
