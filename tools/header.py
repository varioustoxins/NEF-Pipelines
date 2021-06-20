from random import randint

from argparse import ArgumentParser
from datetime import datetime
from pynmrstar import Entry, Saveframe, Loop

from lib.constants import NEF_PIPELINES_VERSION, NEF_VERSION, NEF_PIPELINES


def get_creation_time():
    return datetime.now().isoformat()


def get_uuid(name, creation_time):
    random_value = ''.join(["{}".format(randint(0, 9)) for _ in range(10)])
    return f'{name}-{creation_time}-{random_value}'


def create_header_frame(program_name, program_version, script_name):
    frame = Saveframe.from_scratch('nef_nmr_meta_data', 'nef_nmr_meta_data')

    frame.add_tag('sf_category', 'nef_nmr_meta_data')
    frame.add_tag('sf_framecode', 'nef_nmr_meta_data')
    frame.add_tag('format_name', 'nmr_exchange_format')
    frame.add_tag('nef_nmr_meta_data.format_version', NEF_VERSION)
    frame.add_tag('program_name', program_name)
    frame.add_tag('script_name', script_name)
    frame.add_tag('program_version', program_version)

    creation_time = get_creation_time()
    uuid = get_uuid(NEF_PIPELINES, creation_time)
    frame.add_tag(f'creation_date', creation_time)
    frame.add_tag('uuid', uuid)

    loop = Loop.from_scratch('nef_run_history')
    frame.add_loop(loop)

    history_tags = 'run_number', 'program_name', 'program_version', 'script_name'
    loop.add_tag(history_tags)

    return frame


def create_parser():

    parser = ArgumentParser(description='create a nef file header')
    parser.add_argument('--name', type=str, dest='name', default='new',
                        help='name for the entry', metavar='<ENTRY-NAME>')

    return parser


def main(args):
    from lib.util import script_name
    result = Entry.from_scratch(args.name)
    header_frame = create_header_frame(NEF_PIPELINES, NEF_PIPELINES_VERSION, script_name(__file__))
    result.add_saveframe(header_frame)

    return result


if __name__ == '__main__':

    command_parser = create_parser()
    command_line_args = command_parser.parse_args()

    entry = main(command_line_args)

    print(entry)
