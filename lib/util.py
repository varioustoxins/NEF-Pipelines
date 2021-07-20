import sys
from argparse import Namespace

from cacheable_iter import iter_cache

from pathlib import Path

from typing import Dict, TextIO, Optional, List

from pynmrstar import Loop, Saveframe, Entry

from lib.constants import NEF_UNKNOWN, NEF_META_DATA, NEF_PIPELINES, NEF_PIPELINES_VERSION, EXIT_ERROR
from tools.header import get_creation_time, get_uuid, create_header_frame



def _get_loop_by_category_or_none(frame: Saveframe, category: str) -> Loop:

    result = None
    if f'_{category}' in frame.loop_dict.keys():
        result = frame.get_loop_by_category(category)

    return result


def loop_add_data_tag_dict(loop: Loop, data: Dict[str, object]) -> None:
    tagged_data = []
    for category_tag in loop.get_tag_names():
        _, tag = category_tag.split('.')
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

        last_program = meta_frame.get_tag('program_name')[0]
        last_program_version = meta_frame.get_tag('program_version')[0]
        last_script_name = meta_frame.get_tag('script_name')[0]

        meta_frame.add_tag('program_name', name, update=True)
        meta_frame.add_tag('program_version', version, update=True)
        meta_frame.add_tag('script_name', script, update=True)
        creation_time = get_creation_time()
        meta_frame.add_tag('creation_time', creation_time, update=True)
        uuid = get_uuid(NEF_PIPELINES, creation_time)
        meta_frame.add_tag('uuid', uuid, update=True)


        run_history_loop = _get_loop_by_category_or_none(meta_frame, 'nef_run_history')
        if run_history_loop is not None:
            if run_history_loop.get_tag('run_number'):
                run_number_tags = run_history_loop.get_tag('run_number')
                run_numbers = [int(run_number) for run_number in run_number_tags]
                last_run_number = max(run_numbers)
                next_run_number = last_run_number + 1
            else:
                next_run_number = 1

            data = {
                'run_number': next_run_number,
                'program_name': last_program,
                'program_version': last_program_version,
                'script_name': last_script_name
            }
            loop_add_data_tag_dict(run_history_loop, data)
        else:
            run_history_loop = Loop.from_scratch('nef_run_history')
            run_history_loop.add_tag(['run_number', 'program_name', 'program_version', 'script_name'])
            run_history_loop.add_data(['.'] * 4)
    else:
        header = create_header_frame(NEF_PIPELINES, NEF_PIPELINES_VERSION, script)
        entry.add_saveframe(header)


import io

# https://stackoverflow.com/questions/12593576/adapt-an-iterator-to-behave-like-a-file-like-object-in-python
# second answer with more votes!


class StringIteratorIO(io.TextIOBase):

    def __init__(self, iter):
        self._iter = iter
        self._left = ''

    def readable(self):
        return True

    def _read1(self, n=None):
        while not self._left:
            try:
                self._left = next(self._iter)
            except StopIteration:
                break
        ret = self._left[:n]
        self._left = self._left[len(ret):]
        return ret

    def read(self, n=None):
        l = []
        if n is None or n < 0:
            while True:
                m = self._read1()
                if not m:
                    break
                l.append(m)
        else:
            while n > 0:
                m = self._read1(n)
                if not m:
                    break
                n -= len(m)
                l.append(m)
        return ''.join(l)

    def readline(self):
        l = []
        while True:
            i = self._left.find('\n')
            if i == -1:
                l.append(self._left)
                try:
                    self._left = next(self._iter)
                except StopIteration:
                    self._left = ''
                    break
            else:
                l.append(self._left[:i+1])
                self._left = self._left[i+1:]
                break
        return ''.join(l)

#https://stackoverflow.com/questions/6657820/how-to-convert-an-iterable-to-a-stream/20260030#20260030
def iterable_to_stream(iterable, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """
    Lets you use an iterable (e.g. a generator) that yields bytestrings as a read-only
    input stream.

    The stream implements Python 3's newer I/O API (available in Python 2's io module).
    For efficiency, the stream is buffered.
    """

    return StringIteratorIO(iterable)


def get_pipe_file(args: Namespace) -> Optional[TextIO]:
    """
    get an input on stdin or from an argument called pipe

    Args:
        args (Namespace): command line arguments

    Returns:
        TextIO: an input stream or None

    """

    result = []
    if 'pipe' in args and args.pipe:
        result = cached_file_stream(args.pipe)
    elif not sys.stdin.isatty():
        result = cached_stdin()

    return StringIteratorIO(result)


@iter_cache
def cached_stdin():
    return sys.stdin


@iter_cache
def cached_file_stream(file_name):
    try:
        result = open(file_name, 'r')
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
    return Path(file).name


def exit_error(msg):
    """
    print an error message and exit error

    Args:
        msg: the message
    """

    print(f'ERROR: {msg}', file=sys.stderr)
    print(f'exiting...', file=sys.stderr)
    sys.exit(EXIT_ERROR)


def process_stream_and_add_frames(frames: List[Saveframe], input_args: Namespace) -> Entry:
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
        exit_error(f'failed to load pipe file because {e}')

    new_entry = Entry.from_file(stream) if stream else Entry.from_scratch(input_args.entry_name)

    fixup_metadata(new_entry, NEF_PIPELINES, NEF_PIPELINES_VERSION, script_name(__file__))

    for frame in frames:
        new_entry.add_saveframe(frame)

    return new_entry
