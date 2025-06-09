import contextlib
import functools
import inspect
import io
import os
import sys
import traceback
import warnings
from argparse import Namespace
from enum import auto
from fnmatch import fnmatch
from math import floor
from pathlib import Path
from textwrap import dedent
from typing import (
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    TextIO,
    Tuple,
    TypeVar,
    Union,
)

import click
from pynmrstar import Entry, Loop, Saveframe
from strenum import StrEnum
from tabulate import tabulate

from nef_pipelines.lib.constants import (
    EXIT_ERROR,
    NEF_META_DATA,
    NEF_PIPELINES,
    NEF_UNKNOWN,
)
from nef_pipelines.lib.globals_lib import get_global
from nef_pipelines.lib.header_lib import (
    create_header_frame,
    get_creation_time,
    get_uuid,
)
from nef_pipelines.lib.structures import LineInfo

UNKNOWN_INPUT_SOURCE = "unknown"

FOUR_SPACES = " " * 4

STDIN = Path("-")
STDOUT = Path("-")

NEWLINE = "\n"


def _get_loop_by_category_or_none(frame: Saveframe, category: str) -> Loop:

    result = None
    if f"_{category}" in frame.loop_dict.keys():
        result = frame.get_loop(category)

    return result


def loop_add_data_tag_dict(loop: Loop, data: Dict[str, object]) -> None:
    tagged_data = []
    for category_tag in loop.get_tag_names():
        _, tag = category_tag.split(".")
        if tag in data:
            tagged_data.append(data[tag])
        else:
            tagged_data.append(NEF_UNKNOWN)

    loop.add_data(tagged_data)


# TODO: there is no space for scrript arguments!
def fixup_metadata(entry: Entry, name: str, version: str, script: str):
    """
    add a new entry to a nef metadata frame

    Args:
        entry (Entry): the target entry
        name (str): the name of the program used
        version (str): the vserion of the program used
        script (str): the script used

    Returns:
        Entry: the modified entry
    """

    if entry is not None and NEF_META_DATA in entry.category_list:
        meta_frame = entry[NEF_META_DATA]

        last_program = meta_frame.get_tag("program_name")
        last_program = last_program[0] if last_program else "."

        last_program_version = meta_frame.get_tag("program_version")
        last_program_version = last_program_version[0] if last_program_version else "."

        last_script_name = meta_frame.get_tag("script_name")
        last_script_name = last_script_name[0] if last_script_name else "."

        meta_frame.add_tag("program_name", name, update=True)
        meta_frame.add_tag("program_version", version, update=True)
        meta_frame.add_tag("script_name", script, update=True)
        creation_date = get_creation_time()
        meta_frame.add_tag("creation_date", creation_date, update=True)
        uuid = get_uuid(NEF_PIPELINES, creation_date)
        meta_frame.add_tag("uuid", uuid, update=True)

        run_history_loop = _get_loop_by_category_or_none(meta_frame, "nef_run_history")
        if run_history_loop is not None:
            if run_history_loop.get_tag("run_number"):
                run_number_tags = run_history_loop.get_tag("run_number")
                run_numbers = [int(run_number) for run_number in run_number_tags]
                last_run_number = max(run_numbers)
                next_run_number = last_run_number + 1
            else:
                next_run_number = 1

            data = {
                "run_number": next_run_number,
                "program_name": last_program,
                "program_version": last_program_version,
                "script_name": last_script_name,
            }
            loop_add_data_tag_dict(run_history_loop, data)
        else:
            run_history_loop = Loop.from_scratch("nef_run_history")
            run_history_loop.add_tag(
                ["run_number", "program_name", "program_version", "script_name"]
            )
            run_history_loop.add_data(["."] * 4)
    else:
        header = create_header_frame(NEF_PIPELINES, get_version(), script)
        entry.add_saveframe(header)


