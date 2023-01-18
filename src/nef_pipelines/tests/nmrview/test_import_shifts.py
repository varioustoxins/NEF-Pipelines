from textwrap import dedent

import typer

from nef_pipelines.lib.structures import (
    AtomLabel,
    SequenceResidue,
    ShiftData,
    ShiftList,
)
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.nmrview.importers.shifts import shifts
from nef_pipelines.transcoders.nmrview.nmrview_lib import parse_shifts

SHIFTS_NMRVIEW = "nef_chemical_shift_list_nmrview"


app = typer.Typer()
app.command()(shifts)


def test_lib_parse_shifts():

    EXPECTED = ShiftList(
        shifts=[
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=1, residue_name="ASP"
                    ),
                    atom_name="CA",
                ),
                value=52.00,
                value_uncertainty=None,
            ),
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=1, residue_name="ASP"
                    ),
                    atom_name="HA",
                ),
                value=4.220,
                value_uncertainty=None,
            ),
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=2, residue_name="VAL"
                    ),
                    atom_name="CG2",
                ),
                value=19.300,
                value_uncertainty=None,
            ),
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=2, residue_name="VAL"
                    ),
                    atom_name="HG21",
                ),
                value=0.814,
                value_uncertainty=None,
            ),
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=2, residue_name="VAL"
                    ),
                    atom_name="HG22",
                ),
                value=0.814,
                value_uncertainty=None,
            ),
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=3, residue_name="GLN"
                    ),
                    atom_name="N",
                ),
                value=125.058,
                value_uncertainty=None,
            ),
        ]
    )

    test_data = """\
        1.CA      52.000 1
        1.HA       4.220 1
        2.CG2     19.300 1
        2.HG21     0.814 1
        2.HG22     0.814 1
        3.N      125.058 1
    """

    chain_seqid_to_type = {("A", 1): "ASP", ("A", 2): "VAL", ("A", 3): "GLN"}

    test_data = dedent(test_data)

    shifts = parse_shifts(test_data.split("\n"), chain_seqid_to_type)

    assert shifts == EXPECTED


EXPECTED_PPM_OUT_SHORT = """\
    save_nef_chemical_shift_list_nmrview
        _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
        _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_nmrview

        loop_
            _nef_chemical_shift.chain_code
            _nef_chemical_shift.sequence_code
            _nef_chemical_shift.residue_name
            _nef_chemical_shift.atom_name
            _nef_chemical_shift.value
            _nef_chemical_shift.value_uncertainty
            _nef_chemical_shift.element
            _nef_chemical_shift.isotope_number

            A   1   ASP   CA     52.0      .   .   .
            A   1   ASP   HA     4.22      .   .   .
            A   2   VAL   CG2    19.3      .   .   .
            A   2   VAL   HG21   0.814     .   .   .
            A   2   VAL   HG22   0.814     .   .   .
            A   3   GLN   N      125.058   .   .   .

        stop_

    save_
"""


# # noinspection PyUnusedLocal
def test_ppm_out_short_no_sequence(clear_cache):

    STREAM = open(path_in_test_data(__file__, "header.nef")).read()

    path = path_in_test_data(__file__, "ppm_short.out")
    result = run_and_report(app, [path], expected_exit_code=1, input=STREAM)

    print(result.stdout)
    assert "ERROR" in result.stdout
    assert "did you read a sequence?" in result.stdout


# noinspection PyUnusedLocal
def test_ppm_out_short(clear_cache):

    STREAM = open(path_in_test_data(__file__, "ppm_short_seq.nef")).read()

    path = path_in_test_data(__file__, "ppm_short.out")

    result = run_and_report(app, [path], input=STREAM)

    mol_sys_result = isolate_frame(result.stdout, SHIFTS_NMRVIEW)

    assert_lines_match(EXPECTED_PPM_OUT_SHORT, mol_sys_result)
