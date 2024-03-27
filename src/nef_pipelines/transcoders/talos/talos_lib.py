from pathlib import Path
from typing import List

from nef_pipelines.lib.nef_lib import UNUSED
from nef_pipelines.lib.sequence_lib import (
    get_chain_starts,
    get_residue_name_from_lookup,
    offset_chain_residues,
    sequence_3let_list_from_sequence,
    sequence_3let_to_sequence_residues,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    DiffusionModel,
    RelaxationData,
    RelaxationDataSource,
    RelaxationModelParameter,
    RelaxationModelType,
    RelaxationUnit,
    RelaxationValue,
    Residue,
    SecondaryStructure,
    SecondaryStructureType,
)
from nef_pipelines.lib.util import convert_to_float_or_exit, exit_error
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import (
    VALUES,
    DbFile,
    dbfile_to_first_residue_number,
    exit_if_required_columns_missing,
    gdb_to_3let_sequence,
    get_column_indices,
    get_gdb_columns,
    select_records,
)

SECONDARY_PREDICTION_TRANSLATIONS = {"h": "H", "e": "E", "c": "L"}


SECONDARY_STUCTURE_TRANSLATION = {
    "H": SecondaryStructureType.ALPHA_HELIX,
    "E": SecondaryStructureType.BETA_SHEET,
    "L": SecondaryStructureType.COIL,
    "h": SecondaryStructureType.UNKNOWN,
    "e": SecondaryStructureType.UNKNOWN,
    "c": SecondaryStructureType.UNKNOWN,
}


def _exit_if_sequences_dont_match(chain_code, nef_sequence, talos_sequence):

    nef_sequence_set = set(
        [Residue.from_sequence_residue(residue) for residue in nef_sequence]
    )
    talos_sequence_set = set(
        [Residue.from_sequence_residue(residue) for residue in talos_sequence]
    )

    if not talos_sequence_set.issubset(nef_sequence_set):
        nef_sequence_start = get_chain_starts(nef_sequence)[chain_code]
        nef_sequence_for_chain = [
            residue for residue in nef_sequence if residue.chain_code == chain_code
        ]
        nef_sequence_list = "\n".join(
            sequence_3let_list_from_sequence(
                nef_sequence_for_chain, chain_code=chain_code
            )
        )

        talos_sequence_start = get_chain_starts(talos_sequence)[chain_code]
        talos_sequence_for_chain = [
            residue for residue in talos_sequence if residue.chain_code == chain_code
        ]
        talos_sequence_list = "\n".join(
            sequence_3let_list_from_sequence(
                talos_sequence_for_chain, chain_code=chain_code
            )
        )

        msg = f"""
                nef and talos sequences don't agree...

                talos sequence for chain {chain_code} starts at {talos_sequence_start} and has the sequence
                {talos_sequence_list}

                nef sequence for chain {chain_code} starts at {nef_sequence_start} and has the sequence
                {nef_sequence_list}
            """

        exit_error(msg)


def read_talos_secondary_structure(
    gdb_records: DbFile,
    chain_code: str,
    file_name: str,
    nef_sequence: List[Residue],
    include_predictions: bool,
) -> List[SecondaryStructure]:
    columns = get_gdb_columns(gdb_records)

    required_columns = set("RESID RESNAME CONFIDENCE SS_CLASS".split())
    if not required_columns.issubset(columns):
        exit_if_required_columns_missing(gdb_records, required_columns, file_name)

    sequence_3let = gdb_to_3let_sequence(gdb_records)

    if len(sequence_3let) > 0:

        chain_start = dbfile_to_first_residue_number(gdb_records)

        sequence = sequence_3let_to_sequence_residues(sequence_3let, chain_code)

        sequence = offset_chain_residues(sequence, {chain_code: chain_start - 1})

        _exit_if_sequences_dont_match(chain_code, nef_sequence, sequence)
    else:
        sequence = nef_sequence

    exit_error_if_no_sequence(sequence, file_name)

    return gdb_records_to_secondary_structure(
        gdb_records, sequence, chain_code, include_predictions
    )


