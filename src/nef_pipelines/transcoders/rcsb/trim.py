from pathlib import Path
from typing import Dict, List, Set

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.sequence_lib import sequences_from_frames
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import exit_error, info, warn
from nef_pipelines.transcoders.rcsb import app as rcsb_app
from nef_pipelines.transcoders.rcsb.rcsb_lib import (
    RCSBFileType,
    Structure,
    guess_cif_or_pdb,
    parse_cif,
    parse_pdb,
)


@rcsb_app.command()
def trim(
    pdb_file: Path = typer.Argument(..., help="PDB or mmCIF file to trim"),
    nef_input: Path = typer.Option(
        Path("-"),
        "-i",
        "--in",
        help="NEF file to read molecular system from [stdin if -]",
    ),
    output_template: str = typer.Option(
        "{file_name}_trimmed",
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
    keep_hetero: bool = typer.Option(
        False, "--keep-hetero", help="keep hetero atoms (non-protein residues)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="show verbose trimming information"
    ),
):
    r"""\- trim pdb/cif to match NEF chains α"""

    # Read NEF entry
    entry = read_entry_from_file_or_stdin_or_exit_error(nef_input)

    # Read PDB/mmCIF structure
    structure = _read_structure(pdb_file)

    # Get NEF sequences
    nef_sequences = _get_nef_sequences(entry)

    # Parse chain mapping if provided
    chain_map = _parse_chain_mapping(chain_mapping) if chain_mapping else {}

    # Determine which residues to keep
    residues_to_keep = _determine_residues_to_keep(
        structure, nef_sequences, chain_map, keep_hetero, verbose
    )

    # Trim structure
    trimmed_structure = _trim_structure(structure, residues_to_keep)

    # Write trimmed structure
    output_file = _generate_output_filename(pdb_file, output_template)
    _write_structure(trimmed_structure, pdb_file, output_file)

    if verbose:
        info(f"Trimmed structure written to: {output_file}")


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


def _determine_residues_to_keep(
    structure: Structure,
    nef_sequences: Dict[str, List[SequenceResidue]],
    chain_map: Dict[str, str],
    keep_hetero: bool,
    verbose: bool,
) -> Dict[str, Set[int]]:
    """Determine which residues to keep for each chain"""

    residues_to_keep = {}

    if not structure.models:
        exit_error("No models found in structure")

    model = structure.models[0]

    for chain in model.chains.values():
        pdb_chain_code = chain.chain_code or chain.segment_id

        # Determine NEF chain to compare to
        nef_chain_code = chain_map.get(pdb_chain_code, pdb_chain_code)

        chain_residues_to_keep = set()

        if nef_chain_code not in nef_sequences:
            if verbose:
                warn(
                    f"PDB chain {pdb_chain_code} -> NEF chain {nef_chain_code} not found in NEF file"
                )
                if keep_hetero:
                    info(
                        f"  Keeping all residues in chain {pdb_chain_code} (no NEF reference)"
                    )
                    chain_residues_to_keep.update(
                        res.sequence_code for res in chain.residues
                    )
            if not keep_hetero:
                continue
        else:
            # Get NEF sequence codes for this chain
            nef_sequence_codes = {
                r.sequence_code for r in nef_sequences[nef_chain_code]
            }

            # Check each residue in PDB chain
            for residue in chain.residues:
                pdb_seq_code = residue.sequence_code
                pdb_res_name = residue.residue_name

                # Standard amino acids/nucleotides - check against NEF sequence
                if _is_standard_residue(pdb_res_name):
                    if pdb_seq_code in nef_sequence_codes:
                        chain_residues_to_keep.add(pdb_seq_code)
                        if verbose:
                            info(
                                f"  Keeping {pdb_chain_code}:{pdb_seq_code}:{pdb_res_name} (in NEF)"
                            )
                    else:
                        if verbose:
                            info(
                                f"  Removing {pdb_chain_code}:{pdb_seq_code}:{pdb_res_name} (not in NEF)"
                            )
                else:
                    # Hetero atom - keep if requested
                    if keep_hetero:
                        chain_residues_to_keep.add(pdb_seq_code)
                        if verbose:
                            info(
                                f"  Keeping {pdb_chain_code}:{pdb_seq_code}:{pdb_res_name} (hetero)"
                            )
                    else:
                        if verbose:
                            info(
                                f"  Removing {pdb_chain_code}:{pdb_seq_code}:{pdb_res_name} (hetero)"
                            )

        if chain_residues_to_keep:
            residues_to_keep[pdb_chain_code] = chain_residues_to_keep

        if verbose:
            total_residues = len(chain.residues)
            kept_residues = len(chain_residues_to_keep)
            info(
                f"Chain {pdb_chain_code}: keeping {kept_residues}/{total_residues} residues"
            )

    return residues_to_keep


def _is_standard_residue(residue_name: str) -> bool:
    """Check if residue is a standard amino acid or nucleotide"""
    standard_aa = {
        "ALA",
        "CYS",
        "ASP",
        "GLU",
        "PHE",
        "GLY",
        "HIS",
        "ILE",
        "LYS",
        "LEU",
        "MET",
        "ASN",
        "PRO",
        "GLN",
        "ARG",
        "SER",
        "THR",
        "VAL",
        "TRP",
        "TYR",
    }
    standard_na = {
        "A",
        "C",
        "G",
        "T",
        "U",  # DNA/RNA
        "DA",
        "DC",
        "DG",
        "DT",  # DNA
        "RA",
        "RC",
        "RG",
        "RU",  # RNA
    }

    return residue_name in standard_aa or residue_name in standard_na


def _trim_structure(
    structure: Structure, residues_to_keep: Dict[str, Set[int]]
) -> Structure:
    """Remove residues not in the keep list"""

    for model in structure.models:
        chains_to_remove = []

        for chain_key, chain in model.chains.items():
            chain_code = chain.chain_code or chain.segment_id

            if chain_code not in residues_to_keep:
                # Remove entire chain
                chains_to_remove.append(chain_key)
                continue

            keep_set = residues_to_keep[chain_code]
            residues_to_remove = []

            # Mark residues for removal
            for i, residue in enumerate(chain.residues):
                if residue.sequence_code not in keep_set:
                    residues_to_remove.append(i)

            # Remove residues in reverse order to maintain indices
            for i in reversed(residues_to_remove):
                del chain.residues[i]

        # Remove empty chains
        for chain_key in chains_to_remove:
            del model.chains[chain_key]

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
    """Write PDB structure with trimmed residues"""

    # Create set of atoms to keep
    atoms_to_keep = set()
    for model in structure.models:
        for chain in model.chains.values():
            chain_key = chain.chain_code or chain.segment_id
            for residue in chain.residues:
                for atom in residue.atoms:
                    atoms_to_keep.add((chain_key, residue.sequence_code, atom.serial))

    # Process original lines and keep only specified atoms
    output_lines = []
    for line in original_lines:
        if line.startswith(("ATOM  ", "HETATM")):
            # Check if this atom should be kept
            chain_code = line[21:22].strip() or line[72:76].strip()
            try:
                seq_code = int(line[22:26].strip())
                serial = int(line[6:11].strip())

                if (chain_code, seq_code, serial) in atoms_to_keep:
                    output_lines.append(line)
            except (ValueError, IndexError):
                # Skip malformed lines
                continue
        else:
            # Keep non-atom records (headers, etc.)
            output_lines.append(line)

    # Write to output file
    with open(output_file, "w") as fh:
        fh.writelines(output_lines)


def _write_cif_structure(
    structure: Structure, original_lines: List[str], output_file: Path
):
    """Write mmCIF structure with trimmed residues"""

    # Create set of atoms to keep
    atoms_to_keep = set()
    for model in structure.models:
        for chain in model.chains.values():
            for residue in chain.residues:
                for atom in residue.atoms:
                    atoms_to_keep.add(atom.serial)

    # Process original lines and keep only specified atoms
    output_lines = []
    in_atom_site = False
    atom_site_headers = []
    id_index = None

    for line in original_lines:
        # Track when we're in atom_site section
        if line.strip().startswith("_atom_site."):
            in_atom_site = True
            atom_site_headers.append(line.strip())

            # Find atom ID column index
            if "_atom_site.id" in line:
                id_index = len(atom_site_headers) - 1

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
                    if atom_id in atoms_to_keep:
                        output_lines.append(line)
                except (ValueError, IndexError):
                    # Skip malformed lines
                    continue
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)

    # Write to output file
    with open(output_file, "w") as fh:
        fh.writelines(output_lines)
