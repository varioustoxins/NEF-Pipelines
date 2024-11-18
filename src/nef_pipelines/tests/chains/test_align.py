import copy

import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.chains.align import align

app = typer.Typer()
app.command()(align)


def test_no_offset():

    INPUT = read_test_data("garyt.nef", __file__)

    result = run_and_report(app, [], input=INPUT)

    assert_lines_match(INPUT, result.stdout)


def test_offset_10():

    INPUT = read_test_data("garyt_offset_10.nef", __file__)
    EXPECTED = read_test_data("garyt.nef", __file__)

    result = run_and_report(app, [], input=INPUT)

    assert_lines_match(EXPECTED, result.stdout)


def test_offset_nearest_match():
    INPUT = read_test_data("garyt_offset_10_nearest.nef", __file__)
    EXPECTED = read_test_data("garyt.nef", __file__)
    EXPECTED = EXPECTED.replace("A   5       THR", "A   5       PHE")

    result = run_and_report(app, [], input=INPUT)

    assert_lines_match(result.stdout, EXPECTED)


def test_offset_mol_system_starts_m10():
    INPUT = read_test_data("garyt_offset_10_mol_system_starts_m10.nef", __file__)
    EXPECTED = copy.copy(INPUT)

    for i in range(10, 16):
        expected_fragment = f"A   {i}       "
        new_fragment = f"A   {i-21}       "
        EXPECTED = EXPECTED.replace(expected_fragment, new_fragment)

    result = run_and_report(app, [], input=INPUT)

    assert_lines_match(EXPECTED, result.stdout)


def test_offset_mol_system_starts_m10_is_superset():
    INPUT = read_test_data(
        "garyt_offset_10_mol_system_starts_m10_is_superset.nef", __file__
    )
    EXPECTED = copy.copy(INPUT)
    for i in range(10, 16):
        expected_fragment = f"A   {i}       "
        new_fragment = f"A   {i-21}       "
        EXPECTED = EXPECTED.replace(expected_fragment, new_fragment)

    result = run_and_report(app, [], input=INPUT)

    assert_lines_match(EXPECTED, result.stdout)


def test_multi_chain():
    INPUT = read_test_data("garyt_multi_chain.nef", __file__)
    EXPECTED = read_test_data("garyt_multi_chain_expected.nef", __file__)

    result = run_and_report(app, [], input=INPUT)

    assert_lines_match(EXPECTED, result.stdout)


def test_one_bad():

    INPUT = read_test_data("garyt_one_bad.nef", __file__)
    EXPECTED = read_test_data("garyt_one_bad_expected.nef", __file__)

    result = run_and_report(app, [], input=INPUT)

    assert_lines_match(EXPECTED, result.stdout)


def test_subset():

    INPUT = read_test_data("garyt_subset.nef", __file__)
    EXPECTED = read_test_data("garyt_subset_expected.nef", __file__)

    result = run_and_report(app, [], input=INPUT)

    assert_lines_match(EXPECTED, result.stdout)
