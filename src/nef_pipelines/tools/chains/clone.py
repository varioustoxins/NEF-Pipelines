from dataclasses import replace
from itertools import islice
from typing import List

import typer
from pynmrstar import Entry
from typer import Argument, Option

from nef_pipelines.lib.sequence_lib import (
    chain_code_iter,
    frame_to_chains,
    sequence_from_frame,
    sequence_to_nef_frame,
)
from nef_pipelines.lib.util import (
    exit_error,
    get_pipe_file_or_exit,
    parse_comma_separated_options,
)
from nef_pipelines.tools.chains import chains_app

app = typer.Typer()


# noinspection PyUnusedLocal
@chains_app.command()
def clone(
    target: str = Argument("A", help="chain to clone"),
    count: int = Argument(1, help="how many copys to make"),
    chain_codes: List[str] = Option(
        None,
        "-c",
        "--chains",
        help="new chain codes to add otherwise defaults to next available ascii upper case letter,"
        " can be called mutiple times or be a comma separated list",
    ),
):
    """- duplicate chains one or more times"""

    if not count > 0:
        exit_error(f"clone count must be > 0 i got: {count}")

    chain_codes = parse_comma_separated_options(chain_codes)

    lines = "".join(get_pipe_file_or_exit([]).readlines())

    entry = Entry.from_string(lines)

    molecular_system = entry.get_saveframes_by_category("nef_molecular_system")

    if len(molecular_system) < 1:
        exit_error("couldn't find a molecular system frame in the stream")

    if len(molecular_system) > 1:
        exit_error(
            "found more than one molecular system frame, this is not a valid nef file!"
        )

    molecular_system = molecular_system[0]

    sequence = sequence_from_frame(molecular_system)

    # this should come from a sequence not a frame...
    existing_chain_codes = frame_to_chains(molecular_system)

    if target not in existing_chain_codes:
        exit_error(
            f"couldn't find target chain {target} in {', '.join(existing_chain_codes)}"
        )

    useable_chain_codes = chain_code_iter(chain_codes, [target, *existing_chain_codes])
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
