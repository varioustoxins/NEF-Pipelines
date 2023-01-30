import contextlib
import io
import os
import sys
import traceback
from argparse import Namespace
from enum import auto
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterator, List, Optional, TextIO, TypeVar, Union

import click
from cacheable_iter import iter_cache
from pynmrstar import Entry, Loop, Saveframe
from strenum import StrEnum

from nef_pipelines.lib.constants import (
    EXIT_ERROR,
    NEF_META_DATA,
    NEF_PIPELINES,
    NEF_PIPELINES_VERSION,
    NEF_UNKNOWN,
)
from nef_pipelines.lib.header_lib import (
    create_header_frame,
    get_creation_time,
    get_uuid,
)
from nef_pipelines.lib.structures import LineInfo

STDIN = Path("-")
STDOUT = Path("-")


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

        last_program = meta_frame.get_tag("program_name")[0]
        last_program_version = meta_frame.get_tag("program_version")[0]
        last_script_name = meta_frame.get_tag("script_name")[0]

        meta_frame.add_tag("program_name", name, update=True)
        meta_frame.add_tag("program_version", version, update=True)
        meta_frame.add_tag("script_name", script, update=True)
        creation_time = get_creation_time()
        meta_frame.add_tag("creation_time", creation_time, update=True)
        uuid = get_uuid(NEF_PIPELINES, creation_time)
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
        header = create_header_frame(NEF_PIPELINES, NEF_PIPELINES_VERSION, script)
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
            result = open(file_name).read()
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
    if "pipe" in args and args.pipe:
        result = iter(cached_file_stream(args.pipe))
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


def get_pipe_file_text_or_exit(args: Namespace) -> Optional[TextIO]:

    try:
        result = get_pipe_file_text(args)
    except Exception as e:
        exit_error("couldn't read from stdin or -pipe file", e)

    if result is None:
        exit_error("couldn't read from stdin and no -pipe in command line arguments")

    return result


def get_pipe_file_or_exit(args: Namespace) -> Optional[TextIO]:

    try:
        result = get_pipe_file(args)
    except Exception as e:
        exit_error("couldn't read from stdin or -pipe file", e)

    if isinstance(result, StringIteratorIO):

        result = "\n".join(list(result))

        if len(result) == 0:
            result = None
        else:
            result = io.StringIO(result)

    if result is None:
        exit_error("couldn't read from stdin and no -pipe in command line arguments")

    return result


@iter_cache
def cached_stdin():
    # TODO: this doesn't work!'
    return sys.stdin


class cached_file_stream:
    def __init__(self, file_name):
        self._file_name = file_name

    def __enter__(self):
        return _cached_file_stream(self._file_name)

    def __exit__(self, *args):
        pass

    def __iter__(self):
        return _cached_file_stream(self._file_name)


@iter_cache
def _cached_file_stream(file_name):
    try:
        with open(file_name, "r") as lines:
            result = lines.readlines()
    except IOError as e:
        exit_error(f"couldn't open stream {file_name} because {e}")
    return result


def script_name(file: str) -> Path:
    """
    get the name of the script

    Args:
        file (str): the name of the file

    Returns:
        Path: path to the file
    """

    current_context = click.get_current_context()

    in_pytest = "pytest" in sys.modules
    if in_pytest:
        command = current_context.command_path.split()
    else:
        command = current_context.command_path.split()[1:]

    command = f"{'/'.join(command)}.py"

    return command


def read_from_file_or_exit(file_name: Path, target: str) -> str:
    if file_name == STDIN and sys.stdin.isatty():
        exit_error(
            f"trying to open stdin to read {target}, but stdin is not a stream [did you forget to add a nef file to "
            "your pipeline?]"
        )
    if running_in_pycharm():
        exit_error(
            "reading from stdin doesn't work in pycharm debug environment as there is no shell..."
        )

    display_file_name = get_display_file_name(file_name)

    fh = sys.stdin

    if not file_name == STDIN:
        try:
            fh = open(file_name)
        except Exception as e:
            msg = f"couldn't open {display_file_name} to read {target}"
            exit_error(msg, e)

    try:
        text = fh.read()
    except Exception as e:
        msg = f"couldn't read {target} from {display_file_name}"
        exit_error(msg, e)

    return text


def exit_error(msg, exception=None):
    """
    print an error message and exit error

    Args:
        msg: the message
    """

    if exception is not None:
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info, file=sys.stderr)
        print(file=sys.stderr)

    msg = dedent(msg).split("\n")

    print(file=sys.stderr)

    script = script_name(__file__)

    print(f"ERROR [in {script}]: {msg[0]}", file=sys.stderr)

    for line in msg[1:]:
        print(f"       {line}", file=sys.stderr)
    print("exiting...", file=sys.stderr)
    sys.exit(EXIT_ERROR)


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
        lines = "".join(stream.readlines())
    else:
        lines = ""

    if len(lines.strip()) == 0:
        stream = None

    new_entry = (
        Entry.from_string(lines)
        if stream
        else Entry.from_scratch(input_args.entry_name)
    )

    fixup_metadata(
        new_entry, NEF_PIPELINES, NEF_PIPELINES_VERSION, script_name(__file__)
    )

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
    :param filename: the filename to use '-' indicates a standar stream selected by stream_type
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
    for sublist in in_list:
        out.extend(sublist)
    return out
