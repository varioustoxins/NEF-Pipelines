import sys
from argparse import Namespace
from collections.abc import MutableMapping
from enum import auto
from fnmatch import fnmatch
from itertools import zip_longest
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

# from pandas import DataFrame
from pynmrstar import Entry, Loop, Saveframe
from pynmrstar.definitions import STR_CONVERSION_DICT
from pynmrstar.exceptions import ParsingError
from strenum import LowercaseStrEnum

from nef_pipelines.lib import util
from nef_pipelines.lib.constants import NEF_PIPELINES
from nef_pipelines.lib.globals_lib import set_global
from nef_pipelines.lib.util import (
    exit_error,
    fixup_metadata,
    get_version,
    is_float,
    is_int,
    running_in_pycharm,
    script_name,
    warn,
)

NEF_RELAXATION_VERSION = "0.1.0a"

DEFAULT_INCREMENT_SEPARATOR = "::"
DEFAULT_INCREMENT_END = ""

NEF_TRUE = "true"
NEF_FALSE = "false"
NEF_NONE = "none"

NEF_CATEGORY_ATTR = "__NEF_CATEGORY__"
NEF_MOLECULAR_SYSTEM = "nef_molecular_system"
NEF_METADATA = "nef_nmr_meta_data"

UNUSED = "."
UNDERSCORE = "_"

# this stops pynmrstar failing on empty strings
STR_CONVERSION_DICT[""] = UNUSED


class BadNefFileException(Exception):
    """
    marker class for star files that don't conform to NEF conventions, e.g. files with multiple singletons
    as an example the molecular system should be a singleton
    ths doesn't imply the file has invalid star syntax, the star syntax will be valid
    """

    pass


class NoSuchColumnException(Exception):
    pass


# what the selection type is for Star SaveFrames
class SelectionType(LowercaseStrEnum):
    NAME = auto()
    CATEGORY = auto()
    ANY = auto()

    # see https://github.com/irgeek/StrEnum/issues/9
    def _cmp_values(self, other):
        return self.value, str(other).upper()


SELECTORS_LOWER = ", ".join(
    [selector.lower() for selector in SelectionType.__members__]
)


class PotentialTypes(LowercaseStrEnum):
    UNDEFINED = auto()
    LOG_HARMONIC = "log-harmonic"
    PARABOLIC = auto()
    SQUARE_WELL_PARABOLIC = "square-well-parabolic"
    SQUARE_WELL_PARABOLIC_LINEAR = "square-well-parabolic-linear"
    UPPER_BOUND_PARABOLIC = "upper-bound-parabolic"
    LOWER_BOUND_PARABOLIC = "lower-bound-parabolic"
    UPPER_BOUND_PARABOLIC_LINEAR = "upper-bound-parabolic-linear"
    LOWER_BOUND_PARABOLIC_LINEAR = "lower-bound-parabolic-linear "

    # see https://github.com/irgeek/StrEnum/issues/9
    def _cmp_values(self, other):
        return self.value, str(other).upper()


POTENTIAL_TYPES_LOWER = ", ".join(
    [selector.lower() for selector in PotentialTypes.__members__]
)

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


def get_frame_id(frame: Saveframe) -> str:
    """
    given a frame get its id (the characters after the category and a separating _ charctacter)
    :param frame: the frame to get the name of
    :return: the id of the frame
    """
    return frame.name[len(frame.category) + 1 :]


def get_frame_ids(frames_or_entry: Union[List[Saveframe], Entry]) -> List[str]:
    """
    given a list of frames get theirs id (the characters after the category and a separating _ charctacter)
    :param frames_or_entry: a list of frames or an entty
    :return: a list of ids in the same order
    """

    return list([get_frame_id(frame) for frame in frames_or_entry])


