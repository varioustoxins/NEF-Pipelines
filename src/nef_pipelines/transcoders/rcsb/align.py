from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.sequence_lib import sequences_from_frames
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import exit_error, info, warn
from nef_pipelines.tools.chains.align import (
    _build_per_chain_alignment_sequences,
    _get_offset_or_none,
)
from nef_pipelines.transcoders.rcsb import app as rcsb_app
from nef_pipelines.transcoders.rcsb.rcsb_lib import (
    RCSBFileType,
    Structure,
    guess_cif_or_pdb,
    parse_cif,
    parse_pdb,
)


@rcsb_app.command()
def align(
    pdb_file: Path = typer.Argument(..., help="PDB or mmCIF file to align"),
    nef_input: Path = typer.Option(
        Path("-"),
        "-i",
        "--in",
        help="NEF file to read molecular system from [stdin if -]",
    ),
    output_template: str = typer.Option(
        "{file_name}_aligned",
        "-o",
        "--out",
        help="output file name template, {file_name} will be replaced with input file name",
    ),
    chain_mapping: List[str] = typer.Option(
        None,
        "-m",
        "--map",
        help="map PDB chain to NEF chain (format: pdb_chain:nef_chain)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="show verbose alignment information"
    ),
):
    r"""\- align pdb/cif structures to match NEF chains α"""

    # Read NEF entry
    entry = read_entry_from_file_or_stdin_or_exit_error(nef_input)

    # Read PDB/mmCIF structure
    structure = _read_structure(pdb_file)

    # Get NEF sequences
    nef_sequences = _get_nef_sequences(entry)

    # Parse chain mapping if provided
    chain_map = _parse_chain_mapping(chain_mapping) if chain_mapping else {}

    # Align sequences and calculate offsets
    alignment_info = _align_sequences(structure, nef_sequences, chain_map, verbose)

    # Apply alignment to structure
    aligned_structure = _apply_alignment(structure, alignment_info)

    # Write aligned structure
    output_file = _generate_output_filename(pdb_file, output_template)
    _write_structure(aligned_structure, pdb_file, output_file)

    if verbose:
        info(f"Aligned structure written to: {output_file}")

    print(entry)


def _read_structure(pdb_file: Path) -> Structure:
    """Read PDB or mmCIF file and return Structure object"""
    try:
        with open(pdb_file) as fh:
            lines = fh.readlines()

        file_type = guess_cif_or_pdb(lines, str(pdb_file))

        if file_type == RCSBFileType.PDB:
            return parse_pdb(lines, source=str(pdb_file))
        elif file_type == RCSBFileType.CIF:
            return parse_cif(lines, source=str(pdb_file))
        else:
            exit_error(f"Could not determine file type for {pdb_file}")

    except Exception as e:
        exit_error(f"Failed to read {pdb_file}: {e}")


def _get_nef_sequences(entry: Entry) -> Dict[str, List[SequenceResidue]]:
    """Extract sequences from NEF molecular system"""
    nef_sequences = {}

    # Get sequences from all frames
    all_sequences = sequences_from_frames(entry.frame_list)

    # Group by chain code
    for residue in all_sequences:
        chain_code = residue.chain_code
        if chain_code not in nef_sequences:
            nef_sequences[chain_code] = []
        nef_sequences[chain_code].append(residue)

    # Sort by sequence code within each chain
    for chain_code in nef_sequences:
        nef_sequences[chain_code].sort(key=lambda r: r.sequence_code)

    return nef_sequences


def _parse_chain_mapping(chain_mapping: List[str]) -> Dict[str, str]:
    """Parse chain mapping from command line format"""
    chain_map = {}

    for mapping in chain_mapping:
        if ":" not in mapping:
            exit_error(
                f"Invalid chain mapping format: {mapping}. Use pdb_chain:nef_chain"
            )

        pdb_chain, nef_chain = mapping.split(":", 1)
        chain_map[pdb_chain.strip()] = nef_chain.strip()

    return chain_map


