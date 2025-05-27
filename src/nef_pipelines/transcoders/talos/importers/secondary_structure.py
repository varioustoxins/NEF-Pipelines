from pathlib import Path
from typing import List

import typer
from fyeah import f
from pynmrstar import Entry, Loop

from nef_pipelines.lib.nef_frames_lib import NEF_PIPELINES_NAMESPACE
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    create_nef_save_frame,
    read_file_or_exit,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    exit_if_chain_not_in_entrys_sequence,
    sequence_from_entry,
)
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import read_db_file_records
from nef_pipelines.transcoders.talos import import_app
from nef_pipelines.transcoders.talos.talos_lib import read_talos_secondary_structure

app = typer.Typer()

PIPELINES_SECONDARY_STRUCTURE_CATEGORY = (
    f"{NEF_PIPELINES_NAMESPACE}_secondary_structure"
)
DEFAULT_SEPARATOR = "::"
DEFAULT_END = ""


FRAME_NAME_HELP = """\
                        name for the frame that will be created,
                        default is {chain_code}_talos
                    """


@import_app.command()
def secondary_structure(
    chain_code: str = typer.Option(
        "A",
        "--chain",
        help="chain codes for the new chain",
        metavar="<CHAIN-CODE>",
    ),
    frame_name: str = typer.Option(
        "{chain_code}_talos", "-f", "--frame", help=FRAME_NAME_HELP
    ),
    input: Path = typer.Option(
        None,
        "-i",
        "--input",
        metavar="|INPUT|",
        help="file to read NEF data from",
    ),
    include_predictions: bool = typer.Option(False, help="include predictions"),
    file_name: Path = typer.Argument(
        ..., help="input files of type <TALOS-FILE>.pred", metavar="<PRED-FILE>"
    ),
):
    """-  convert talos secondary structure predictions to NEF [namespace nefpls]"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    lines = read_file_or_exit(file_name)

    entry = pipe(entry, lines, chain_code, frame_name, file_name, include_predictions)

    print(entry)


def pipe(
    entry: Entry,
    lines: List[str],
    chain_code: str,
    frame_name: str,
    file_name: Path,
    include_predictions: bool,
):

    exit_if_chain_not_in_entrys_sequence(chain_code, entry)

    nef_sequence = sequence_from_entry(entry)

    gdb_records = read_db_file_records(lines)

    talos_secondary_structure = read_talos_secondary_structure(
        gdb_records,
        chain_code=chain_code,
        file_name=file_name,
        nef_sequence=nef_sequence,
        include_predictions=include_predictions,
    )

    frame_name = f(frame_name)

    frame = create_nef_save_frame(PIPELINES_SECONDARY_STRUCTURE_CATEGORY, frame_name)

    extra_tags = {"method": "talos", "version": UNUSED}

    for tag, value in extra_tags.items():
        frame.add_tag(tag, value)

    data_loop = Loop.from_scratch(f"{NEF_PIPELINES_NAMESPACE}_secondary_structure")

    tags = """
        index
        chain_code sequence_code residue_name
        secondary_structure merit comment
        """.lower().split()

    for tag in tags:
        data_loop.add_tag(tag)

    frame.add_loop(data_loop)

    for index, secondary_structure in enumerate(talos_secondary_structure, start=1):

        residue = secondary_structure.residue
        row = {
            "index": index,
            "chain_code": residue.chain_code,
            "sequence_code": residue.sequence_code,
            "residue_name": residue.residue_name,
            "secondary_structure": secondary_structure.secondary_structure,
            "merit": secondary_structure.merit,
            "comment": secondary_structure.comment,  # TODO: lose whole column if there are none...
        }

        data_loop.add_data(
            [
                row,
            ]
        )

    entry.add_saveframe(frame)

    return entry
