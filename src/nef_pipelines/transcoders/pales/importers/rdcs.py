from collections import Counter
from enum import auto
from pathlib import Path
from typing import List

import typer
from pynmrstar import Loop, Saveframe
from strenum import LowercaseStrEnum

from nef_pipelines.lib.nef_frames_lib import NEF_PIPELINES_NAMESPACE
from nef_pipelines.lib.nef_lib import (
    create_nef_save_frame,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.structures import (
    UNUSED,
    AtomLabel,
    RdcRestraint,
    RdcTensorFrameData,
    SequenceResidue,
)
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import (
    VALUES,
    get_column_indices,
    read_db_file_records,
    select_data_records,
    select_records,
)
from nef_pipelines.transcoders.pales import import_app

FLOAT_NAN = float("nan")
UNDEFINED_VECTOR_3D = [FLOAT_NAN, FLOAT_NAN, FLOAT_NAN]

_PALES_ANALYSIS_MODES = ("DC", "DC_CP", "SAUPE_CP")
_PALES_SIMULATION_MODES = ("STERIC", "STERIC_FREE")
_PALES_EXPECTED_REMARKS = (
    "REMARK Dipolar couplings.",
    "REMARK Molecular Alignment Simulation.",
    "REMARK Order matrix.",
    "REMARK Simulation parameters.",
)

_CHAINS_HELP = """\
    chains to import to, to add multiple chains use repeated calls, values can be comma separated there should
    be one chain per file if a single chain is provides for multiple files it is applied to all files
"""

PALES_EIGENVECTOR_AXIS_LIST = "XAXIS YAXIS ZAXIS".split()

app = typer.Typer()


_NEF_RDC_RESTRAINT_FRAME_CATEGORY = "nef_rdc_restraint_list"
_NEF_RDC_RESTRAINT_CATEGORY = "nef_rdc_restraint"
_NEFL_RDC_TENSOR_FRAME_FRAME_CATEGORY = NEF_PIPELINES_NAMESPACE + "_rdc_tensor"

_PALES_RDCS_EXPECTED_FIELDS = (
    "RESID_I RESNAME_I ATOMNAME_I RESID_J RESNAME_J ATOMNAME_J DI D".split()
)


class RestraintOrigin(LowercaseStrEnum):
    MEASURED = auto()
    PREDICTED = auto()
    BACK_CALCULATED = auto()


class PalesDataType(LowercaseStrEnum):
    OBSERVED = auto()
    PREDICTED = auto()
    BACK_CALCULATED = auto()


seen_frame_names = Counter()


# noinspection PyUnusedLocal
@import_app.command()
def rdcs(
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        help="input to read NEF data from [- is stdin]",
    ),
    entry_name: str = typer.Option(
        "pales", "-e", "--entry-name", help="a name for the entry"
    ),
    chain_codes: List[str] = typer.Option(
        [],
        "-c",
        "--chains",
        help=_CHAINS_HELP,
        metavar="<CHAIN-CODE>",
    ),
    frame_name_template: str = typer.Option(
        "{file_name}_{data_type}",
        "-t",
        "--frame-name-template",
        help="name of the frame to add the restraints to, by defauylt templated from the file name",
    ),
    pales_input_files: List[Path] = typer.Argument(
        None,
        help="list of files to read PALES data from [- is stdin]",
    ),
):
    chain_codes = _normalise_chain_codes(chain_codes, pales_input_files)

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name=entry_name)

    entry = pipe(entry, pales_input_files, chain_codes, frame_name_template)

    print(entry)


