# TODO: what do unassigned nmrpipe shifts look like?
# TODO: support general nmrpipe shift input
# TODO: support the HA2|HA3 syntax
# TODO: support unassigned

import sys
from enum import auto
from pathlib import Path
from typing import Dict, List, Tuple

import typer
from fyeah import f
from pynmrstar import Loop, Saveframe
from strenum import StrEnum

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_file_or_exit,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    get_residue_name_from_lookup,
    offset_chain_residues,
    sequence_3let_to_sequence_residues,
    sequence_from_entry,
    sequence_to_chains,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    DihedralRestraint,
    Residue,
    SequenceResidue,
)
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    is_float,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import (
    VALUES,
    DbFile,
    DbRecord,
    gdb_to_3let_sequence,
    get_column_indices,
    get_gdb_columns,
    read_db_file_records,
    select_data_records,
    select_records,
)
from nef_pipelines.transcoders.talos import import_app
from nef_pipelines.transcoders.talos.talos_lib import _exit_if_sequences_dont_match

app = typer.Typer()

CLASS_TO_MERIT = {
    "None": 0.0,
    "Strong": 1.0,
    "Generous": 0.6,
    "Warn": 0.3,
    "Dyn": 0.0,
    "Bad": 0.0,
}

CLASS_HELP = ",".join([f"{class_},{merit}" for class_, merit in CLASS_TO_MERIT.items()])
MERIT_HELP = f"""
a comma separated list of merit pairs of class (one of Dyn, Strong, Generous Warn Bad or None) and value (a floating
point number) e.g dyn,0.0,strong,7.0 [default is {CLASS_HELP}] multiple values can also be added by multiple uses of the
option
"""


# noinspection PyUnusedLocal
@import_app.command()
def restraints(
    chain_code: str = typer.Option(
        "A",
        "-c",
        "--chain",
        help="chain to import to",
        metavar="<CHAIN-CODE>",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        help="input to read NEF data from [- is stdin]",
    ),
    frame_name: str = typer.Option(
        "talos_restraints_{chain_code}_{angle}",
        "-f",
        "--frame",
        help="name for the frame that will be created default is talos_restraints_<CHAIN-CODE>",
    ),
    merits: List[str] = typer.Option([], help=MERIT_HELP),
    file_name: Path = typer.Argument(..., help="input talos output file pred.tab"),
):
    """- convert talos restraints to nef [alpha]"""

    class_to_merit = _parse_merits_and_merge(merits)

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    lines = read_file_or_exit(file_name)

    entry = pipe(entry, lines, file_name, chain_code, frame_name, class_to_merit)

    print(entry)


def _parse_merits_and_merge(merits):
    new_merits = parse_comma_separated_options(merits)

    _exit_error_if_merits_arent_pairs(new_merits)

    new_merits_dict = dict(zip(new_merits[::2], new_merits[1::2]))

    _exit_error_if_merits_have_bad_classes(new_merits_dict)

    new_merits_non_float = {
        key: value for key, value in new_merits_dict.items() if not is_float(value)
    }

    _exit_error_if_merits_arent_floats(new_merits_non_float)

    new_merits = {key.lower(): float(value) for key, value in new_merits_dict.items()}

    return CLASS_TO_MERIT.update(new_merits)


def _exit_error_if_merits_arent_floats(new_merits_non_float):
    if len(new_merits_non_float) > 0:
        new_merits_non_float_string = ", ".join(
            [f"{key}:{value}" for key, value in new_merits_non_float.items()]
        )
        msg = f"""
            merit values must be floats, the following class,values pairs have non float values

            {new_merits_non_float_string}

        """
        exit_error(msg)


def _exit_error_if_merits_have_bad_classes(new_merits_dict):
    unexpected_classes = set(new_merits_dict) - set(CLASS_TO_MERIT.keys())
    if len(unexpected_classes) > 0:
        talos_classes_string = ", ".join(CLASS_TO_MERIT.keys())
        new_class_string = ", ".join(unexpected_classes)
        msg = f"""
        some merit classes provided are not used by TALOS

        Talos classes are:

        {talos_classes_string}

        unexpected classes are:

        {new_class_string}

        """
        exit_error(msg)


