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

parser = None
EXIT_ERROR = 1

def list_frames(entry, file_name):

    print(f'file name: {file_name}')
    print()


    for frame_data in entry.frame_dict.values():
        category = frame_data.category

        category_length =len(category)

        frame_id = frame_data.name[category_length:].lstrip('_')
        frame_id=frame_id.strip()
        frame_id = frame_id if len(frame_id) > 0 else "''"

        print(f'{frame_id} [{category}]')

        for loop in frame_data.loops:
            print(f'    {loop.category}')
        print()


def exit_error(msg):
        if parser:
            parser.print_help()
        print()
        print(f'ERROR: {msg}')
        print('exiting...')
        sys.exit(EXIT_ERROR)

def check_stream():
    # make stdin a non-blocking file
    # fd = sys.stdin.fileno()
    # fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    # fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    try:
        result = sys.stdin.read()
    except:
        result = ''

    return result

def read_args():
    global parser
    parser = argparse.ArgumentParser(description='List frames in a NEF file')
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
            print(lines)
            if len(lines) != 0:
                entries.append((Entry.from_string(lines), '< stdin'))
            else:
                exit_error(("Error: input appears to be empty"))
        else:
            for file in args.files:
                entries.append((Entry.from_file(file), file))
    except OSError as e:
        msg = f"couldn't open target nef file because {e}"
        exit_error(msg)

    for entry, file in entries:
        list_frames(entry, file)

        # print(entry)