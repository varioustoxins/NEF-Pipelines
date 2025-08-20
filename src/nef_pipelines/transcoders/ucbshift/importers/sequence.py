import sys
from enum import auto
from pathlib import Path
from typing import List

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry
from strenum import LowercaseStrEnum

from nef_pipelines.lib.nef_lib import (
    NEF_MOLECULAR_SYSTEM,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import sequence_from_entry, sequence_to_nef_frame
from nef_pipelines.lib.util import STDIN, exit_error, parse_comma_separated_options
from nef_pipelines.transcoders.ucbshift import import_app
from nef_pipelines.transcoders.ucbshift.ucbshift_lib import parse_ucbshift_sequence

app = typer.Typer()

NO_CHAIN_START_HELP = """don't include the start chain link type on a chain for the first residue [linkage will be
                         middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                         option multiple times to set chain starts for multiple chains"""
NO_CHAIN_END_HELP = """don't include the end chain link type on a chain for the last residue [linkage will be
                       middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                       option multiple times to set chain ends for multiple chains"""

CHAIN_MODE_HELP = """how to handle conflicting residues when importing sequences into an existing molecular system:
                     ERROR (default) - exit with an error message if there are conflicts between existing and new
                                       residues
                     FORCE - overwrite any conflicting residues in the existing molecular system with the new residues
                             from UCBShift files
                     REPLACE - completely replace the existing molecular system with the new residues from UCBShift
                               files
                     RETAIN - keep existing residues and only add non-conflicting new residues, warn to stderr about
                              any skipped conflicts
                     NEW - create separate named molecular system frames for each input file (e.g.
                           nef_molecular_system_filename)
                     WARN - add all residues but warn to stderr about conflicts, using new residue values for
                            conflicting positions"""


class ChainMode(LowercaseStrEnum):
    ERROR = auto()
    FORCE = auto()
    REPLACE = auto()
    RETAIN = auto()
    NEW = auto()
    WARN = auto()


@import_app.command()
def sequence(
    no_chain_starts: List[str] = typer.Option(
        [], "--no-chain-start", help=NO_CHAIN_START_HELP
    ),
    no_chain_ends: List[str] = typer.Option(
        [], "--no-chain-end", help=NO_CHAIN_END_HELP
    ),
    chain_mode: ChainMode = typer.Option(
        ChainMode.ERROR, "--chain-mode", help=CHAIN_MODE_HELP
    ),
    chain_code: str = typer.Option(
        "A", "--chain-code", help="chain code to assign to the sequence (default: A)"
    ),
    entry_name: str = typer.Option("ucbshift", help="a name for the entry if required"),
    input_path: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="file to read NEF data from default is stdin '-'",
    ),
    file_paths: List[Path] = typer.Argument(
        ..., help="UCBShift CSV files to read", metavar="<UCBSHIFT-CSV-FILES>"
    ),
):
    """- convert sequence from UCBShift CSV file to NEF α"""

    if len(file_paths) == 0:
        exit_error("no UCBShift CSV files provided")

    if input_path and input_path != STDIN:
        entry = read_entry_from_file_or_stdin_or_exit_error(input_path)
    else:
        entry = Entry.from_scratch(entry_id=entry_name)

    no_chain_starts = parse_comma_separated_options(no_chain_starts)
    no_chain_ends = parse_comma_separated_options(no_chain_ends)

    entry = pipe(
        entry, chain_mode, chain_code, file_paths, no_chain_starts, no_chain_ends
    )

    print(entry)


