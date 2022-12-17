import typer

from nef_pipelines.lib.structures import AtomLabel, Peak, PeakValues, SequenceResidue
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.nmrview.exporters.peaks import (
    _make_names_unique,
    _row_to_peak,
    peaks,
)

app = typer.Typer()
app.command()(peaks)

EXPECTED = open(
    path_in_test_data(__file__, "expected_sequence_and_peaks_nmrview.txt")
).read()

EXPECTED_AXES = ["1H_1", "1H_2", "15N"]


def test_make_names_unique():
    TEST = ["1H", "1H", "15N"]

    result = _make_names_unique(TEST)

    assert result == EXPECTED_AXES


def test_row_to_peak():
    TEST_ROW = {
        "index": 1,
        "peak_id": 0,
        "volume": 0.38,
        "volume_uncertainty": ".",
        "height": 0.38,
        "height_uncertainty": ".",
        "position_1": 10.405,
        "position_uncertainty_1": ".",
        "position_2": 8.796,
        "position_uncertainty_2": ".",
        "position_3": 132.49,
        "position_uncertainty_3": ".",
        "chain_code_1": "A",
        "sequence_code_1": 1,
        "residue_name_1": "ala",
        "atom_name_1": "HE1",
        "chain_code_2": "A",
        "sequence_code_2": 3,
        "residue_name_2": "ala",
        "atom_name_2": "HN",
        "chain_code_3": "A",
        "sequence_code_3": 1,
        "residue_name_3": "ala",
        "atom_name_3": "N",
    }

    result = _row_to_peak(EXPECTED_AXES, TEST_ROW)

    assignments = {
        "15N": [
            AtomLabel(
                SequenceResidue(chain_code="A", sequence_code=1, residue_name="ala"),
                atom_name="N",
            )
        ],
        "1H_1": [
            AtomLabel(
                SequenceResidue(chain_code="A", sequence_code=1, residue_name="ala"),
                atom_name="HE1",
            )
        ],
        "1H_2": [
            AtomLabel(
                SequenceResidue(chain_code="A", sequence_code=3, residue_name="ala"),
                atom_name="HN",
            )
        ],
    }
    positions = {"1H_1": 10.405, "1H_2": 8.796, "15N": 132.49}

    EXPECTED_PEAK = Peak(
        id=0,
        positions=positions,
        assignments=assignments,
        values=PeakValues(serial=1, volume=0.38, height=0.38),
    )

    assert result == EXPECTED_PEAK


EXPECTED = open(path_in_test_data(__file__, "expected_nmr_view.xpk")).read()


# noinspection PyUnusedLocal
def test_3peaks(clear_cache):

    STREAM = open(path_in_test_data(__file__, "nef_3_peaks.nef")).read()

    result = run_and_report(app, [], input=STREAM)

    assert_lines_match(EXPECTED, result.stdout)
