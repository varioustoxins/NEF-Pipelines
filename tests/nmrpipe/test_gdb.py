
import io

from textwrap import dedent

import pytest

from tests.test_sequence_lib import ABC_SEQUENCE_1LET, ABC_SEQUENCE_3LET
from transcoders.nmrpipe.nmrpipe_lib import read_db_file_records, DbFile, DbRecord, NoVarsLine, \
     MultipleVars, WrongColumnCount, MultipleFormat, DataBeforeFormat, BadFieldFormat, \
     gdb_to_3let_sequence


def test_read_gdb_file():
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

    pales_stream = io.StringIO(PALES_DATA)

    result = read_db_file_records(pales_stream)

    records = [ DbRecord(index=1, type='DATA',
                         values=['SEQUENCE', 'MQIFVKTLTG', 'KTITLEVEPS', 'DTIENVKAKI', 'QDKEGIPPDQ', 'QRLIFAGKQL']),
                DbRecord(index=2, type='DATA',
                         values=['SEQUENCE', 'EDGRTLSDYN','IQKESTLHLV', 'LRLRGG']),
                DbRecord(index=1, type='VARS',
                         values=['RESID_I', 'RESNAME_I', 'ATOMNAME_I', 'RESID_J', 'RESNAME_J', 'ATOMNAME_J', 'D', 'DD', 'W']),
                DbRecord(index=1, type='FORMAT',
                         values=['%5d', '%6s', '%6s', '%5d', '%6s', '%6s', '%9.3f', '%9.3f',  '%.2f']),
                DbRecord(index=1, type='__VALUES__',
                         values=['GLN', 'N', 2, 'GLN', 'HN', -15.524, 1.0, 1.0]),
                DbRecord(index=2, type='__VALUES__',
                         values=['ILE', 'N', 3, 'ILE', 'HN', 10.521, 1.0, 1.0]),
                DbRecord(index=3, type='__VALUES__',
                         values=['PHE', 'N', 4, 'PHE', 'HN', 9.648, 1.0, 1.0]),
                DbRecord(index=4, type='__VALUES__',
                         values=['VAL', 'N', 5, 'VAL', 'HN', 6.082, 1.0, 1.0]),
                DbRecord(index=5, type='__VALUES__',
                         values=['MET', 'C', 2, 'GLN', 'HN', 3.993, 0.333, 3.0]),
                DbRecord(index=6, type='__VALUES__',
                         values=['GLN', 'C', 3, 'ILE', 'HN', -5.646, 0.333, 3.0]),
                DbRecord(index=7, type='__VALUES__',
                         values=['ILE', 'C', 4, 'PHE', 'HN', 1.041, 0.333, 3.0]),
                DbRecord(index=8, type='__VALUES__',
                         values=['PHE', 'C', 5, 'VAL', 'HN', 0.835, 0.333, 3.0])]


    expected = DbFile(name='unknown', records= records)
    assert result == expected


def test_too_many_vars():
    TOO_MANY_VARS = """\
    DATA SEQUENCE MQIFVKTLTG KTITLEVEPS DTIENVKAKI QDKEGIPPDQ QRLIFAGKQL
    DATA SEQUENCE EDGRTLSDYN IQKESTLHLV LRLRGG

    VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W
    VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W
    """
    TOO_MANY_VARS = dedent(TOO_MANY_VARS)

    gdb_stream = io.StringIO(TOO_MANY_VARS)

    msg = '''\
              bad NMRPipe db file, multiple VARS statements found
              file: unknown
              line no: 5
              line: VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W'''
    msg = dedent(msg)

    with pytest.raises(MultipleVars, match=msg):
        read_db_file_records(gdb_stream)


def test_format_no_vars():
    NO_VARS = """\
    FORMAT %5d     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f %.2f

        2    GLN      N      2    GLN     HN     -15.524     1.000 1.00
    """
    NO_VARS = dedent(NO_VARS)

    gdb_stream = io.StringIO(NO_VARS)

    msg = '''\
              no column names defined by a VARS line when FORMAT line read
              file: unknown
              line no: 1
              line: FORMAT %5d     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f %.2'''
    msg = dedent(msg)

    with pytest.raises(NoVarsLine, match=msg):
        read_db_file_records(gdb_stream)


def test_vars_format_mismatch():
    TOO_FEW_FORMATS = """\
    VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W
    FORMAT %5d     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f"""
    TOO_FEW_FORMATS = dedent(TOO_FEW_FORMATS)

    gdb_stream = io.StringIO(TOO_FEW_FORMATS)

    msgs = '''\
              number of column names and formats must agree
              got 8 column names 
              9 formats
              file: unknown
              line no: 2
              line: FORMAT
              '''
    msgs = dedent(msgs).strip()
    msgs = msgs.split('\n')


    with pytest.raises(WrongColumnCount) as exc_info:
        read_db_file_records(gdb_stream)

    for msg in msgs:
        assert msg in exc_info.value.args[0]


def test_empty_and_comment():
    EMPTY_AND_COMMENT = '''\
    #
    
    #
    '''
    EMPTY_AND_COMMENT = dedent(EMPTY_AND_COMMENT)

    gdb_stream = io.StringIO(EMPTY_AND_COMMENT)
    db_records = read_db_file_records(gdb_stream)

    assert len(db_records.records) == 2

    REMARK = '''REMARK'''

    gdb_stream = io.StringIO(REMARK)
    db_records = read_db_file_records(gdb_stream)

    assert len(db_records.records) == 1


