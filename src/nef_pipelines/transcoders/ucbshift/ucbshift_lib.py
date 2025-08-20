import csv
from typing import Any, Dict, Iterator, List, Tuple

from nef_pipelines.lib.structures import (
    AtomLabel,
    LineInfo,
    Residue,
    SequenceResidue,
    ShiftData,
)
from nef_pipelines.lib.util import exit_error


def parse_ucbshift_csv_rows(
    csvfile, file_name
) -> Iterator[Tuple[Dict[str, Any], LineInfo]]:
    """Parse UCBShift CSV file and yield row data with line info for validation"""
    lines = csvfile.readlines()

    # Create CSV reader from the lines
    reader = csv.DictReader(lines)

    _validate_csv_file_header(reader, file_name)

    # Iterate through lines and rows together
    data_lines = lines[1:]  # Skip header line
    for i, row in enumerate(reader):
        line_number = i + 2  # +2 because enumerate starts at 0 and we skip header
        line_content = data_lines[i].rstrip() if i < len(data_lines) else ""
        line_info = LineInfo(file_name, line_number, line_content)

        # Basic validation of required fields
        _exit_if_required_fields_missing(row, line_info)

        yield row, line_info


def parse_ucbshift_shifts(
    csvfile, chain_code, file_name, prediction_type=None
) -> List[ShiftData]:
    """Parse UCBShift CSV file to extract shift data"""

    shifts = []

    # Determine column suffix based on prediction type
    if prediction_type is None:
        suffix = "_UCBShift"
    elif str(prediction_type) == "combined":
        suffix = "_UCBShift"
    elif str(prediction_type) == "x":
        suffix = "_X"
    elif str(prediction_type) == "y":
        suffix = "_Y"
    else:
        suffix = "_UCBShift"  # default fallback

    # Mapping of UCBShift atom types to standard names with element and isotope information
    # Format: 'ucb_atom_name': (nef_atom_name, element, isotope_number)
    atom_mapping = {
        f"H{suffix}": ("H", "H", 1),
        f"HA{suffix}": ("HA", "H", 1),
        f"C{suffix}": ("C", "C", 13),
        f"CA{suffix}": ("CA", "C", 13),
        f"CB{suffix}": ("CB", "C", 13),
        f"N{suffix}": ("N", "N", 15),
    }

    for row, line_info in parse_ucbshift_csv_rows(csvfile, file_name):
        try:
            # Parse RESNUM
            resnum_str = row["RESNUM"].strip()
            _exit_if_resnum_is_not_int(resnum_str, line_info)
            resnum = int(resnum_str)

            # Parse RESNAME
            resname = row["RESNAME"].strip()
            _exit_if_resnum_missing_or_bad(resname, line_info)

            # Extract shifts for each atom type
            for ucb_atom, (nef_atom, element, isotope) in atom_mapping.items():
                if ucb_atom in row and row[ucb_atom] and row[ucb_atom].strip():
                    # Validate and parse shift value
                    _exit_if_shift_not_a_float(row[ucb_atom], ucb_atom, line_info)
                    shift_value = round(float(row[ucb_atom].strip()), 3)

                    residue = Residue(
                        chain_code=chain_code,
                        sequence_code=resnum,
                        residue_name=resname,
                    )

                    atom_label = AtomLabel(
                        residue=residue,
                        atom_name=nef_atom,
                        element=element,
                        isotope_number=isotope,
                    )

                    shift = ShiftData(atom=atom_label, value=shift_value)
                    shifts.append(shift)

        except KeyError as e:
            exit_error(
                f"in UCBShift file {file_name} at line {line_info.line_no}: missing required column {e}"
            )
        except Exception as e:
            exit_error(
                f"in UCBShift file {file_name} at line {line_info.line_no}: {str(e)}"
            )

    return shifts


def parse_ucbshift_sequence(csvfile, chain_code, file_name) -> List[SequenceResidue]:
    """Parse UCBShift CSV file to extract sequence data"""

    residues = []

    for row, line_info in parse_ucbshift_csv_rows(csvfile, file_name):
        try:
            # Parse RESNUM
            resnum_str = row["RESNUM"].strip()
            _exit_if_resnum_is_not_int(resnum_str, line_info)
            resnum = int(resnum_str)

            # Parse RESNAME
            resname = row["RESNAME"].strip()
            _exit_if_resnum_missing_or_bad(resname, line_info)

            # Create SequenceResidue with specified chain code
            residue = SequenceResidue(
                chain_code=chain_code,
                sequence_code=resnum,
                residue_name=resname,
                linking=None,  # Will be set later based on position
            )
            residues.append(residue)

        except KeyError as e:
            exit_error(
                f"in UCBShift file {file_name} at line {line_info.line_no}: missing required column {e}"
            )
        except Exception as e:
            exit_error(
                f"in UCBShift file {file_name} at line {line_info.line_no}: {str(e)}"
            )

    return residues


def _validate_csv_file_header(reader, file_name):
    """Validate CSV file format and required columns"""
    if reader.fieldnames is None:
        exit_error(
            f"the UCBShift file {file_name} file appears to be empty or not in a valid CSV format"
        )

    required_columns = ["RESNUM", "RESNAME"]
    missing_columns = [col for col in required_columns if col not in reader.fieldnames]
    if missing_columns:
        exit_error(
            f"the UCBShift file {file_name} is missing some required columns: {', '.join(missing_columns)}"
        )


def _exit_if_required_fields_missing(row, line_info):
    """Validate required fields in a CSV row"""
    if "RESNUM" not in row or not row["RESNUM"].strip():
        exit_error(
            f"""in the UCBShift file {line_info.file_name} at line {line_info.line_no}: RESNUM is missing or empty
            the line was:
            {line_info.line}"""
        )

    if "RESNAME" not in row or not row["RESNAME"].strip():
        exit_error(
            f"""in the UCBShift file {line_info.file_name} at line {line_info.line_no}: RESNAME is missing or empty
            the line was:
            {line_info.line}"""
        )


def _exit_if_resnum_is_not_int(resnum_str, line_info):
    """Validate RESNUM field as integer"""
    try:
        int(resnum_str)
    except ValueError:
        exit_error(
            f"""in the UCBShift file {line_info.file_name} at line {line_info.line_no}: RESNUM '{resnum_str}'
                is not a valid integer the line was:

            {line_info.line}"""
        )


def _exit_if_resnum_missing_or_bad(resname, line_info):
    """Validate RESNAME field is not empty"""
    if not resname:
        exit_error(
            f"""in the UCBShift file {line_info.file_name} at line {line_info.line_no}: RESNAME is empty
            the line was:
            {line_info.line}"""
        )


def _exit_if_shift_not_a_float(value, ucb_atom, line_info):
    """Validate a chemical shift value is a valid number"""
    try:
        float(value.strip())
    except ValueError:
        exit_error(
            f"""in the UCBShift file {line_info.file_name} at line {line_info.line_no}: '{ucb_atom}' value '{value}'
                is not a valid number the line was:
            {line_info.line}"""
        )
