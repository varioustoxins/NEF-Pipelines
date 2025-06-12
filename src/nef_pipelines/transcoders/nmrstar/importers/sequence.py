from dataclasses import replace
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    loop_row_namespace_iter,
    read_entry_from_file_or_exit_error,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    get_chain_code_iter,
    offset_chain_residues,
    sequence_to_nef_frame,
)
from nef_pipelines.lib.structures import Residue
from nef_pipelines.lib.util import STDIN, exit_error, parse_comma_separated_options
from nef_pipelines.transcoders.fasta.importers.sequence import (
    _get_sequence_offsets,
    residues_to_chain_codes,
)
from nef_pipelines.transcoders.nmrstar import import_app

app = typer.Typer()

NO_CHAIN_START_HELP = """don't include the start chain link type on a chain for the first residue [linkage will be
                         middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                         option multiple times to set chain starts for multiple chains"""
NO_CHAIN_END_HELP = """don't include the end chain link type on a chain for the last residue [linkage will be
                       middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                       option multiple times to set chain ends for multiple chains"""


# todo add comment to other sequences etc
@import_app.command()
def sequence(
    chain_codes: List[str] = typer.Option(
        [],
        "--chains",
        help="chain codes to use for the imported chains, can be a a comma separated list or can be called "
        "multiple times",
        metavar="<CHAIN-CODES>",
    ),
    starts: List[str] = typer.Option(
        [],
        "--starts",
        help="first residue number of sequences can be a comma separated list or ",
        metavar="<START>",
    ),
    use_author: bool = typer.Option(False, help="use author field for sequence codes"),
    no_chain_starts: List[str] = typer.Option(
        [], "--no-chain-start", help=NO_CHAIN_START_HELP
    ),
    no_chain_ends: List[str] = typer.Option(
        [], "--no-chain-end", help=NO_CHAIN_END_HELP
    ),
    # # TODO: unused inputs!
    entry_name: str = typer.Option(
        None, help="a name for the entry (defaults to the bmrb entry number)"
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="file to read NEF data from [- is stdin; defaults is stdin]",
    ),
    file_path: Path = typer.Argument(
        ..., help="the file to read", metavar="<NMR-STAR-FILE>"
    ),
):
    """- convert NMR_STAR sequence to NEF [alpha]"""

    chain_codes = parse_comma_separated_options(chain_codes)

    no_chain_starts = parse_comma_separated_options(no_chain_starts)
    if not no_chain_starts:
        no_chain_starts = [False]

    no_chain_ends = parse_comma_separated_options(no_chain_ends)
    if no_chain_ends:
        no_chain_ends = [False]

    starts = [int(elem) for elem in parse_comma_separated_options(starts)]
    if not starts:
        starts = [1]

    nef_entry = read_or_create_entry_exit_error_on_bad_file(input)

    nmrstar_entry = read_entry_from_file_or_exit_error(file_path)

    if entry_name is None:
        entry_name = f"nmrstar_{nmrstar_entry.entry_id}"

    if len(nef_entry.frame_list) == 0:
        nef_entry.entry_id = entry_name

    nef_entry = pipe(
        nef_entry,
        chain_codes,
        starts,
        no_chain_starts,
        no_chain_ends,
        entry_name,
        nmrstar_entry,
        file_path,
        use_author,
    )

    print(nef_entry)


def pipe(
    nef_entry: Entry,
    chain_codes: List[str],
    starts: List[str],
    no_chain_starts: List[str],
    no_chain_ends: List[str],
    entry_name: str,
    nmrstar_entry: Entry,
    file_path: Path,
    use_author: bool,
):

    nef_entry.name = entry_name

    entity_saveframes = nmrstar_entry.get_saveframes_by_category("entity")

    num_entities = len(entity_saveframes)
    if num_entities == 0:
        msg = f"""
            No sequences (entities) found in {file_path}.
        """

        exit_error(msg)

    entity_saveframe_ids = [
        entity.get_tag("_Entity.ID")[0] for entity in entity_saveframes
    ]
    chain_code_iter = get_chain_code_iter(chain_codes)
    entity_id_to_chain_code = {
        int(entity_id): chain_code
        for entity_id, chain_code in zip(entity_saveframe_ids, chain_code_iter)
    }
    # print(entity_id_to_chain_code)
    # import sys
    # sys.exit()

    sequence_residues = []
    for entity_saveframe in entity_saveframes:

        try:
            sequence_loop = entity_saveframe.get_loop("_Entity_comp_index")
        except KeyError:
            # not all entity saveframes have a comp_index loop cf bmr4115 2 [E2]
            continue

        # TODO: add ability to skip unknown chem comps
        # TODO add warnings and check all required fields are present
        for row in loop_row_namespace_iter(sequence_loop):
            if use_author:
                seq_code = row.Auth_seq_ID
            else:
                seq_code = row.ID

            if seq_code == UNUSED and row.Auth_seq_ID != UNUSED:
                seq_code = row.Auth_seq_ID

            residue_name = row.Comp_ID
            entity_id = row.Entity_ID

            residue = Residue(entity_id, seq_code, residue_name)
            sequence_residues.append(residue)

    for i, residue in enumerate(sequence_residues):
        sequence_residues[i] = replace(
            residue, chain_code=entity_id_to_chain_code[residue.chain_code]
        )

    read_chain_codes = residues_to_chain_codes(sequence_residues)

    offsets = _get_sequence_offsets(read_chain_codes, starts)

    sequence_residues = offset_chain_residues(sequence_residues, offsets)

    nmrstar_frame = sequence_to_nef_frame(
        sequence_residues, no_chain_starts, no_chain_ends
    )

    return add_frames_to_entry(
        nef_entry,
        [
            nmrstar_frame,
        ],
    )
