import pytest
from frozendict import frozendict

from nef_pipelines.lib.pdb_parser import PdbSecondaryStructureType, parse_cif, parse_pdb
from nef_pipelines.lib.test_lib import path_in_test_data

# # test=PdbxReader()
#
# def test_short_cif():
#     short_file_name = "1l2y_short.cif"
#     file_path = path_in_test_data(__file__, short_file_name)
#     lines = open(file_path)
#
#     structure = parse_cif(lines, short_file_name)
#     assert len(structure.sequences) == 1
#     assert len(structure.secondary_structure) == 1
#     assert len(structure.models) == 2
#
#     model_0 = structure.models[0]
#     model_1 = structure.models[1]
#     assert len(model_0.chains) == len(model_1.chains) == 1
#
#     model_0_chain_A = model_0.chains['A']
#     model_1_chain_A = model_1.chains['A']
#     assert len(model_0_chain_A.residues) == len(model_1_chain_A.residues) == 4
#
#     assert model_0_chain_A.residues[0] != model_1_chain_A.residues[0]
#
#     assert list(structure.sequences.keys()) == ['1',]
#     assert structure.sequences['1'].id == '1'
#     assert structure.sequences['1'].residues == ['ASN', 'LEU', 'TYR', 'ILE']
#     assert structure.sequences['1'].structure is structure
#
#     secondary_structure =structure.secondary_structure['A'][0]
#     assert secondary_structure.chain_code == 'A'
#     assert secondary_structure.start_sequence_code ==  1
#     assert secondary_structure.end_sequence_code == 4
#     assert secondary_structure.alternative_location == None
#     assert secondary_structure.secondary_structure_type == PdbSecondaryStructureType.HELIX_RIGHT_HANDED_ALPHA
#     assert secondary_structure.structure == structure
#
#     EXPECTED_ATOMS = {
#         frozendict({'model': 1, 'chain_code': 'A', 'sequence_code': 1, 'residue_name': 'ASN', 'atom_number': 0}): {
#             'name': 'N',
#             'x': -8.901,
#             'y': 4.127,
#             'z': -0.555,
#             'element': 'N',
#         },
#
#         frozendict({'model': 1, 'chain_code': 'A', 'sequence_code': 3,'residue_name': 'TYR', 'atom_number': 19}): {
#             'name': 'HE2',
#             'x': 0.033,
#             'y': 4.952,
#             'z': 4.233,
#             'element': 'H',
#         },
#
#         frozendict({'model': 2, 'chain_code': 'A', 'sequence_code': 2, 'residue_name': 'LEU', 'atom_number': 4}): {
#             'name': 'CB',
#             'x': -4.073,
#             'y':  4.863,
#             'z': -3.128,
#             'element': 'C',
#         },
#
#         frozendict({'model': 2, 'chain_code': 'A', 'sequence_code': 4, 'residue_name': 'ILE', 'atom_number': 18}): {
#             'name': 'HD13',
#             'x': -9.973,
#             'y':  1.875,
#             'z':  1.360,
#             'element': 'H',
#         },
#     }
#
#     for key_values, data_values in EXPECTED_ATOMS.items():
#         model = structure.models[key_values['model']-1]
#         chain = model.chains[key_values['chain_code']]
#         residue = chain.residues[key_values['sequence_code']-1]
#         atom = residue.atoms[key_values['atom_number']]
#
#         assert model.serial == key_values['model']
#         assert chain.chain_code == key_values['chain_code']
#         assert residue.chain.chain_code == key_values['chain_code']
#         assert atom.residue.name == key_values['residue_name']
#         for key, value in data_values.items():
#             assert getattr(atom, key) == value


@pytest.mark.parametrize(
    "file_name, reader_function",
    [
        ("1l2y_short.pdb", parse_pdb),
        ("1l2y_short.cif", parse_cif),
    ],
)
def test_short(file_name, reader_function):

    file_path = path_in_test_data(__file__, file_name)
    lines = open(file_path)

    structure = reader_function(lines, file_name)
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
        "1",
    ]
    assert structure.sequences["1"].id == "1"
    assert structure.sequences["1"].residues == ["ASN", "LEU", "TYR", "ILE"]
    assert structure.sequences["1"].structure is structure

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
            "name": "N",
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
            "name": "HE2",
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
            "name": "CB",
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
            "name": "HD13",
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
        assert atom.residue.name == key_values["residue_name"]
        for key, value in data_values.items():
            assert getattr(atom, key) == value
