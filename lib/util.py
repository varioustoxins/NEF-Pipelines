import sys
from icecream import ic

from pathlib import Path

from typing import Dict

from pynmrstar import Loop, Saveframe, Entry

from lib.constants import NEF_UNKNOWN, NEF_META_DATA, NEF_PIPELINES, NEF_PIPELINES_VERSION, EXIT_ERROR
from tools.header import get_creation_time, get_uuid, create_header_frame



def get_loop_by_category_or_none(frame: Saveframe, category: str) -> Loop:

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
    ic(tagged_data)
    ic(loop)


def fixup_metadata(entry: Entry, name: str, version: str, script: str):

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


        run_history_loop = get_loop_by_category_or_none(meta_frame, 'nef_run_history')
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


def get_pipe_file(args):

    result = None
    if args.pipe:
        try:
            result = open(args.pipe, 'r')
        except IOError as e:
            exit_error(f"couldn't open stream {args.pipe.name} because {e}")
    elif not sys.stdin.isatty():
        result = sys.stdin

    return result


def script_name(file):
    return Path(file).name


def exit_error(msg):

    print(f'ERROR: {msg}', file=sys.stderr)
    print(' exiting...', file=sys.stderr)
    sys.exit(EXIT_ERROR)


def process_stream_and_add_frames(frames, input_args):

    stream = get_pipe_file(input_args)

    new_entry = Entry.from_file(stream) if stream else Entry.from_scratch(input_args.entry_name)

    fixup_metadata(new_entry, NEF_PIPELINES, NEF_PIPELINES_VERSION, script_name(__file__))

    for frame in frames:
        new_entry.add_saveframe(frame)

    return new_entry