def _exit_error_if_merits_arent_pairs(new_merits):
    if len(new_merits) % 2 != 0:
        merit_string = ", ".join(new_merits)
        msg = f"""
        merit values must come in pairs I got {len(new_merits)} values:

        {merit_string}
        """

        exit_error(msg)


DIHEDRAL_FRAME_CATEGORY = "nef_dihedral_restraint_list"
DIHEDRAL_RESTRAINT_TAGS = """index restraint_id restraint_combination_id name
                                chain_code_1 sequence_code_1 residue_name_1 atom_name_1
                                chain_code_2 sequence_code_2 residue_name_2 atom_name_2
                                chain_code_3 sequence_code_3 residue_name_3 atom_name_3
                                chain_code_4 sequence_code_4 residue_name_4 atom_name_4
                                target_value target_value_error
                                ccpn_comment np_merit""".split()


def _dihedral_restraints_to_frame(dihedral_restraints, frame_code, comment):

    frame_code = f"{DIHEDRAL_FRAME_CATEGORY}_{frame_code}"

    frame = Saveframe.from_scratch(frame_code, DIHEDRAL_FRAME_CATEGORY)
    frame.add_tag("sf_category", DIHEDRAL_FRAME_CATEGORY)
    frame.add_tag("sf_framecode", frame_code)
    frame.add_tag("potential_type", "square-well-parabolic")
    frame.add_tag("ccpn_comment", comment)

    loop = Loop.from_scratch("nef_dihedral_restraint")

    for tag in DIHEDRAL_RESTRAINT_TAGS:
        loop.add_tag(tag)

    for index, dihedral_restraint in enumerate(dihedral_restraints, start=1):
        data = {
            "index": index,
            "restraint_id": index,
            "restraint_combination_id": UNUSED,
            "name": dihedral_restraint.name,
            "chain_code_1": dihedral_restraint.atom_1.residue.chain_code,
            "sequence_code_1": dihedral_restraint.atom_1.residue.sequence_code,
            "residue_name_1": dihedral_restraint.atom_1.residue.residue_name,
            "atom_name_1": dihedral_restraint.atom_1.atom_name,
            "chain_code_2": dihedral_restraint.atom_2.residue.chain_code,
            "sequence_code_2": dihedral_restraint.atom_2.residue.sequence_code,
            "residue_name_2": dihedral_restraint.atom_2.residue.residue_name,
            "atom_name_2": dihedral_restraint.atom_2.atom_name,
            "chain_code_3": dihedral_restraint.atom_3.residue.chain_code,
            "sequence_code_3": dihedral_restraint.atom_3.residue.sequence_code,
            "residue_name_3": dihedral_restraint.atom_3.residue.residue_name,
            "atom_name_3": dihedral_restraint.atom_3.atom_name,
            "chain_code_4": dihedral_restraint.atom_4.residue.chain_code,
            "sequence_code_4": dihedral_restraint.atom_4.residue.sequence_code,
            "residue_name_4": dihedral_restraint.atom_4.residue.residue_name,
            "atom_name_4": dihedral_restraint.atom_4.atom_name,
            "target_value": round(dihedral_restraint.target_value, 3),
            "target_value_error": round(dihedral_restraint.target_value_error, 3),
            "np_merit": dihedral_restraint.merit,
            "ccpn_comment": dihedral_restraint.remark,
        }

        loop.add_data(
            [
                data,
            ]
        )

    frame.add_loop(loop)

    return frame


def _get_source_file(gdb_records: DbFile):
    def predicate(x):
        return "Prediction Summary for Chemical Shift Input" in x.values

    records = select_records(gdb_records, "REMARK", predicate)

    file = "unknown"

    if len(records) == 1:
        file = records[0].values.split()[-1]

    return file


def _get_talos_version(gdb_records: DbFile):
    def predicate(x):
        return "Version" in x.values and "INFO" in x.values

    records = select_records(gdb_records, "REMARK", predicate)

    version = "unknown"

    if len(records) == 1:
        version = " ".join(records[0].values.split()[3:-1])

    return version


