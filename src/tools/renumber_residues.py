#!/usr/bin/env python3
# Importing libraries
import argparse
import fcntl
import os
import sys

from pynmrstar import Entry

CHAIN_CODE = "chain_code"

SEQUENCE_CODE = "sequence_code"

parser = None

EXIT_ERROR = 1


def exit_error(msg):
    if parser:
        parser.print_help()
    print()
    print(f"ERROR: {msg}")
    print("exiting...")
    sys.exit(EXIT_ERROR)


def offset_residue_numbers(entry, chain, offset):
    for frame_data in entry.frame_dict.values():
        for loop_data in frame_data.loop_dict.values():
            if SEQUENCE_CODE in loop_data.tags:
                sequence_index = loop_data.tag_index(SEQUENCE_CODE)
                chain_index = loop_data.tag_index(CHAIN_CODE)
                for line in loop_data:
                    if line[chain_index] == chain:
                        sequence = line[sequence_index]
                        if "@" not in sequence:
                            try:
                                sequence = int(sequence)
                            except ValueError:
                                pass
                        if isinstance(sequence, int):
                            sequence = sequence + offset
                            line[sequence_index] = str(sequence)


def read_args():
    global parser
    parser = argparse.ArgumentParser(
        description="Add chemical shift errors to a NEF file"
    )
    parser.add_argument(
        "-c",
        "--chain",
        metavar="CHAIN",
        type=str,
        default="A",
        dest="chain",
        help="chain in which to offset residue numbers",
    )
    parser.add_argument(
        "-o",
        "--offset",
        metavar="OFFSET",
        type=int,
        default=0,
        dest="offset",
        help="offset to add to residue numbers",
    )
    parser.add_argument(metavar="FILES", nargs=argparse.REMAINDER, dest="files")

    return parser.parse_args()


def check_stream():
    # make stdin a non-blocking file
    fd = sys.stdin.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    try:
        result = sys.stdin.read()
    except Exception:
        result = ""

    return result


if __name__ == "__main__":

    args = read_args()

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
                entries.append(Entry.from_string(lines))
            else:
                exit_error("Error: input appears to be empty")
        else:
            for file in args.files:
                entries.append(Entry.from_file(file))
    except OSError as e:
        msg = f"couldn't open target nef file because {e}"
        exit_error(msg)

    for entry in entries:
        offset_residue_numbers(entry, args.chain, args.offset)

        # print(entry)
