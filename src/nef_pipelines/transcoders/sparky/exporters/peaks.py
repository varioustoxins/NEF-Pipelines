# TODO move some of this to a spark lib
import re
import sys
from enum import auto
from os.path import commonprefix
from pathlib import Path
from typing import Dict, List, Tuple

import typer
from pynmrstar import Entry, Loop
from strenum import LowercaseStrEnum
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.peak_lib import frame_to_peaks
from nef_pipelines.lib.sequence_lib import TRANSLATIONS_3_1_PROTEIN
from nef_pipelines.lib.structures import NewPeak
from nef_pipelines.lib.util import (
    STDIN,
    STDOUT,
    exit_error,
    is_float,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.sparky import export_app

STARS_30 = "*" * 30

STDOUT_STR = str(STDOUT)


FILE_NAME_TEMPLATE_HELP = """\
    the template for the filename to export to %s will get replaced by the axis_name of the peak
    frame. - will write to stdout.
"""


class SparkyPeaksExportException(Exception):
    pass


class OverlappingChainsException(SparkyPeaksExportException):
    pass


SPECTRUM_CATEGORY = "nef_nmr_spectrum"
FULL_ASSIGNMENTS_HELP = """
    print full assignments of the form PR_36N-PR_36H [generally assignments are printed in the form PR_36N-H if all the
    the residues in the assignment are the same]
"""
ADD_DATA_HELP = "don't include the data string before the volume and height columns"

NO_CHAINS_HELP = "don't include chains in the output [this will fail warnings if try to output more than one chain...]"

NO_NEGATIVES_HELP = (
    "don't include information on shifts from negative nmr_residues "
    "[default: @-.@65-1..CA -> PR_65p1CA with this option @-.@65-1..CA -> ?CA]"
)

DISCARD_ASSIGNMENTS_HELP = (
    "discard the peak assignments. note: peaks unassign provides more options"
)


class SUPRESSABLE_COLUMNS(LowercaseStrEnum):
    ASSIGNMENT = auto()
    HEIGHT = auto()
    VOLUME = auto()


COLUMNS_TO_SUPPRESS_HELP = f"""
    name columns to suppress in the output [{', '.join(SUPRESSABLE_COLUMNS)}], can be called multiple times or with a
    comma sepatated list [no spaces!]
"""

DEFAULT_CHAIN_SEPARATOR = "."


# noinspection PyUnusedLocal
@export_app.command()
def peaks(
    file_name_template: str = typer.Option(
        "%s.txt",
        help=FILE_NAME_TEMPLATE_HELP,
        metavar="<peak-file.xpk>",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    frame_selectors: List[str] = typer.Argument(
        None, help="the names of the frames to export", metavar="<frames>"
    ),
    discard_assignments: bool = typer.Option(False, help=DISCARD_ASSIGNMENTS_HELP),
    full_assignments: bool = typer.Option(False, help=FULL_ASSIGNMENTS_HELP),
    add_data: bool = typer.Option(False, help=ADD_DATA_HELP),
    no_chains: bool = typer.Option(False, help=NO_CHAINS_HELP),
    chain_separator: str = typer.Option(
        DEFAULT_CHAIN_SEPARATOR, help="characters used to separate chains from residues"
    ),
    no_negative_residues: bool = typer.Option(False, help=NO_NEGATIVES_HELP),
    columns_to_suppress: List[str] = typer.Option(
        [], "--suppress-column", help=COLUMNS_TO_SUPPRESS_HELP
    ),
    # no_volume: bool = typer.Option(
    #     False, help="don't include a volume column in the output"
    # ),
    # no_height: bool = typer.Option(
    #     False, help="don't include a height column in the output"
    # ),
    # no_assignment: bool = Typer
):
    """-  write sparky peaks"""

    columns_to_suppress = parse_comma_separated_options(columns_to_suppress)

    output_to_files = file_name_template != STDOUT_STR

    frame_selectors = parse_comma_separated_options(frame_selectors)

    if len(frame_selectors) == 0:
        frame_selectors = [
            "*",
        ]

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    selected_frame_names = [
        frame.name for frame in select_frames_by_name(entry, frame_selectors)
    ]

    _if_no_frames_selected_exit(frame_selectors, selected_frame_names)

    _if_multiple_frame_and_no_template_exit_error(
        file_name_template, selected_frame_names
    )

    frame_name_to_file_name = _build_file_names(
        file_name_template, selected_frame_names
    )

    try:
        entry, sparky_tables = pipe(
            entry,
            selected_frame_names,
            include_assignments=not discard_assignments,
            include_full_assignments=full_assignments,
            show_data_tag_in_header=add_data,
            chain_separator=chain_separator,
            no_negative_pseudo_residues=no_negative_residues,
            no_chains=no_chains,
            columns_to_suppress=columns_to_suppress,
        )
    except SparkyPeaksExportException as e:
        exit_error(str(e))

    sparky_tables = _map_frame_names_to_paths_if_required(
        sparky_tables, frame_name_to_file_name, output_to_files
    )

    _write_output_tables(sparky_tables, output_to_files)

    _output_entry_if_required(entry, output_to_files)


def _output_entry_if_required(entry, output_to_files):

    if (not sys.stdout.isatty()) and output_to_files:
        print(entry)


def _write_output_tables(sparky_lines, output_to_files):

    if output_to_files:
        _write_results_to_files(sparky_lines)
    else:
        _print_results_to_stderr(sparky_lines)


def _map_frame_names_to_paths_if_required(
    sparky_lines, frame_name_to_file_name, output_to_files
):
    if output_to_files:
        sparky_lines = {
            frame_name_to_file_name[frame_name]: header_and_lines
            for frame_name, header_and_lines in sparky_lines.items()
        }
    return sparky_lines


def _write_results_to_files(sparky_lines):
    for file_name, header_and_lines in sparky_lines.items():
        with open(file_name, "w") as fp:
            _print_table(*sparky_lines[file_name], fp)


def _print_results_to_stderr(sparky_lines):

    for frame_name, header_and_lines in sparky_lines.items():
        header = f"{STARS_30} {frame_name} {STARS_30}"

        print(header, file=sys.stderr)

        print(file=sys.stderr)

        _print_table(*header_and_lines, sys.stderr)

        print(file=sys.stderr)

    if len(sparky_lines) > 0:
        trailer = f'{STARS_30}*{"*" * len(frame_name)}*{STARS_30}'
        print(trailer, file=sys.stderr)


def _build_file_names(file_name_template, selected_frame_names):
    if "%s" not in file_name_template and file_name_template != "-":
        return {selected_frame_names[0]: file_name_template}
    elif file_name_template == "-":
        return {frame_name: frame_name for frame_name in selected_frame_names}
    else:
        return {
            frame_name: file_name_template % frame_name
            for frame_name in selected_frame_names
        }


def _if_no_frames_selected_exit(frame_selectors, selected_frame_names):
    if len(selected_frame_names) == 0:
        msg = f"""\
            WARNING []: no spectrum frames were selected by the selectors {' '.join(frame_selectors)}
        """
        print(msg, file=sys.stderr)
        exit(0)


def _if_multiple_frame_and_no_template_exit_error(
    file_name_template, selected_frame_names
):
    if file_name_template != "-":
        if "%s" not in file_name_template and len(selected_frame_names) > 1:
            exit_error(
                f"%s is not in the filename template and there is more than one file, template {file_name_template}"
            )


def _print_table(header, lines, file_pointer):

    table = [header, [""], *lines]
    alignments = ["right"] * len(header)
    alignments[0] = "left"
    print(tabulate(table, colalign=alignments, tablefmt="plain"), file=file_pointer)


def _if_chains_overlap_raise(peaks):
    peak_residues_by_chain = {}
    for peak in peaks:
        for shift in peak.shifts:
            chain_code = shift.atom.residue.chain_code
            sequence_code = shift.atom.residue.sequence_code

            peak_residues_by_chain.setdefault(chain_code, set()).add(sequence_code)

    residue_intersection = set.intersection(*peak_residues_by_chain.values())
    if len(peak_residues_by_chain) > 1:
        msg = f"""
            you asked to ignore chains but there is an overlap in the sequence codes between the chains present
            the chain codes  are {' '.join(peak_residues_by_chain.keys())} the overlapping sequence codes are
            {' '.join([str(residue) for residue in residue_intersection])}
        """

        raise OverlappingChainsException(msg)


def pipe(
    entry: Entry,
    selected_frame_names: List[str],
    include_assignments=True,
    include_full_assignments: bool = False,
    show_data_tag_in_header=False,
    chain_separator=":",
    no_negative_pseudo_residues=False,
    no_chains=False,
    columns_to_suppress: List[SUPRESSABLE_COLUMNS] = (),
) -> Tuple[Entry, Dict[str, List[str]]]:

    selected_frame_names = set(selected_frame_names)

    spectrum_frames = entry.get_saveframes_by_category(SPECTRUM_CATEGORY)

    names_and_frames = {
        frame.name: frame
        for frame in spectrum_frames
        if frame.name in selected_frame_names
    }

    sparky_lines = {}
    for frame_name, frame in names_and_frames.items():

        peaks = frame_to_peaks(frame)

        if no_chains:
            _if_chains_overlap_raise(peaks)

        sparky_lines[frame_name] = _build_sparky_lines(
            peaks,
            include_assignments=include_assignments,
            abbreviate_assignments=not include_full_assignments,
            show_data_tag_in_header=show_data_tag_in_header,
            chain_sequence_separator=chain_separator,
            no_negative_pseudo_residues=no_negative_pseudo_residues,
            no_chains=no_chains,
            columns_to_suppress=columns_to_suppress,
        )

    return entry, sparky_lines


def _check_column_has_floats(peak_list: List[NewPeak], column_name: str):
    result = False

    for peak in peak_list:

        value = getattr(peak, column_name)
        if value != UNUSED and is_float(value):
            result = True
            break
    return result


def _peak_loop_has_volumes(loop: Loop):
    return _check_column_has_floats(loop, "volume")


def _peak_loop_has_heights(loop: Loop):
    return _check_column_has_floats(loop, "height")


def _build_sparky_lines(
    peaks_list: List[NewPeak],
    include_assignments=False,
    abbreviate_assignments=False,
    show_data_tag_in_header=False,
    chain_sequence_separator=".",
    no_negative_pseudo_residues=False,
    no_chains=False,
    columns_to_suppress=(),
):

    lines = []

    header = []
    if SUPRESSABLE_COLUMNS.ASSIGNMENT not in columns_to_suppress:
        header.append("Assignment")

    if len(peaks_list) > 0:
        num_dimensions = len(peaks_list[0].shifts)

        position_headers = [
            f"w{dimension}" for dimension in range(1, num_dimensions + 1)
        ]

        header.extend(position_headers)

        has_volumes = (
            _peak_loop_has_volumes(peaks_list)
            and SUPRESSABLE_COLUMNS.VOLUME not in columns_to_suppress
        )
        has_heights = (
            _peak_loop_has_heights(peaks_list)
            and SUPRESSABLE_COLUMNS.HEIGHT not in columns_to_suppress
        )

        if (has_heights or has_volumes) and show_data_tag_in_header:
            header.append("Data")

        if has_heights:
            header.append("Height")

        if has_volumes:
            header.append("Volume")

        #
        # # could check for line widths here
        # # format for line widths is lw1 (hz)
        #

        for peak in peaks_list:
            out_row = []
            lines.append(out_row)

            assignments = []

            number_residues = len(
                set([shift.atom.residue.sequence_code for shift in peak.shifts])
            )
            number_chains = len(
                set([shift.atom.residue.chain_code for shift in peak.shifts])
            )

            can_abbreviate = number_residues == 1 and number_chains == 1

            if SUPRESSABLE_COLUMNS.ASSIGNMENT not in columns_to_suppress:
                if include_assignments:
                    for atom in [shift.atom for shift in peak.shifts]:

                        chain_code = atom.residue.chain_code
                        sequence_code = str(atom.residue.sequence_code)
                        residue_name = atom.residue.residue_name
                        atom_name = atom.atom_name
                        current_chain_sequence_separator = chain_sequence_separator

                        if chain_code == "@-":
                            chain_code = ""
                        elif chain_code.startswith("#"):
                            chain_code = f"PC_{chain_code}"
                        elif chain_code == UNUSED or no_chains:
                            chain_code = ""
                            current_chain_sequence_separator = ""

                        if not chain_code or len(chain_code) == 0:
                            current_chain_sequence_separator = ""

                        if sequence_code.endswith("-1"):
                            if no_negative_pseudo_residues:
                                sequence_code = "?"
                            else:
                                sequence_code = f"{sequence_code[:-2]}"
                                atom_name = f"{atom_name}m1"
                            can_abbreviate = False

                        if sequence_code.startswith("@"):
                            sequence_code = f"PR_{sequence_code[1:]}"
                        # if chain_code.startswith('PC_'):
                        #     sequence_code = f'{chain_code}:{sequence_code}'
                        #     chain_sequence_separator = ''

                        if residue_name in TRANSLATIONS_3_1_PROTEIN:
                            residue_name = TRANSLATIONS_3_1_PROTEIN[residue_name]

                        if not residue_name:
                            residue_name = ""

                        group = f"{chain_code}{current_chain_sequence_separator}{residue_name}{sequence_code}"

                        assignment = f"{group}{atom_name}"
                        assignments.append(assignment)

                else:
                    assignments.extend(["?"] * num_dimensions)

                common_prefix = commonprefix(assignments)
                need_to_join = True
                if common_prefix != "?" and abbreviate_assignments and can_abbreviate:

                    split_common_prefix = re.split(r"(\d+)", common_prefix)
                    common_prefix = f"{split_common_prefix[0]}{split_common_prefix[1]}"

                    if len(common_prefix) > 0 and common_prefix != "?":
                        for i, assignment in enumerate(assignments):
                            assignments[i] = assignment[len(common_prefix) :]

                        assignments = f"{common_prefix}{'-'.join(assignments)}"
                        need_to_join = False

                if need_to_join:
                    assignments = "-".join(assignments)

                out_row.append(assignments)

            out_row.extend([f"{shift.value:7.3f}" for shift in peak.shifts])

            if (has_heights or has_volumes) and show_data_tag_in_header:
                out_row.append("")
            if has_heights:
                height = peak.height if peak.height != UNUSED else 0.000
                out_row.append(height)

            if has_volumes:
                volume = peak.volume if peak.volume != UNUSED else 0.000
                out_row.append(volume)

    return header, lines