def select_frames_by_name(
    frames: Union[List[Saveframe], Entry],
    name_selectors: Union[List[str], str],
    exact=False,
) -> Tuple[Saveframe, ...]:
    """
    select frames  by names and wild cards, to avoid typing *s on the command line the match is greedy by default,
    if an exact match is not found for one of the frames first time we search again with all the name selectors
    turned into wild cards by surrounding them with the * as a fence so name_selector-> *name_selector*

    :param frames: the list of frames or entry to search
    :param name_selectors: a single string or list of strings to use to match frame names, selectors can contain
                           wild cards used by pythons fnmatch
    :param exact: do exact matching and don't search again with wildcards added if no frames are selected
    :return: a list or matching frames
    """

    def match_frames(
        frames: List[Saveframe], name_selectors: List[str]
    ) -> Dict[Any, Saveframe]:
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

    return tuple(result.values())


# refactor to two functions one of which gets a TextIO
def create_entry_from_stdin() -> Optional[Entry]:
    """
    read a star file entry from stdin or return None

    can throw a ParsingError from PyNMRStar

    :return: a star file entry or None
    """

    try:
        entry = None
        if not sys.stdin.isatty() or running_in_pycharm():
            stdin_lines = sys.stdin.read()
            if stdin_lines is None:
                lines = ""
            else:
                lines = "".join(stdin_lines)

            if len(lines.strip()) != 0:
                entry = Entry.from_string(lines)
    except ParsingError as e:
        raise BadNefFileException(str(e)) from e

    if entry:
        entry.source = "-"

    return entry


def read_file_or_exit(file_path: Path) -> List[str]:
    """
    read the contents of a file or exit with error

    :param file_path: the path to the file
    :return: a list of strings from the file
    """
    try:
        with open(file_path) as fh:
            result = fh.readlines()
    except IOError as e:
        msg = f"""\
            failed to read from {file_path} because {e}
        """
        exit_error(msg)

    return result


# refactor to two functions one of which gets a TextIO
def read_entry_from_stdin_or_exit() -> Entry:
    """
    read a star file entry from stdin or exit with an error message
    :return: a star file entry
    """

    if sys.stdin.isatty():
        exit_error("you appear to be reading from an empty stdin")

    try:
        stdin_lines = sys.stdin.read()
        if stdin_lines is None:
            lines = [
                "",
            ]
        lines = "".join(stdin_lines)
    except IOError as e:
        exit_error(
            f"failed to read stdin because: {e}",
            e,
        )

    if len(lines.strip()) == 0:
        exit_error("stdin is empty")

    try:
        entry = Entry.from_string(lines)

    except ParsingError as e:
        exit_error(
            f"failed to read nef entry from stdin because the NEF parser replied: {e}",
            e,
        )

    entry.source = "-"

    return entry


class RowDict(MutableMapping):
    def __init__(self, loop: Loop, row: int, convert: bool):
        super().__init__()
        self._data = row
        self._convert = convert
        self._tag_to_index = {tag: i for i, tag in enumerate(loop.tags)}
        self._tag_types = {
            tag: type(value) for tag, value in zip(loop.tags, self._data)
        }

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._tag_to_index.keys())

    def __delitem__(self, key):
        self._data[self._tag_to_index[key]] = UNUSED

    def __getitem__(self, key):
        index = self._tag_to_index[key]
        value = self._data[index]
        if self._convert:
            value = do_reasonable_type_conversions(value)
        return value

    def __setitem__(self, key, value):
        index = self._tag_to_index[key]
        if self._tag_types[key] == str and not isinstance(value, str):
            value = str(value)
        self._data[index] = value

    def __repr__(self):
        row = {key: self._data[index] for key, index in self._tag_to_index.items()}
        return str(row)

    def __str__(self):
        return self.__repr__()

    # def __getattribute__(self, item):
    #     print(item)
    #     try:
    #         return self[item]
    #     except Exception:
    #         return object.__getattribute__(self, item)
    #
    # def __setattr__(self, item, value):
    #     if hasattr(self, item):
    #         self[item] = value
    #     else:
    #         return super().__setattr__(item, value)
    #
    # def __delattr__(self, key):
    #     self.__delitem__(key)


