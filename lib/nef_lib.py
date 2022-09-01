from argparse import Namespace
from fnmatch import fnmatch
from types import MappingProxyType
from typing import List, Union, Dict, Iterator

from pandas import DataFrame
from pynmrstar import Loop, Saveframe, Entry

from lib.util import cached_stdin, exit_error, is_float, is_int

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


def select_frames_by_name(frames: Union[List[Saveframe], Entry], name_selectors: Union[List[str], str], exact=False) -> List[Saveframe]:\

    """
    select frames  by names and wild cards, to avoid typing *s on the command line the match is greedy by default
    if an exact match is not found for one of the frames first time we search will all the name selectors turned into
    wild cards by surrounding them with the * as a fence so name_selector-> *name_selector*
    
    :param frames: the list of frames or entry to search
    :param name_selectors: a single string or list of strings to use to match frame names, selectors can contain 
                           wild cards used by pythons fnmatch            
    :param exact: do exact matching and don't search again with wildcards added if no frames are selected
    :return: a list or matching frames
    """

    def match_frames(frames, name_selectors):

        result = {}

        for frame in frames:
            for selector in name_selectors:

                if fnmatch(frame.name, selector):
                    # frames aren't hashable and so can't be saved in a set
                    # but names should be unique
                    result[frame.name] = frame

        return result



    if isinstance(name_selectors, str):
        name_selectors = [name_selectors, ]

    result = match_frames(frames, name_selectors)

    if not exact and len(result) == 0:

        name_selectors = [f'*{selector}*' for selector in name_selectors]
        result = match_frames(frames, name_selectors)

    return list(result.values())

def create_entry_from_stdin_or_exit() -> Entry:

    """
    read a star file entry from stdin or exit withan error message
    :return: a star file entry
    """

    try:
        stdin = cached_stdin()
        if cached_stdin == None:
            lines = ''
        else:
            lines = ''.join(cached_stdin())

        if len(lines.strip()) == 0:
            raise Exception('stdin is empty')
        else:
            entry = Entry.from_string(lines)
    except Exception as e:
        exit_error(f"failed to read nef entry from stdin because {e}", e)

    return entry

#TODO we should examine columns for types not individual rows entries
def loop_row_dict_iter(loop: Loop, convert: bool = True) -> Iterator[Dict[str, Union[str,int,float]]]:
    """
    create an iterator that loops over the rows in a star file Loop as dictionaries, by default sensible
    conversions from strings to ints and floats are made
    :param loop: the Loop
    :param convert: try to convert values to ints or floats if possible [default is True]
    :return: iterator of rows as dictionaries
    """
    for row in loop:
        row = {tag: value for tag, value in zip(loop.tags, row)}

        if convert:
            for key in row:
                row[key] = do_reasonable_type_conversions(row[key])

        yield row


def do_reasonable_type_conversions(value: str) -> Union[str, float,int]:
    """
    do reasonable type conversion from str to int or float
    :param value: the string to convert
    :return: value converted from str to int or float if possible
    """
    if is_int(value):
        value = int(value)
    elif is_float(value):
        value = float(value)
    return value


def loop_row_namespace_iter(loop: Loop, convert:bool = True) -> Iterator[Namespace]:
    """
    create an iterator that loops over the rows in a star file Loop as Namespaces, by default sensible
    conversions from strings to ints and floats are made
    :param loop: thr Loop
    :param convert: try to convert values to ints or floats if possible [default is True]
    :return: iterator of rows as dictionaries
    """
    for row in loop_row_dict_iter(loop, convert=convert):
        yield Namespace(**row)
