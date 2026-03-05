import sys
from pathlib import Path
from typing import Dict, List, Tuple, Union

import typer
from pynmrstar import Entry, Saveframe
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.sequence_lib import (
    TRANSLATIONS_3_1_PROTEIN,
    sequence_from_entry,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.structures import ShiftData
from nef_pipelines.lib.util import (
    STDIN,
    STDOUT,
    exit_if_file_has_bytes_and_no_force,
    warn,
)
from nef_pipelines.transcoders.sparky import export_app

STDOUT_STR = str(STDOUT)
DEFAULT_OUTPUT_TEMPLATE = "{shift_list}_{chain}_shifts.txt"


@export_app.command()
def shifts(
    input_path: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [stdin = -] [default: -]",
    ),
    output: str = typer.Option(
        DEFAULT_OUTPUT_TEMPLATE,
        "-o",
        "--out",
        help="""\
            output filename template {shift_list}_{chain}_shifts.txt or - for stdout
            [default: {shift_list}_{chain}_shifts.txt] [possible values {shift_list}, {chain}, {entry}]
        """,
    ),
    frame_selectors: List[str] = typer.Argument(
        None,
        help="frames to export (wildcards allowed, default: all chemical shift frames)",
        metavar="<frames>",
    ),
    include_negative_residues: bool = typer.Option(
        False,
        "--include-negative-residues",
        help="include shifts with negative residue offsets like 4-1, 5-1 [default: exclude them]",
    ),
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="force overwrite of output file if it exists and isn't empty",
    ),
):
    """- write sparky shift lists

    Export NEF chemical shift frames to Sparky shift list format (.txt files).
    One file per chain will be created using the output template.

    TODO: plan add ability to offset unassigned
    TODO: plan add --full-assignments option
    TODO: plan add --no-chains option
    TODO: plan add --chain-separator option
    TODO: plan add --chain option for single chain export
    TODO: plan what to do on non shift frame... policy
    TODO: plan what to do if no shift frames seletced
    """

    entry = read_entry_from_file_or_stdin_or_exit_error(input_path)

    if not frame_selectors:
        frame_selectors = ["*"]

    shift_frames = _select_shift_frames(entry, frame_selectors)

    if not shift_frames:
        frame_selectors_list = ", ".join(frame_selectors)
        warn(
            f"No chemical shift frames found matching selectors {frame_selectors_list}"
        )

    output_to_stdout = output == "-" or output == STDOUT_STR

    entry, shift_files = pipe(
        entry,
        shift_frames,
        output,
        include_negative_residues,
    )

    _write_output_files(shift_files, output_to_stdout, force)

    if not sys.stdout.isatty() and not output_to_stdout:
        print(entry)


def pipe(
    entry: Entry,
    frames: List[Saveframe],
    output_template: str,
    include_negative_residues: bool = False,
) -> Tuple[Entry, Dict[str, str]]:
    """Export NEF chemical shift frames to Sparky shift format.

    Args:
        entry: NEF entry containing chemical shift frames
        frames: Saveframes to export
        output_template: Template for output filenames
        include_negative_residues: Include shifts with negative residue offsets

    Returns:
        Tuple of (entry, dict of {filename: content})
    """
    output_files = {}

    entry_name = entry.entry_id

    sequence = sequence_from_entry(entry)
    sequence_lookup = sequence_to_residue_name_lookup(sequence)

    shifts = nef_frames_to_shifts(frames)

    if not include_negative_residues:
        shifts = _filter_negative_residues(shifts)

    chains_data = _group_shifts_by_chain_and_frame(shifts)

    for (frame_name, chain_code), chain_shifts in chains_data.items():
        filename = _build_filename(output_template, frame_name, chain_code, entry_name)
        content = _format_sparky_shifts(chain_shifts, sequence_lookup)
        output_files[filename] = content

    return entry, output_files


def _select_shift_frames(entry: Entry, frame_selectors: List[str]) -> List[Saveframe]:
    """Select chemical shift frames matching selectors."""

    all_frames = select_frames(entry, frame_selectors)

    shift_frames = select_frames(
        entry, ["nef_chemical_shift_list"], SelectionType.CATEGORY
    )

    shift_frame_names = {frame.name for frame in shift_frames}
    result = [frame for frame in all_frames if frame.name in shift_frame_names]

    return result


def _group_shifts_by_chain_and_frame(
    shifts: List[ShiftData],
) -> Dict[Tuple[str, str], List[ShiftData]]:
    """Group shifts by frame name and chain code."""

    chains_data = {}

    for shift in shifts:
        chain_code = shift.atom.residue.chain_code
        if chain_code == UNUSED or not chain_code:
            chain_code = "A"

        frame_name = shift.frame_name if shift.frame_name else "default"

        key = (frame_name, chain_code)

        if key not in chains_data:
            chains_data[key] = []

        chains_data[key].append(shift)

    return chains_data


def _format_sparky_shifts(
    shifts: List[ShiftData], sequence_lookup: Dict[Tuple[str, str], str]
) -> str:
    """Convert shift data to Sparky shift format.

    Args:
        shifts: List of shift data to format
        sequence_lookup: Lookup dict for residue names

    Returns:
        Formatted shift list as string
    """
    headers = ["Group", "Atom", "Nuc", "Shift", "SDev", "Assignments"]

    table = []
    for shift in shifts:
        row = _build_shift_row(shift, sequence_lookup)
        table.append(row)

    result = tabulate(table, headers=headers, tablefmt="plain")

    return result