def pipe(entry, lines, file_name, chain_code, frame_name, class_to_merit=None):

    class_to_merit = CLASS_TO_MERIT if class_to_merit is None else class_to_merit

    nef_sequence = sequence_from_entry(entry)

    nef_chain_codes = sequence_to_chains(nef_sequence)

    gdb_records = read_db_file_records(lines)

    talos_restraints, talos_sequence, angle = _read_dihedral_restraints(
        gdb_records,
        chain_code=chain_code,
        file_name=file_name,
        class_to_merit=class_to_merit,
        nef_sequence=nef_sequence,
    )

    frame_name = f(frame_name)

    if chain_code in nef_chain_codes:
        _exit_if_sequences_dont_match(chain_code, nef_sequence, talos_sequence)
    else:
        _exit_error_no_chain_code(chain_code, file_name)

    source_file = _get_source_file(gdb_records)
    talos_version = _get_talos_version(gdb_records)

    comment = (
        f"file: {file_name}, source file: {source_file}, talos version: {talos_version}"
    )

    dihedral_restraint_frame = _dihedral_restraints_to_frame(
        talos_restraints, frame_name, comment
    )

    add_frames_to_entry(
        entry,
        [
            dihedral_restraint_frame,
        ],
    )

    return entry


def _exit_error_no_chain_code(chain_code, file_name):
    args = " ".join(sys.argv[1:])
    msg = f"""
            There is no sequence defined for the chain {chain_code}, please import a sequence! You may want to do
            nef talos import sequence {file_name} | nef {args}
        """
    exit_error(msg)


REQUIRED_COLUMNS_PHI_PSI = "RESID RESNAME PHI PSI DPHI DPSI CLASS".split()
REQUIRED_COLUMNS_CHI = "RESID RESNAME CHI1 DCHI1".split()


class Angles(StrEnum):
    PHI_PSI = auto()
    CHI1 = auto()


def _check_if_phi_psi_or_chi(columns):
    if "PHI" in columns and "PSI" in columns:
        result = Angles.PHI_PSI
    elif "CHI1" in columns:
        result = Angles.CHI1
    else:
        result = None

    return result


def _read_dihedral_restraints(
    gdb_records: List[DbRecord],
    chain_code: str,
    file_name: str,
    class_to_merit: Dict[str, float],
    nef_sequence: List[SequenceResidue],
) -> List[DihedralRestraint]:

    columns = get_gdb_columns(gdb_records)

    angle_type = _check_if_phi_psi_or_chi(columns)

    _exit_if_no_phi_psi_or_chi_detected(angle_type, columns, file_name)

    if angle_type is Angles.PHI_PSI:
        required_columns = REQUIRED_COLUMNS_PHI_PSI
    elif angle_type is Angles.CHI1:
        required_columns = REQUIRED_COLUMNS_CHI

    _exit_if_required_columns_missing(columns, required_columns, file_name)

    sequence_3let = gdb_to_3let_sequence(gdb_records)

    if len(sequence_3let) > 0:

        chain_start = _first_residue_number(gdb_records)

        sequence = sequence_3let_to_sequence_residues(sequence_3let, chain_code)

        sequence = offset_chain_residues(sequence, {chain_code: chain_start - 1})
    else:
        sequence = nef_sequence

    return (
        _gdb_records_to_torsion_restraints(
            gdb_records, sequence, chain_code, class_to_merit, angle_type
        ),
        sequence,
        angle_type,
    )


def _exit_if_no_phi_psi_or_chi_detected(angle_type, columns, file_name):
    if angle_type is None:
        column_string = ", ".join(columns)
        msg = f"""
            in the file {file_name}
            columns found don't match those for phi/psi or chi1, columns were

            {column_string}
        """
        exit_error(msg)


TALOS_MISSING_VALUE_FLOAT = 9999.0
PHI = "PHI"
PSI = "PSI"
CHI1 = "CHI1"
TORSION_ATOMS = {
    PHI: (("C", 1), ("N", 0), ("CA", 0), ("C", 0)),
    PSI: (("N", 0), ("CA", 0), ("C", 0), ("N", 1)),
    CHI1: (("N", 0), ("CA", 0), ("CB", 0), ("*G", 0)),
}

