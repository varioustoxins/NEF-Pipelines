import typer
from pynmrstar.loop import Loop

from nef_pipelines.lib.test_lib import isolate_loop, path_in_test_data, run_and_report
from nef_pipelines.tools.frames.filter import filter

app = typer.Typer()
app.command()(filter)


def test_filter_unassigned():
    path = path_in_test_data(__file__, "assigned_partially_and_unassigned.nef")
    result = run_and_report(app, ["--in", path])

    loop = isolate_loop(
        result.stdout, "nef_rdc_restraint_list_test_1", "nef_rdc_restraint"
    )

    loop = Loop.from_string(loop)
    assert len(loop) == 1
    assert "1  1  .  A  1  ALA  H  A  1   ALA  N  1  -4.2  0.22".split() in loop.data


def test_filter_unassigned_partial():
    path = path_in_test_data(__file__, "assigned_partially_and_unassigned.nef")
    result = run_and_report(app, f"--in {path} --state partial".split())

    loop = isolate_loop(
        result.stdout, "nef_rdc_restraint_list_test_1", "nef_rdc_restraint"
    )

    loop = Loop.from_string(loop)
    assert len(loop) == 2
    assert (
        "1   1   .   A   1   ALA   H   A   1   ALA   N   1   -4.2   0.22".split()
        in loop.data
    )
    assert (
        "2   2   .   .   .   .     .   A   2   TRP   N   1   -5.2   0.33".split()
        in loop.data
    )


def test_filter_assigned():
    path = path_in_test_data(__file__, "assigned_partially_and_unassigned.nef")
    result = run_and_report(app, ["--in", path, "--assigned"])

    loop = isolate_loop(
        result.stdout, "nef_rdc_restraint_list_test_1", "nef_rdc_restraint"
    )

    loop = Loop.from_string(loop)
    assert len(loop) == 1
    assert "3  3  .  .  .  .    .  .  .   .    .  1   3.1  0.4".split() in loop.data


def test_filter_assigned_full():
    path = path_in_test_data(__file__, "assigned_partially_and_unassigned.nef")
    result = run_and_report(app, f"--in {path} --assigned --state full".split())

    loop = isolate_loop(
        result.stdout, "nef_rdc_restraint_list_test_1", "nef_rdc_restraint"
    )

    loop = Loop.from_string(loop)
    assert len(loop) == 2
    assert " 2  2  .  .  .  .    .  A  2   TRP  N  1  -5.2  0.33".split() in loop.data
    assert "3  3  .  .  .  .    .  .  .   .    .  1   3.1  0.4".split() in loop.data