def _align_sequences(
    structure: Structure,
    nef_sequences: Dict[str, List[SequenceResidue]],
    chain_map: Dict[str, str],
    verbose: bool,
) -> Dict[str, Tuple[int, float]]:
    """Align PDB sequences to NEF sequences using chains align logic"""

    alignment_info = {}

    # Get first model from structure
    if not structure.models:
        exit_error("No models found in structure")

    model = structure.models[0]

    # Build NEF sequences in chains align format
    nef_chain_codes = list(nef_sequences.keys())
    reference_sequences_by_chains = _build_per_chain_alignment_sequences(
        _nef_sequences_to_sequence_residues(nef_sequences), nef_chain_codes
    )

    for chain in model.chains.values():
        pdb_chain_code = chain.chain_code or chain.segment_id

        # Determine NEF chain to align to
        nef_chain_code = chain_map.get(pdb_chain_code, pdb_chain_code)

        if nef_chain_code not in nef_sequences:
            if verbose:
                warn(
                    f"PDB chain {pdb_chain_code} -> NEF chain {nef_chain_code} not found in NEF file"
                )
            continue

        if nef_chain_code not in reference_sequences_by_chains:
            if verbose:
                warn(f"Could not build reference sequence for chain {nef_chain_code}")
            continue

        # Build PDB sequence in chains align format
        pdb_sequence_residues = _pdb_chain_to_sequence_residues(chain, pdb_chain_code)
        target_sequences = _build_per_chain_alignment_sequences(
            pdb_sequence_residues, [pdb_chain_code]
        )

        if pdb_chain_code not in target_sequences:
            if verbose:
                warn(f"Could not build target sequence for chain {pdb_chain_code}")
            continue

        reference_sequence = reference_sequences_by_chains[nef_chain_code]
        target_sequence = target_sequences[pdb_chain_code]

        if (not reference_sequence.sequence) or (not target_sequence.sequence):
            if verbose:
                warn(f"Empty sequence for chain {pdb_chain_code}")
            continue

        # Use chains align logic
        matcher = SequenceMatcher(
            a=reference_sequence.sequence,
            b=target_sequence.sequence,
            autojunk=False,
        )

        ratio = matcher.ratio()
        offset = _get_offset_or_none(matcher)

        if verbose:
            # Format ratio same way as chains align does it
            ratio_formatted = f"{ratio:7.3f}"
            info(
                f"[PDB] align chain {pdb_chain_code} -> {nef_chain_code} ratio: {ratio_formatted}"
            )

        # Warn if no match, same as chains align
        if offset is None:
            if verbose:
                warn(
                    f"couldn't align chain {pdb_chain_code} to NEF chain {nef_chain_code}"
                )
                warn("this chain was ignored")
            continue

        # Calculate the sequence code offset using chains align formula
        sequence_offset = (
            reference_sequence.start - 1 - target_sequence.start + offset + 1
        )
        alignment_info[pdb_chain_code] = (sequence_offset, ratio)

    return alignment_info


def _nef_sequences_to_sequence_residues(
    nef_sequences: Dict[str, List[SequenceResidue]]
) -> List[SequenceResidue]:
    """Convert NEF sequences dict to flat list"""
    all_residues = []
    for chain_residues in nef_sequences.values():
        all_residues.extend(chain_residues)
    return all_residues


def _pdb_chain_to_sequence_residues(chain, chain_code: str) -> List[SequenceResidue]:
    """Convert PDB chain to SequenceResidue list"""
    residues = []
    for residue in chain.residues:
        seq_residue = SequenceResidue(
            chain_code=chain_code,
            sequence_code=residue.sequence_code,
            residue_name=residue.residue_name,
        )
        residues.append(seq_residue)
    return residues


def _apply_alignment(
    structure: Structure, alignment_info: Dict[str, Tuple[int, float]]
):
    """Apply sequence alignment offsets to structure"""

    for model in structure.models:
        for chain in model.chains.values():
            chain_code = chain.chain_code or chain.segment_id

            if chain_code in alignment_info:
                offset, ratio = alignment_info[chain_code]

                # Apply offset to all residues in chain
                for residue in chain.residues:
                    residue.sequence_code += offset

    return structure


def _generate_output_filename(input_file: Path, template: str) -> Path:
    """Generate output filename using template"""
    file_name = input_file.stem
    output_name = template.format(file_name=file_name)

    # Check if output name already has the right extension
    if output_name.lower().endswith((".pdb", ".cif", ".mmcif", ".pdbx")):
        output_file = input_file.parent / output_name
    else:
        # Preserve the original file extension
        output_file = input_file.parent / f"{output_name}{input_file.suffix}"

    return output_file


