import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.mars.importers.shifts import shifts

app = typer.Typer()
app.command()(shifts)


def test_export_shifts_nef5_short():

    result = run_and_report(app, [path_in_test_data(__file__, "sec5_short.txt")])

    EXPECTED = """\
        save_nef_chemical_shift_list_mars
           _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_mars

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

             @-   @1     .   H    8.594     .   .   .
             @-   @1     .   N    133.252   .   .   .
             @-   @1     .   CA   61.159    .   .   .
             @-   @1-1   .   CA   59.291    .   .   .
             @-   @1     .   CB   33.274    .   .   .
             @-   @1-1   .   CB   37.309    .   .   .
             @-   @2     .   H    8.928     .   .   .
             @-   @2     .   N    131.397   .   .   .
             @-   @3     .   H    9.671     .   .   .
             @-   @3     .   N    130.698   .   .   .
             @-   @3     .   CA   60.735    .   .   .
             @-   @3-1   .   CA   62.418    .   .   .
             @-   @3     .   CB   39.792    .   .   .
             @-   @3-1   .   CB   69.744    .   .   .
             @-   @4     .   H    8.185     .   .   .
             @-   @4     .   N    128.894   .   .   .
             @-   @4     .   CA   53.744    .   .   .
             @-   @4-1   .   CA   54.679    .   .   .
             @-   @4     .   CB   43.207    .   .   .
             @-   @4-1   .   CB   34.05     .   .   .
             @-   @5     .   H    8.548     .   .   .
             @-   @5     .   N    128.09    .   .   .
             @-   @5     .   CA   56.292    .   .   .
             @-   @5-1   .   CA   65.574    .   .   .
             @-   @5     .   CB   32.964    .   .   .
             @-   @5-1   .   CB   69.899    .   .   .

           stop_

        save_

    """

    frame = isolate_frame(result.stdout, "nef_chemical_shift_list_mars")
    assert_lines_match(EXPECTED, frame)
