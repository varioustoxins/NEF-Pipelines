#!/usr/bin/env python3
# Importing libraries
import argparse
import fcntl
import os
import sys
from fnmatch import fnmatch

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


target_frames = {
    "nef_chemical_shift_list": ["_nef_chemical_shift"],
    "nef_nmr_spectrum": ["_nef_peak"],
}


def offset_chemical_shifts(entry, args):

    if not args.target:
        exit_error(
            "WARNING: i need a target nucleus or atom name provided by -t / --target,  such as *CB* or 13C"
        )

    target_loops = []
    for frame_data in entry.frame_dict.values():
        if (frame_category := frame_data.category) in target_frames:
            for loop in frame_data.loops:
                if (loop_category := loop.category) in target_frames[frame_category]:
                    target_loops.append(((frame_category, loop_category), loop))

    for loop_type, target_loop in target_loops:
        if loop_type == ("nef_chemical_shift_list", "_nef_chemical_shift"):
            chain_index = target_loop.tag_index("chain_code")
            value_index = target_loop.tag_index("value")
            element_index = target_loop.tag_index("element")
            isotope_index = target_loop.tag_index("isotope_number")
            atom_name_index = target_loop.tag_index("atom_name")

            for line in target_loop:
                isotope = line[isotope_index] + line[element_index]
                chain = line[chain_index]
                value = line[value_index]
                atom_name = line[atom_name_index]

                if chain == args.chain_code:
                    if args.target == isotope or fnmatch(atom_name, args.target):
                        value = float(value) + args.offset
                        line[value_index] = value

        if loop_type == ("nef_nmr_spectrum", "_nef_peak"):
            exit_error("Error: not implemented for peak lists yet")

        # for loop_data in frame_data.loop_dict.values():
        #     print(loop_data.category)
        # if SEQUENCE_CODE in loop_data.tags:
        #     sequence_index = loop_data.tag_index(SEQUENCE_CODE)
        #     chain_index = loop_data.tag_index(CHAIN_CODE)
        #     for line in loop_data:
        #         if line[chain_index] == chain:
        #             sequence = line[sequence_index]
        #             if  '@' not in sequence:
        #                 try:
        #                     sequence = int(sequence)
        #                 except ValueError:
        #                     pass
        #             if isinstance(sequence, int):
        #                 sequence = sequence + offset
        #                 line[sequence_index] = str(sequence)


def read_args():
    global parser
    parser = argparse.ArgumentParser(description="Offset chemical shifts")
    parser.add_argument(
        "-c",
        "--chain",
        metavar="CHAIN",
        type=str,
        default="A",
        dest="chain",
        help="chain in which to offset shifts",
    )
    parser.add_argument(
        "-o",
        "--offset",
        metavar="OFFSET",
        type=float,
        default=0.0,
        dest="offset",
        help="offset to add to shifts",
    )
    parser.add_argument(
        "-t",
        "--target",
        metavar="TARGET",
        type=str,
        default=None,
        dest="target",
        help="nucleus or atom to offset",
    )
    parser.add_argument(
        "-s",
        "--spectra",
        metavar="OFFSET",
        type=str,
        default="*",
        dest="spectra",
        action="append",
        nargs="+",
        help="nucleus  or atom to offset",
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
        offset_chemical_shifts(entry, args)

        print(entry)
