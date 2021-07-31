import io
import pytest
from icecream import ic

from transcoders.nmrpipe.nmrpipe_lib import read_db_file_records, DbFile, DbRecord

PALES_DATA = """\
DATA SEQUENCE MQIFVKTLTG KTITLEVEPS DTIENVKAKI QDKEGIPPDQ QRLIFAGKQL
DATA SEQUENCE EDGRTLSDYN IQKESTLHLV LRLRGG

VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W
FORMAT %5d     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f %.2f

    2    GLN      N      2    GLN     HN     -15.524     1.000 1.00
    3    ILE      N      3    ILE     HN      10.521     1.000 1.00
    4    PHE      N      4    PHE     HN       9.648     1.000 1.00
    5    VAL      N      5    VAL     HN       6.082     1.000 1.00

    1    MET      C      2    GLN     HN       3.993     0.333 3.00
    2    GLN      C      3    ILE     HN      -5.646     0.333 3.00
    3    ILE      C      4    PHE     HN       1.041     0.333 3.00
    4    PHE      C      5    VAL     HN       0.835     0.333 3.00
"""


def test_read_gdb_file():
    pales_stream = io.StringIO(PALES_DATA)

    result = read_db_file_records(pales_stream)

    records = [ DbRecord(index=0, type='DATA',
                         values=['SEQUENCE', 'MQIFVKTLTG', 'KTITLEVEPS', 'DTIENVKAKI', 'QDKEGIPPDQ', 'QRLIFAGKQL']),
                DbRecord(index=1, type='DATA',
                         values=['SEQUENCE', 'EDGRTLSDYN','IQKESTLHLV', 'LRLRGG']),
                DbRecord(index=0, type='VARS',
                         values=['RESID_I', 'RESNAME_I', 'ATOMNAME_I', 'RESID_J', 'RESNAME_J', 'ATOMNAME_J', 'D', 'DD', 'W']),
                DbRecord(index=0, type='FORMAT',
                         values=['%5d', '%6s', '%6s', '%5d', '%6s', '%6s', '%9.3f', '%9.3f',  '%.2f']),
                DbRecord(index=0, type='__VALUES__',
                         values=['GLN', 'N', 2, 'GLN', 'HN', -15.524, 1.0, 1.0]),
                DbRecord(index=0, type='__VALUES__',
                         values=['ILE', 'N', 3, 'ILE', 'HN', 10.521, 1.0, 1.0]),
                DbRecord(index=0, type='__VALUES__',
                         values=['PHE', 'N', 4, 'PHE', 'HN', 9.648, 1.0, 1.0]),
                DbRecord(index=0, type='__VALUES__',
                         values=['VAL', 'N', 5, 'VAL', 'HN', 6.082, 1.0, 1.0]),
                DbRecord(index=0, type='__VALUES__',
                         values=['MET', 'C', 2, 'GLN', 'HN', 3.993, 0.333, 3.0]),
                DbRecord(index=1, type='__VALUES__',
                         values=['GLN', 'C', 3, 'ILE', 'HN', -5.646, 0.333, 3.0]),
                DbRecord(index=1, type='__VALUES__',
                         values=['ILE', 'C', 4, 'PHE', 'HN', 1.041, 0.333, 3.0]),
                DbRecord(index=1, type='__VALUES__',
                         values=['PHE', 'C', 5, 'VAL', 'HN', 0.835, 0.333, 3.0])]


    expected = DbFile(name='unknown', records= records)
    assert result == expected


if __name__ == '__main__':
    pytest.main([__file__, '-vv'])