# these should be looked up in chem comps
CHI1_ATOMS = {
    "ARG": "CG",
    "ASN": "CG",
    "ASP": "CG",
    "CYS": "SG",
    "GLN": "CG",
    "GLU": "CG",
    "HIS": "CG",
    "ILE": "CG1",
    "LEU": "CG",
    "LYS": "CG",
    "MET": "CG",
    "PHE": "CG",
    "PRO": "CG",
    "SER": "OG",
    "THR": "OG1",
    "TRP": "CG1",
    "TYR": "CG",
    "VAL": "CG1",
}


def _residue_to_torsion_atoms(
    chain_code,
    sequence_code: int,
    residue_lookup: Dict[Tuple[str, str], str],
    angle_name: str,
) -> List[AtomLabel]:

    labels = []

    for atom_name, offset in TORSION_ATOMS[angle_name]:

        offset_sequence_code = sequence_code + offset

        residue_name = get_residue_name_from_lookup(
            chain_code, offset_sequence_code, residue_lookup
        )

        if atom_name == "*G":
            atom_name = CHI1_ATOMS[residue_name]

        residue = Residue(chain_code, offset_sequence_code, residue_name)

        labels.append(AtomLabel(residue, atom_name))

    return labels


def _gdb_records_to_torsion_restraints(
    gdb_records, sequence, chain_code, class_to_merit, angle_type
):

    residue_lookup = sequence_to_residue_name_lookup(sequence)

    column_indices = get_column_indices(gdb_records)

    restraints = []
    for record in select_records(gdb_records, VALUES):

        class_ = record.values[column_indices["CLASS"]]

        if class_ in ("None", "na"):
            continue

        if angle_type == Angles.PHI_PSI:

            phi = _build_restraint(
                record,
                "PHI",
                column_indices,
                chain_code,
                residue_lookup,
                class_to_merit,
            )
            psi = _build_restraint(
                record,
                "PSI",
                column_indices,
                chain_code,
                residue_lookup,
                class_to_merit,
            )

            restraints.append(phi)
            restraints.append(psi)
        elif angle_type == Angles.CHI1:
            chi1 = _build_restraint(
                record,
                "CHI1",
                column_indices,
                chain_code,
                residue_lookup,
                class_to_merit,
            )
            restraints.append(chi1)

    return restraints


def _build_restraint(
    record, type, column_indices, chain_code, residue_lookup, class_to_merit
):

    sequence_code = record.values[column_indices["RESID"]]
    class_ = record.values[column_indices["CLASS"]]

    angle = record.values[column_indices[type]]
    delta_angle = record.values[column_indices[f"D{type}"]]
    atoms = _residue_to_torsion_atoms(chain_code, sequence_code, residue_lookup, type)

    merit = 0.0
    remark = ""
    if type in ["PHI", "PSI"]:
        merit = class_to_merit[class_]
        remark = f"class: {class_}"
    elif type == "CHI1":
        merit = 1.0
        Q_Gm = record.values[column_indices["Q_Gm"]]
        Q_Gp = record.values[column_indices["Q_Gp"]]
        Q_T = record.values[column_indices["Q_T"]]

        remark = f"Q_Gm: {Q_Gm}, Q_Gt: {Q_Gp}, Q_T: {Q_T}"

    restraint = DihedralRestraint(
        *atoms,
        target_value=angle,
        target_value_error=delta_angle,
        name=type,
        remark=remark,
        merit=merit,
    )

    return restraint


def _first_residue_number(gdb_records):
    first_residue_records = select_data_records(gdb_records, "FIRST_RESID")
    first_residue = 1
    if len(first_residue_records) == 1:
        first_residue = int(first_residue_records[0].values[1])
    return first_residue


def _exit_if_required_columns_missing(columns, required_columns, file_name):
    column_set = set(columns)

    required_column_set = set(required_columns)

    if not required_column_set.issubset(column_set):
        msg = f"""
            the required column in the file {file_name} are:

            {', '.join(required_columns)}

            found columns are

            {', '.join(columns)}

            missing columns are

            {', '.join(required_column_set - column_set)}
        """

        exit_error(msg)
