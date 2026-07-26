from dataclasses import dataclass
from enum import auto
from pathlib import Path
from textwrap import dedent
from typing import List, Optional

import typer
from pynmrstar import Loop
from strenum import LowercaseStrEnum

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    MoleculeType,
    get_chain_code_iter,
    guess_molecule_type,
    translate_1_to_3,
)
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import (
    AtomLabel,
    LineInfo,
    NEFPipelinesException,
    Residue,
    ShiftData,
    ShiftList,
)
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    is_float,
    is_int,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.starch import import_app


class SequenceSource(LowercaseStrEnum):
    """Source for sequence numbering and atom naming in STARCH files.

    AUTH: Use author-provided IDs (Auth_seq_ID, Auth_comp_ID, Auth_atom_ID)
    SYSTEM: Use system-generated IDs (Seq_ID, Comp_ID, Atom_ID)
    """

    AUTH = auto()
    SYSTEM = auto()


@dataclass
class ColumnSelector:
    """Result of column selection with name and index for traceability.

    Attributes:
        name: The column name that was selected (or None if not found)
        index: The column index (or None if not found)
    """

    name: Optional[str]
    index: Optional[int]


@dataclass
class StarchParseException(NEFPipelinesException):
    """Exception raised when parsing STARCH files fails.

    Attributes:
        reason: Human-readable error message
        line_info: Optional LineInfo with file location details
    """

    reason: str
    line_info: Optional[LineInfo] = None

    def __str__(self):
        """Format the exception as a string."""
        if self.line_info:
            msg = f"""
                    parsing of the STARCH file failed at line {self.line_info.line_no} \
                    in file {self.line_info.file_name} because {self.reason}
                    the line was:

                    {self.line_info.line}
                """
            msg = dedent(msg)
        else:
            msg = f"parsing of the STARCH file failed because {self.reason}"
        return msg


@dataclass
class StarchUndefinedMoleculeType(StarchParseException):
    """Exception raised when molecule type cannot be determined from STARCH file residue codes.

    Attributes:
        reason: Human-readable error message explaining why molecule type couldn't be determined
        residue_codes: Optional set of residue codes that caused the ambiguity
    """

    residue_codes: Optional[set] = None

    def __str__(self):
        """Format the exception as a string."""
        msg = self.reason
        if self.residue_codes:
            codes_str = ", ".join(sorted(self.residue_codes))
            msg = f"{msg}\nProblematic residue codes: {codes_str}"
        return msg


@import_app.command(no_args_is_help=True)
def shifts(
    chain_codes: List[str] = typer.Option(
        None,
        "--chains",
        help="chain codes as a list of names separated by commas, repeated calls will add further chains [default A]",
        metavar="<CHAIN-CODES>",
    ),
    frame_name: str = typer.Option(
        "starch",
        "-f",
        "--frame-name",
        help="name for the NEF chemical shift frame",
    ),
    molecule_type: Optional[MoleculeType] = typer.Option(
        None,
        "--molecule-type",
        help="molecule type (protein, dna, rna) - will be guessed from residue codes if not specified",
    ),
    sequence_source: SequenceSource = typer.Option(
        SequenceSource.AUTH,
        "--sequence-source",
        help="source for sequence numbering and atom naming: auth (author IDs) or system (system IDs)",
    ),
    input_path: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type STARCH", metavar="<STARCH-shifts>"
    ),
):
    """convert shifts from STARCH file to NEF"""

    chain_codes = parse_comma_separated_options(chain_codes)

    entry = read_or_create_entry_exit_error_on_bad_file(input_path, "starch")

    try:
        entry = pipe(
            entry, chain_codes, frame_name, file_names, molecule_type, sequence_source
        )
    except (StarchParseException, StarchUndefinedMoleculeType) as e:
        exit_error(str(e))

    print(entry)


