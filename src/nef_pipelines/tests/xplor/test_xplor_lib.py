import pytest
from pyparsing import ParseException

from nef_pipelines.lib.structures import AtomLabel, SequenceResidue
from nef_pipelines.lib.test_lib import NOQA_E501, path_in_test_data
from nef_pipelines.transcoders.xplor.xplor_lib import (
    XPLOR_COMMENT,
    XPLORParseException,
    _atom_factor,
    _dihedral_restraint,
    _dihedral_restraints,
    _distance_restraints,
    _get_approximate_restraint_strings,
    _get_selection_expressions_from_selection,
    _get_single_atom_selection,
    _NamedToken,
    _residue_factor,
    _segid_factor,
    _selection,
)


def test_parse_residue_factor():
    assert _residue_factor.parseString("residue  20")[0].get_name() == "resid"
    assert _residue_factor.parseString("residue  20")[0][0] == 20
    assert _residue_factor.parseString("residue  -20")[0][0] == -20


def test_parse_atom_factor():
    assert _atom_factor.parseString("name  HD1#")[0].get_name() == "atom"
    assert _atom_factor.parseString("name  HD1#")[0][0] == "HD1#"


def test_parse_segid_factor():
    assert _segid_factor.parseString("segid  HDAA")[0].get_name() == "segid"
    assert _segid_factor.parseString("segid  HDAA")[0][0] == "HDAA"


def test_parse_selection_name():
    TEST_DATA = "(segid AAAA and resid 23 and  (name HA or name HB))"

    selection_result = _selection.parseString(TEST_DATA)

    assert selection_result.getName() == "selection"


def test_simple_selection_no_segid():
    TEST_DATA = "(resid 23 and name HA)"
    result = _selection.parseString(TEST_DATA)

    assert str(result) == "[[[resid : 23, atom : HA]]]"
    assert result.get("selection")[0][0][0][0] == 23
    assert result.get("selection")[0][0][1][0] == "HA"


def test_parse_selection_multiple_names():
    TEST_DATA = "(segid AAAA and resid 23 and  (name HA or name HB))"

    result = _selection.parseString(TEST_DATA)

    assert str(result) == "[[[segid : AAAA, resid : 23, [[atom : HA], [atom : HB]]]]]"

    assert result[0][0][-1][0][0][0] == "HA"
    assert result[0][0][-1][1][0][0] == "HB"


def test_parse_dihedral():
    SEL_1 = "(SEGID AAAA and resid 10 and name HA)"
    SEL_2 = "(SEGID BBBB and resid 11 and name CA)"
    SEL_3 = "(SEGID CCCC and resid 12 and name C)"
    SEL_4 = "(SEGID DDDD and resid 13 and name O)"

    TEST_DATA = f"ASSI {SEL_1} {SEL_2} {SEL_3} {SEL_4}  1.234 4.567 7.8910 2"

    result = _dihedral_restraint.parseString(TEST_DATA)[0]
    assert result.get("atoms_1").as_list() == [
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 10),
                _NamedToken("atom", "HA"),
            ]
        ]
    ]
    assert result.get("atoms_2").as_list() == [
        [
            [
                _NamedToken("segid", "BBBB"),
                _NamedToken("resid", 11),
                _NamedToken("atom", "CA"),
            ]
        ]
    ]
    assert result.get("atoms_3").as_list() == [
        [
            [
                _NamedToken("segid", "CCCC"),
                _NamedToken("resid", 12),
                _NamedToken("atom", "C"),
            ]
        ]
    ]
    assert result.get("atoms_4").as_list() == [
        [
            [
                _NamedToken("segid", "DDDD"),
                _NamedToken("resid", 13),
                _NamedToken("atom", "O"),
            ]
        ]
    ]

    assert result.get("energy_constant") == 1.234
    assert result.get("angle") == 4.567
    assert result.get("range") == 7.8910
    assert result.get("exponent") == 2


def test_read_multiple_dihedral_restraints():

    TEST_DATA = open(path_in_test_data(__file__, "test_2_dihedrals.tbl")).read()

    # print(TEST_DATA)

    result = _dihedral_restraints.ignore(XPLOR_COMMENT).parseString(TEST_DATA)

    assert len(result) == 2

    print(result[0].as_list())
    assert result[0].as_list() == [
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 1),
                _NamedToken("atom", "C"),
            ]
        ],
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 2),
                _NamedToken("atom", "N"),
            ]
        ],
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 2),
                _NamedToken("atom", "CA"),
            ]
        ],
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 2),
                _NamedToken("atom", "C"),
            ]
        ],
        1.0,
        -45.7,
        120.5,
        2,
    ]

    assert result[1].as_list() == [
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 2),
                _NamedToken("atom", "N"),
            ]
        ],
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 2),
                _NamedToken("atom", "CA"),
            ]
        ],
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 2),
                _NamedToken("atom", "C"),
            ]
        ],
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 3),
                _NamedToken("atom", "N"),
            ]
        ],
        1.0,
        65.4,
        120.7,
        2,
    ]


def test_read_3_dihedral_restraints_incomplete():

    TEST_DATA = open(path_in_test_data(__file__, "test_2_dihedrals.tbl")).read()

    TEST_DATA = f"""\
        {TEST_DATA}
        assign (
    """

    with pytest.raises(ParseException) as e_info:
        _dihedral_restraints.ignore(XPLOR_COMMENT).parseString(
            TEST_DATA, parse_all=True
        )

    assert "Expected end of text, found 'assign'" in str(e_info.value)


