import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.mars.exporters.shifts import shifts

app = typer.Typer()
app.command()(shifts)


def test_export_shifts_nef5_short():
    input = read_test_data("sec5_short.neff", __file__)

    result = run_and_report(app, "--out -".split(), input=input)

    EXPECTED = """\
              H      N        CA      CA-1    CB      CB-1
        PR_1  8.594  133.252  61.159  59.291  33.274  37.309
        PR_2  8.928  131.397  -       -       -       -
        PR_3  9.671  130.698  60.735  62.418  39.792  69.744
        PR_4  8.185  128.894  53.744  54.679  43.207  34.050
        PR_5  8.548  128.090  56.292  65.574  32.964  69.899
    """

    assert_lines_match(result.stdout, EXPECTED, squash_spaces=True)


def test_export_shifts_pete_co():

    input = read_test_data("short_co.neff", __file__)

    result = run_and_report(app, "--out -".split(), input=input)

    EXPECTED = """\
                   H        N  CA      CA-1    CB-1    CO       CO-1
        PR_1  11.671  136.682  -       -       -       -        -
        PR_2  10.946  131.689  -       -       -       -        -
        PR_3  10.266  112.518  46.281  63.862  32.984  176.722  178.726
        PR_4   9.632  104.529  46.465  -       -       173.390  175.767

    """

    assert_lines_match(result.stdout, EXPECTED, squash_spaces=True)


def test_export_shifts_david_bad_residue_name():

    input = read_test_data("sec5_short_bad_res_name.neff", __file__)

    result = run_and_report(
        app, "--out -".split(), input=input, expected_exit_code=1
    )  # , separate_stderr=True)

    # TODO: this should check in stderr not stdout but see note in test_lib: its currently not possible to capture
    # the stdout and stderr streams separately
    EXPECTED_ERROR_STRINGS = [
        "error for atom H in chain A",
        "the residue type in the sequence doesn't match residue type in shifts",
        "sequence residue name .",
        "frame name nef_chemical_shift_list_default",
        "row number 27",
    ]
    for error_string in EXPECTED_ERROR_STRINGS:
        assert error_string in result.stdout