def pipe(
    entry,
    chain_codes,
    frame_name,
    file_names,
    molecule_type=None,
    sequence_source=SequenceSource.AUTH,
):
    """Import STARCH shift files and add them to the NEF entry.

    Args:
        entry: The NEF Entry to add shifts to
        chain_codes: List of chain codes to assign to each file
        frame_name: Name for the chemical shift frame
        file_names: List of STARCH files to import
        molecule_type: Molecule type (protein, dna, rna) or None to auto-detect
        sequence_source: Source for IDs (AUTH for author IDs, SYSTEM for system IDs)

    Returns:
        The updated Entry with imported shifts

    Raises:
        StarchParseException: If file parsing fails or molecule type cannot be determined
    """
    frames = []

    chain_code_iter = get_chain_code_iter(chain_codes)
    for file_name, chain_code in zip(file_names, chain_code_iter):

        with open(file_name, "r") as shift_file:
            lines = shift_file.readlines()

        file_shifts = _parse_starch_shifts(
            lines, chain_code, file_name, molecule_type, sequence_source
        )

        shift_list = ShiftList(file_shifts)
        frame = shifts_to_nef_frame(shift_list, frame_name)
        frames.append(frame)

    return add_frames_to_entry(entry, frames)


def lines_to_lineinfos(lines, file_name):
    """Convert lines to LineInfo objects.

    Args:
        lines: String or list of lines
        file_name: Name of the source file

    Returns:
        List of LineInfo objects
    """
    if isinstance(lines, str):
        lines_list = lines.split("\n")
    else:
        lines_list = lines

    line_infos = []
    for line_no, line in enumerate(lines_list, start=1):
        if isinstance(line, str) and line.endswith("\n"):
            line = line[:-1]
        line_infos.append(LineInfo(file_name=file_name, line_no=line_no, line=line))

    return line_infos


def _parse_starch_shifts(
    lines,
    chain_code,
    file_name,
    molecule_type=None,
    sequence_source=SequenceSource.AUTH,
):
    """Parse STARCH chemical shift file and return list of ShiftData.

    STARCH files are pseudo-STAR format with:
    - A data_ line at the top
    - Comment blocks (lines starting with #)
    - A loop_ with shift data
    - A stop_ at the end

    This is NOT a valid STAR file, so we strip the data_ line and comments
    before parsing the loop with pynmrstar.

    Args:
        lines: List of lines from STARCH file
        chain_code: Chain code to assign to all shifts
        file_name: Name of the file being parsed (for error messages)
        molecule_type: Molecule type or None to auto-detect
        sequence_source: Source for IDs (AUTH for author IDs, SYSTEM for system IDs)

    Returns:
        List of ShiftData objects parsed from the file

    Raises:
        StarchParseException: If file format is invalid or molecule type cannot be determined
    """
    line_infos = lines_to_lineinfos(lines, file_name)
    data_line_infos = _remove_data_line_and_comments(line_infos)

    cleaned_content = "\n".join(
        [data_line_info.line for data_line_info in data_line_infos]
    )
    try:
        loop = Loop.from_string(cleaned_content)
    except Exception as e:
        msg = f"Error parsing STARCH file {file_name} as STAR loop: {e}"
        raise StarchParseException(reason=msg)

    shifts = _convert_loop_to_shifts(
        loop, chain_code, file_name, data_line_infos, molecule_type, sequence_source
    )

    return shifts