def test_read_multiple_noe_restraints():

    TEST_DATA = open(path_in_test_data(__file__, "test_2_noes.tbl")).read()

    result = _distance_restraints.ignore(XPLOR_COMMENT).parseString(TEST_DATA)

    assert len(result) == 2

    assert result[0].as_list() == [
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 3),
                _NamedToken("atom", "HN"),
            ]
        ],
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 3),
                _NamedToken("atom", "HDA#"),
            ]
        ],
        3.6,
        3.0,
        2.4,
        "",
    ]
    assert result[1].as_list() == [
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 7),
                _NamedToken("atom", "HN"),
            ]
        ],
        [
            [
                _NamedToken("segid", "AAAA"),
                _NamedToken("resid", 7),
                _NamedToken("atom", "HD1#"),
            ]
        ],
        4.0,
        3.3,
        2.7,
        "",
    ]


def test_get_single_atom_selection_correct():
    TEST_DATA = "(segid AAAA and resid 1 and  name HA)"

    selected_atoms = _selection.parseString(TEST_DATA)

    result = _get_single_atom_selection(
        selected_atoms, residue_types={("AAAA", "1"): "Ala"}
    )

    EXPECTED = AtomLabel(
        atom_name="HA",
        residue=SequenceResidue(chain_code="AAAA", sequence_code=1, residue_name="Ala"),
    )

    assert result == EXPECTED


def test_get_single_atom_selection_multiple_selections():

    TEST_DATA = "((resid 1 and  name HA and segid AAAA) or (resid 2 and  name HB and segid BBBB))"

    selected_atoms = _selection.parseString(TEST_DATA)

    with pytest.raises(XPLORParseException):
        _get_single_atom_selection(selected_atoms, residue_types={("AAAA", "1"): "Ala"})


def test_convert_selection_to_selection_expressions_double():
    selection_text = (
        "((segid AAAA and resid 1 and name HA) or (segid BBBB and resid 2 and name HB))"
    )
    result = _selection.parseString(selection_text, parse_all=True)

    selections = _get_selection_expressions_from_selection(result, selection_text)
    assert len(selections) == 2
    assert str(selections[0]) == "[[segid : AAAA, resid : 1, atom : HA]]"
    assert str(selections[1]) == "[[segid : BBBB, resid : 2, atom : HB]]"


def test_convert_selection_to_selection_expressions_single():
    selection_text = "(segid AAAA and resid 1 and name HA)"
    result = _selection.parseString(selection_text, parse_all=True)

    selections = _get_selection_expressions_from_selection(result, selection_text)

    assert len(selections) == 1
    assert str(selections[0]) == "[[segid : AAAA, resid : 1, atom : HA]]"


def test_convert_selection_to_selection_expressions_double_sub_selection():
    selection_text = (
        "((segid AAAA and resid 1 and name HA) or "
        "((segid AAAA or segid BBBB) and (resid 1 or resid 2) and (name HA or name HB)))"
    )

    result = _selection.parseString(selection_text, parse_all=True)

    selections = _get_selection_expressions_from_selection(result, selection_text)

    assert len(selections) == 2
    assert str(selections[0]) == "[[segid : AAAA, resid : 1, atom : HA]]"
    assert (
        str(selections[1]) == "[["
        "[[segid : AAAA], [segid : BBBB]], "
        "[[resid : 1], [resid : 2]], "
        "[[atom : HA], [atom : HB]]"
        "]]"
    )


def test_get_approximate_restraint():
    dihedrals_path = path_in_test_data(__file__, "test_2_dihedrals.tbl")

    dihdedral_restraints = open(dihedrals_path, "r").read()

    result = _get_approximate_restraint_strings(dihdedral_restraints)

    EXPECTED = [
        """# noqa: E501 \
           assign  (segid AAAA and resid    1 and name C    ) (segid AAAA and resid    2 and name N    )
                   (segid AAAA and resid    2 and name CA   ) (segid AAAA and resid    2 and name C    )    1.0 -45.7   120.5 2
        """.replace(
            NOQA_E501, ""
        ),
        """# noqa: E501 \
           assign  (segid AAAA and resid    2 and name N    ) (segid AAAA and resid    2 and name CA   )
                   (segid AAAA and resid    2 and name C    ) (segid AAAA and resid    3 and name N    )    1.0  65.4   120.7 2
        """.replace(
            NOQA_E501, ""
        ),
    ]

    for expected, reported in zip(EXPECTED, result):
        expected = [elem.strip() for elem in expected.split()]
        reported = [elem.strip() for elem in reported.split()]

        assert reported == expected


def test_get_single_atom_selection_dihderal_restraint():
    dihedrals_path = path_in_test_data(__file__, "test_2_dihedrals.tbl")

    dihdedral_restraints = open(dihedrals_path, "r").read()

    xplor_basic_restraints = _dihedral_restraints.ignore(XPLOR_COMMENT).parseString(
        dihdedral_restraints
    )

    restraint = xplor_basic_restraints[0].get("atoms_1")[0]

    selection_expressions = _get_selection_expressions_from_selection(restraint, "")

    assert len(selection_expressions) == 1

    assert str(selection_expressions[0]) == "[[segid : AAAA, resid : 1, atom : C]]"
