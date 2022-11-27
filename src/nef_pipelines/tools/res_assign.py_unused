#!/usr/bin/env python3
import argparse
import operator
import sys
from dataclasses import dataclass

from numpy import average
from pynmrstar import Entry

parser = None

EXIT_ERROR = 1


def exit_error(msg):

    print(f"ERROR: {msg}")
    print("exiting...")
    sys.exit(EXIT_ERROR)


@dataclass(frozen=True)
class Assignment:
    assignment: int
    fixed: bool = False
    merit: float = 0.0


def read_args():
    global parser
    parser = argparse.ArgumentParser(
        description="Assign a NEF file based on output from an assignment in NEF format"
    )
    parser.add_argument(
        "-t",
        "--target",
        metavar="TARGET_NEF",
        type=str,
        default=None,
        dest="target",
        help="target nef file to assign",
    )
    parser.add_argument(metavar="ASSIGNMENT", nargs=1, dest="assignment")

    return parser.parse_args()


if __name__ == "__main__":

    args = read_args()

    try:
        nef_target_data = Entry.from_file(args.target)
    except OSError as e:
        msg = f"couldn't open target nef file because {e}"
        exit_error(msg)

    try:
        res_assign = Entry.from_file(args.assignment[0])
    except OSError as e:
        msg = f"couldn't open residue assignments file because {e}"
        exit_error(msg)

    shift_list_frames = []
    for frame_name in nef_target_data.frame_dict:
        if "nef_chemical_shift_list" in frame_name:
            shift_list_frames.append(frame_name)

    if "ccpn_residue_assignments" not in res_assign.frame_dict:
        exit_error("res_assign doesn't contain a ccpn_residue_assignments frame")

    residue_assignments = {}
    residue_types = {}

    # TODO need constants for names
    # TODO need a check of required columns
    for loop in res_assign["ccpn_residue_assignments"].loop_dict.values():

        loop_tags = {tag: i for i, tag in enumerate(loop.tags)}

        for line_number, line in enumerate(loop):

            fixed = line[loop_tags["fixed"]].lower() in ("true", ".")

            # need functions to check
            chain = line[loop_tags["chain_code"]]
            residue_number = int(line[loop_tags["residue_number"]])
            residue_type = line[loop_tags["residue_type"]]

            residue_key = chain, residue_number
            residue_types[residue_key] = residue_type

            if not fixed:
                assignment = int(line[loop_tags["assignment"]])
                assigned_residue = int(line[loop_tags["assignment"]])
                merit = float(line[loop_tags["merit"]])

                residue_assignments.setdefault(residue_key, []).append(
                    Assignment(assignment, False, merit)
                )

                if residue_key in residue_types:
                    if (bad_residue_type := residue_types[residue_key]) != residue_type:
                        msg = f"""more than one residue type for assignment
                                   line {line_number}
                                   file {sys.argv[2]}

                                   residue types {bad_residue_type} {residue_type}
                                """

    min_merit = 0.6
    filtered_residue_assignments = {}
    for residue_key, assignments in residue_assignments.items():
        assignments.sort(key=operator.attrgetter("merit"))

        assignment = assignments[0]
        if assignment.merit > min_merit:
            filtered_residue_assignments[residue_key] = assignment


assignment_to_residue = {}
for residue, assignment in filtered_residue_assignments.items():
    assignment_to_residue[assignment] = residue


nmr_residue_to_residue = {}
for assignment, residue in assignment_to_residue.items():

    nmr_residue = "@%i" % assignment.assignment
    nmr_residue_minus_1 = "@%i-1" % assignment.assignment

    nmr_residue_to_residue[nmr_residue] = (*residue, residue_types[residue])

    residue_minus_1 = (residue[0], residue[1] - 1)
    nmr_residue_to_residue[nmr_residue_minus_1] = (
        *residue_minus_1,
        residue_types[residue_minus_1],
    )

# for key, value in nmr_residue_to_residue.items():
#     print(key,value)


class TagIndexKey:
    def __init__(self, tag_indices):
        self._tags_indices = tag_indices

    def __call__(self, data):
        result = []

        for tag_index in self._tags_indices:
            value = data[tag_index]

            try:
                value = int(value)
            except ValueError:
                pass

            if isinstance(value, int):
                result.append((0, value))
            elif isinstance(value, str):
                result.append((1, value))

        return tuple(result)


