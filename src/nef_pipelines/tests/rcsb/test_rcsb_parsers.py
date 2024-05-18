import pytest
from frozendict import frozendict

from nef_pipelines.lib.test_lib import path_in_test_data, read_test_data
from nef_pipelines.transcoders.rcsb.rcsb_lib import (
    PdbSecondaryStructureType,
    RCSBFileType,
    SequenceSource,
    guess_cif_or_pdb,
    parse_cif,
    parse_pdb,
)

FILE_TYPE_TO_READER = {"cif": parse_cif, "pdb": parse_pdb}


@pytest.mark.parametrize(
    "file_name",
    [
        # ("1l2y_short.pdb"),
        ("1l2y_short.cif"),
    ],
)
def test_short(file_name):

    file_path = path_in_test_data(__file__, file_name)
    file_type = file_name.split(".")[-1]

    reader = FILE_TYPE_TO_READER[file_type]

    with open(file_path) as lines:
        structure = reader(lines, file_name)

    assert len(structure.sequences) == 1
    assert len(structure.secondary_structure) == 1
    assert len(structure.models) == 2

    model_0 = structure.models[0]
    model_1 = structure.models[1]
    assert len(model_0.chains) == len(model_1.chains) == 1

    model_0_chain_A = model_0.chains["A"]
    model_1_chain_A = model_1.chains["A"]
    assert len(model_0_chain_A.residues) == len(model_1_chain_A.residues) == 4

    assert model_0_chain_A.residues[0] != model_1_chain_A.residues[0]

    assert list(structure.sequences.keys()) == [
        1,
    ]
    assert structure.sequences[1].id == 1
    assert structure.sequences[1].residues == ["ASN", "LEU", "TYR", "ILE"]
    assert structure.sequences[1].structure is structure

    secondary_structure = structure.secondary_structure["A"][0]
    assert secondary_structure.chain_code == "A"
    assert secondary_structure.start_sequence_code == 1
    assert secondary_structure.end_sequence_code == 4
    assert secondary_structure.alternative_location is None
    assert (
        secondary_structure.secondary_structure_type
        == PdbSecondaryStructureType.HELIX_RIGHT_HANDED_ALPHA
    )
    assert secondary_structure.structure == structure

    EXPECTED_ATOMS = {
        frozendict(
            {
                "model": 1,
                "chain_code": "A",
                "sequence_code": 1,
                "residue_name": "ASN",
                "atom_number": 0,
            }
        ): {
            "atom_name": "N",
            "x": -8.901,
            "y": 4.127,
            "z": -0.555,
            "element": "N",
        },
        frozendict(
            {
                "model": 1,
                "chain_code": "A",
                "sequence_code": 3,
                "residue_name": "TYR",
                "atom_number": 19,
            }
        ): {
            "atom_name": "HE2",
            "x": 0.033,
            "y": 4.952,
            "z": 4.233,
            "element": "H",
        },
        frozendict(
            {
                "model": 2,
                "chain_code": "A",
                "sequence_code": 2,
                "residue_name": "LEU",
                "atom_number": 4,
            }
        ): {
            "atom_name": "CB",
            "x": -4.073,
            "y": 4.863,
            "z": -3.128,
            "element": "C",
        },
        frozendict(
            {
                "model": 2,
                "chain_code": "A",
                "sequence_code": 4,
                "residue_name": "ILE",
                "atom_number": 18,
            }
        ): {
            "atom_name": "HD13",
            "x": -9.973,
            "y": 1.875,
            "z": 1.360,
            "element": "H",
        },
    }

    for key_values, data_values in EXPECTED_ATOMS.items():
        model = structure.models[key_values["model"] - 1]
        chain = model.chains[key_values["chain_code"]]
        residue = chain.residues[key_values["sequence_code"] - 1]
        atom = residue.atoms[key_values["atom_number"]]

        assert model.serial == key_values["model"]
        assert chain.chain_code == key_values["chain_code"]
        assert residue.chain.chain_code == key_values["chain_code"]
        assert atom.residue.residue_name == key_values["residue_name"]
        for key, value in data_values.items():
            assert getattr(atom, key) == value


def test_file_type_from_extension():
    assert guess_cif_or_pdb("", "test.mmcif") == RCSBFileType.CIF
    assert guess_cif_or_pdb("", "test.pdb") == RCSBFileType.PDB


@pytest.mark.parametrize(
    "file_name",
    [
        ("1l2y_short.pdb"),
        ("1l2y_short.cif"),
    ],
)
def test_file_type_from_data(file_name):

    file_type_str = file_name.split(".")[-1]

    file_data = read_test_data(file_name, __file__).split("\n")
    assert guess_cif_or_pdb(file_data) == RCSBFileType[file_type_str.upper()]


@pytest.mark.parametrize(
    "file_name",
    [
        ("1k0o.pdb"),
        ("1k0o.cif"),
    ],
)
def test_parse_clic1(file_name):
    file_data = read_test_data(file_name, __file__).split("\n")
    if file_name.endswith(".pdb"):
        structure = parse_pdb(file_data, file_name)
    elif file_name.endswith(".cif"):
        structure = parse_cif(file_data, file_name)
    else:
        raise Exception(f"unexpected file type {file_name.split('.')[-1]}")

    assert len(structure.sequences) == 1
    assert len(structure.secondary_structure) == 2
    assert list(structure.secondary_structure.keys()) == ["A", "B"]
    assert len(structure.models) == 1

    model_0 = structure.models[0]
    model_0_chain_A = model_0.chains["A"]
    model_0_chain_B = model_0.chains["B"]

    assert len(model_0_chain_A.residues) == 225
    assert len(model_0_chain_B.residues) == 213

    assert list(structure.sequences.keys()) == [
        1,
    ]
    assert structure.sequences[1].id == 1
    assert len(structure.sequences[1].residues) == 241
    assert structure.sequences[1].structure is structure

    for chain in "AB":
        secondary_structure = structure.secondary_structure[chain][0]
        assert (
            secondary_structure.secondary_structure_type
            == PdbSecondaryStructureType.SHEET
        )
        assert secondary_structure.start_sequence_code == 8
        assert secondary_structure.end_sequence_code == 13

        secondary_structure = structure.secondary_structure[chain][-1]
        assert (
            secondary_structure.secondary_structure_type
            == PdbSecondaryStructureType.HELIX_RIGHT_HANDED_ALPHA
        )
        assert secondary_structure.start_sequence_code == 225
        assert secondary_structure.end_sequence_code == 233

    for sequence in structure.sequences.values():
        assert id(sequence.structure) == id(structure)
        assert sequence.id == 1
        assert sequence.source == SequenceSource.SEQRES