def _select_column(
    tag_to_index,
    auth_name,
    system_name,
    fallback_name=None,
    sequence_source=SequenceSource.AUTH,
):
    """Select column based on sequence_source priority.

    Tries columns in priority order and returns the first match found.
    For AUTH mode: Auth_* → system → fallback
    For SYSTEM mode: system → fallback (skips Auth_*)

    Args:
        tag_to_index: Dictionary mapping tag names to indices
        auth_name: Author column name (e.g., "Auth_seq_ID")
        system_name: System column name (e.g., "Seq_ID")
        fallback_name: Optional fallback column name (e.g., "Comp_index_ID")
        sequence_source: SequenceSource.AUTH or SequenceSource.SYSTEM

    Returns:
        ColumnSelector with name and index if found, or ColumnSelector(None, None) if not found

    Examples:
        >>> tags = {"Auth_seq_ID": 0, "Seq_ID": 1, "Comp_index_ID": 2}
        >>> _select_column(tags, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.AUTH)
        ColumnSelector(name="Auth_seq_ID", index=0)
        >>> _select_column(tags, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", SequenceSource.SYSTEM)
        ColumnSelector(name="Seq_ID", index=1)
    """
    if sequence_source == SequenceSource.AUTH:
        # Try Auth first, then system, then fallback
        if auth_name in tag_to_index:
            return ColumnSelector(name=auth_name, index=tag_to_index[auth_name])
        if system_name in tag_to_index:
            return ColumnSelector(name=system_name, index=tag_to_index[system_name])
        if fallback_name and fallback_name in tag_to_index:
            return ColumnSelector(name=fallback_name, index=tag_to_index[fallback_name])
        return ColumnSelector(name=None, index=None)
    else:  # SYSTEM
        # Try system first, then fallback, skip Auth
        if system_name in tag_to_index:
            return ColumnSelector(name=system_name, index=tag_to_index[system_name])
        if fallback_name and fallback_name in tag_to_index:
            return ColumnSelector(name=fallback_name, index=tag_to_index[fallback_name])
        return ColumnSelector(name=None, index=None)


def _remove_data_line_and_comments(line_infos):
    """Remove data_ line and comment lines from STARCH content.

    Args:
        lines: List of lines from STARCH file

    Returns:
        Tuple of (cleaned_content, list of LineInfo for data rows)
    """

    data_line_infos = []

    for line_info in line_infos:
        stripped = line_info.line.strip()
        if stripped.startswith("data_") or stripped.startswith("#"):
            continue

        # Track data lines (non-tag, non-loop, non-stop lines)
        if stripped:
            data_line_infos.append(line_info)

    return data_line_infos