def pipe(entry, pales_input_files, chain_codes, frame_name_template):

    for file_path, chain_code in zip(pales_input_files, chain_codes):

        db_text = _read_file_or_exit_error(file_path)

        db_records = read_db_file_records(db_text, file_path)
        rdc_data_measured = _parse_rdcs(
            db_records, (chain_code, chain_code), source=PalesDataType.OBSERVED
        )
        rdc_data_calculated = _parse_rdcs(
            db_records, (chain_code, chain_code), source=PalesDataType.PREDICTED
        )

        tensor_data = _parse_rdc_tensor(db_records)
        data_origin = _parse_data_origin(db_records)
        simulation_data = _parse_pales_simulation_data(db_records)

        calculated_frame_name, measured_frame_name = _make_frame_names(
            data_origin, file_path, frame_name_template
        )

        if data_origin != RestraintOrigin.PREDICTED:
            nef_measured_rdc_frame = _create_nef_output_frame(
                measured_frame_name, rdc_data_measured, "measured", None, None
            )
            entry.add_saveframe(nef_measured_rdc_frame)

        nef_calculated_rdc_frame = _create_nef_output_frame(
            calculated_frame_name,
            rdc_data_calculated,
            data_origin,
            simulation_data,
            tensor_data,
        )
        entry.add_saveframe(nef_calculated_rdc_frame)

    return entry


def _parse_pales_simulation_data(db_records):
    simulation_data = {}
    for db_record in select_data_records(db_records, "PALES"):
        simulation_data[db_record.values[1]] = " ".join(db_record.values[2:])
    return simulation_data


def _add_data_origin_to_frame(nef_rdc_frame, data_origin):
    nef_rdc_frame.add_tag("restraint_origin", data_origin)
    return nef_rdc_frame


def _add_da_and_dr_to_frame(nef_rdc_frame, tensor_data):
    if tensor_data.is_defined():
        nef_rdc_frame.add_tag("magnitude", tensor_data.da)
        nef_rdc_frame.add_tag("rhombicity", tensor_data.dr)
    return nef_rdc_frame


def _add_simulation_data_to_frame(nef_rdc_frame, simulation_data):
    if simulation_data:
        simulation_data_string = "\n".join(
            [f"{key}: {value}" for key, value in simulation_data.items()]
        )
        simulation_data_string = f"simulation data:\n\n{simulation_data_string}"

        nef_rdc_frame.add_tag("nefl_comment", simulation_data_string)
    return nef_rdc_frame


def _make_frame_names(data_origin, file_path, frame_name_template):
    if data_origin == RestraintOrigin.MEASURED:
        calculated_data_type = PalesDataType.BACK_CALCULATED
    else:
        calculated_data_type = PalesDataType.PREDICTED
    keys = {"file_name": file_path.stem, "data_type": calculated_data_type}
    calculated_frame_name = frame_name_template.format(**keys)
    keys = {"file_name": file_path.stem, "data_type": PalesDataType.OBSERVED}
    measured_frame_name = frame_name_template.format(**keys)
    if calculated_frame_name in seen_frame_names:
        calculated_frame_name = (
            f"{calculated_frame_name}__{seen_frame_names[calculated_frame_name]}"
        )
    seen_frame_names[calculated_frame_name] += 1
    if measured_frame_name in seen_frame_names:
        measured_frame_name = (
            f"{measured_frame_name}__{seen_frame_names[measured_frame_name]}"
        )
    seen_frame_names[measured_frame_name] += 1
    return calculated_frame_name, measured_frame_name


def _create_nef_output_frame(
    frame_name, rdc_data_measured, data_origin, simulation_data, tensor_data
):
    nef_rdc_frame = _RDCS_to_nef_saveframe(rdc_data_measured, frame_name)
    if tensor_data:
        nef_rdc_frame = _add_da_and_dr_to_frame(nef_rdc_frame, tensor_data)
        if tensor_data.is_defined():
            nef_tensor_loop = rdc_tensors_to_nef_loop(tensor_data)
            nef_rdc_frame.add_loop(nef_tensor_loop)

    nef_rdc_frame = _add_data_origin_to_frame(nef_rdc_frame, data_origin)
    if simulation_data:
        nef_rdc_frame = _add_simulation_data_to_frame(nef_rdc_frame, simulation_data)

    return nef_rdc_frame