class StringIteratorIO(io.TextIOBase):

    # https://stackoverflow.com/questions/12593576/adapt-an-iterator-to-behave-like-a-file-like-object-in-python
    # second answer with more votes!

    def __init__(self, iter):
        self._iter = iter
        self._left = ""

    def readable(self):
        return True

    def _read1(self, n=None):
        while not self._left:
            try:
                self._left = next(self._iter)
            except StopIteration:
                break
        ret = self._left[:n]
        self._left = self._left[len(ret) :]
        return ret

    def read(self, n=None):
        line = []
        if n is None or n < 0:
            while True:
                m = self._read1()
                if not m:
                    break
                line.append(m)
        else:
            while n > 0:
                m = self._read1(n)
                if not m:
                    break
                n -= len(m)
                line.append(m)
        return "".join(line)

    def readline(self):
        line = []
        while True:
            i = self._left.find("\n")
            if i == -1:
                line.append(self._left)
                try:
                    self._left = next(self._iter)
                except StopIteration:
                    self._left = ""
                    break
            else:
                line.append(self._left[: i + 1])
                self._left = self._left[i + 1 :]
                break
        return "".join(line)


# https://stackoverflow.com/questions/6657820/how-to-convert-an-iterable-to-a-stream/20260030#20260030
def iterable_to_stream(iterable, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """
    Lets you use an iterable (e.g. a generator) that yields bytestrings as a read-only
    input stream.

    The stream implements Python 3's newer I/O API (available in Python 2's io module).
    For efficiency, the stream is buffered.
    """

    return StringIteratorIO(iterable)


def running_in_pycharm():
    return "PYCHARM_HOSTED" in os.environ


def get_text_from_file_or_exit(file_name: Path) -> str:
    """
    get text from stdin or from a file argument

    Args:
        file_name (str): name of the file Path('-') indicates stdin

    Returns:
        str: text from file

    """

    result = None

    if file_name == Path("-") or not file_name:
        if sys.stdin.isatty():
            exit_error("attempting to read from a terminal")
        result = sys.stdin.read()
    else:
        try:
            with open(file_name) as fh:
                result = fh.read()
        except IOError as e:
            exit_error(f"couldn't read from {file_name} because of an error", e)

    return result


def get_pipe_file(args: Namespace) -> Optional[TextIO]:
    """
    get an input on stdin or from an argument called pipe

    Args:
        args (Namespace): command line arguments

    Returns:
        TextIO: an input stream or None

    """

    result = None
    if "input" in args and args.input and args.input != STDIN:
        with open(args.input) as fh:
            pipe_lines = fh.read()
        result = io.StringIO(pipe_lines)
    # pycharm doesn't treat stdstreams correcly and hangs
    elif not sys.stdin.isatty() and not running_in_pycharm():
        result = iter(sys.stdin.read().split("\n"))

    return StringIteratorIO(result) if result else None


def get_pipe_file_text(args: Namespace) -> Optional[str]:
    """
    get an input on stdin or from an argument called pipe

    Args:
        args (Namespace): command line arguments

    Returns:
        TextIO: an input stream or None

    """

    result = None
    if "pipe" in args and args.pipe:
        result = open(args.pipe, "r").read()
    # pycharm doesn't treat stdstreams correcly and hangs
    elif not sys.stdin.isatty() and not running_in_pycharm():
        result = sys.stdin.read()

    return result if result else None


def in_pytest():
    return "pytest" in sys.modules


def script_name(file: str) -> Path:
    """
    get the name of the script

    Args:
        file (str): the name of the file

    Returns:
        Path: path to the file
    """
    try:
        current_context = click.get_current_context()
    except RuntimeError:

        current_context = Namespace(command_path="unknown unknown")

    if in_pytest():
        command = current_context.command_path.split()
    else:
        command = current_context.command_path.split()[1:]

    command = f"{'/'.join(command)}.py"

    return command


def read_from_file_or_exit(file_path: Path, target: str = UNKNOWN_INPUT_SOURCE) -> str:

    if file_path == STDIN and sys.stdin.isatty():

        msg = """
            while trying to read from STDIN [-] the input is not a stream
            [did you forget to add a nef file to your pipeline?]
        """
        exit_error(msg)

    display_file_name = get_display_file_name(file_path)

    fh = sys.stdin

    if not file_path == STDIN:
        try:
            fh = open(file_path)
        except Exception as e:
            msg = f"couldn't open {display_file_name} to read {target}"
            exit_error(msg, e)

    try:
        text = fh.read()
    except Exception as e:
        msg = f"couldn't read {target} from {display_file_name}"
        exit_error(msg, e)

    if file_path != STDIN:
        fh.close()

    return text


def _script_to_command(script: str) -> str:
    """
    turns a script path into the equivalent nef pipelines command
    :param script: the script path
    :return: the command name
    """
    script_path = script.split("/")
    script_path[-1] = script_path[-1][: -len(".py")]
    return " ".join(script_path)


def exit_error(msg, exception=None):
    """
    print an error message and exit error

    Args:
        msg: the message
    """

    # This should only happen in verbose mode
    if exception is not None:
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info, file=sys.stderr)
        print(file=sys.stderr)

    msg = dedent(msg).split("\n")

    print(file=sys.stderr)

    script = script_name(__file__)

    command = _script_to_command(script)

    print(f"ERROR [in: {command}]: {msg[0]}", file=sys.stderr)
    print(file=sys.stderr)

    for line in msg[1:]:
        print(f"  {line}", file=sys.stderr)
    print("exiting...", file=sys.stderr)
    sys.exit(EXIT_ERROR)


