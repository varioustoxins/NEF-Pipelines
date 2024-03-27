from argparse import Namespace
from itertools import zip_longest
from pathlib import Path
from typing import List

import typer

from nef_pipelines.lib.nef_lib import file_name_path_to_frame_name
from nef_pipelines.lib.sequence_lib import (
    ANY_CHAIN,
    get_sequence_or_exit,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.util import (
    parse_comma_separated_options,
    process_stream_and_add_frames,
)
from nef_pipelines.transcoders.xplor import import_app
from nef_pipelines.transcoders.xplor.xplor_lib import (
    _exit_if_chains_and_filenames_dont_match,
    dihedral_restraints_to_nef,
    read_dihedral_restraints_or_exit_error,
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
def dihedrals(
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
        ..., help="input dihedral restraint tables", metavar="<DIHEDRALS-TBL>"
    ),
):
    """- read xplor dihedral restraints"""

    chains = parse_comma_separated_options(chains)

    sequence = get_sequence_or_exit(input)

    residue_name_lookup = sequence_to_residue_name_lookup(sequence)

    dihedral_restraints = []

    _exit_if_chains_and_filenames_dont_match(chains, file_names)

    frame_names = []
    for file_name, chain in zip_longest(file_names, chains, fillvalue=ANY_CHAIN):
        frame_names.append(file_name_path_to_frame_name(file_name))
        dihedral_restraints.append(
            read_dihedral_restraints_or_exit_error(
                file_name, residue_name_lookup, chain, use_chains
            )
        )

    for i, (restraint_list, frame_name) in enumerate(
        zip(dihedral_restraints, frame_names)
    ):
        nef_restraints = dihedral_restraints_to_nef(restraint_list, frame_name)

    entry = process_stream_and_add_frames(
        [nef_restraints], Namespace(pipe=None, entry_name="xplor_dihedral_restraints")
    )

    print(entry)