def _read_file_or_exit_error(file_path):
    file_name = str(file_path)
    try:
        with file_path.open() as file_h:
            db_text = file_h.readlines()

    except Exception as e:
        exit_error(f"Error reading file {file_name} because {e}", e)
    return db_text


def _normalise_chain_codes(chain_codes, pales_input_files):
    if not pales_input_files:
        _exit_error_no_input_files()
    if not chain_codes:
        chain_codes = ["A"]
    if len(chain_codes) == 1 and len(pales_input_files) > 1:
        chain_codes = chain_codes * len(pales_input_files)
    elif len(chain_codes) != len(pales_input_files):
        _exit_error_number_chains_doesnt_match_number_files(
            chain_codes, pales_input_files
        )
    return chain_codes


def _exit_error_no_input_files():
    exit_error("No input files provided")


def _exit_error_number_chains_doesnt_match_number_files(chain_codes, pales_input_files):
    NEWLINE = "\n"
    input_file_names = [str(file) for file in pales_input_files]
    msg = f"""
            Number of chain codes must be zero or one or must be the same as the number of input files

            I got

            chain codes: {', '.join(chain_codes)}
            file_names:
            {NEWLINE.join(input_file_names)}
        """
    exit_error(msg)


def rdc_tensors_to_nef_loop(tensors: List[RdcTensorFrameData]) -> Loop:
    if isinstance(tensors, RdcTensorFrameData):
        tensors = [
            tensors,
        ]

    loop = Loop.from_scratch()
    loop.category = "_nefpls_tensor"
    loop.add_tag(
        [
            "index",
            "ex_x",
            "ex_y",
            "ex_z",
            "ey_x",
            "ey_y",
            "ey_z",
            "ez_x",
            "ez_y",
            "ez_z",
        ]
    )

    for index, tensor in enumerate(tensors, start=1):
        loop.add_data(
            [
                index,
                *tensor.eigen_vector_x,
                *tensor.eigen_vector_y,
                *tensor.eigen_vector_z,
            ]
        )
    return loop


def rdc_tensor_to_nef_saveframe(tensor: RdcTensorFrameData, frame_name) -> Saveframe:
    saveframe = create_nef_save_frame(_NEFL_RDC_TENSOR_FRAME_FRAME_CATEGORY, frame_name)

    saveframe.add_tag("Da", tensor.da)
    saveframe.add_tag("Dr", tensor.dr)

    loop = rdc_tensors_to_nef_loop([tensor])
    saveframe.add_loop(loop)

    return saveframe


def _parse_data_origin(db_records):
    mode = select_data_records(db_records, "PALES_MODE")

    result = UNUSED
    if mode:
        mode = mode[0].values[1]
        if mode in _PALES_SIMULATION_MODES:
            result = RestraintOrigin.PREDICTED
        elif mode == _PALES_ANALYSIS_MODES:
            result = RestraintOrigin.MEASURED
        else:
            UNUSED  # effectively i don't know
    return result


def _parse_rdc_tensor(db_records):

    raw_da = select_data_records(db_records, "Da")
    da = float(raw_da[0].values[1]) if raw_da else FLOAT_NAN

    raw_dr = select_data_records(db_records, "Dr")
    dr = float(raw_dr[0].values[1]) if raw_dr else FLOAT_NAN

    raw_eigen_vectors = select_data_records(db_records, "EIGENVECTORS")

    raw_eigen_vectors = {
        vector.values[1]: [float(elem) for elem in vector.values[2:]]
        for vector in raw_eigen_vectors
        if len(vector.values) > 1 and vector.values[1] in PALES_EIGENVECTOR_AXIS_LIST
    }

    eigen_vectors = [
        tuple(raw_eigen_vectors[key]) for key in sorted(raw_eigen_vectors.keys())
    ]
    if not eigen_vectors:
        eigen_vectors = [UNDEFINED_VECTOR_3D, UNDEFINED_VECTOR_3D, UNDEFINED_VECTOR_3D]

    return RdcTensorFrameData(da, dr, *eigen_vectors)


