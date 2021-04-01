#!/usr/bin/env python3
# Importing libraries
import fcntl
import os
import sys
import termios
import tty
from fnmatch import fnmatch

from pynmrstar import Entry
import argparse
from tabulate import tabulate


parser = None
EXIT_ERROR = 1

def tabulate_frames(entry, file_name, args):

    print(f'file name: {file_name}')


    frames = []
    for frame_data in entry.frame_dict.values():
        add_frame = False

        if not args.select:
            add_frame = True

        if not add_frame and frame_data.category in args.select:
            add_frame = True

        if not add_frame and frame_data.name in args.select:
            add_frame=True

        if add_frame:
            frames.append(frame_data)

    for frame_data in frames:
        category = frame_data.category

        category_length =len(category)

        frame_id = frame_data.name[category_length:].lstrip('_')
        frame_id = frame_id.strip()
        frame_id = frame_id if len(frame_id) > 0 else "''"



        for loop in frame_data.loops:
            print()
            print(f'{frame_id} [{category}] / {loop.category}')
            print()


            table = []
            headers = loop.tags
            for line in loop.data:
                row = list(line)
                table.append(row)

            print(tabulate(table, headers=headers,tablefmt='plain'))
            print()
        print()


def exit_error(msg):
        if parser:
            parser.print_help()
        print()
        print(f'ERROR: {msg}')
        print('exiting...')
        sys.exit(EXIT_ERROR)

def check_stream():
    # # make stdin a non-blocking file
    # fd = sys.stdin.fileno()
    # fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    # fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    try:
        result = sys.stdin.read()
    except Exception as e:
        print(e)
        result = ''

    return result

def read_args():
    global parser
    parser = argparse.ArgumentParser(description='Tabulate frames and loops in a NEF file')
    parser.add_argument('-s', '--select', metavar='select', type=str, default=None, dest='select',
                        nargs='?', help='nucleus or atom to offset')
    parser.add_argument(metavar='FILES', nargs=argparse.REMAINDER, dest='files')

    return parser.parse_args()

if __name__ == '__main__':

    args = read_args()

    print(args)

    is_tty = sys.stdin.isatty()

    if is_tty and len(args.files) == 0:
        parser.print_help()
        print()
        msg = """I require at least 1 argument or input stream with a chemical_shift_list frame"""

        exit_error(msg)

    entries = []
    try:
        if len(args.files) == 0:
            lines = check_stream()
            if len(lines) != 0:
                entries.append((Entry.from_string(lines), '< stdin'))
            else:
                exit_error(("Error: input appears to be empty"))
        else:
            for file in args.files:
                if file != '--':
                    entries.append((Entry.from_file(file), file))
    except OSError as e:
        msg = f"couldn't open target nef file because {e}"
        exit_error(msg)

    for entry, file in entries:
        tabulate_frames(entry, file, args)

        # print(entry)