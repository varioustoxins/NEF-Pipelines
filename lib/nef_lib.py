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


