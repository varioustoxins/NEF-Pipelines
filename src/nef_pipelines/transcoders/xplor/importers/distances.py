from itertools import zip_longest
from pathlib import Path
from typing import List

import typer

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    file_name_path_to_frame_name,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    ANY_CHAIN,
    sequence_from_entry_or_exit,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.util import parse_comma_separated_options
from nef_pipelines.transcoders.xplor import import_app
from nef_pipelines.transcoders.xplor.xplor_lib import (
    _exit_if_chains_and_filenames_dont_match,
    distance_restraints_to_nef,
    read_distance_restraints_or_exit_error,
)

CHAINS_HELP = """\
                 A list of chains to be used instead or as well as segids. Multiple calls can be used to add multiple
                 chains. Also comma separated list of chains [without spaces] can be added [e.g. --chains A,B,C].
                 Chains are added to save frames in the order the files with restraints are added. '_' indicates to use
                 the segid in the file if chains are not it is assumed they willl be provided by segids'
              """
USE_CHAINS_HELP = (
    "use chains from the command line replacing the segids found in the file"
)


@import_app.command(no_args_is_help=True)
def distances(
    input: Path = typer.Option(
        Path("-"),
        "--input",
        "-i",
        metavar="|INPUT|",
        help="input to read NEF data from [stdin = -]",
    ),
    chains: List[str] = typer.Option(
        ["A"], "--chains", "-c", metavar="<CHAIN> [,<CHAIN>,...", help=CHAINS_HELP
    ),
    use_chains: bool = typer.Option(False, "--use-chains", help=USE_CHAINS_HELP),
    file_names: List[Path] = typer.Argument(
        ..., help="input distance restraint tables", metavar="<DIHEDRALS-TBL>"
    ),
):
    """- read xplor distance restraints [note: currently limited to 'single' atom selections]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    sequence = sequence_from_entry_or_exit(entry)

    chains = parse_comma_separated_options(chains)

    residue_name_lookup = sequence_to_residue_name_lookup(sequence)

    distance_restraints = []

    _exit_if_chains_and_filenames_dont_match(chains, file_names)

    frame_names = []
    for file_name, chain in zip_longest(file_names, chains, fillvalue=ANY_CHAIN):
        frame_names.append(file_name_path_to_frame_name(file_name))
        distance_restraints.append(
            read_distance_restraints_or_exit_error(
                file_name, residue_name_lookup, chain, use_chains
            )
        )

    for i, (restraint_list, frame_name) in enumerate(
        zip(distance_restraints, frame_names)
    ):
        nef_restraints = distance_restraints_to_nef(restraint_list, frame_name)

    entry = add_frames_to_entry(entry, [nef_restraints])

    print(entry)
