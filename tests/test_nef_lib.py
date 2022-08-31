from pandas import DataFrame
from pynmrstar import Loop, Entry

from lib.nef_lib import loop_to_dataframe, dataframe_to_loop, NEF_CATEGORY_ATTR, select_frames_by_name


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


def test_pandas_to_nef():

    TEST_DATA_NEF = '''
        loop_
          _test_loop.tag_1 _test_loop.tag_2
          1                 2
          3                 .
        stop_
    '''

    EXPECTED_NEF = Loop.from_string(TEST_DATA_NEF)

    data_frame = DataFrame()
    data_frame['tag_1'] = ['1', '3']
    data_frame['tag_2'] = ['2', '.']

    result = dataframe_to_loop(data_frame, category='test_loop')

    assert result == EXPECTED_NEF

def test_nef_category():

    TEST_DATA_NEF = '''
        loop_
          _test_loop.tag_1 _test_loop.tag_2
          1                 2
          3                 .
        stop_
    '''

    loop = Loop.from_string(TEST_DATA_NEF, convert_data_types=True)
    frame = loop_to_dataframe(loop)

    assert frame.attrs[NEF_CATEGORY_ATTR] == 'test_loop'

    new_loop = dataframe_to_loop(frame)

    # note pynmrstar includes the leading _ in the category, I don't...!
    assert new_loop.category == '_test_loop'

    new_loop_2 = dataframe_to_loop(frame, category='wibble')
    # note pynmrstar includes the leading _ in the category, I don't...!
    assert new_loop_2.category == '_wibble'


def test_select_frames():
    TEST_DATA = """\
    data_test
        save_test_frame_1
            _test.sf_category test
            loop_
                _test.col_1
                .
            stop_
        save_ 
    
    
        save_test_frame_2
            _test.sf_category test
            loop_
                _test.col_1
                .
            stop_
        save_ 
        
        save_test_frame_13
            _test.sf_category test
            loop_
                _test.col_1
                .
            stop_
        save_ 
        
    """

    test = Entry.from_string(TEST_DATA)

    frames = select_frames_by_name(test, 'test_frame_1')

    assert len(frames) == 1
    assert frames[0].name == 'test_frame_1'


    frames = select_frames_by_name(test, ['test_frame_13'])

    assert len(frames) == 1
    assert frames[0].name == 'test_frame_13'


    frames = select_frames_by_name(test, 'frame_')
    assert len(frames) == 3
    names = sorted([frame.name for frame in frames])
    assert names == ['test_frame_1', 'test_frame_13', 'test_frame_2']


    frames = select_frames_by_name(test, ['frame_1'], greedy=True)

    assert len(frames) == 2
    names = sorted([frame.name for frame in frames])
    assert names == ['test_frame_1', 'test_frame_13']

    frames = select_frames_by_name(test, ['*frame_1*'])

    assert len(frames) == 2
    names = sorted([frame.name for frame in frames])
    assert names == ['test_frame_1', 'test_frame_13']

    frames = select_frames_by_name(test, ['frame_[1]'])

    assert len(frames) == 2
    names = sorted([frame.name for frame in frames])
    assert names == ['test_frame_1', 'test_frame_13']

    frames = select_frames_by_name(test, ['frame_[2]'])

    assert len(frames) == 1
    assert frames[0].name == 'test_frame_2'