# TODO we should examine columns for types not individual rows entries
# TODO we should rename this loop_row_iter
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

    if not isinstance(loop, Loop):
        msg = f"""\
            loop must be of type Loop you provided a {loop.__class__.__name__}"
            value: {loop}
        """
        raise Exception(msg)

    for i, row in enumerate(loop):
        result = RowDict(loop, row, convert)
        yield result


def do_reasonable_type_conversions(value: str) -> Union[str, float, int]:
    """
    do reasonable type conversion from str to int or float
    :param value: the string to convert
    :return: value converted from str to int or float if possible
    """

    # only apply conversions to strings otherwise you get nice unexpected conversions like float -> int
    if isinstance(value, str):
        if is_int(value):
            value = int(value)
        elif is_float(value):
            value = float(value)
        elif value.lower() == NEF_FALSE:
            value = False
        elif value.lower() == NEF_TRUE:
            value = True
    return value


def loop_row_namespace_iter(loop: Loop, convert: bool = True) -> Iterator[Namespace]:
    """
    create an iterator that loops over the rows in a star file Loop as Namespaces, by default sensible
    conversions from strings to ints and floats are made
    :param loop: thr Loop
    :param convert: try to convert values to ints or floats if possible [default is True]
    :return: iterator of rows as dictionaries

    NOTE: This function is effectively replaced by loop_row_dict_iter, which returns a RowDict object
          with support for attribute lookup
    """
    for row in loop_row_dict_iter(loop, convert=convert):
        # yield row needs more tests modified
        yield Namespace(**row)


# TODO this partially overlaps with select_frames_by_name in this file, combine and simplify!
def select_frames(
    entry: Entry,
    predicate: Union[str, List[str]],
    selector_type: SelectionType = SelectionType.ANY,
) -> List[Saveframe]:
    """
    select a list of frames by name of either category or name, if no predicates are provided all frames are selected

    :param entry: the entry in which frames are looked for
    :param predicate: a string or list of strings to use as filters as defined by fnmatch
    :param selector_type: the matching type frame.name or frame.category or both [default, search order
           frame.name frame.category]
    :return: a list of selected saveframes
    """

    if isinstance(predicate, str):
        predicate = [
            predicate,
        ]
    if not predicate:
        predicate = ["*"]

    star_filters = [f"*{filter}*" for filter in predicate]
    predicate = list(predicate)
    predicate.extend(star_filters)

    result = {}
    for frame in entry.frame_dict.values():

        if frame.category is not None:
            accept_frame_category = any(
                [fnmatch(frame.category, filter) for filter in predicate]
            )
        else:
            accept_frame_category = False
        accept_frame_name = any([fnmatch(frame.name, filter) for filter in predicate])

        if (
            selector_type in (SelectionType.NAME, SelectionType.ANY)
            and accept_frame_name
        ):
            result[frame.category, frame.name] = frame

        if (
            selector_type in (SelectionType.CATEGORY, SelectionType.ANY)
            and accept_frame_category
        ):
            result[frame.category, frame.name] = frame

    return list(result.values()) if result else []


def read_entry_from_file_or_stdin_or_exit_error(file: Path) -> Entry:
    """
    read a star entry from stdin or a file or exit.
    note this exits with an error if stdin can't be read because its a terminal

    :param file:
    :return:
    """
    if file is None or file == Path("-"):
        entry = read_entry_from_stdin_or_exit()
    else:
        entry = read_entry_from_file_or_exit_error(file)
    return entry


def read_entry_from_file_or_exit_error(file):
    """
    read a star entry from a file or exit with an error message

    :param file: a file on the file system
    :return: a new Entry read from the file
    """

    file = Path(file)

    if not file.exists() or not file.is_file():
        exit_error(f"the file {file} doesn't exist or isn't a file")
    try:
        with open(file) as fh:
            entry = Entry.from_file(fh)

    except IOError as e:
        exit_error(f"couldn't read from the file {file}", e)

    return entry


