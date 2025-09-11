from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Set, Tuple

import typer
from typer import Option

from nef_pipelines.lib.nef_lib import (
    loop_row_namespace_iter,
    molecular_system_from_entry_or_exit,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import sequences_from_frames
from nef_pipelines.lib.util import STDIN, exit_error, info, warn
from nef_pipelines.tools.chains import chains_app


@chains_app.command()
def validate(
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [- is stdin]",
    ),
    output: str = typer.Option(
        "chain_validation_{entry}.txt",
        "-o",
        "--out",
        help="output file template for validation results (use {entry} for entry ID)",
    ),
    verbose: bool = Option(
        False, "-v", "--verbose", help="print verbose validation info"
    ),
    strict: bool = Option(
        False, "-s", "--strict", help="exit with error code if validation fails"
    ),
):
    """- validate chain consistency between molecular system and all frames α"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    # Get molecular system
    molecular_system = molecular_system_from_entry_or_exit(entry)

    # Validate molecular system chains
    validation_results = validate_molecular_system_chains(
        entry, molecular_system, verbose
    )

    # Validate all frames against molecular system
    frame_validation_results = validate_frames_against_molecular_system(
        entry, molecular_system, verbose
    )

    # Combine results
    all_valid = validation_results["valid"] and frame_validation_results["valid"]

    # Count total errors
    error_count = _count_validation_errors(validation_results, frame_validation_results)

    # Generate output filename
    output_file = output.format(entry=entry.entry_id)

    # Print summary (to both console and file)
    if verbose or not all_valid:
        summary_text = _generate_validation_summary(
            entry, validation_results, frame_validation_results
        )
        print(summary_text)
        _write_to_file(output_file, summary_text)
    else:
        # For valid files with no verbose output, still write basic summary to file
        basic_summary = (
            f"[{entry.entry_id}] Validation completed successfully - no errors found.\n"
        )
        _write_to_file(output_file, basic_summary)

    # Always print error count summary
    if error_count > 0:
        info(f"[{entry.entry_id}] Total validation errors found: {error_count}")
        info(f"[{entry.entry_id}] Detailed results written to: {output_file}")
    else:
        info(f"[{entry.entry_id}] Validation results written to: {output_file}")

    if strict and not all_valid:
        exit_error("Validation failed")

    if all_valid:
        info("All chain validations passed")


def _write_to_file(filename: str, content: str):
    """Write content to a file"""
    try:
        with open(filename, "w") as f:
            f.write(content)
    except IOError as e:
        warn(f"Failed to write to output file {filename}: {e}")


def _generate_validation_summary(
    entry, molecular_system_results: Dict, frame_results: Dict
) -> str:
    """Generate validation summary text (same as print_validation_summary but returns string)"""

    # Calculate error counts
    duplicate_errors = 0
    for chain_info in molecular_system_results["chains"].values():
        if chain_info["duplicates"]:
            for seq_code, count in chain_info["duplicates"]:
                duplicate_errors += count - 1

    mismatch_errors = len(frame_results["mismatches"])
    missing_residue_errors = len(frame_results["missing_residues"])
    total_errors = duplicate_errors + mismatch_errors + missing_residue_errors

    lines = []
    lines.append("=" * 60)
    lines.append(f"[{entry.entry_id}] VALIDATION SUMMARY")
    lines.append("=" * 60)

    # Error count summary
    if total_errors > 0:
        lines.append("")
        lines.append(f"[{entry.entry_id}] TOTAL ERRORS: {total_errors}")
        if duplicate_errors > 0:
            lines.append(f"  - Duplicate residues: {duplicate_errors}")
        if mismatch_errors > 0:
            lines.append(f"  - Residue name mismatches: {mismatch_errors}")
        if missing_residue_errors > 0:
            lines.append(f"  - Missing residues: {missing_residue_errors}")
    else:
        lines.append("")
        lines.append(f"[{entry.entry_id}] NO ERRORS FOUND")

    # Molecular system results
    lines.append("")
    lines.append(
        f"[{entry.entry_id}] MOLECULAR SYSTEM: {'VALID' if molecular_system_results['valid'] else 'INVALID'}"
    )

    for chain_code, chain_info in molecular_system_results["chains"].items():
        status = "VALID" if chain_info["valid"] else "INVALID"
        lines.append(
            f"  [{entry.entry_id}] Chain {chain_code}: {chain_info['residue_count']} residues - {status}"
        )

        if chain_info["duplicates"]:
            for seq_code, count in chain_info["duplicates"]:
                lines.append(
                    f"    [{entry.entry_id}] ERROR: Sequence code {seq_code} appears {count} times"
                )

    # Frame results
    lines.append("")
    lines.append(
        f"[{entry.entry_id}] FRAME VALIDATION: {'VALID' if frame_results['valid'] else 'INVALID'}"
    )

    valid_frames = sum(1 for f in frame_results["frames"].values() if f["valid"])
    total_frames = len(frame_results["frames"])
    lines.append(f"  {valid_frames}/{total_frames} frames valid")

    if frame_results["mismatches"]:
        lines.append("")
        lines.append(
            f"[{entry.entry_id}] RESIDUE NAME MISMATCHES ({len(frame_results['mismatches'])}):"
        )
        for mismatch in frame_results["mismatches"]:
            lines.append(
                f"  [{entry.entry_id}] Frame {mismatch['frame_name']}: "
                f"{mismatch['chain_code']}.{mismatch['sequence_code']} "
                f"frame={mismatch['frame_residue_name']} vs "
                f"molecular_system={mismatch['molecular_system_residue_name']}"
            )

    if frame_results["missing_residues"]:
        lines.append("")
        lines.append(f"MISSING RESIDUES ({len(frame_results['missing_residues'])}):")
        for missing in frame_results["missing_residues"]:
            lines.append(
                f"  [{entry.entry_id}] Frame {missing['frame_name']}: "
                f"{missing['chain_code']}.{missing['sequence_code']}.{missing['residue_name']} "
                f"not found in molecular system"
            )

    lines.append("=" * 60)

    return "\n".join(lines) + "\n"


def _count_validation_errors(
    molecular_system_results: Dict, frame_results: Dict
) -> int:
    """
    Count the total number of validation errors

    :param molecular_system_results: Results from molecular system validation
    :param frame_results: Results from frame validation
    :return: Total error count
    """
    error_count = 0

    # Count duplicate residue errors
    for chain_code, chain_info in molecular_system_results["chains"].items():
        if chain_info["duplicates"]:
            # Each duplicate sequence code counts as one error per occurrence beyond the first
            for seq_code, count in chain_info["duplicates"]:
                error_count += count - 1  # count - 1 because first occurrence is valid

    # Count frame validation errors
    error_count += len(frame_results["mismatches"])  # Residue name mismatches
    error_count += len(frame_results["missing_residues"])  # Missing residues

    return error_count


def validate_molecular_system_chains(entry, molecular_system, verbose: bool) -> Dict:
    """
    Validate that chains in molecular system have no duplicate residues

    :param molecular_system: The molecular system saveframe
    :param verbose: Whether to print detailed output
    :return: Dictionary with validation results
    """
    # Check for raw duplicates directly from the molecular system loop
    # before sequences_from_frames does any deduplication
    raw_residues = []
    try:
        loop = molecular_system.get_loop("_nef_sequence")
        for row in loop_row_namespace_iter(loop):
            chain_code = row.chain_code
            sequence_code = int(row.sequence_code)
            residue_name = row.residue_name
            raw_residues.append((chain_code, sequence_code, residue_name))
    except (KeyError, AttributeError):
        # Fallback to processed sequences if raw loop isn't available
        sequences = sequences_from_frames(molecular_system)
        raw_residues = [
            (r.chain_code, r.sequence_code, r.residue_name) for r in sequences
        ]

    # Group residues by chain
    chain_residues = defaultdict(list)
    for chain_code, sequence_code, residue_name in raw_residues:
        chain_residues[chain_code].append((sequence_code, residue_name))

    results = {"valid": True, "chains": {}, "duplicates": defaultdict(list)}

    for chain_code, residue_tuples in chain_residues.items():
        # Check for duplicate sequence codes within chain
        sequence_codes = [seq_code for seq_code, _ in residue_tuples]
        sequence_counter = Counter(sequence_codes)
        duplicates = [
            (seq_code, count)
            for seq_code, count in sequence_counter.items()
            if count > 1
        ]

        chain_valid = len(duplicates) == 0
        results["chains"][chain_code] = {
            "valid": chain_valid,
            "residue_count": len(residue_tuples),
            "duplicates": duplicates,
        }

        if not chain_valid:
            results["valid"] = False
            # Find actual duplicate residues for reporting
            for seq_code, count in duplicates:
                duplicate_residues = [
                    residue_tuple
                    for residue_tuple in residue_tuples
                    if residue_tuple[0] == seq_code
                ]
                results["duplicates"][chain_code].extend(duplicate_residues)

        if verbose:
            status = "VALID" if chain_valid else "INVALID"
            info(
                f"[{entry.entry_id}] Chain {chain_code}: {len(residue_tuples)} residues - {status}"
            )
            if duplicates:
                for seq_code, count in duplicates:
                    warn(
                        f"  [{entry.entry_id}]: duplicate sequence code {seq_code} appears {count} times in entry"
                    )

    return results


def validate_frames_against_molecular_system(
    entry, molecular_system, verbose: bool
) -> Dict:
    """
    Validate all frames against the molecular system

    :param entry: The NEF entry
    :param molecular_system: The molecular system saveframe
    :param verbose: Whether to print detailed output
    :return: Dictionary with validation results
    """
    # Get molecular system residues as lookup
    sequences = sequences_from_frames(molecular_system)
    molecular_system_residues = {}
    for residue in sequences:
        key = (residue.chain_code, residue.sequence_code)
        molecular_system_residues[key] = residue

    results = {"valid": True, "frames": {}, "mismatches": [], "missing_residues": []}

    # Check all frames that might contain residue references
    frame_categories_to_check = [
        "nef_chemical_shift_list",
        "nef_peak_list",
        "nef_distance_restraint_list",
        "nef_dihedral_restraint_list",
        "nef_rdc_restraint_list",
        "nef_nmr_meta_data",
        "nef_T1_relaxation_list",
        "nef_T2_relaxation_list",
        "nef_heteronoe_list",
        "nef_chemical_shift_perturbation_list",
        "nef_spectral_peak_list",
    ]

    # Iterate through all saveframes in the entry
    for frame in entry:
        if hasattr(frame, "category") and frame.category in frame_categories_to_check:
            frame_results = _validate_frame_residues(
                entry, frame, molecular_system_residues, verbose
            )

            results["frames"][frame.name] = frame_results

            if not frame_results["valid"]:
                results["valid"] = False
                results["mismatches"].extend(frame_results["mismatches"])
                results["missing_residues"].extend(frame_results["missing_residues"])

    return results


def _validate_frame_residues(
    entry, frame, molecular_system_residues: Dict, verbose: bool
) -> Dict:
    """
    Validate residues in a specific frame against molecular system

    :param frame: The saveframe to validate
    :param molecular_system_residues: Dictionary of molecular system residues
    :param verbose: Whether to print detailed output
    :return: Dictionary with frame validation results
    """
    results = {
        "valid": True,
        "category": frame.category,
        "mismatches": [],
        "missing_residues": [],
        "residue_count": 0,
    }

    # Extract residue information from frame based on category
    frame_residues = _extract_residues_from_frame(frame)
    results["residue_count"] = len(frame_residues)

    for chain_code, sequence_code, residue_name in frame_residues:
        key = (chain_code, sequence_code)

        if key not in molecular_system_residues:
            # Residue not found in molecular system
            results["valid"] = False
            missing = {
                "frame_name": frame.name,
                "chain_code": chain_code,
                "sequence_code": sequence_code,
                "residue_name": residue_name,
            }
            results["missing_residues"].append(missing)

            if verbose:
                msg = f"""
                    [{entry.entry_id}] Frame {frame.name}: Residue {chain_code}.{sequence_code}
                    not found in molecular system
                """
                warn(msg)

        else:
            # Check if residue name matches (only if residue name is provided in frame)
            mol_sys_residue = molecular_system_residues[key]
            if residue_name != "." and mol_sys_residue.residue_name != residue_name:
                results["valid"] = False
                mismatch = {
                    "frame_name": frame.name,
                    "chain_code": chain_code,
                    "sequence_code": sequence_code,
                    "frame_residue_name": residue_name,
                    "molecular_system_residue_name": mol_sys_residue.residue_name,
                }
                results["mismatches"].append(mismatch)

                if verbose:
                    warn(
                        f"[{entry.entry_id}]:Frame {frame.name}: Residue {chain_code}.{sequence_code} name mismatch: "
                        f"frame={residue_name}, molecular_system={mol_sys_residue.residue_name}"
                    )
            elif residue_name == "." and verbose:
                # Just log that residue name is missing but don't mark as invalid
                info(
                    f"Frame {frame.name}: Residue {chain_code}.{sequence_code} has missing residue name (using '.')"
                )

    if verbose and results["valid"] and results["residue_count"] > 0:
        info(
            f"[{entry.entry_id}] Frame {frame.name}: All {results['residue_count']} residues valid"
        )

    return results


def _extract_residues_from_frame(frame) -> Set[Tuple[str, int, str]]:
    """
    Extract residue information from a frame using dynamic column detection

    :param frame: The saveframe to extract residues from
    :return: Set of (chain_code, sequence_code, residue_name) tuples
    """
    residues = set()

    # Try to get the main loop for this frame type
    loop = None
    loop_name = None

    # Common NEF loop names by category
    loop_mappings = {
        "nef_chemical_shift_list": "_nef_chemical_shift",
        "nef_peak_list": "_nef_peak",
        "nef_distance_restraint_list": "_nef_distance_restraint",
        "nef_dihedral_restraint_list": "_nef_dihedral_restraint",
        "nef_rdc_restraint_list": "_nef_rdc_restraint",
        "nef_nmr_meta_data": "_nef_nmr_meta_data",
    }

    if frame.category in loop_mappings:
        loop_name = loop_mappings[frame.category]

    # Try to get the loop
    try:
        if loop_name:
            loop = frame.get_loop(loop_name)
        else:
            # Try to find any loop in the frame
            if hasattr(frame, "loops") and frame.loops:
                loop = list(frame.loops.values())[0]
    except (KeyError, AttributeError):
        return residues

    if not loop:
        return residues

    # Get all column names from the loop
    try:
        column_names = [tag.replace(f"{loop_name}.", "") for tag in loop.tags]
    except (AttributeError, TypeError):
        try:
            column_names = loop.tags if hasattr(loop, "tags") else []
        except Exception:
            return residues

    # Find all residue-related columns (with and without dimension numbers)
    chain_cols = []
    sequence_cols = []
    residue_cols = []
    atom_cols = []

    for col in column_names:
        if col.startswith("chain_code"):
            chain_cols.append(col)
        elif col.startswith("sequence_code"):
            sequence_cols.append(col)
        elif col.startswith("residue_name"):
            residue_cols.append(col)
        elif col.startswith("atom_name"):
            atom_cols.append(col)

    # Process each row in the loop
    try:
        for row in loop_row_namespace_iter(loop):
            # Extract residues from all available dimension combinations
            processed_combinations = set()

            # Handle both numbered dimensions (_1, _2, etc.) and unnumbered columns
            for chain_col in chain_cols:
                # Determine dimension suffix
                if "_" in chain_col and chain_col.split("_")[-1].isdigit():
                    dim_suffix = "_" + chain_col.split("_")[-1]
                else:
                    dim_suffix = ""

                seq_col = f"sequence_code{dim_suffix}"
                res_col = f"residue_name{dim_suffix}"

                # Check if we have the required columns for this dimension
                if hasattr(row, chain_col) and hasattr(row, seq_col):
                    try:
                        chain_code = getattr(row, chain_col)
                        sequence_code_str = getattr(row, seq_col)

                        if (
                            chain_code
                            and sequence_code_str
                            and chain_code != "."
                            and sequence_code_str != "."
                        ):
                            sequence_code = int(sequence_code_str)

                            # Get residue name if available
                            residue_name = "."
                            if hasattr(row, res_col):
                                residue_name = getattr(row, res_col) or "."

                            # Create a unique key to avoid duplicates
                            residue_key = (chain_code, sequence_code, residue_name)

                            if residue_key not in processed_combinations:
                                processed_combinations.add(residue_key)

                                # Warn if residue name is missing
                                if residue_name == ".":
                                    warn(
                                        f"Frame {frame.name}: Missing residue name for {chain_code}.{sequence_code}"
                                    )

                                residues.add(residue_key)

                    except (ValueError, AttributeError, TypeError):
                        # Skip invalid entries
                        continue

    except (AttributeError, TypeError):
        # Skip if loop processing fails
        pass

    return residues


def print_validation_summary(
    entry, molecular_system_results: Dict, frame_results: Dict
):
    """Print a summary of validation results"""

    # Calculate error counts
    duplicate_errors = 0
    for chain_info in molecular_system_results["chains"].values():
        if chain_info["duplicates"]:
            for seq_code, count in chain_info["duplicates"]:
                duplicate_errors += count - 1

    mismatch_errors = len(frame_results["mismatches"])
    missing_residue_errors = len(frame_results["missing_residues"])
    total_errors = duplicate_errors + mismatch_errors + missing_residue_errors

    print("\n" + "=" * 60)
    print(f"[{entry.entry_id}] VALIDATION SUMMARY")
    print("=" * 60)

    # Error count summary
    if total_errors > 0:
        print(f"\n[{entry.entry_id}] TOTAL ERRORS: {total_errors}")
        if duplicate_errors > 0:
            print(f"  - Duplicate residues: {duplicate_errors}")
        if mismatch_errors > 0:
            print(f"  - Residue name mismatches: {mismatch_errors}")
        if missing_residue_errors > 0:
            print(f"  - Missing residues: {missing_residue_errors}")
    else:
        print(f"\n[{entry.entry_id}] NO ERRORS FOUND")

    # Molecular system results
    print(
        f"\n[{entry.entry_id}] MOLECULAR SYSTEM: {'VALID' if molecular_system_results['valid'] else 'INVALID'}"
    )

    for chain_code, chain_info in molecular_system_results["chains"].items():
        status = "VALID" if chain_info["valid"] else "INVALID"
        print(
            f"  [{entry.entry_id}] Chain {chain_code}: {chain_info['residue_count']} residues - {status}"
        )

        if chain_info["duplicates"]:
            for seq_code, count in chain_info["duplicates"]:
                print(
                    f"    [{entry.entry_id}] ERROR: Sequence code {seq_code} appears {count} times"
                )

    # Frame results
    print(
        f"\n[{entry.entry_id}] FRAME VALIDATION: {'VALID' if frame_results['valid'] else 'INVALID'}"
    )

    valid_frames = sum(1 for f in frame_results["frames"].values() if f["valid"])
    total_frames = len(frame_results["frames"])
    print(f"  {valid_frames}/{total_frames} frames valid")

    if frame_results["mismatches"]:
        print(
            f"\n[{entry.entry_id}] RESIDUE NAME MISMATCHES ({len(frame_results['mismatches'])}):"
        )
        for mismatch in frame_results["mismatches"]:
            print(
                f"  [{entry.entry_id}] Frame {mismatch['frame_name']}: "
                f"{mismatch['chain_code']}.{mismatch['sequence_code']} "
                f"frame={mismatch['frame_residue_name']} vs "
                f"molecular_system={mismatch['molecular_system_residue_name']}"
            )

    if frame_results["missing_residues"]:
        print(f"\nMISSING RESIDUES ({len(frame_results['missing_residues'])}):")
        for missing in frame_results["missing_residues"]:
            print(
                f"  [{entry.entry_id}] Frame {missing['frame_name']}: "
                f"{missing['chain_code']}.{missing['sequence_code']}.{missing['residue_name']} "
                f"not found in molecular system"
            )

    print("=" * 60)