def _convert_loop_to_shifts(
    loop,
    chain_code,
    file_name,
    data_line_infos,
    molecule_type=None,
    sequence_source=SequenceSource.AUTH,
):
    """Convert pynmrstar Loop to list of ShiftData.

    Required loop columns (pynmrstar strips the category prefix):
    - ID (sequential ID)
    - Comp_index_ID or Auth_seq_ID (residue sequence number)
    - Comp_ID or Auth_comp_ID (residue name, 1-letter code)
    - Atom_ID or Auth_atom_ID (atom name)
    - Val (chemical shift value)

    Optional columns:
    - Seq_ID (system sequence number, used as fallback)
    - Atom_type (element symbol, e.g., C, H, N)
    - Atom_isotope_number (isotope number, e.g., 13, 1, 15)
    - Val_err (shift value uncertainty)
    - Details (comment/notes)
    - Auth_asym_ID (author chain/assembly ID)
    - Entity_assembly_asym_ID (system chain/assembly ID)

    When sequence_source is AUTH (default), Auth_* columns take priority.
    When sequence_source is SYSTEM, non-Auth columns are used.

    Args:
        loop: pynmrstar Loop object containing shift data
        chain_code: Chain code to assign to all shifts
        file_name: Name of file being parsed (for error messages)
        data_line_infos: List of LineInfo objects for data rows
        molecule_type: Molecule type or None to auto-detect
        sequence_source: Source for IDs (AUTH uses Auth_*, SYSTEM uses non-Auth)

    Returns:
        List of ShiftData objects

    Raises:
        StarchParseException: If required tags are missing or data is invalid
    """
    shifts = []

    _check_for_correct_tags_or_raise(data_line_infos, file_name, loop)

    # Guess molecule type if not provided
    if molecule_type is None:
        molecule_type = _find_molecule_type_or_raise(loop)

    tag_to_index = {tag: i for i, tag in enumerate(loop.tags)}

    # Select columns with auth/system preferences
    sequence_code_col = _select_column(
        tag_to_index, "Auth_seq_ID", "Seq_ID", "Comp_index_ID", sequence_source
    )
    comp_id_col = _select_column(
        tag_to_index, "Auth_comp_ID", "Comp_ID", None, sequence_source
    )
    atom_id_col = _select_column(
        tag_to_index, "Auth_atom_ID", "Atom_ID", None, sequence_source
    )

    # Val column is always required (no auth variant)
    chemical_shift_tag_index = tag_to_index["Val"]

    # Validate that required columns were found
    if sequence_code_col.index is None:
        raise StarchParseException(
            reason="No sequence code column found (tried Auth_seq_ID, Seq_ID, Comp_index_ID)"
        )
    if comp_id_col.index is None:
        raise StarchParseException(
            reason="No residue name column found (tried Auth_comp_ID, Comp_ID)"
        )
    if atom_id_col.index is None:
        raise StarchParseException(
            reason="No atom name column found (tried Auth_atom_ID, Atom_ID)"
        )

    # Optional columns
    atom_type_index = tag_to_index.get("Atom_type")
    isotope_number_index = tag_to_index.get("Atom_isotope_number")
    val_err_index = tag_to_index.get("Val_err")
    details_index = tag_to_index.get("Details")

    for row_index, row in enumerate(loop.data):
        # Get residue and atom names first (using selected column indices)
        residue_name_1let = row[comp_id_col.index]
        atom_name = row[atom_id_col.index]

        # Validate and parse sequence code
        sequence_code = _read_sequence_code_or_raise(
            row, sequence_code_col.index, data_line_infos
        )

        # Validate and parse shift value
        shift_value = _read_shift_or_raise(
            row, chemical_shift_tag_index, data_line_infos
        )

        # Extract optional fields if present
        element = row[atom_type_index] if atom_type_index is not None else None
        isotope_number = (
            int(row[isotope_number_index]) if isotope_number_index is not None else None
        )
        value_uncertainty = (
            float(row[val_err_index]) if val_err_index is not None else None
        )
        comment = row[details_index] if details_index is not None else None

        # Translate residue name using detected or specified molecule type
        residue_name_3let = _read_residue_name_or_raise(
            data_line_infos, molecule_type, residue_name_1let
        )

        residue = Residue(
            chain_code=chain_code,
            sequence_code=sequence_code,
            residue_name=residue_name_3let,
        )
        atom = AtomLabel(
            residue, atom_name, element=element, isotope_number=isotope_number
        )
        shift = ShiftData(
            atom=atom,
            value=shift_value,
            value_uncertainty=value_uncertainty,
            comment=comment,
        )
        shifts.append(shift)

    return shifts


def _find_best_matching_line(data_line_infos, row):
    """Find the LineInfo that best matches the given row data.

    Args:
        data_line_infos: List of LineInfo objects from the file
        row: Data row from pynmrstar loop

    Returns:
        LineInfo: Best matching LineInfo, or None if no good match
    """
    best_match = None
    best_score = 0

    for line_info in data_line_infos:
        # Skip non-data lines (tags, loop, stop)
        line_stripped = line_info.line.strip()
        if not line_stripped or line_stripped.startswith(("_", "loop", "stop")):
            continue

        # Simple matching: count how many values from row appear in this line
        score = sum(1 for val in row if str(val) in line_stripped)
        if score > best_score:
            best_score = score
            best_match = line_info

    return best_match


def _read_residue_name_or_raise(data_line_infos, molecule_type, residue_name_1let):
    """Translate 1-letter residue code to 3-letter, or raise exception with line info.

    Args:
        data_line_infos: List of LineInfo objects (for error reporting)
        molecule_type: MoleculeType to use for translation
        residue_name_1let: 1-letter residue code

    Returns:
        str: 3-letter residue code
    """
    try:
        residue_name_3let = translate_1_to_3(
            residue_name_1let, molecule_type=molecule_type
        )[0]
    except (ValueError, IndexError) as e:
        # Only find matching line when raising exception
        line_info = _find_best_matching_line(data_line_infos, [residue_name_1let])
        msg = f"Invalid residue code '{residue_name_1let}' for molecule type {molecule_type.value}. Error: {e}"
        raise StarchParseException(reason=msg, line_info=line_info)
    return residue_name_3let


