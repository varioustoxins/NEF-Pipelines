from pandas import DataFrame
from pynmrstar import Loop

from lib.nef_lib import loop_to_dataframe


def test_nef_to_pandas():

    TEST_DATA_NEF = '''
        loop_
          _test_loop.tag_1 _test_loop.tag_2
          1                 2
          3                 .
        stop_
    '''


    loop = Loop.from_string(TEST_DATA_NEF, convert_data_types=True)
    result = loop_to_dataframe(loop)

    EXPECTED_DATA_FRAME = DataFrame()
    EXPECTED_DATA_FRAME['tag_1'] = ['1','3']
    EXPECTED_DATA_FRAME['tag_2'] = ['2', '.']

    assert result.equals(EXPECTED_DATA_FRAME)



