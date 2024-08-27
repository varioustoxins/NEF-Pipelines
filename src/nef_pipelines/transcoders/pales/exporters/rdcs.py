from collections import OrderedDict
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, NoReturn, Tuple, Union

import tabulate
import typer
from pynmrstar import Saveframe

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    loop_row_dict_iter,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.sequence_lib import sequence_from_entry, sequence_to_chains
from nef_pipelines.lib.structures import AtomLabel, RdcRestraint, SequenceResidue
from nef_pipelines.lib.translation_lib import IUPAC_XPLOR, translate_atom_label
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    flatten,
    get_display_file_name,
    read_float_or_exit,
)
from nef_pipelines.transcoders.pales import export_app

app = typer.Typer()

# TODO: name translations
# TODO: correct weights
# TODO: move utilities to lib
# TODO: support multiple chains

NEF_RDC_RESTRAINT_FRAME_CATEGORY = "nef_rdc_restraint_list"
NEF_RDC_RESTRAINT_CATEGORY = "nef_rdc_restraint"


# noinspection PyUnusedLocal
@export_app.command()
def rdcs(
    user_chains: List[str] = typer.Option(
        [],
        "-c",
        "--chain",
        help="chains to export, to add mutiple chains use repeated calls  [default: all the chains in the rdc restraint"
        "frames]",
        metavar="<CHAIN-CODE>",
    ),
    file_name_template: str = typer.Option(
        "%s.out",
        "-t",
        "--template",
        help="the template for the filename to export to %s will get replaced by the name of the chain or a filename if"
        "set with the sequence_text-names option",
        metavar="<sequence-sequence_text.seq>",
    ),
    output_to_stdout: bool = typer.Option(
        False, "-o", "--out", help="write the files to stdout for debugging"
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        help="input to read NEF data from [- is stdin]",
    ),
    raw_weights: List[str] = typer.Option(
        [],
        "-w",
        "--weight",
        help="weights for rdcs as a comma separated triple of 2 atom names and a weight [no spaces e.g HN,N,1.0],"
        " multiple weights may be added by repeated calls, efault is HN,N,1.0",
    ),
    segids: bool = typer.Option(
        False,
        "-s",
        "--segids",
        help="include segids in the file",
    ),
    default_uncertainty: float = typer.Option(
        1.0,
        "-u",
        "--uncertainty",
        help="the uncertainty to use if none is provided",
    ),
    frame_selectors: List[str] = typer.Option(
        [],
        "-f",
        "--frame",
        help="selector for the rdc restraint frame to use, can be called multiple times and include wild cards",
    ),
):
    """- convert nef rdc restraints to pales"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    weights = _parse_weights(raw_weights)

    sequence = sequence_from_entry(entry)

    sequence_chains = sequence_to_chains(sequence)

    rdc_frames = entry.get_saveframes_by_category(NEF_RDC_RESTRAINT_FRAME_CATEGORY)

    rdc_restaints_by_frame = {
        frame.name: _rdc_restraints_from_frame(frame, weights) for frame in rdc_frames
    }

    rdc_chains = [
        _rdc_restraints_to_chains(rdc_frame)
        for rdc_frame in rdc_restaints_by_frame.values()
    ]

    rdc_chains = flatten(rdc_chains)

    if not frame_selectors:
        frame_selectors = ["*"]

    rdc_frames = select_frames_by_name(rdc_frames, frame_selectors)

    if not user_chains:
        user_chains = set(rdc_chains).intersection(set(sequence_chains))

    _exit_if_user_chains_not_in_restraints(rdc_chains, user_chains, input, rdc_frames)

    for frame_name, restraints in rdc_restaints_by_frame.items():

        _exit_if_mixed_chain_restraints(restraints, frame_name, input)

        restraints = _translate_atom_names(restraints, IUPAC_XPLOR)

        restraints = _update_restraint_uncertainty(restraints, default_uncertainty)

        print()

        _print_restraints(restraints, weights, segids)


def _translate_atom_names(
    restraints: List[RdcRestraint], naming_scheme=IUPAC_XPLOR
) -> List[RdcRestraint]:
    result = []
    for restraint in restraints:
        atom_1 = restraint.atom_1
        atom_2 = restraint.atom_2

        atom_1 = translate_atom_label(atom_1, naming_scheme)
        atom_2 = translate_atom_label(atom_2, naming_scheme)

        restraint = replace(restraint, atom_1=atom_1)
        restraint = replace(restraint, atom_2=atom_2)
        restraint.atom_1 = atom_1

        result.append(restraint)

    return result


def _rdc_restraints_from_frame(frame: Saveframe, weights: Dict[Tuple[str, str], float]):
    result = []

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

        weight_key = _build_weights_key(row["atom_name_1"], row["atom_name_2"])
        # this should be
        weight = weights[weight_key] if weight_key in weights else 1.0
        rdc = RdcRestraint(
            atom_1,
            atom_2,
            row["target_value"],
            row["target_value_uncertainty"],
            weight,
        )

        result.append(rdc)

    return result


def _parse_weights(raw_weights):

    result = {}
    for raw_weight in raw_weights:

        raw_weight_fields = raw_weight.split(",")

        if len(raw_weight_fields) != 3:
            exit_error(
                f"bad weight {raw_weight} weights should have 3 fields separated by commas [no spaces]"
                f" atom_1,atom_2,weight. e.g HN,N,1.0"
            )

        atom_1, atom_2, raw_rdc_weight = raw_weight_fields

        rdc_weight = read_float_or_exit(
            raw_rdc_weight,
            message=f"weights should have 3 fields separated by commas [no spaces] atom_1,atom_2,weight weight should"
            f" be a float i got {raw_weight} for field feild [{raw_rdc_weight}] which is not a float",
        )

        key = _build_weights_key(atom_1, atom_2)
        result[key] = rdc_weight

    # it not possibe to add default weights?
    HN_N_key = _build_weights_key("HN", "N")
    if HN_N_key not in result:
        result[HN_N_key] = 1.0

    return result


def _build_weights_key(atom_1, atom_2):
    return tuple(sorted([atom_1, atom_2]))


def _print_restraints(
    restraints: List[RdcRestraint],
    weights: Dict[Tuple[str, str], float],
    use_segids: bool = True,
):

    segid_i = "SEGNAME_I" if use_segids else ""
    segid_i_format = "%4s" if use_segids else ""
    segid_j = "SEGNAME_J" if use_segids else ""
    segid_j_format = "%4s" if use_segids else ""

    VARS_1 = f"VARS   {segid_i}        RESID_I RESNAME_I ATOMNAME_I {segid_j}         RESID_J RESNAME_J ATOMNAME_J"
    FORMAT_1 = f"FORMAT {segid_i_format} %5d     %6s       %6s        {segid_j_format}  %5d     %6s       %6s       "

    VARS_2 = "D     DD     W   "
    FORMAT_2 = "%9.3f %9.3f  %.2f"

    VARS = " ".join([VARS_1, VARS_2]).strip().split()
    FORMAT = " ".join([FORMAT_1, FORMAT_2]).strip().split()

    table = [VARS, FORMAT]

    for i, restraint in enumerate(restraints):
        atom_1 = restraint.atom_1
        atom_2 = restraint.atom_2

        weights_key = _build_weights_key(atom_1.atom_name, atom_2.atom_name)
        weight = weights[weights_key]
        row_data = OrderedDict(
            [
                ("chain_code_1", atom_1.residue.chain_code),
                ("sequence_code_1", atom_1.residue.sequence_code),
                ("residue_name_1", atom_1.residue.residue_name),
                ("atom_name_1", atom_1.atom_name),
                ("chain_code_2", atom_2.residue.chain_code),
                ("sequence_code_2", atom_2.residue.sequence_code),
                ("residue.residue_name", atom_2.residue.residue_name),
                ("atom_name", atom_2.atom_name),
                ("target_value", restraint.value),
                ("rdc_error", restraint.value_uncertainty),
                ("weight", weight),
            ]
        )
        row = [""]
        for key, value in row_data.items():
            if "chain_code" not in key:
                row.append(value)
            elif "chain_code" in key and use_segids:
                row.append(value)

        table.append(row)
    print()
    print(tabulate.tabulate(table, tablefmt="plain"))


def _rdc_restraints_to_chains(restrants: List[RdcRestraint]) -> List[str]:
    chains = set()

    for restraint in restrants:

        chains.add(restraint.atom_1.residue.chain_code)
        chains.add(restraint.atom_2.residue.chain_code)

    if UNUSED in chains:
        chains.remove(UNUSED)

    return sorted(list(chains))


def _exit_if_user_chains_not_in_restraints(
    rdc_chains: List[str],
    user_chains: List[str],
    input: Path,
    rdc_frames: List[Saveframe],
) -> Union[None, NoReturn]:
    rdc_chains = set(rdc_chains)
    user_chains = set(user_chains)
    if not rdc_chains.issubset(user_chains):
        missing_chains = user_chains - rdc_chains
        rdc_frame_names = ", ".join([frame.name for frame in rdc_frames])
        msg = f"""\
            some of the selected chains are not present in the restraints in the input nef stream
            the chains selected were: {', '.join(user_chains)}
            the chains in the input were: {', '.join(rdc_chains)}
            the missing chains were: {', '.join(missing_chains) }
            input was: {get_display_file_name(input)}
            rdc_frames_were: {rdc_frame_names}
        """
        exit_error(msg)


def _exit_if_mixed_chain_restraints(
    restraints: List[RdcRestraint], frame_name, input
) -> Union[NoReturn, None]:

    for row, restraint in enumerate(restraints, start=1):

        chain_1 = restraint.atom_1.residue.chain_code
        chain_2 = restraint.atom_2.residue.chain_code
        if chain_1 != chain_2:
            msg = f"""\
                in row {row} of frame {frame_name} in {get_display_file_name(input)}
                the two chains have different chain ids [not currently supported]
                chain 1: {chain_1}, chain_2: {chain_2}
            """

            exit_error(msg)


def _update_restraint_uncertainty(
    restraints: List[RdcRestraint], uncertainty: float
) -> List[RdcRestraint]:
    result = []

    for restraint in restraints:
        if restraint.value_uncertainty == UNUSED:
            result.append(replace(restraint, value_uncertainty=uncertainty))
        else:
            result.append(restraint)

    return result