def _read_shift_or_raise(row, tag_index, data_line_infos):
    """Read and validate shift value from row, or raise exception with line info.

    Args:
        data_line_infos: List of LineInfo objects (for error reporting)
        row: Data row from loop
        tag_index: Index of shift value in row

    Returns:
        float: Validated shift value
    """
    shift_value_str = row[tag_index]
    if not is_float(shift_value_str):
        # Only find matching line when raising exception
        line_info = _find_best_matching_line(data_line_infos, row)
        raise StarchParseException(
            reason=f"Chemical shift value must be a number, got: {shift_value_str}",
            line_info=line_info,
        )
    return float(shift_value_str)


def _read_sequence_code_or_raise(row, tag_index, data_line_infos):
    """Read and validate sequence code from row, or raise exception with line info.

    Args:
        data_line_infos: List of LineInfo objects (for error reporting)
        row: Data row from loop
        tag_index: Index of sequence code in row

    Returns:
        int: Validated sequence code
    """
    seq_code_str = row[tag_index]
    if not is_int(seq_code_str):
        # Only find matching line when raising exception
        line_info = _find_best_matching_line(data_line_infos, row)
        raise StarchParseException(
            reason=f"Sequence code must be an integer, got: {seq_code_str}",
            line_info=line_info,
        )
    return int(seq_code_str)


def _find_molecule_type_or_raise(loop) -> MoleculeType:
    """Determine molecule type from residue codes in loop data.

    Args:
        loop: pynmrstar Loop object
        tag_to_index: Dictionary mapping tag names to column indices

    Returns:
        MoleculeType: Guessed molecule type
    """
    # Collect all residue codes from the data

    tag_to_index = {tag: i for i, tag in enumerate(loop.tags)}

    # Try Auth_comp_ID first, then Comp_ID
    comp_id_index = tag_to_index.get("Auth_comp_ID")
    if comp_id_index is None:
        comp_id_index = tag_to_index["Comp_ID"]

    residue_codes = set()
    for row in loop.data:
        residue_codes.add(row[comp_id_index])

    molecule_type_result, error_message = guess_molecule_type(residue_codes)

    if error_message:
        # Add CLI-appropriate context to library error message
        cli_message = f"{error_message}\nPlease specify --molecule-type explicitly."
        raise StarchUndefinedMoleculeType(
            reason=cli_message, residue_codes=residue_codes
        )

    return molecule_type_result


def _check_for_correct_tags_or_raise(data_line_infos, file_name, loop):
    """Check that required tags (or their Auth_* alternatives) are present."""
    loop_tags = set(loop.tags)

    # Required fields with accepted alternatives
    required_fields = {
        "sequence_code": {"Auth_seq_ID", "Seq_ID", "Comp_index_ID"},
        "residue_name": {"Auth_comp_ID", "Comp_ID"},
        "atom_name": {"Auth_atom_ID", "Atom_ID"},
        "shift_value": {"Val"},
    }

    missing_fields = []
    for field_name, accepted_tags in required_fields.items():
        if not any(tag in loop_tags for tag in accepted_tags):
            missing_fields.append(
                f"{field_name} (needs one of: {', '.join(sorted(accepted_tags))})"
            )

    if missing_fields:
        # Find tag lines for better error reporting
        tag_line_info = None
        for line_info in data_line_infos:
            if line_info.line.strip().startswith("_"):
                tag_line_info = line_info
                break

        msg = (
            f"STARCH file {file_name} is missing required fields:\n"
            + "\n".join(f"  - {field}" for field in missing_fields)
            + f"\n\nFound tags: {', '.join(sorted(loop.tags))}"
        )
        raise StarchParseException(reason=msg, line_info=tag_line_info)
