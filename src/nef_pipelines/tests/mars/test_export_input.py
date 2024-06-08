import re
from pathlib import Path

import typer

from nef_pipelines.lib.test_lib import read_test_data, run_and_report
from nef_pipelines.transcoders.mars.exporters.input import input_

app = typer.Typer()
app.command()(input_)

ROOT_INPUT_FILENAME = "Sec5Part2_read_only_new_x31m_f1"


def test_input_stdout(tmpdir):
    input = read_test_data("sec5_short.neff", __file__)

    result = run_and_report(app, "-".split(), input=input)

    entry_name = "Sec5Part2_read_only_new_x31m_f1"

    INPUTS_AND_SUFFIXES = {
        "fixConn:": "_fix_con.tab",
        "fixAss:": "_fix_ass.tab",
        "sequence:": ".fasta",
        "secondary:": "_psipred.tab",
        "csTab:": "_shifts.tab",
    }

    for input, suffix in INPUTS_AND_SUFFIXES.items():
        test = re.compile(rf"{input}\s+{entry_name}{suffix}")
        assert test.search(result.stdout)

    assert re.search(r"deuterated:\s+0", result.stdout)
    assert re.search(r"rand_coil:\s+0", result.stdout)

    fix_con_path = tmpdir / f"{entry_name}_fix_con.tab"
    assert not fix_con_path.exists()

    fix_ass_path = tmpdir / f"{entry_name}_fix_ass.tab"
    assert not fix_ass_path.exists()


def test_input_stdout_deuterated_random_coil():
    input = read_test_data("sec5_short.neff", __file__)

    result = run_and_report(app, "--random-coil -".split(), input=input)

    assert re.search(r"rand_coil:\s+1", result.stdout)
    assert re.search(r"deuterated:\s+0", result.stdout)

    result = run_and_report(app, "--deuterated -".split(), input=input)

    assert re.search(r"rand_coil:\s+0", result.stdout)
    assert re.search(r"deuterated:\s+1", result.stdout)


def test_output_to_dir(tmpdir):
    input = read_test_data("sec5_short.neff", __file__)

    run_and_report(
        app,
        [
            str(tmpdir),
        ],
        input=input,
    )

    tmpdir = Path(tmpdir)
    input_path = tmpdir / f"{ROOT_INPUT_FILENAME}.inp"

    assert input_path.is_file()
    assert input_path.stat().st_size > 2023

    fix_con_path = tmpdir / f"{ROOT_INPUT_FILENAME}_fix_con.tab"

    assert fix_con_path.is_file()
    assert fix_con_path.stat().st_size == 0

    fix_ass_path = tmpdir / f"{ROOT_INPUT_FILENAME}_fix_con.tab"

    assert fix_ass_path.is_file()
    assert fix_ass_path.stat().st_size == 0


def test_output_to_dir_existing_no_force(tmpdir):
    input = read_test_data("sec5_short.neff", __file__)

    tmpdir = Path(tmpdir)
    input_path = tmpdir / f"{ROOT_INPUT_FILENAME}.inp"
    with input_path.open("w") as fh:
        fh.write("test")

    run_and_report(
        app,
        [
            str(tmpdir),
        ],
        input=input,
        expected_exit_code=1,
    )


def test_output_to_dir_existing_force(tmpdir):
    input = read_test_data("sec5_short.neff", __file__)

    tmpdir = Path(tmpdir)
    input_path = tmpdir / f"{ROOT_INPUT_FILENAME}.inp"
    write_test_file(input_path)

    run_and_report(
        app,
        [
            "--force",
            str(tmpdir),
        ],
        input=input,
    )

    assert input_path.is_file()
    assert input_path.stat().st_size > 2023


def write_test_file(input_path):
    with input_path.open("w") as fh:
        fh.write("test")


def test_fix_con_fix_ass_existing(tmpdir):
    input = read_test_data("sec5_short.neff", __file__)

    tmpdir = Path(tmpdir)

    fix_con_path = tmpdir / f"{ROOT_INPUT_FILENAME}_fix_con.tab"
    write_test_file(fix_con_path)

    fix_ass_path = tmpdir / f"{ROOT_INPUT_FILENAME}_fix_ass.tab"
    write_test_file(fix_ass_path)

    run_and_report(
        app,
        [
            str(tmpdir),
        ],
        input=input,
    )

    assert fix_con_path.stat().st_size == 4
    assert fix_ass_path.stat().st_size == 4