def warn(msg):
    """print a warning to stderr prefixed with WARNING:"""
    msg = dedent(msg)
    print(f"WARNING: {msg}", file=sys.stderr)


def process_stream_and_add_frames(
    frames: List[Saveframe], input_args: Namespace
) -> Entry:
    """
    take a set of save frames and either add them to a stream from stdin / a pipe-file or create
    a new stream with a proper NEF metadata header

    Args:
        frames: a set of save frames
        input_args: command line arguments for an entry_name and pipe file source

    Returns:
        a new entry containing the frames
    """

    try:
        stream = get_pipe_file(input_args)
    except Exception as e:
        exit_error(f"failed to load pipe file because {e}")

    if stream is not None:
        lines = stream.read()
    else:
        lines = ""

    if len(lines.strip()) == 0:
        stream = None

    new_entry = (
        Entry.from_string(lines)
        if stream
        else Entry.from_scratch(input_args.entry_name)
    )

    fixup_metadata(new_entry, NEF_PIPELINES, get_version(), script_name(__file__))

    # TODO: check if frame exists
    for frame in frames:
        new_entry.add_saveframe(frame)

    return new_entry


def is_int(value: str) -> bool:
    """
    Check if a string is an integer
    Args:
        value (str): the putative integer

    Returns bool:
        true is if its an integer

    """
    result = False
    try:
        int(value)
        result = True
    except (ValueError, TypeError):
        pass

    return result


def is_float(value: str) -> bool:
    """
    Check if a string is an float
    Args:
        value (str): the putative float

    Returns bool:
        true is if its an integer

    """
    result = False
    try:
        float(value)
        result = True
    except (ValueError, TypeError):
        pass

    return result


T = TypeVar("T")


def nef_pipelines_root():
    """
    get the root of the nef pipelines installation

    Returns:
        the root of the nef pipelines installation
    """
    return Path(__file__).parent.parent.parent


# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(input: Iterator[T], n: int) -> Iterator[List[T]]:
    """Yield successive n-sized chunks from lst.
       lst: the list to chunk
       n: the chunk size

    Returns:
        an iterator of chunks from lst of length T

    """
    lst = list(input)
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _build_int_float_error_message(message, line_info, field, format):
    messages = []
    if message:
        messages.append(message)
    if line_info:
        message = f"""
                    couldn't convert {line_info.line} to format

                    at {line_info.line_no + 1} in f{line_info.file_name}

                    line value was

                    {line_info.line}

                    field was

                    {field}
                """
        messages.append(message)
    message = "\n\n".join(messages)
    return message


def read_float_or_exit(
    string: str, line_info: LineInfo = None, field="unknown", message=None
) -> float:
    """
    convert a string to an float or exit with error including line information

    Args:
        string: string to parse
        line_info: the line the string came from
        field: the name of the field defininbg the string (ignored if there is no line info)
        message: any other messages to show

    Returns:
        a float
    """

    format = "float"
    try:
        result = float(string)
    except Exception:
        message = _build_int_float_error_message(message, line_info, field, format)

        exit_error(message)

    return result


