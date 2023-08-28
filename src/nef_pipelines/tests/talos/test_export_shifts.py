import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.talos.exporters.shifts import shifts

app = typer.Typer()
app.command()(shifts)

EXPECTED = """
REMARK Chemical shift table for nmrpipe

DATA CHAIN A
DATA FIRST_RESID 1

DATA SEQUENCE MQIF

VARS   RESID    RESNAME    ATOMNAME      SHIFT
FORMAT %4d      %1s        %4s           %8.3f
1               M          CB           33.27
1               M          CA           54.45
1               M          C           170.54
1               M          HA            4.23
2               Q          CA           55.08
2               Q          CB           30.76
2               Q          C           175.92
2               Q          HA            5.249
2               Q          N           123.22
3               I          HA            4.213
3               I          C           172.45
3               I          CA           59.57
3               I          N           115.34
3               I          CB           42.21
4               F          HA            5.63
4               F          C           175.32
4               F          CB           41.48
4               F          CA           55.21
4               F          N           118.11
"""


def test_4peaks(clear_cache):

    STREAM = open(path_in_test_data(__file__, "ubi_4.nef")).read()

    result = run_and_report(app, [], input=STREAM)

    assert_lines_match(EXPECTED, result.stdout)


# TODO check filtering & bad inputs
