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
from nef_pipelines.transcoders.nmrpipe.importers.shifts import shifts as shifts_app
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import (
    read_db_file_records,
    read_shift_file,
)

app = typer.Typer()
app.command()(shifts_app)

SHIFTS_NMRPIPE = "nef_chemical_shift_list_nmrpipe"

HEADER = open(path_in_test_data(__file__, "test_header_entry.txt")).read()


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
                shift=125.74,
                error=None,
            ),
            ShiftData(
                atom=AtomLabel(
                    SequenceResidue(
                        chain_code="A", sequence_code=2, residue_name="GLY"
                    ),
                    atom_name="HN",
                ),
                shift=8.31,
                error=None,
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

    shifts = read_shift_file(test_records)
    assert shifts == EXPECTED


EXPECTED_NS3_S135A_BMRB1_SHORT = """\
    save_nef_chemical_shift_list_nmrpipe
       _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_nmrpipe

       loop_
          _nef_chemical_shift_list.chain_code
          _nef_chemical_shift_list.sequence_code
          _nef_chemical_shift_list.residue_name
          _nef_chemical_shift_list.atom_name
          _nef_chemical_shift_list.value
          _nef_chemical_shift_list.value_uncertainty
          _nef_chemical_shift_list.element
          _nef_chemical_shift_list.isotope_number

         A   1   ALA   N     125.74   .   .   .
         A   1   ALA   C     179.08   .   .   .
         A   2   GLY   CA    44.77    .   .   .
         A   2   GLY   HA2   3.89     .   .   .
         A   2   GLY   HA3   3.8      .   .   .

       stop_

    save_
"""


# noinspection PyUnusedLocal
def test_ns3_S135A_BMRB1_short():

    path = path_in_test_data(__file__, "ns3_S135A_BMRB1_short.txt")
    result = run_and_report(app, [path], input=HEADER)

    if result.exit_code != 0:
        print(result.stdout)

    assert result.exit_code == 0
    mol_sys_result = isolate_frame(result.stdout, "%s" % SHIFTS_NMRPIPE)

    assert_lines_match(EXPECTED_NS3_S135A_BMRB1_SHORT, mol_sys_result)