def gdb_records_to_secondary_structure(
    gdb_records: DbFile,
    sequence: List[Residue],
    chain_code: str,
    include_predictions: bool = False,
) -> List[SecondaryStructure]:

    residue_lookup = sequence_to_residue_name_lookup(sequence)

    column_indices = get_column_indices(gdb_records)

    result = []
    for record in select_records(gdb_records, VALUES):

        sequence_code = record.values[column_indices["RESID"]]

        residue_name_3let_talos = get_residue_name_from_lookup(
            chain_code, sequence_code, residue_lookup
        )

        talos_secondary_structure = record.values[column_indices["SS_CLASS"]]

        is_prediction = False
        if (
            include_predictions
            and talos_secondary_structure in SECONDARY_PREDICTION_TRANSLATIONS
        ):
            talos_secondary_structure = SECONDARY_PREDICTION_TRANSLATIONS[
                talos_secondary_structure
            ]
            is_prediction = True

        if talos_secondary_structure in SECONDARY_STUCTURE_TRANSLATION:
            secondary_structure = SECONDARY_STUCTURE_TRANSLATION[
                talos_secondary_structure
            ]
        else:
            line_info = record.line_info
            msg = f"""
                    the secondary structure type {talos_secondary_structure} is unrecognised at
                    line: {line_info.line_no} in
                    file: {line_info.file_name} the line was
                    line: {line_info.line}
                """
            exit_error(msg)

        if secondary_structure != SecondaryStructureType.UNKNOWN:
            merit = record.values[column_indices["CONFIDENCE"]]
            merit = convert_to_float_or_exit(merit, record.line_info)
        else:
            merit = UNUSED

        residue = Residue(
            chain_code=chain_code,
            sequence_code=sequence_code,
            residue_name=residue_name_3let_talos,
        )

        comment = ""

        if is_prediction:
            comment = "*PREDICTION*"
        value = SecondaryStructure(residue, secondary_structure, merit, comment=comment)
        result.append(value)

    return result


def gdb_records_to_s2(gdb_records, sequence, chain_code):

    residue_lookup = sequence_to_residue_name_lookup(sequence)

    column_indices = get_column_indices(gdb_records)

    values = []
    for record in select_records(gdb_records, VALUES):

        sequence_code = record.values[column_indices["RESID"]]

        residue_name_3let_talos = get_residue_name_from_lookup(
            chain_code, sequence_code, residue_lookup
        )
        s2 = record.values[column_indices["S2"]]

        residue = Residue(
            chain_code=chain_code,
            sequence_code=sequence_code,
            residue_name=residue_name_3let_talos,
        )
        atom = AtomLabel(atom_name="N", residue=residue, element="N", isotope_number=15)
        dipole_atom = AtomLabel(
            atom_name="H", residue=residue, element="H", isotope_number=1
        )
        value = RelaxationValue(
            atom=atom,
            dipole_atom=dipole_atom,
            unit=RelaxationUnit.UNITLESS,
            value_type=RelaxationModelParameter.S2,
            value=s2,
        )
        values.append(value)

    return RelaxationData(
        model_type=RelaxationModelType.MODEL_FREE,
        values=values,
        diffusion_model=DiffusionModel.SPHERE,
        data_source=RelaxationDataSource.ESTIMATE,
    )


def read_order_parmeters(gdb_records, chain_code, file_name, nef_sequence):

    required_columns = set("RESID RESNAME S2".split())
    exit_if_required_columns_missing(gdb_records, required_columns, file_name)

    sequence_3let = gdb_to_3let_sequence(gdb_records)

    if len(sequence_3let) > 0:

        chain_start = dbfile_to_first_residue_number(gdb_records)

        sequence = sequence_3let_to_sequence_residues(sequence_3let, chain_code)

        sequence = offset_chain_residues(sequence, {chain_code: chain_start - 1})

        _exit_if_sequences_dont_match(chain_code, nef_sequence, sequence)
    else:
        sequence = nef_sequence

    exit_error_if_no_sequence(sequence, file_name)

    return gdb_records_to_s2(gdb_records, sequence, chain_code)


def exit_error_if_no_sequence(sequence, file_name):
    if len(sequence) == 0:
        pref_file_path = Path(file_name).parent / "pred.tab"
        msg = f"""
            There is no sequence from the file {file_name}, please provide a sequence as a nef input stream

            e.g.   nef talos import sequence {pref_file_path}
                 | nef talos import order-parameters {file_name}
        """
        exit_error(msg)
