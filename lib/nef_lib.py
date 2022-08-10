from types import MappingProxyType

from pandas import DataFrame
from pynmrstar import Loop

NEF_CATEGORY_ATTR = '__NEF_CATEGORY__'

UNUSED = '.'

def loop_to_dataframe(loop: Loop) -> DataFrame:
    """
    convert a pynmrstar Loop to a pandas DataFrame. Note the Loop category is
    saved in the dataframe's attrs['__NEF_CATEGORY__']

    :param loop: the pynmrstar Loop
    :return: a pandas DataFrame
    """
    tags = loop.tags
    data = DataFrame()

    # note this strips the preceding _
    data.attrs[NEF_CATEGORY_ATTR] = loop.category[1:]

    for tag in tags:
        if tag!= 'index':
            data[tag] = loop.get_tag(tag)

    return data

def dataframe_to_loop(frame: DataFrame, category: str =  None) -> Loop:
    """
    convert a pandas DataFrame to a pynmrstar Loop

    :param frame: the pandas DataFrame
    :param category: the star category note this will override any category stored in attrs
    :return: the new pynmrstar Loop
    """
    loop = Loop.from_scratch(category=category)
    loop_data = {}
    for column in frame.columns:
        loop.add_tag(column)
        loop_data[column] = list(frame[column])

    loop.add_data(loop_data)

    if NEF_CATEGORY_ATTR in frame.attrs and not category:
        loop.set_category(frame.attrs[NEF_CATEGORY_ATTR])
    elif category:
        loop.set_category(category)

    return loop

