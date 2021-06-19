from random import randint

from argparse import ArgumentParser
from datetime import datetime
from pynmrstar import Entry, Saveframe, Loop

from lib.constants import PIPELINES_VERSION, NEF_VERSION, NEF_PIPELINES


def main(args):
    result = Entry.from_scratch(args.name)
    frame = Saveframe.from_scratch('nef_nmr_meta_data', 'nef_nmr_meta_data')
    result.add_saveframe(frame)

    frame.add_tag('format_name','nmr_exchange_format')
    frame.add_tag('nef_nmr_meta_data.format_version', NEF_VERSION)
    frame.add_tag('program_name', NEF_PIPELINES)
    frame.add_tag('program_version',  PIPELINES_VERSION)

    utc_date_time = datetime.now().isoformat()
    frame.add_tag(f'creation_date', utc_date_time)

    random_value = ''.join(["{}".format(randint(0, 9)) for num in range(10)])
    frame.add_tag('uuid', f'NEFPipelines-{utc_date_time}-{random_value}')

    loop = Loop.from_scratch('nef_run_history')
    frame.add_loop(loop)

    loop.add_tag('run_number')
    loop.add_tag('program_name')
    loop.add_tag('program_version')
    loop.add_tag('script_name')

    loop.add_data_by_tag('run_number', 1)
    loop.add_data_by_tag('program_name', NEF_PIPELINES)
    loop.add_data_by_tag('program_version', PIPELINES_VERSION)
    loop.add_data_by_tag('script_name', 'header.p')

    return result


def create_parser():

    parser = ArgumentParser(description='create a nef file header')
    parser.add_argument('--name', type=str, dest='name', default='new',
                        help='name for the entry', metavar='<ENTRY-NAME>')

    return parser


if __name__ == '__main__':

    command_parser = create_parser()
    command_line_args = command_parser.parse_args()

    entry = main(command_line_args)

    print(entry)