def pipe(entry, chain_mode, chain_code, file_paths, no_chain_starts, no_chain_ends):
    """Process UCBShift sequence files and add to NEF entry"""

    existing_sequence_residues = OrderedSet(sequence_from_entry(entry))

    # Parse all UCBShift CSV files
    all_ucbshift_residues = []
    for file_path in file_paths:
        with open(file_path, "r") as csvfile:
            ucbshift_residues = parse_ucbshift_sequence(
                csvfile, chain_code, str(file_path)
            )
            all_ucbshift_residues.extend(ucbshift_residues)

    if len(all_ucbshift_residues) == 0:
        exit_error(f"no residues read from {file_paths}")

    # Handle chain conflicts based on chain_mode
    final_sequence_residues = _handle_chain_conflicts(
        existing_sequence_residues, all_ucbshift_residues, chain_mode
    )

    # Handle NEW mode by creating separate molecular system frames
    if chain_mode == ChainMode.NEW:
        for file_path in file_paths:
            with open(file_path, "r") as csvfile:
                file_residues = parse_ucbshift_sequence(
                    csvfile, chain_code, str(file_path)
                )
                if file_residues:
                    frame_name = f"nef_molecular_system_{file_path.stem}"
                    sequence_frame = sequence_to_nef_frame(
                        file_residues, no_chain_starts, no_chain_ends
                    )
                    sequence_frame.name = frame_name
                    entry.add_saveframe(sequence_frame)
    else:
        sequence_frame = sequence_to_nef_frame(
            list(final_sequence_residues), no_chain_starts, no_chain_ends
        )

        if NEF_MOLECULAR_SYSTEM in entry:
            entry.remove_saveframe(NEF_MOLECULAR_SYSTEM)
        entry.add_saveframe(sequence_frame)

    return entry


def _handle_chain_conflicts(existing_residues, new_residues, chain_mode):
    """Handle conflicts between existing and new sequence residues based on chain_mode"""

    # Create lookup for existing residues (chain_code, sequence_code) -> residue
    existing_lookup = {
        (res.chain_code, res.sequence_code): res for res in existing_residues
    }

    # Find conflicts
    conflicts = []
    for new_res in new_residues:
        key = (new_res.chain_code, new_res.sequence_code)
        if key in existing_lookup:
            existing_res = existing_lookup[key]
            if existing_res.residue_name != new_res.residue_name:
                conflicts.append((key, existing_res, new_res))

    # Handle conflicts based on mode
    if chain_mode == ChainMode.ERROR:
        if conflicts:
            conflict_msgs = []
            for (chain, seq), existing, new in conflicts:
                conflict_msgs.append(
                    f"chain {chain} residue {seq}: existing={existing.residue_name} vs new={new.residue_name}"
                )
            exit_error("sequence conflicts found:\n" + "\n".join(conflict_msgs))
        # No conflicts, just merge the residues
        result = OrderedSet(existing_residues)
        result.update(new_residues)
        return result

    elif chain_mode == ChainMode.FORCE:
        # Overwrite conflicting residues with new ones
        result = OrderedSet(existing_residues)
        for _, existing, new in conflicts:
            result.discard(existing)
            result.add(new)
        # Add non-conflicting new residues
        for new_res in new_residues:
            if (new_res.chain_code, new_res.sequence_code) not in [
                (c, s) for (c, s), _, _ in conflicts
            ]:
                result.add(new_res)
        return result

    elif chain_mode == ChainMode.REPLACE:
        # Replace the whole molecular system with new residues
        return OrderedSet(new_residues)

    elif chain_mode == ChainMode.RETAIN:
        # Keep existing residues, only add non-conflicting new ones
        result = OrderedSet(existing_residues)
        for new_res in new_residues:
            key = (new_res.chain_code, new_res.sequence_code)
            if key not in existing_lookup:
                result.add(new_res)
        if conflicts:
            for (chain, seq), existing, new in conflicts:
                print(
                    f"Warning: skipping conflicting residue chain {chain} residue {seq}: "
                    f"keeping existing {existing.residue_name}, ignoring new {new.residue_name}",
                    file=sys.stderr,
                )
        return result

    elif chain_mode == ChainMode.NEW:
        # This is handled separately in the main function
        return OrderedSet(new_residues)

    elif chain_mode == ChainMode.WARN:
        # Add all residues but warn about conflicts
        result = OrderedSet(existing_residues)
        for new_res in new_residues:
            key = (new_res.chain_code, new_res.sequence_code)
            if key in existing_lookup:
                existing_res = existing_lookup[key]
                if existing_res.residue_name != new_res.residue_name:
                    print(
                        f"Warning: residue conflict at chain {key[0]} residue {key[1]}: "
                        f"existing={existing_res.residue_name} vs new={new_res.residue_name}, "
                        f"using new value",
                        file=sys.stderr,
                    )
                result.discard(existing_res)
            result.add(new_res)
        return result

    # Should never reach here due to enum validation
    exit_error(f"Unknown chain_mode: {chain_mode}")