def _build_shift_row(
    shift: ShiftData, sequence_lookup: Dict[Tuple[str, str], str]
) -> List[str]:
    """Build a single shift data row for tabulation.

    Args:
        shift: Shift data to format
        sequence_lookup: Lookup dict for residue names

    Returns:
        List of formatted values for the row
    """
    residue = shift.atom.residue
    sequence_code = residue.sequence_code
    chain_code = residue.chain_code
    residue_name = residue.residue_name
    atom_name = shift.atom.atom_name
    value = shift.value
    value_uncertainty = shift.value_uncertainty
    element = shift.atom.element
    isotope_number = shift.atom.isotope_number

    base_sequence_code, offset = _parse_sequence_code_and_offset(sequence_code)

    residue_1let = _convert_residue_to_1_letter(
        residue_name, chain_code, base_sequence_code, sequence_lookup
    )

    if offset != 0:
        group = f"{residue_1let}{base_sequence_code}{offset}"
    else:
        group = f"{residue_1let}{sequence_code}"

    if isotope_number and isotope_number != UNUSED:
        nucleus = f"{isotope_number}{element}"
    else:
        nucleus = element if element != UNUSED else ""

    if value_uncertainty == UNUSED or value_uncertainty is None:
        sdev = "0.000"
    else:
        try:
            sdev = f"{float(value_uncertainty):.3f}"
        except (ValueError, TypeError):
            sdev = "0.000"

    try:
        shift_val = f"{float(value):.3f}"
    except (ValueError, TypeError):
        shift_val = "0.000"

    assignments = "1"

    return [group, atom_name, nucleus, shift_val, sdev, assignments]


# TODO this should be library code...
def _has_offset(sequence_code: Union[str, int]) -> bool:
    """Check if sequence code has an offset like '10-1' or '10+1'.

    TODO: move this code to shift_lib and generalise

    Args:
        sequence_code: Sequence code to check

    Returns:
        True if sequence code contains an offset
    """
    seq_str = str(sequence_code)
    for separator in ["-", "+"]:
        if separator in seq_str:
            parts = seq_str.rsplit(separator, 1)
            if (
                len(parts) == 2
                and parts[0]
                and parts[0].lstrip("-+").isdigit()
                and parts[1].isdigit()
            ):
                return True
    return False


# TODO this should be library code...
def _parse_sequence_code_and_offset(
    sequence_code: Union[str, int]
) -> Tuple[Union[str, int], int]:
    """Parse sequence code with offset like '10-1' into base and offset.

    Args:
        sequence_code: Sequence code that may contain offset notation

    Returns:
        Tuple of (base_sequence_code, offset)
    """
    seq_str = str(sequence_code)

    for separator, sign in [("-", -1), ("+", 1)]:
        if separator in seq_str:
            parts = seq_str.rsplit(separator, 1)
            if (
                len(parts) == 2
                and parts[0]
                and parts[0].lstrip("-+").isdigit()
                and parts[1].isdigit()
            ):
                base_seq = parts[0]
                if base_seq.lstrip("-+").isdigit():
                    base_seq = int(base_seq)
                return base_seq, sign * int(parts[1])

    return sequence_code, 0


def _filter_negative_residues(shifts: List[ShiftData]) -> List[ShiftData]:
    """Filter out shifts with negative residue offsets.

    Args:
        shifts: List of shift data

    Returns:
        Filtered list excluding shifts with residue offsets
    """
    return [
        shift for shift in shifts if not _has_offset(shift.atom.residue.sequence_code)
    ]


def _convert_residue_to_1_letter(
    residue_3let: str,
    chain_code: str,
    sequence_code: Union[str, int],
    sequence_lookup: Dict[Tuple[str, str], str],
) -> str:
    """Convert 3-letter residue code to 1-letter code with fallback lookup.

    Args:
        residue_3let: 3-letter residue code
        chain_code: Chain code for lookup
        sequence_code: Sequence code (base residue number)
        sequence_lookup: Lookup dict from molecular system

    Returns:
        1-letter residue code
    """
    if not residue_3let or residue_3let == UNUSED:
        residue_3let = sequence_lookup.get((chain_code, str(sequence_code)))

        if not residue_3let or residue_3let == UNUSED:
            return "X"

    residue_upper = residue_3let.upper()

    if residue_upper in TRANSLATIONS_3_1_PROTEIN:
        return TRANSLATIONS_3_1_PROTEIN[residue_upper]
    else:
        return residue_3let


def _build_filename(
    template: str, shift_list_name: str, chain_code: str, entry_name: str
) -> str:
    """Build output filename from template."""

    if template == "-" or template == STDOUT_STR:
        return shift_list_name

    filename = template.format(
        shift_list=shift_list_name, chain=chain_code, entry=entry_name
    )

    return filename


# TODO should be lib utility code
def _write_output_files(
    output_files: Dict[str, str], output_to_stdout: bool, force: bool
) -> None:
    """Write shift files to disk or stdout."""

    if output_to_stdout:
        for content in output_files.values():
            print(content)
    else:
        for filename, content in output_files.items():
            exit_if_file_has_bytes_and_no_force(Path(filename), force)
            with open(filename, "w") as f:
                f.write(content)