def _write_structure(structure: Structure, original_file: Path, output_file: Path):
    """Write structure to file in the same format as input"""

    # Read original file to preserve format and headers
    with open(original_file, "r") as fh:
        original_lines = fh.readlines()

    # Determine file type
    file_type = guess_cif_or_pdb(original_lines, str(original_file))

    if file_type == RCSBFileType.PDB:
        _write_pdb_structure(structure, original_lines, output_file)
    elif file_type == RCSBFileType.CIF:
        _write_cif_structure(structure, original_lines, output_file)
    else:
        exit_error(f"Unknown file type for {original_file}")


def _write_pdb_structure(
    structure: Structure, original_lines: List[str], output_file: Path
):
    """Write PDB structure with updated sequence codes"""

    # Create mapping of old to new sequence codes
    sequence_mapping = {}

    for model in structure.models:
        for chain in model.chains.values():
            chain_key = chain.chain_code or chain.segment_id
            for residue in chain.residues:
                for atom in residue.atoms:
                    old_key = (chain_key, atom.serial)
                    sequence_mapping[old_key] = residue.sequence_code

    # Process original lines and update sequence codes
    output_lines = []
    for line in original_lines:
        if line.startswith(("ATOM  ", "HETATM")):
            # Update sequence code in ATOM/HETATM records
            chain_code = line[21:22].strip() or line[72:76].strip()
            serial = int(line[6:11].strip())

            key = (chain_code, serial)
            if key in sequence_mapping:
                new_seq_code = sequence_mapping[key]
                # Replace sequence code (columns 23-26)
                new_line = line[:22] + f"{new_seq_code:4d}" + line[26:]
                output_lines.append(new_line)
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)

    # Write to output file
    with open(output_file, "w") as fh:
        fh.writelines(output_lines)


def _write_cif_structure(
    structure: Structure, original_lines: List[str], output_file: Path
):
    """Write mmCIF structure with updated sequence codes"""

    # Create mapping of atom IDs to new sequence codes
    sequence_mapping = {}
    for model in structure.models:
        for chain in model.chains.values():
            for residue in chain.residues:
                for atom in residue.atoms:
                    sequence_mapping[atom.serial] = residue.sequence_code

    # Process original lines and update sequence codes
    output_lines = []
    in_atom_site = False
    atom_site_headers = []
    seq_id_index = None
    auth_seq_id_index = None
    id_index = None

    for line in original_lines:
        # Track when we're in atom_site section
        if line.strip().startswith("_atom_site."):
            in_atom_site = True
            atom_site_headers.append(line.strip())

            # Find relevant column indices
            if "_atom_site.id" in line:
                id_index = len(atom_site_headers) - 1
            elif "_atom_site.label_seq_id" in line:
                seq_id_index = len(atom_site_headers) - 1
            elif "_atom_site.auth_seq_id" in line:
                auth_seq_id_index = len(atom_site_headers) - 1

            output_lines.append(line)

        elif line.strip().startswith("#") or line.strip() == "":
            if in_atom_site:
                in_atom_site = False
                atom_site_headers = []
            output_lines.append(line)

        elif in_atom_site and not line.strip().startswith(("_", "loop_", "#")):
            # This is an atom site data line
            fields = line.strip().split()

            if id_index is not None and id_index < len(fields):
                try:
                    atom_id = int(fields[id_index])
                    if atom_id in sequence_mapping:
                        new_seq_code = sequence_mapping[atom_id]

                        # Update sequence ID fields
                        if seq_id_index is not None and seq_id_index < len(fields):
                            fields[seq_id_index] = str(new_seq_code)
                        if auth_seq_id_index is not None and auth_seq_id_index < len(
                            fields
                        ):
                            fields[auth_seq_id_index] = str(new_seq_code)

                        output_lines.append(" ".join(fields) + "\n")
                    else:
                        output_lines.append(line)
                except (ValueError, IndexError):
                    output_lines.append(line)
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)

    # Write to output file
    with open(output_file, "w") as fh:
        fh.writelines(output_lines)