# TODO: should be used as underpinnings for other related functions here
def read_or_create_entry_exit_error_on_bad_file(
    file: Path, entry_name: str = "nef"
) -> Entry:
    """
    read a star entry from stdin or create a new one. If a badly formatted Star file is read exit error...

    :param file: a file whih can be either on the file system or stding Path('-')
    :return: an Entry a new Entry is created if no entry can be read
    """

    entry = None
    try:
        if file is None or file == Path("-"):
            entry = create_entry_from_stdin()
            if entry and entry.entry_id == "nefpls_globals":
                entry.entry_id = entry_name
        else:
            try:
                with open(file) as fh:
                    entry = Entry.from_file(fh)
                    _parse_globals(entry)

            except IOError as e:
                msg = f"""
                    while reading the file {util.get_display_file_name(file)} the file wasn't readable
                    error from operating system was {str(e)}
                """
                exit_error(msg)
    except BadNefFileException as e:
        msg = f"""
            while reading the file {util.get_display_file_name(file)} the format was bad
            error from star file parser was {str(e)}
        """
        exit_error(msg)

    if entry is None:
        entry = Entry.from_scratch(entry_name)

    return entry


def _parse_globals(entry: Entry):

    globals_frames = entry.get_saveframes_by_category("nefpls_globals")
    for globals_frame in globals_frames:

        values = {name: globals_frame.get_tag(name) for name in globals_frame.tags}
        values = {
            name: do_reasonable_type_conversions(value)
            for name, value in values.items()
        }
        for key, value in values.items():
            set_global(key, value)


def file_name_path_to_frame_name(path: str) -> str:
    """
    convert a filename or complete path to a name suitable for use as a frame name, this does the following mappings
        . -> _
        - -> _

    :param file_name: the filename to convert
    :return: a string suitable for use as a NEF framename
    """
    path = Path(path)

    stem = str(path.stem)
    stem = stem.replace("-", "_")
    stem = stem.replace(".", "_")

    return stem


def molecular_system_from_entry_or_exit(entry: Entry):
    """
    read the nef molecular system [a singleton] from a star entry or exit with a helpful message
    :param entry: The NEF star entry
    :return: the molecular system save frame or None if there isn't one
    """

    molecular_system = None
    try:
        molecular_system = molecular_system_from_entry(entry)
    except BadNefFileException as e:
        exit_error(str(e))

    if not molecular_system:
        exit_error(
            "Couldn't find a molecular system frame it should be labelled 'save_nef_molecular_system'"
        )

    return molecular_system


def molecular_system_from_entry(entry):
    """
    read the nef molecular system [a singleton] from a star entry or raise a BadNefFileException
    :param entry: The NEF star entry
    :return: the molecular system save frame or None if there isn't one
    """
    result = None

    molecular_systems = entry.get_saveframes_by_category(NEF_MOLECULAR_SYSTEM)
    if len(molecular_systems) == 1:
        result = molecular_systems[0]
    elif len(molecular_systems) > 1:
        msg = f"""\
                there must be only one molecular_system i found {len(molecular_systems)}
                frame_names are {', '.join([frame.name for frame in molecular_systems])}
        """
        raise BadNefFileException(msg)

    return result


