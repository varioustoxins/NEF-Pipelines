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
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.nmrpipe.importers.shifts import shifts as shifts_app
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import (
    read_db_file_records,
    read_shift_file,
)

app = typer.Typer()
app.command()(shifts_app)

SHIFTS_NMRPIPE = "nef_chemical_shift_list_nmrpipe"

HEADER = read_test_data("test_header_entry.txt", __file__)


def test_lib_parse_shifts():

    EXPECTED = ShiftList(
        shifts=[
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=1, residue_name="ALA"
                    ),
                    atom_name="N",
                ),
                value=125.74,
                value_uncertainty=None,
            ),
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=2, residue_name="GLY"
                    ),
                    atom_name="HN",
                ),
                value=8.31,
                value_uncertainty=None,
            ),
        ]
    )

    test_data = """
        VARS   RESID RESNAME ATOMNAME SHIFT
        FORMAT %4d %1s %4s %8.2f

        1   ALA   N   125.74
        2   GLY   HN   8.31

    """

    test_data = dedent(test_data)

    test_records = read_db_file_records(test_data.split("\n"))

    shifts = read_shift_file(test_records, chain_code="A")
    assert shifts == EXPECTED


# noinspection PyUnusedLocal
def test_ns3_S135A_BMRB1_short():
    EXPECTED = """\
        save_nef_chemical_shift_list_nmrpipe
           _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_nmrpipe

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

             A   1   ALA   N     125.74   .   .   .
             A   1   ALA   C     179.08   .   .   .
             A   2   GLY   CA    44.77    .   .   .
             A   2   GLY   HA2   3.89     .   .   .
             A   2   GLY   HA3   3.8      .   .   .

           stop_

        save_
    """
    path = path_in_test_data(__file__, "ns3_S135A_BMRB1_short.txt")
    result = run_and_report(app, [path], input=HEADER)

    mol_sys_result = isolate_frame(result.stdout, SHIFTS_NMRPIPE)

    assert_lines_match(EXPECTED, mol_sys_result)


def test_residue_1let_3let_translation():
    EXPECTED = """\
        save_nef_chemical_shift_list_nmrpipe
            _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
            _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_nmrpipe

            loop_
                _nef_chemical_shift.chain_code
                _nef_chemical_shift.sequence_code
                _nef_chemical_shift.residue_name
                _nef_chemical_shift.atom_name
                _nef_chemical_shift.value
                _nef_chemical_shift.value_uncertainty
                _nef_chemical_shift.element
                _nef_chemical_shift.isotope_number

                A   1   MET   CB   33.27    .   .   .
                A   1   MET   CA   54.45    .   .   .
                A   1   MET   C    170.54   .   .   .
                A   1   MET   HA   4.23     .   .   .
                A   2   GLN   HN   8.9      .   .   .
                A   2   GLN   CA   55.08    .   .   .
                A   2   GLN   CB   30.76    .   .   .
                A   2   GLN   C    175.92   .   .   .
                A   2   GLN   HA   5.249    .   .   .
                A   2   GLN   N    123.22   .   .   .

           stop_

        save_
    """

    path = path_in_test_data(__file__, "P3a_l273R_nmrpipe_shifts_short.tab")

    result = run_and_report(app, [path], input=HEADER)

    mol_sys_result = isolate_frame(result.stdout, SHIFTS_NMRPIPE)

    assert_lines_match(EXPECTED, mol_sys_result)
