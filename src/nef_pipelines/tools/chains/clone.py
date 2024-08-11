from dataclasses import replace
from itertools import islice
from pathlib import Path
from typing import List

import typer
from typer import Argument, Option

from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.sequence_lib import (
    chains_from_frames,
    get_chain_code_iter,
    sequence_to_nef_frame,
    sequences_from_frames,
)
from nef_pipelines.lib.util import exit_error, parse_comma_separated_options
from nef_pipelines.tools.chains import chains_app

app = typer.Typer()


# noinspection PyUnusedLocal
@chains_app.command()
def clone(
    input_path: Path = typer.Option(
        None,
        metavar="|PIPE|",
        help="file to read NEF data from default is stdin '-'",
    ),
    target: str = Argument("A", help="chain to clone"),
    count: int = Argument(1, help="how many copys to make"),
    chain_codes: List[str] = Option(
        None,
        "-c",
        "--chains",
        help="new chain codes to add otherwise defaults to next available ascii upper case letter,"
        " can be called multiple times or be a comma separated list",
    ),
):
    """- duplicate chains one or more times"""

    if not count > 0:
        exit_error(f"clone count must be > 0 i got: {count}")

    chain_codes = parse_comma_separated_options(chain_codes)

    entry = read_entry_from_file_or_stdin_or_exit_error(input_path)

    molecular_system = entry.get_saveframes_by_category("nef_molecular_system")

    if len(molecular_system) < 1:
        exit_error("couldn't find a molecular system frame in the stream")

    if len(molecular_system) > 1:
        exit_error(
            "found more than one molecular system frame, this is not a valid nef file!"
        )

    molecular_system = molecular_system[0]

    sequence = sequences_from_frames(molecular_system)

    # this should come from a sequence not a frame...
    existing_chain_codes = chains_from_frames(molecular_system)

    if target not in existing_chain_codes:
        exit_error(
            f"couldn't find target chain {target} in {', '.join(existing_chain_codes)}"
        )
    useable_chain_codes = get_chain_code_iter(
        chain_codes, [target, *existing_chain_codes]
    )
    new_chain_codes = islice(useable_chain_codes, count)

    target_residues = [residue for residue in sequence if residue.chain_code == target]

    for new_chain_code in new_chain_codes:
        for residue in target_residues:
            new_residue = replace(residue, chain_code=new_chain_code)
            sequence.append(new_residue)

    sequence = sorted(sequence)

    molecular_system_frame = sequence_to_nef_frame(sequence)

    entry.remove_saveframe("nef_molecular_system")

    entry.add_saveframe(molecular_system_frame)

    print(entry)