def test_multiple_format_lines():
    MULTIPLE_FORMAT = """\
        VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W
        FORMAT %5d     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f %.2f
        FORMAT %5d     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f %.2f
    """

    MULTIPLE_FORMAT = dedent(MULTIPLE_FORMAT)

    gdb_stream = io.StringIO(MULTIPLE_FORMAT)

    msgs = '''\
            bad NMRPipe db file, multiple FORMAT statements found
            file: unknown
            line no: 3
            line: FORMAT
            '''
    msgs = dedent(msgs).strip()
    msgs = msgs.split('\n')

    with pytest.raises(MultipleFormat) as exc_info:
        read_db_file_records(gdb_stream)

    for msg in msgs:
        assert msg in exc_info.value.args[0]


def test_too_few_columns():

    TOO_FEW_COLUMNS = """\
                        DATA SEQUENCE MQIFVKTLTG KTITLEVEPS DTIENVKAKI QDKEGIPPDQ QRLIFAGKQL
                        DATA SEQUENCE EDGRTLSDYN IQKESTLHLV LRLRGG
                    
                        VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W
                        FORMAT %5d     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f %.2f
                    
                            2    GLN      N      2    GLN     HN     -15.524     1.000 
                        """

    TOO_FEW_COLUMNS = dedent(TOO_FEW_COLUMNS)

    gdb_stream = io.StringIO(TOO_FEW_COLUMNS)

    msgs = '''\
            number fields (9) doesn't not match number of columns (10)
            expected
            RESID_I  RESNAME_I  ATOMNAME_I  RESID_J  RESNAME_J  ATOMNAME_J  D        DD     W
            int      str        str         int      str        str         float    float  float
            2        GLN        N           2        GLN        HN          -15.524  1.000  *
            file: unknown
            line no: 7
            line:     2    GLN 
            '''
    msgs = dedent(msgs).strip()
    msgs = msgs.split('\n')

    with pytest.raises(WrongColumnCount) as exc_info:
        read_db_file_records(gdb_stream)

    for msg in msgs:
        assert msg in exc_info.value.args[0]


def test_data_before_format():
    DATA_BEFORE_FORMAT = """\
                            2    GLN      N      2    GLN     HN     -15.524     1.000 
                        """

    DATA_BEFORE_FORMAT = dedent(DATA_BEFORE_FORMAT)

    gdb_stream = io.StringIO(DATA_BEFORE_FORMAT)

    msgs = '''\
            bad nmrpipe db file, data seen before VAR and FORMAT
            file: unknown
            line no: 1
            line: 2    GLN 
            '''
    msgs = dedent(msgs).strip()
    msgs = msgs.split('\n')

    with pytest.raises(DataBeforeFormat) as exc_info:
        read_db_file_records(gdb_stream)

    for msg in msgs:
        assert msg in exc_info.value.args[0]


def test_bad_data_format():
    BAD_DATA_FORMAT = """\
                        VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W
                        FORMAT %5d     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f %.2f
                    
                            2    GLN      N      GLN     2      HN     -15.524     1.000  1.00
                        """

    BAD_DATA_FORMAT = dedent(BAD_DATA_FORMAT)

    gdb_stream = io.StringIO(BAD_DATA_FORMAT)

    msgs = '''\
            Couldn't convert GLN to type int
            file: unknown
            line no: 4
            column: 3
            line:     2    GLN      N      GLN     2      HN     -15.524     1.000  1.00
                                           ^
            '''
    msgs = dedent(msgs).strip()
    msgs = msgs.split('\n')

    with pytest.raises(BadFieldFormat) as exc_info:
        read_db_file_records(gdb_stream)

    for msg in msgs:
        assert msg in exc_info.value.args[0]


def test_bad_format():
    BAD_FIELD_FORMAT = """\
                        VARS   RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J D      DD    W
                        FORMAT %5g     %6s       %6s        %5d     %6s       %6s    %9.3f   %9.3f %.2f

                            2    GLN      N      GLN     2      HN     -15.524     1.000  1.00
                        """
    BAD_FIELD_FORMAT = dedent(BAD_FIELD_FORMAT)

    gdb_stream = io.StringIO(BAD_FIELD_FORMAT)


    with pytest.raises(BadFieldFormat) as exc_info:
        read_db_file_records(gdb_stream)

    msgs ='''\
          unexpected format g at index 1
          expected formats are 
          s, d, e, f 
          string
          integer
          scientific(float)
          float
          file: unknown
          line no: 2
          ^
          '''
    msgs = dedent(msgs)
    msgs = msgs.split('\n')

    for msg in msgs:
        assert msg.strip() in exc_info.value.args[0]


def test_sequence():

    SEQUENCE = dedent(ABC_SEQUENCE_1LET)

    gdb_stream = io.StringIO(SEQUENCE)

    records = read_db_file_records(gdb_stream)
    sequence = gdb_to_3let_sequence(records)

    sequence == ABC_SEQUENCE_3LET


if __name__ == '__main__':
    pytest.main([__file__, '-vv'])