target_frames = ["nef_chemical_shift_list", "nef_nmr_spectrum"]
for frame_name, frame_data in nef_target_data.frame_dict.items():

    target_type = None
    for target_frame in target_frames:
        if frame_name.startswith(target_frame):
            target_type = target_frame
            break
    # print(frame_name, target_type)

    if target_type == "nef_chemical_shift_list":

        for loop_name, loop_data in frame_data.loop_dict.items():

            sequence_code_index = loop_data.tag_index("sequence_code")
            chain_code_index = loop_data.tag_index("chain_code")
            residue_name_index = loop_data.tag_index("residue_name")
            atom_name_index = loop_data.tag_index("atom_name")

            value_index = loop_data.tag_index("value")
            value_uncertainty_index = loop_data.tag_index("value_uncertainty")

            tagKey = TagIndexKey(
                [chain_code_index, sequence_code_index, atom_name_index]
            )
            for line_number, line in enumerate(loop_data):
                nmr_residue = line[sequence_code_index]

                if nmr_residue in nmr_residue_to_residue:

                    chain_code, residue_number, residue_type = nmr_residue_to_residue[
                        nmr_residue
                    ]

                    line[chain_code_index] = chain
                    line[sequence_code_index] = residue_number
                    line[residue_name_index] = residue_type

            line_by_assignment = {}
            for line_number, line in enumerate(loop_data):
                key = (
                    line[chain_code_index],
                    line[sequence_code_index],
                    line[atom_name_index],
                )
                line_by_assignment.setdefault(key, []).append(line)

            for key, lines in line_by_assignment.items():
                if len(lines) > 1:
                    value = average([float(line[value_index]) for line in lines])
                    uncertainty = average(
                        [float(line[value_uncertainty_index]) for line in lines]
                    )

                    lines[0][value_index] = value
                    lines[0][value_uncertainty_index] = uncertainty
                    for line in lines[1:]:
                        del loop_data.data[loop_data.data.index(line)]

                # elif '@' in nmr_residue:
                #     print(f'WARNING: shift list, nmr residue {nmr_residue} not found in file skipping')

            loop_data.sort_rows(
                tags=["chain_code", "sequence_code", "atom_name"], key=tagKey
            )  # print(line)

    # print (nmr_residue_to_residue)
    if target_type == "nef_nmr_spectrum":

        loop_types = {}

        for loop_name, loop_data in frame_data.loop_dict.items():

            if loop_name == "_nef_peak":

                loop_tags = {tag: i for i, tag in enumerate(loop_data.tags)}

                # print(loop_tags)

                active_indices = []
                for i in range(1, 15):
                    test_name = "atom_name_%i" % i
                    if test_name in loop_tags:
                        active_indices.append(i)

                for data in loop_data:
                    for active_index in active_indices:
                        # print(data)
                        chain_index = loop_tags["chain_code_%i" % active_index]
                        atom_index = loop_tags["atom_name_%i" % active_index]
                        residue_number_index = loop_tags[
                            "sequence_code_%i" % active_index
                        ]
                        residue_type_index = loop_tags["residue_name_%i" % active_index]

                        residue_number = data[residue_number_index]
                        if residue_number in nmr_residue_to_residue:
                            (
                                chain_code,
                                residue_number,
                                residue_type,
                            ) = nmr_residue_to_residue[residue_number]

                            data[chain_index] = chain_code
                            data[residue_number_index] = residue_number
                            data[residue_type_index] = residue_type

                        elif "@" in nmr_residue:
                            print(
                                f"WARNING: spectrum, nmr residue {nmr_residue} not found in file skipping"
                            )

                    # print(data)
    # print(nef_target_data)
    # for active_index in active_indices:

    # tag_indices = set()
    # for tag in loop_tags:
    #     if tag.startswith('position'):
    #         tag_index = tag.split('_')[-1]
    #     # print(tag_index)
    #         tag_indices.add(tag_index)
    # # print('indices',tag_indices)
    # print(loop_data.category)

    # print(loop.tag_index)

    # sequence_code_index = loop_tags['sequence_code']
    # chain_code_index = loop_tags['chain_code']
    # residue_name_index = loop_tags['residue_name']
    # for line_number, line in enumerate(loop_data):
    #     if (nmr_residue := line[sequence_code_index]) in nmr_residue_to_residue:
    #         chain_code, residue_number, residue_type = nmr_residue_to_residue[nmr_residue]

    #         line[chain_code_index] =  chain
    #         line[sequence_code_index] = residue_number
    #         line[residue_name_index] =  residue_type

    # line[sequence]

# should sort rows but need a schema
# for loop in nef_target_data['nef_chemical_shift_list_default']:
#     loop.sort_rows(tags =['chain_code', 'sequence_code'])
print(nef_target_data)

# for frame_name, frame_data in nef_target_data.frame_dict.items():
#
#
#
#
#     for loop_name, loop_data in frame_data.loop_dict.items():
#         print(id(loop_data))