def read_integer_or_exit(
    string: str, line_info: LineInfo = None, field="unknown", message=None
) -> int:
    """
    convert a string to an int or exit with error including line information

    Args:
        string: string to parse
        line_info: the line the string came from
        field: the name of the field defining the string (ignored if there is no line info)
        message: any other messages to show

    Returns:
        an integer
    """

    format = "integer"
    try:
        result = int(string)
    except Exception:

        message = _build_int_float_error_message(message, line_info, field, format)

        exit_error(message)

    return result


# TODO test this!
def parse_comma_separated_options(
    lists: Union[List[List[str]], List[str], str]
) -> List[str]:
    """
    Take a mixed list of strings or strings that can be parsed as a comma separated list of strings
    and make a list of all the items

    e.g.

    test = [['1','2','3'], 'a,b,c', ['4','5']]

    gives

    ['1','2','3','a','b','c','4','5']

    :param lists: a mixture of  lists of string or comma separated as a at sting
    :return: list of items
    """
    result = []
    for item in lists:
        if isinstance(item, str):
            item = item.strip(",")
            result.extend(item.split(","))
        else:
            result.append(item)

    return result


def end_with_ordinal(n):
    return str(n) + {1: "st", 2: "nd", 3: "rd"}.get(
        4 if 10 <= n % 100 < 20 else n % 10, "th"
    )


def get_display_file_name(file_name: Path) -> str:
    return "stdin" if file_name == STDIN else file_name


class StdStream(StrEnum):
    STDIN = auto()
    STDOUT = auto()
    STDERR = auto()


STREAM_MODES = {StdStream.STDIN: "r", StdStream.STDOUT: "w", StdStream.STDERR: "w"}


@contextlib.contextmanager
def smart_open(filename=None, stream_type=StdStream.STDOUT):
    f"""
    context manager to open a file or use stdout depending on the filename, stdin is defined as '-'
    by corollary a std stream won't be closed on exit only file system streams
    :param filename: the filename to use '-' indicates a standard stream selected by stream_type
    :param stream_type: how to treat the stream choices are {', '.join(StdStream.__members__)}

    """

    mode = STREAM_MODES[stream_type]
    if filename and str(filename) != "-":
        fh = open(filename, mode)
    else:
        fh = sys.stdout

    try:
        yield fh
    finally:
        if fh not in (sys.stdout, sys.stdin, sys.stderr):
            fh.close()


class DebugStdout:
    """
    class to intercept stdout and print debugging info of where strings ae printed from

    usage:

        from contextlib import redirect_stdout
        with redirect_stdout(DebugStdout):
            ... # your code here
    """

    def __init__(self, in_old_stdout):
        self.old_stdout = in_old_stdout

    def write(self, msg):
        self.old_stdout.write(msg)
        from inspect import currentframe, getframeinfo

        frameinfo = getframeinfo(currentframe().f_back)

        print(f" <-[{frameinfo.filename}, {frameinfo.lineno}]", file=sys.stderr)


def flatten(in_list: Union[List[Any], List[Union[List[Any], Any]]]) -> List[Any]:
    """
    flatten a list of lists into a single list
    :param in_list: a putative lists of lists
    :return: a list of anything but lists
    """
    out = []
    for elem in in_list:
        if not isinstance(elem, str):
            out.extend(elem)
        else:
            out.append(elem)
    return out


def get_version() -> str:
    """
        get the current version of nef pipelines
    :return: a version string
    """

    file_path = Path(__file__)
    root_path = file_path.parent.parent
    version_path = root_path / "VERSION"

    with open(version_path) as file_h:
        version = file_h.read().strip()

    return version


class FStringTemplate:
    """class for makes an f string based template substitution is delayed
    until the instance is converted to a string
    """

    def __init__(self, template):
        self.template = template

    def __str__(self):
        variables = inspect.currentframe().f_back.f_globals.copy()
        variables.update(inspect.currentframe().f_back.f_locals)
        return self.template.format(**variables)


def unused_to_none(value: str) -> str:
    """
    If the value is a NEF UNUSED [.] replace it with None
    :param value: value which might be UNUSED
    :return: value or None if the value was UNUSED
    """
    from nef_pipelines.lib.nef_lib import (
        UNUSED,  # to avoid circular import, move to constants?
    )

    if value == UNUSED:
        value = None
    return value