def add_frames_to_entry(entry: Entry, frames: List[Saveframe]) -> Entry:
    # TODO deal with merging esp wrt to molecular systems and possibly with other information
    # TODO add frame rename and frame delete
    """
    take a set of save frames and  add them to an Entry and update the NEF metadata header

    Args:
        entry: an entry to add the save frames to
        frames: a set of save frames to add, they must have different names to those present already


    Returns:
        the updated entry containing the frames
    """

    fixup_metadata(entry, NEF_PIPELINES, get_version(), script_name(__file__))

    for frame in frames:

        new_frame_name = frame.name

        proposed_new_frame_name = new_frame_name
        offset = ""
        while is_save_frame_name_in_entry(entry, proposed_new_frame_name):
            if offset == "":
                offset = 1
            else:
                offset += 1
            if offset != "":
                proposed_new_frame_name = f"{new_frame_name}_{offset}"

        if proposed_new_frame_name != new_frame_name:

            msg = f"""
                the frame named {new_frame_name} already exists in the stream, the frame name has been updated to
                {proposed_new_frame_name}. if you want to replace the original frame named {new_frame_name} delete
                it first!
            """
            msg = dedent(msg).strip()
            warn(msg)

        frame.name = proposed_new_frame_name

        entry.add_saveframe(frame)

    return entry


def is_save_frame_name_in_entry(entry: Entry, frame_name: str) -> bool:
    """
    check if a save frame name exists in an entry
    :param entry: the entry
    :param frame_name: the frame name
    :return: if a savefame with the name is present
    """
    frame_in_entry = True
    try:
        entry.get_saveframe_by_name(frame_name)
    except KeyError:
        frame_in_entry = False

    return frame_in_entry


def set_column(loop: Loop, column: Union[int, str], values: List[Any]) -> Loop:
    """
    set the values of a column in a loop from a list
    :param loop:  the loop
    :param column: the name or index of the column to modify
    :param values: the values to put into the column
    :return: the loop (same instance)
    """

    column = _ensure_column_is_index(loop, column)

    SENTINEL = "!!SENTINEL!!"
    for row, merit in zip_longest(loop, values, fillvalue=SENTINEL):
        if row is SENTINEL:
            break
        row[column] = merit

    return loop


def _ensure_column_is_index(loop: Loop, column: Union[str, int]) -> int:
    if isinstance(column, str):
        if column in loop.tags:
            column = loop.tag_index(column)
        else:
            msg = f"""
                the column {column} wasn't found in the loop {loop.category}

                the available columns are {', '.join(loop.tags)}
            """
            raise NoSuchColumnException(msg)
    return column


def set_column_to_value(loop: Loop, column: Union[str, int], value: Any) -> Loop:
    """

    set the values of a column in a loop to a single value

    :param loop:  the loop
    :param column: the name or index of the column to modify
    :param values: the values to put
    :return: the loop (same instance)
    """
    column = _ensure_column_is_index(loop, column)
    for row in loop:
        row[column] = value

    return loop


def extract_column(loop: Loop, column: Union[str, int]) -> Loop:
    """
    Extract all the values in the column of a loop into a list

    :param the loop
    :param column: the name or index of the column to modify
    :return: the values in the column as a list in row order
    """
    column = _ensure_column_is_index(loop, column)
    values = []
    for row in loop:
        values.append(row[column])
    return values


def create_nef_save_frame(
    frame_category: str,
    frame_id: str = None,
    increment: str = "",
    separator: str = DEFAULT_INCREMENT_SEPARATOR,
    end: str = DEFAULT_INCREMENT_END,
) -> Saveframe:
    """
    Create a NEF save frame from a category and a frame name, including the tags sf_category and sf_framecode

    :param category: the category including an organisation prefix
    :param frame_id: the id of the frame  (can be None for singletons)
    :param separator: separator between the category and the frame_id (default ::)
    :param end: text after the frame_id (can be used to create a fence  default is the empty string
    :return: a NEF style saveframe
    """

    if frame_id and increment:
        frame_name = f"{frame_category}_{frame_id}{separator}{increment}{end}"
    elif frame_id:
        frame_name = f"{frame_category}_{frame_id}"
    else:
        frame_name = f"{frame_category}"

    frame = Saveframe.from_scratch(frame_name, f"{frame_category}")
    frame.add_tag("sf_category", frame_category)
    frame.add_tag("sf_framecode", frame_name)
    return frame
