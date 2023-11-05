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

EXPECTED_PROTONATED_HIS = """
REMARK Chemical shift table for nmrpipe

DATA CHAIN A
DATA FIRST_RESID 1

DATA SEQUENCE MhIF

VARS   RESID    RESNAME    ATOMNAME      SHIFT
FORMAT %4d      %1s        %4s           %8.3f
1               M          CB           33.27
1               M          CA           54.45
1               M          C           170.54
1               M          HA            4.23
2               h          CA           55.08
2               h          CB           30.76
2               h          C           175.92
2               h          HA            5.249
2               h          N           123.22
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


def test_4peak_his_he(clear_cache):

    STREAM = open(path_in_test_data(__file__, "protonated_his.nef")).read()

    result = run_and_report(app, [], input=STREAM)

    assert_lines_match(EXPECTED_PROTONATED_HIS, result.stdout)


EXPECTED_OXIDISED_CYS = """
REMARK Chemical shift table for nmrpipe

DATA CHAIN A
DATA FIRST_RESID 1

DATA SEQUENCE McIF

VARS   RESID    RESNAME    ATOMNAME      SHIFT
FORMAT %4d      %1s        %4s           %8.3f
1               M          CB           33.27
1               M          CA           54.45
1               M          C           170.54
1               M          HA            4.23
2               c          CA           55.08
2               c          CB           30.76
2               c          C           175.92
2               c          HA            5.249
2               c          N           123.22
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


def test_4peak_cis_oxidised(clear_cache):

    STREAM = open(path_in_test_data(__file__, "oxidised_cys.nef")).read()

    result = run_and_report(app, [], input=STREAM)

    assert_lines_match(EXPECTED_OXIDISED_CYS, result.stdout)


EXPECTED_OFFSET_1 = """
    REMARK Chemical shift table for nmrpipe

    DATA CHAIN A
    DATA FIRST_RESID 2

    DATA SEQUENCE MQIF

    VARS   RESID    RESNAME    ATOMNAME      SHIFT
    FORMAT %4d      %1s        %4s           %8.3f
    2               M          CB           33.27
    2               M          CA           54.45
    2               M          C           170.54
    2               M          HA            4.23
    3               Q          CA           55.08
    3               Q          CB           30.76
    3               Q          C           175.92
    3               Q          HA            5.249
    3               Q          N           123.22
    4               I          HA            4.213
    4               I          C           172.45
    4               I          CA           59.57
    4               I          N           115.34
    4               I          CB           42.21
    5               F          HA            5.63
    5               F          C           175.32
    5               F          CB           41.48
    5               F          CA           55.21
    5               F          N           118.11
"""


def test_4peaks_offset(clear_cache):
    STREAM = open(path_in_test_data(__file__, "ubi_4_offset_1.nef")).read()

    result = run_and_report(app, [], input=STREAM)

    assert_lines_match(EXPECTED_OFFSET_1, result.stdout)
