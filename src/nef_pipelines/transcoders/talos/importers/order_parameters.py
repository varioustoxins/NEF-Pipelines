from pathlib import Path
from typing import List

import typer
from fyeah import f
from pynmrstar import Entry, Loop

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    create_nef_save_frame,
    read_file_or_exit,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    exit_if_chain_not_in_sequence,
    sequence_from_entry,
)
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import read_db_file_records
from nef_pipelines.transcoders.talos import import_app
from nef_pipelines.transcoders.talos.talos_lib import read_order_parmeters

app = typer.Typer()

FRAME_NAME_HELP = """\
                        name for the frame that will be created,
                        default is {chain_code}_{element_1}{isotope_number_1}_{element_2}{isotope_number_2}
                    """

NEF_PIPELINES = "nefpls"
PIPELINES_ORDER_DATA_CATEGORY = f"{NEF_PIPELINES}_order_data"
DEFAULT_SEPARATOR = "::"
DEFAULT_END = ""


@import_app.command()
def order_parameters(
    chain_code: str = typer.Option(
        "A",
        "--chain",
        help="chain codes for the new chain",
        metavar="<CHAIN-CODE>",
    ),
    frame_name: str = typer.Option(
        "{chain_code}_{element_1}{isotope_number_1}_{element_2}{isotope_number_2}",
        "-f",
        "--frame",
        help=FRAME_NAME_HELP,
    ),
    input: Path = typer.Option(
        None,
        "-i",
        "--input",
        metavar="|INPUT|",
        help="file to read NEF data from",
    ),
    file_name: Path = typer.Argument(
        ..., help="input files of type <TALOS-FILE>.pred", metavar="<PRED-FILE>"
    ),
):
    """-  convert rci order parameters (S2) from a talos file to NEF"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    lines = read_file_or_exit(file_name)

    entry = pipe(entry, lines, chain_code, frame_name, file_name)

    print(entry)


def pipe(
    entry: Entry, lines: List[str], chain_code: str, frame_name: str, file_name: Path
):
    exit_if_chain_not_in_sequence(chain_code, entry, file_name)

    nef_sequence = sequence_from_entry(entry)

    gdb_records = read_db_file_records(lines)

    talos_order = read_order_parmeters(
        gdb_records,
        chain_code=chain_code,
        file_name=file_name,
        nef_sequence=nef_sequence,
    )

    order_data_by_dipoles = {}
    for value in talos_order.values:
        atom = value.atom
        dipole_atom = value.dipole_atom
        dipole_pair = (atom.element, atom.isotope_number), (
            dipole_atom.element,
            dipole_atom.isotope_number,
        )
        atom_pair_values = order_data_by_dipoles.setdefault(dipole_pair, {})

        atom_pair = atom, dipole_atom

        value_set = atom_pair_values.setdefault(atom_pair, {})

        value_set[value.value_type] = (value.value, value.value_error)

    for isotopes, values in order_data_by_dipoles.items():

        # used in f function below
        (element_1, isotope_number_1), (element_2, isotope_number_2) = isotopes
        frame_name = f(frame_name)
        frame_id = f(frame_name)

        frame = create_nef_save_frame(PIPELINES_ORDER_DATA_CATEGORY, frame_id)

        extra_tags = {
            "data_type": "model_free",
            "relaxation_atom_id": "2",
            "source": "estimate",
            "diffusion_model": UNUSED,
        }

        for tag, value in extra_tags.items():
            frame.add_tag(tag, value)

        data_loop = Loop.from_scratch(f"{NEF_PIPELINES}_order_values")

        value_types = set()
        for value in values.values():
            value_types.update(value.keys())

        type_strings = [f"{str(type)}  {str(type)}_err" for type in value_types]
        type_string = " ".join(type_strings)

        tags = f"""
            index
            chain_code_1 sequence_code_1 residue_name_1 atom_name_1
            chain_code_2 sequence_code_2 residue_name_2 atom_name_2
            {type_string}
            """.lower().split()

        for tag in tags:
            data_loop.add_tag(tag)

        frame.add_loop(data_loop)

        for index, ((atom_1, atom_2), value_dict) in enumerate(values.items(), start=1):
            residue_1 = atom_1.residue
            residue_2 = atom_2.residue
            row = {
                "index": index,
                "chain_code_1": residue_1.chain_code,
                "sequence_code_1": residue_1.sequence_code,
                "residue_name_1": residue_1.residue_name,
                "atom_name_1": atom_1.atom_name,
                "chain_code_2": residue_2.chain_code,
                "sequence_code_2": residue_2.sequence_code,
                "residue_name_2": residue_2.residue_name,
                "atom_name_2": atom_2.atom_name,
            }

            for value_type, (value, error) in value_dict.items():
                value_type = value_type.lower()
                row[str(value_type)] = value
                row[f"{value_type}_err"] = error

            data_loop.add_data(
                [
                    row,
                ]
            )

        entry.add_saveframe(frame)

        return entry