def unused_to_empty_string(value):
    """
    If the value is a NEF UNUSED [.] replace it with the empty string
    :param value: value which might be UNUSED
    :return: value or "" if the value was UNUSED
    """
    from nef_pipelines.lib.nef_lib import (
        UNUSED,  # to avoid circular import , move to constants?
    )

    if value == UNUSED:
        value = ""
    return value


def _row_to_table(rows: Dict[str, str], headers=("tag", "value")) -> List[List[str]]:
    """
    convert a dictionary into a table with tabulate with two columns containing
    keys and values
    :param rows: a dictionary of key value pairs [tags and values...]
    :return: a formatted tabulate table as a string
    """
    values = [
        headers,
    ]
    for key, value in rows.items():
        values.append([key, value])
    value_string = tabulate(values, headers="firstrow")
    return value_string


def strings_to_table_terminal_sensitive(
    strings: str,
    used_width: int = 0,
    min_width: int = 20,
    fallback_terminal_width: int = 100,
):
    """
    given a list of strings convert them to a table where the number of columns os compatible with the terminal width
    :param strings: a list of strings to tabulate
    :param used_width: any width of the terminal already used
    :param min_width: the minum width for a table column
    :param fallback_terminal_width: if the terminal width can't be determined use this width
    :return: a list of list where each sub list is a row, which is  suitable for formatting with tabulate.tabulate
    """
    try:
        width, _ = os.get_terminal_size()
    except Exception:
        width = fallback_terminal_width

    width -= used_width

    # apply a sensible minimum width
    if width < min_width:
        width = min_width

    if len(strings) > 0:
        frame_name_widths = [len(frame_name) for frame_name in strings]
        max_frame_name_width = max(frame_name_widths)

        columns = int(floor(width / (max_frame_name_width + 1)))
        column_width = int(floor(width / columns))

        columns = 1 if columns == 0 else columns

        strings = [frame_name.rjust(column_width) for frame_name in strings]
        table_list = chunks(strings, columns)
    else:
        table_list = [
            [],
        ]

    return list(table_list)


def strings_to_tabulated_terminal_sensitive(
    strings: str,
    used_width: int = 0,
    min_width: int = 20,
    fallback_terminal_width: int = 100,
):

    table = strings_to_table_terminal_sensitive(
        strings, used_width, min_width, fallback_terminal_width
    )
    return tabulate(table, tablefmt="plain")


def strip_characters_left(target: str, letters: str) -> Tuple[str, str]:
    """
     strip the characters from letters from the left of the target and return a tuple containing
        1. the string without the stripped letters
        2. the letters that were stripped off

    :param target: the string to strip
    :param letters:  the letters to be stripper
    :return: a tuple of the form (<stripped-string>, <stripped-letters>)
    """

    remaining = target.lstrip(letters)

    num_stripped = len(target) - len(remaining)
    stripped = target[:num_stripped] if num_stripped > 0 else ""

    return stripped, remaining


def strip_characters_right(target: str, letters: str) -> Tuple[str, str]:
    """
    strip the characters from letters from the right of the target and return a tuple containing
        1. the string without the stripped letters
        2. the letters that were stripped off

    :param target: the string to strip
    :param letters:  the letters to be stripper
    :return: a tuple of the form (<stripped-string>, <stripped-letters>)
    """

    remaining = target.rstrip(letters)
    num_stripped = len(target) - len(remaining)
    stripped = target[-num_stripped:] if num_stripped > 0 else ""

    return remaining, stripped


def strip_line_comment(line: str, comment_character: str = "#") -> Tuple[str, str]:
    comment = None
    if comment_character in line:
        index = line.index(comment_character)
        comment = line[index + 1 :]
        line = line[:index]

    return line, comment


# https://stackoverflow.com/questions/480214/how-do-i-remove-duplicates-from-a-list-while-preserving-order
def remove_duplicates_stable(seq: Iterable) -> List:
    """
    remove  duplicates from a list while preseving its order, so for example
    [1 2 2 3 45 2 1 6] would yield 1 2 3 4 5 6
    :param seq: the iteratble to remove duplicates from
    :return: the original iterable without the duplicates

    TODO: could this be recast as an iterable returning an iterable
    """

    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


