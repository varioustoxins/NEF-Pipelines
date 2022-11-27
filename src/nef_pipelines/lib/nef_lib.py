import sys
from argparse import Namespace
from enum import auto
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, Iterator, List, Union

# from pandas import DataFrame
from pynmrstar import Entry, Loop, Saveframe
from strenum import LowercaseStrEnum

from nef_pipelines.lib.util import (
    cached_stdin,
    exit_error,
    is_float,
    is_int,
    running_in_pycharm,
)

NEF_CATEGORY_ATTR = "__NEF_CATEGORY__"

UNUSED = "."


# what the selection type is for Star SaveFrames
class SelectionType(LowercaseStrEnum):
    NAME = auto()
    CATEGORY = auto()
    ANY = auto()

    # see https://github.com/irgeek/StrEnum/issues/9
    def _cmp_values(self, other):
        return self.value, str(other).upper()


# currently disabled as they add a dependency on pandas and numpy
# def loop_to_dataframe(loop: Loop) -> DataFrame:
#     """
#     convert a pynmrstar Loop to a pandas DataFrame. Note the Loop category is
#     saved in the dataframe's attrs['__NEF_CATEGORY__']
#
#     :param loop: the pynmrstar Loop
#     :return: a pandas DataFrame
#     """
#     tags = loop.tags
#     data = DataFrame()
#
#     # note this strips the preceding _
#     data.attrs[NEF_CATEGORY_ATTR] = loop.category[1:]
#
#     for tag in tags:
#         if tag != "index":
#             data[tag] = loop.get_tag(tag)
#
#     return data
#
#
# def dataframe_to_loop(frame: DataFrame, category: str = None) -> Loop:
#     """
#     convert a pandas DataFrame to a pynmrstar Loop
#
#     :param frame: the pandas DataFrame
#     :param category: the star category note this will override any category stored in attrs
#     :return: the new pynmrstar Loop
#     """
#     loop = Loop.from_scratch(category=category)
#     loop_data = {}
#     for column in frame.columns:
#         loop.add_tag(column)
#         loop_data[column] = list(frame[column])
#
#     loop.add_data(loop_data)
#
#     if NEF_CATEGORY_ATTR in frame.attrs and not category:
#         loop.set_category(frame.attrs[NEF_CATEGORY_ATTR])
#     elif category:
#         loop.set_category(category)
#
#     return loop


def select_frames_by_name(
    frames: Union[List[Saveframe], Entry],
    name_selectors: Union[List[str], str],
    exact=False,
) -> List[Saveframe]:
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
        name_selectors = [
            name_selectors,
        ]

    result = match_frames(frames, name_selectors)

    if not exact and len(result) == 0:

        name_selectors = [f"*{selector}*" for selector in name_selectors]
        result = match_frames(frames, name_selectors)

    return list(result.values())


# refactor to two functions one of which gets a TextIO
def create_entry_from_stdin_or_exit() -> Entry:

    """
    read a star file entry from stdin or exit withan error message
    :return: a star file entry
    """

    try:
        if not sys.stdin.isatty() or running_in_pycharm():
            stdin = cached_stdin()
            if cached_stdin is None:
                lines = ""
            else:
                lines = "".join(stdin)

            if len(lines.strip()) == 0:
                raise Exception("stdin is empty")
            else:
                entry = Entry.from_string(lines)
        else:
            exit_error("you appear to be reading from an empty stdin")
    except Exception as e:
        exit_error(
            f"failed to read nef entry from stdin because the NEF parser replied: {e}",
            e,
        )

    return entry


# TODO we should examine columns for types not individual rows entries
def loop_row_dict_iter(
    loop: Loop, convert: bool = True
) -> Iterator[Dict[str, Union[str, int, float]]]:
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


def do_reasonable_type_conversions(value: str) -> Union[str, float, int]:
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


def loop_row_namespace_iter(loop: Loop, convert: bool = True) -> Iterator[Namespace]:
    """
    create an iterator that loops over the rows in a star file Loop as Namespaces, by default sensible
    conversions from strings to ints and floats are made
    :param loop: thr Loop
    :param convert: try to convert values to ints or floats if possible [default is True]
    :return: iterator of rows as dictionaries
    """
    for row in loop_row_dict_iter(loop, convert=convert):
        yield Namespace(**row)


# TODO this partially overlaps with select_frames_by_name in this file, combine and simplify!
def select_frames(
    entry: Entry, selector_type: SelectionType, filters: List[str]
) -> List[Saveframe]:
    """
    select a list of frames by name of either category or name

    :param entry: the entry in which frames are looked for
    :param selector_type: the matching type frame.name or frame.category or both [default, search order
           frame.name frame.category]
    :param filters: a list of strings to use as filters as defined by fnmatch
    :return: a list of selected saveframes
    """

    star_filters = [f"*{filter}*" for filter in filters]
    filters = list(filters)
    filters.extend(star_filters)

    result = []
    for frame in entry.frame_dict.values():

        accept_frame_category = any(
            [fnmatch(frame.category, filter) for filter in filters]
        )
        accept_frame_name = any([fnmatch(frame.name, filter) for filter in filters])

        if (
            selector_type in (SelectionType.NAME, SelectionType.ANY)
            and not accept_frame_name
        ):
            continue

        if (
            selector_type in (SelectionType.CATEGORY, SelectionType.ANY)
            and not accept_frame_category
        ):
            continue

        result.append(frame)

    return result


def read_entry_from_file_or_stdin_or_exit_error(file: Path) -> Entry:
    """
    read a star entry from stdin or a file or exit.
    note 1. the stdin stream is cached
         2. this exits with an error if stdin can't be read because its a terminal

    :param file:
    :return:
    """
    if file is None:
        entry = create_entry_from_stdin_or_exit()
    else:
        try:
            with open(file) as fh:
                entry = Entry.from_file(fh)

        except IOError as e:
            exit_error(f"couldn't read from the file {file}", e)
    return entry
