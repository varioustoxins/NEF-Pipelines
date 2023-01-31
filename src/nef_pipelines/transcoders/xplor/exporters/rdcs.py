from dataclasses import replace
from pathlib import Path
from typing import List, Tuple

import tabulate
import typer
from pynmrstar import Saveframe

from nef_pipelines.lib.nef_lib import (
    loop_row_dict_iter,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.structures import AtomLabel, RdcRestraint, SequenceResidue
from nef_pipelines.transcoders.xplor import export_app

app = typer.Typer()

TENSOR_ATOMS_HELP = """\
    name of the atoms in the tensor in the order o,z,x,y can be provided as a series of calls or
    or comma separated values with no gaps
"""

TENSOR_CHAIN_CODE_HELP = (
    """chain_code/segid of the tensor frame [taken from nef input if present]"""
)
TENSOR_SEQUENCE_CODE_HELP = (
    """sequence_code of the tensor frame [taken from nef input if present]"""
)
TENSOR_RESIDUE_NAME_HELP = """\
    residue name of the tensor frame [taken from nef input if present, if you have multiple tensor frames the
    default will generally not work and you will need to provide chain codes [segids] or sequence  codes]"""


@export_app.command()
def rdcs(
    tensor_atom_names: List[str] = typer.Option(
        ["OO", "Z", "X", "Y"], "--tensor_atom_names", help=TENSOR_ATOMS_HELP
    ),
    tensor_chain_code: str = typer.Option(
        None, "--tensor-chain-code", help=TENSOR_CHAIN_CODE_HELP
    ),
    tensor_sequence_code: int = typer.Option(
        None, "--tensor-sequence-code", help=TENSOR_SEQUENCE_CODE_HELP
    ),
    tensor_residue_name: str = typer.Option(
        "ANI", "--tensor-residue-name", help=TENSOR_RESIDUE_NAME_HELP
    ),
    frame_selectors: List[str] = typer.Option(
        [],
        "-f",
        "--frame",
        help="selector for the rdc restraint frame to use, can be called multiple times and include wild cards",
    ),
):
    """- convert nef rdc restraints to xplor"""

    tensor_selector = SequenceResidue(
        tensor_chain_code, tensor_sequence_code, tensor_residue_name
    )

    entry = read_entry_from_file_or_stdin_or_exit_error(Path("-"))

    NEF_RDC_CATEGORY = "nef_rdc_restraint_list"

    rdc_frames = entry.get_saveframes_by_category(NEF_RDC_CATEGORY)

    if not frame_selectors:
        frame_selectors = ["*"]

    frames = select_frames_by_name(rdc_frames, frame_selectors)

    restraints = _rdc_restraints_from_frames(frames)

    for i, restraint_list in enumerate(restraints):
        restraints[i] = _translate_atom_names(restraint_list, "xplor")

    for restraint_list, frame in zip(restraints, frames):
        print(f"! restraints from frame {frame.name} in nef entry {entry.entry_id}")
        _print_restraints(restraint_list, tensor_selector, tensor_atom_names)
        print()


def _translate_atom_names(
    restraints: List[RdcRestraint], naming_scheme="iupac"
) -> List[RdcRestraint]:
    result = []
    for restraint in restraints:
        atom_1 = restraint.atom_1
        atom_2 = restraint.atom_2

        if atom_1.atom_name == "H":
            restraint.atom_1 = replace(atom_1, atom_name="HN")

        if atom_2.atom_name == "H":
            restraint.atom_1 = replace(atom_2, atom_name="HN")

        result.append(restraint)

    return result


def _rdc_restraints_from_frames(frames: List[Saveframe]):
    all_results = []
    for frame in frames:
        result = []
        all_results.append(result)

        for row in loop_row_dict_iter(frame.loops[0]):

            atom_1 = AtomLabel(
                SequenceResidue(
                    row["chain_code_1"],
                    int(row["sequence_code_1"]),
                    row["residue_name_1"],
                ),
                row["atom_name_1"],
            )
            atom_2 = AtomLabel(
                SequenceResidue(
                    row["chain_code_2"],
                    int(row["sequence_code_2"]),
                    row["residue_name_2"],
                ),
                row["atom_name_2"],
            )

            rdc = RdcRestraint(
                atom_1,
                atom_2,
                row["target_value"],
                row["target_value_uncertainty"],
            )

            result.append(rdc)

        result.sort()
    return all_results


def _print_restraints(
    restraints: List[RdcRestraint],
    tensor_frame_selector: SequenceResidue,
    tensor_atom_names: Tuple[str, str, str, str],
    value_uncertainty: float = 1.0,
):
    table = []

    for i, restraint in enumerate(restraints):
        origin = tensor_atom_names[0]

        tensor_chain_code = tensor_frame_selector.chain_code
        tensor_sequence_code = tensor_frame_selector.sequence_code
        tensor_residue_name = tensor_frame_selector.residue_name

        selectors = []
        for name, selector in zip(
            ("segid", "resid", "resn"),
            (tensor_chain_code, tensor_sequence_code, tensor_residue_name),
        ):
            if selector is not None:
                selectors.append(f"{name} {selector}")
        selectors = " and ".join(selectors).split()

        row = f"and name {origin} )".split()
        tensor_fields = ["assign", "(", *selectors, *row]
        table.append(tensor_fields)
        num_tensor_fields = len(tensor_fields)

        for name in tensor_atom_names[1:]:
            row = f"and name {name} )".split()
            tensor_fields = ["", "(", *selectors, *row]
            table.append(tensor_fields)
            num_tensor_fields = (
                len(tensor_fields)
                if len(tensor_fields) > num_tensor_fields
                else num_tensor_fields
            )

        atom_1 = restraint.atom_1
        chain_code_1 = atom_1.residue.chain_code
        sequence_code_1 = atom_1.residue.sequence_code
        residue_name_1 = atom_1.residue.residue_name
        atom_name_1 = atom_1.atom_name

        line = (
            f"( segid {chain_code_1} and resid {sequence_code_1}"
            f" and resname {residue_name_1} and name {atom_name_1} )"
        )
        row = line.split()
        row = ["", *row]
        num_row_fields = len(row)
        num_extra_spaces = num_tensor_fields - num_row_fields
        if num_extra_spaces < 0:
            num_extra_spaces = 0
        extra_spaces = [""] * num_extra_spaces
        row = [*row, *extra_spaces]
        table.append(row)

        atom_2 = restraint.atom_2
        chain_code_2 = atom_2.residue.chain_code
        sequence_code_2 = atom_2.residue.sequence_code
        residue_name_2 = atom_2.residue.residue_name
        atom_name_2 = atom_2.atom_name
        line = (
            f"( segid {chain_code_2} and resid {sequence_code_2}"
            f" and resname {residue_name_2} and name {atom_name_2} )"
        )
        row = line.split()
        row = ["", *row]
        num_row_fields = len(row)

        num_extra_spaces = num_tensor_fields - num_row_fields
        if num_extra_spaces < 0:
            num_extra_spaces = 0
        extra_spaces = [""] * num_extra_spaces
        row = [*row, *extra_spaces]

        table.append([*row, restraint.value, value_uncertainty])

        table.append([])

    print(tabulate.tabulate(table, tablefmt="plain", floatfmt="7.3f"))