# https://stackoverflow.com/questions/21303224/iterate-over-all-pairs-of-consecutive-items-in-a-list
def iter_consecutive_pairs(seq: Iterator) -> Iterator[Tuple]:
    """
    iterate over consecutive pairs from a list, for example for the list [1, 7, 3, 5]
    this will yield the items (1,7), (7,3), (3,5)
    :param seq: the sequence to iterate pairs from
    :return: an iteration over the consecutive pairs as tuples
    """
    for first, second in zip(seq, seq[1:]):
        yield first, second


# https://stackoverflow.com/questions/2536307/decorators-in-the-python-standard-lib-deprecated-specifically
string_types = (type(b""), type(""))


def deprecated(reason):
    """
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    """

    if isinstance(reason, string_types):

        # The @deprecated is used with a 'reason'.
        #
        # .. code-block:: python
        #
        #    @deprecated("please, use another function")
        #    def old_function(x, y):
        #      pass

        def decorator(func1):

            if inspect.isclass(func1):
                fmt1 = "Call to deprecated class {name} ({reason})."
            else:
                fmt1 = "Call to deprecated function {name} ({reason})."

            @functools.wraps(func1)
            def new_func1(*args, **kwargs):
                warnings.simplefilter("always", DeprecationWarning)
                warnings.warn(
                    fmt1.format(name=func1.__name__, reason=reason),
                    category=DeprecationWarning,
                    stacklevel=2,
                )
                warnings.simplefilter("default", DeprecationWarning)
                return func1(*args, **kwargs)

            return new_func1

        return decorator

    elif inspect.isclass(reason) or inspect.isfunction(reason):

        # The @deprecated is used without any 'reason'.
        #
        # .. code-block:: python
        #
        #    @deprecated
        #    def old_function(x, y):
        #      pass

        func2 = reason

        if inspect.isclass(func2):
            fmt2 = "Call to deprecated class {name}."
        else:
            fmt2 = "Call to deprecated function {name}."

        @functools.wraps(func2)
        def new_func2(*args, **kwargs):
            warnings.simplefilter("always", DeprecationWarning)
            warnings.warn(
                fmt2.format(name=func2.__name__),
                category=DeprecationWarning,
                stacklevel=2,
            )
            warnings.simplefilter("default", DeprecationWarning)
            return func2(*args, **kwargs)

        return new_func2

    else:
        raise TypeError(repr(type(reason)))


def convert_to_float_or_exit(putative_float: str, line_info: LineInfo) -> float:
    """
    convert input string to a float or call exit_error with a reasonable error message
    :param putative_float: the string that could be a float
    :param line_info: line info of where the string came from for error message
    :return: the string converted to a float
    """
    if not is_float(putative_float):
        msg = f"""
                the text {putative_float} could not be converted to a float, at
                line: {line_info.line_no} in
                file: {line_info.file_name} the line was
                line: {line_info.line}
            """
        exit_error(msg)
    return float(putative_float)


def fnmatch_one_of(target: str, patterns: Tuple[str, ...]) -> bool:
    """
    Check if a string code matches any of the patterns

    Args:
        target: the string to match
        patterns: a tuple of patterns to match using fnmatch

    Returns:
        True if the chain code matches any of the patterns
    """
    return any(fnmatch(target, pattern) for pattern in patterns)


def exit_if_file_has_bytes_and_no_force(output_file: Path, force: bool):
    """
    Exit if the output file exists is not empty and the force flag is not set

    Args:
        output_file: the output file
        force: if the file exists and isn't empty it still isn't an error if this flag is set
    """
    if output_file != STDOUT:
        if file_exists_and_has_bytes(output_file) and not get_global("force", force):
            msg = f"""
            the file {output_file} already exists and is not empty, if you want to overwrite it use the --force flag
            """
            exit_error(msg)


def file_exists_and_has_bytes(output_file: Path):
    """
    Check if a file exists and has bytes in it

    Args:
        output_file: the file to check

    Returns:
        True if the file exists and has bytes in it
    """
    return (
        output_file.exists()
        and output_file.is_file()
        and output_file.stat().st_size != 0
    )
