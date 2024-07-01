import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry
from tabulate import tabulate

from nef_pipelines.lib.isotope_lib import MAGNETOGYRIC_RATIO_1H
from nef_pipelines.lib.nef_lib import (
    NEF_PIPELINES_PREFIX,
    SelectionType,
    loop_row_namespace_iter,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
    select_frames_by_name,
)
from nef_pipelines.lib.sequence_lib import translate_3_to_1
from nef_pipelines.lib.util import (
    STDIN,
    STDOUT,
    exit_error,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.modelfree import export_app

NAMESPACE = NEF_PIPELINES_PREFIX

MODELFREE_TYPES = "R1 R2 NOE".split()
RELAXATION_EXPERIMENT_TYPES_TO_MODELFREE_TYPES = {
    "heteronuclear_R1_relaxation": "R1",
    "heteronuclear_R2_relaxation": "R2",
    "heteronuclear_NOEs": "NOE",
}


@export_app.command()
def data(
    input_file: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    output_file: Path = typer.Option(
        "mfdata",
        "-o",
        "--out",
        help="file name to output to [default mfdata] for stdout use -",
        metavar="<MODELFREE-DATA>",
    ),
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="force overwrite of output file if it exists and isn't empty",
    ),
    frame_selectors=typer.Argument(
        None,
        help="a list of relaxation list frames to output, [default is all], can be reepeated",
    ),
    exact: bool = typer.Option(
        False, "-e", "--exact", help="don't frame names as a wild cards"
    ),
):
    """- write a modelfree data file [alpha]"""

    if not frame_selectors:
        frame_selectors = [
            "*",
        ]
    else:
        frame_selectors = parse_comma_separated_options(frame_selectors)

    entry = read_entry_from_file_or_stdin_or_exit_error(input_file)

    entry = pipe(entry, frame_selectors, exact, Path(output_file), force)

    if entry:
        print(entry)


@dataclass
class ModelfreeRecord:
    experiment_type: str
    spectrometer_frequency: float
    value: float
    value_uncertainty: float
    flag: int = 1


def pipe(
    entry: Entry,
    frame_selectors: List[str],
    exact: bool,
    output_file: Path,
    force: bool,
):

    relaxation_list = f"{NAMESPACE}_relaxation_list"

    relaxation_lists = select_frames(entry, relaxation_list, SelectionType.CATEGORY)

    named_relaxation_lists = select_frames_by_name(
        relaxation_lists, frame_selectors, exact
    )

    _exit_if_output_file_and_no_force(output_file, force)

    relaxation_list_spectrometer_frequencies = _get_spectrometer_frequencies(
        relaxation_lists
    )

    relaxation_list_experiment_types = _get_experiment_types(relaxation_lists, entry)

    relaxation_loop_name = f"_{NAMESPACE}_relaxation"

    data_by_title = {}
    for relaxation_list in named_relaxation_lists:
        relaxation_list_name = relaxation_list.name
        relaxation_loop = (
            relaxation_list[relaxation_loop_name]
            if relaxation_loop_name in relaxation_list
            else None
        )

        for i, row in enumerate(loop_row_namespace_iter(relaxation_loop), start=1):

            title = _build_rows_title(row)

            _exit_if_title_is_too_long(title, row, i, relaxation_list, entry)

            experiment_type = relaxation_list_experiment_types[relaxation_list.name]
            spectrometer_frequency = relaxation_list_spectrometer_frequencies[
                relaxation_list_name
            ]

            modelfree_record = ModelfreeRecord(
                experiment_type,
                spectrometer_frequency,
                row.value,
                row.value_error,
            )

            values_for_title = data_by_title.setdefault(title, {})
            values_for_title[experiment_type] = modelfree_record

    table = []

    output = sys.stdout if output_file == STDOUT else output_file.open("w")
    for title, data in data_by_title.items():
        table.append(
            [
                "spin",
                title,
            ]
        )

        for name in MODELFREE_TYPES:
            datum = data[name] if name in data else None
            if not datum:
                continue
            row = [
                datum.experiment_type,
                datum.spectrometer_frequency,
                datum.value,
                datum.value_uncertainty,
                datum.flag,
            ]
            table.append(row)

        table.append([])

    print(tabulate(table, tablefmt="plain"), file=output)

    if output_file != STDOUT:
        output.close()

    return entry if output_file != STDOUT else None


def _build_rows_title(row):
    chain_code = row.chain_code_1
    sequence_code = row.sequence_code_1
    residue_name = row.residue_name_1

    residue_name_1_letter = translate_3_to_1(
        [residue_name],
    )[0]

    return f"{chain_code}_{sequence_code}_{residue_name_1_letter}"


def _exit_if_title_is_too_long(title, row, i, relaxation_list, entry):
    if len(title) > 10:
        chain_code = row.chain_code_1
        sequence_code = row.sequence_code_1
        residue_name = row.residue_name_1

        residue_name_1_letter = translate_3_to_1(
            [residue_name],
        )[0]

        msg = f"""
                    in entry {entry} in the relaxarion list {relaxation_list.name} at row {i}
                    the title derived from the first atom name is too long modelfree requires
                    less that 10 letters you have {len(title)}

                    the title was: {title}

                    it was built from

                    chain_code: {chain_code}
                    sequence_code: {sequence_code}
                    residue_name: {residue_name_1_letter} [{residue_name}]

                    your chain_code is most probably to long rename the chain with
                    nef rename chain {chain_code} A as an example

                """

        exit_error(msg)


def _get_experiment_types(relaxation_lists, entry):

    result = {}
    for relaxation_list in relaxation_lists:
        nef_experiment_type = relaxation_list.get_tag("experiment_type")[0]

        exit_if_experiment_type_isnt_recognised(
            nef_experiment_type, relaxation_list, entry
        )

        modelfree_experiment_type = RELAXATION_EXPERIMENT_TYPES_TO_MODELFREE_TYPES[
            nef_experiment_type
        ]

        result[relaxation_list.name] = modelfree_experiment_type

    return result


def exit_if_experiment_type_isnt_recognised(
    nef_experiment_type, relaxation_list, entry
):
    if nef_experiment_type not in RELAXATION_EXPERIMENT_TYPES_TO_MODELFREE_TYPES:
        msg = f"""
                in the entry {entry}

                the relaxation list {relaxation_list.name} contains an experiment type
                that the model free converter does understand it was {nef_experiment_type}
                the experiment_types this converter understands are:

                {', '.join(RELAXATION_EXPERIMENT_TYPES_TO_MODELFREE_TYPES)}

            """

        exit_error(msg)


def _exit_if_output_file_and_no_force(output_file, force):
    if output_file.exists() and not force:
        msg = f"""
            The file {output_file} exists

            use the --force option to overwrite it
        """
        exit_error(msg)


def _get_spectrometer_frequencies(relaxation_lists):
    result = {}
    for relaxation_list in relaxation_lists:
        field_strength = relaxation_list.get_tag("field_strength")[0]
        spectrometer_frequency = MAGNETOGYRIC_RATIO_1H * float(field_strength)
        result[relaxation_list.name] = spectrometer_frequency

    return result