def _parse_rdcs(db_records, chain_codes, source):

    _exit_if_not_pales_rdc_file(db_records)

    chain_code_1, chain_code_2 = chain_codes

    rdcs = []

    data = select_records(db_records, VALUES)
    column_indices = get_column_indices(db_records)

    for index, line in enumerate(data, start=1):

        atom_name_1 = line.values[column_indices["ATOMNAME_I"]]
        residue_number_1 = line.values[column_indices["RESID_I"]]
        residue_type_1 = line.values[column_indices["RESNAME_I"]]

        atom_name_2 = line.values[column_indices["ATOMNAME_J"]]
        residue_number_2 = line.values[column_indices["RESID_J"]]
        residue_type_2 = line.values[column_indices["RESNAME_J"]]

        if source == PalesDataType.OBSERVED:
            rdc_value = line.values[column_indices["D_OBS"]]
            rdc_value_uncertainty = None
        else:
            rdc_value = line.values[column_indices["D"]]
            rdc_value_uncertainty = line.values[column_indices["DD"]]

        weight = line.values[column_indices["W"]]

        atom_1 = AtomLabel(
            SequenceResidue(chain_code_1, residue_number_1, residue_type_1), atom_name_1
        )

        atom_2 = AtomLabel(
            SequenceResidue(chain_code_2, residue_number_2, residue_type_2), atom_name_2
        )
        rdc = RdcRestraint(atom_1, atom_2, rdc_value, rdc_value_uncertainty, weight)

        rdcs.append(rdc)

    return rdcs


def _exit_if_not_pales_rdc_file(db_records):
    if not _check_is_pales_rdc_file(db_records):
        file_name = str(db_records.file_name)
        msg = f"""
                File {file_name} is not a valid PALES RDC file
                [which must have the columns {','.join(_PALES_RDCS_EXPECTED_FIELDS)}]
            """
        exit_error(msg)


def _check_is_pales_rdc_file(gdb_file):
    remarks = select_records(gdb_file, "REMARK")

    remark_strings = [remark.values for remark in remarks]
    return set(_PALES_EXPECTED_REMARKS).issubset(remark_strings)


# def _check_is_pales_rdc_file(gdb_file):
#     columns = set(get_gdb_columns(gdb_file))
#     expected_fields = set(_PALES_RDCS_EXPECTED_FIELDS)
#
#     return expected_fields.issubset(columns)


def _RDCS_to_nef_saveframe(rdcs: List[RdcRestraint], frame_name) -> Saveframe:
    saveframe = create_nef_save_frame(_NEF_RDC_RESTRAINT_FRAME_CATEGORY, frame_name)
    saveframe.add_tag("potential_type", UNUSED)

    if rdcs:
        loop = Loop.from_scratch()
        loop.category = "_" + _NEF_RDC_RESTRAINT_CATEGORY
        loop.add_tag(
            [
                "index",
                "restraint_id",
                "chain_code_1",
                "sequence_code_1",
                "residue_name_1",
                "atom_name_1",
                "chain_code_2",
                "sequence_code_2",
                "residue_name_2",
                "atom_name_2",
                "target_value",
                "target_value_uncertainty",
                "scale",
            ]
        )
        saveframe.add_loop(loop)

        for index, rdc in enumerate(rdcs, start=1):
            loop.add_data(
                [
                    index,
                    index,
                    rdc.atom_1.residue.chain_code,
                    rdc.atom_1.residue.sequence_code,
                    rdc.atom_1.residue.residue_name,
                    rdc.atom_1.atom_name,
                    rdc.atom_2.residue.chain_code,
                    rdc.atom_2.residue.sequence_code,
                    rdc.atom_2.residue.residue_name,
                    rdc.atom_2.atom_name,
                    rdc.value,
                    rdc.value_uncertainty,
                    rdc.weight,
                ]
            )

    return saveframe
