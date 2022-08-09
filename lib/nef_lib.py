from types import MappingProxyType

from pandas import DataFrame
from pynmrstar import Loop

def loop_to_dataframe(loop: Loop) -> DataFrame:
    tags = loop.tags
    data = DataFrame()

    for tag in tags:
        if tag!= 'index':
            data[tag] = loop.get_tag(tag)

    return data

def dataframe_to_loop(frame: DataFrame, category: str =  None) -> Loop:
    loop = Loop.from_scratch(category=category)
    loop_data = {}
    for column in frame.columns:
        loop.add_tag(column)
        loop_data[column] = list(frame[column])

    loop.add_data(loop_data)

    return loop

