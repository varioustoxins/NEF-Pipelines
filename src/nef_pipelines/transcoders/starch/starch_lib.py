"""Library functions for parsing STARCH chemical shift files."""

from pathlib import Path
from typing import IO, List

from pynmrstar import Loop

from nef_pipelines.lib.sequence_lib import translate_1_to_3
from nef_pipelines.lib.structures import AtomLabel, Residue, ShiftData
from nef_pipelines.lib.util import exit_error


def parse_starch_shifts(
    shift_file: IO, chain_code: str, file_name: Path
) -> List[ShiftData]:
    """Parse STARCH chemical shift file and return list of ShiftData.

    STARCH files are pseudo-STAR format with:
    - A data_ line at the top
    - Comment blocks (lines starting with #)
    - A loop_ with shift data
    - A stop_ at the end

    This is NOT a valid STAR file, so we strip the data_ line and comments
    before parsing the loop with pynmrstar.

    Args:
        shift_file: File handle to read STARCH data from
        chain_code: Chain code to assign to all shifts
        file_name: Name of the file being parsed (for error messages)

    Returns:
        List of ShiftData objects parsed from the file

    Raises:
        SystemExit: If file format is invalid or cannot be parsed
    """
    content = shift_file.read()

    cleaned_content = _remove_data_line_and_comments(content)

    try:
        loop = Loop.from_string(cleaned_content)
    except Exception as e:
        msg = f"""\
            Error parsing STARCH file {file_name} as STAR loop:
            {e}
        """
        exit_error(msg)

    shifts = _convert_loop_to_shifts(loop, chain_code, file_name)

    return shifts


def _remove_data_line_and_comments(content: str) -> str:
    """Remove data_ line and comment lines from STARCH content.

    Args:
        content: Raw STARCH file content

    Returns:
        Cleaned content with data_ line and comments removed
    """
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("data_"):
            continue

        if stripped.startswith("#"):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _convert_loop_to_shifts(
    loop: Loop, chain_code: str, file_name: Path
) -> List[ShiftData]:
    """Convert pynmrstar Loop to list of ShiftData.

    Expected loop columns (pynmrstar strips the category prefix):
    - ID (sequential ID)
    - Comp_index_ID (residue sequence number)
    - Comp_ID (residue name, 1-letter code)
    - Atom_ID (atom name)
    - Val (chemical shift value)

    Args:
        loop: pynmrstar Loop object containing shift data
        chain_code: Chain code to assign to all shifts
        file_name: Name of file being parsed (for error messages)

    Returns:
        List of ShiftData objects
    """
    shifts = []

    required_tags = {"Comp_index_ID", "Comp_ID", "Atom_ID", "Val"}

    loop_tags = set(loop.tags)
    missing_tags = required_tags - loop_tags

    if missing_tags:
        msg = f"""\
            STARCH file {file_name} is missing required tags:
            {', '.join(sorted(missing_tags))}
            Found tags: {', '.join(sorted(loop.tags))}
        """
        exit_error(msg)

    tag_to_index = {tag: i for i, tag in enumerate(loop.tags)}

    for row in loop.data:
        try:
            sequence_code = int(row[tag_to_index["Comp_index_ID"]])
            residue_name_1let = row[tag_to_index["Comp_ID"]]
            atom_name = row[tag_to_index["Atom_ID"]]
            shift_value = float(row[tag_to_index["Val"]])

            residue_name_3let = translate_1_to_3(residue_name_1let)[0]

            residue = Residue(
                chain_code=chain_code,
                sequence_code=sequence_code,
                residue_name=residue_name_3let,
            )
            atom = AtomLabel(residue, atom_name)
            shift = ShiftData(atom=atom, value=shift_value)
            shifts.append(shift)

        except (ValueError, IndexError) as e:
            msg = f"""\
                Error converting STARCH loop row to shift data in {file_name}:
                Row: {row}
                Error: {e}
            """
            exit_error(msg)

    return shifts
