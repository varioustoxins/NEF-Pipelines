import pytest
from pyparsing import ParseException

from nef_pipelines.lib.test_lib import path_in_test_data
from nef_pipelines.transcoders.xplor.xplor_lib import (
    XPLOR_COMMENT,
    atom_factor,
    dihedral_restraint,
    dihedral_restraints,
    distance_restraints,
    residue_factor,
    segid_factor,
    selection,
)


def test_parse_residue_factor():
    assert residue_factor.parseString("residue   20").get("residue_number")[0] == 20
    assert residue_factor.parseString("residue   -20").get("residue_number")[0] == -20


def test_parse_atom_factor():
    assert atom_factor.parseString("name  HD1#").get("atom_name")[0] == "HD1#"


def test_parse_segid_factor():
    assert segid_factor.parseString("segid  HDAA").get("segment_id")[0] == "HDAA"


def test_parse_selection_name():
    TEST_DATA = "(segid AAAA and resid 23 and  (name HA or name HB))"

    assert selection.parseString(TEST_DATA).getName() == "selection"


def test_simple_selection_no_segid():
    TEST_DATA = "(resid 23 and name HA)"
    result = selection.parseString(TEST_DATA)

    assert result.get("selection")[0][0].get("atom_name")[0] == "HA"
    assert result.get("selection")[0][0].get("residue_number")[0] == 23
    assert result.get("selection")[0][0].get("segment_id") is None


def test_parse_selection_multiple_names():
    TEST_DATA = "(segid AAAA and resid 23 and  (name HA or name HB))"

    result = selection.parseString(TEST_DATA)

    assert list(result.get("selection")[0][0][2][0]) == ["HA", "HB"]


def test_parse_dihedral():
    SEL_1 = "(SEGID AAAA and resid 10 and name HA)"
    SEL_2 = "(SEGID BBBB and resid 11 and name CA)"
    SEL_3 = "(SEGID CCCC and resid 12 and name C)"
    SEL_4 = "(SEGID DDDD and resid 13 and name O)"

    TEST_DATA = f"ASSI {SEL_1} {SEL_2} {SEL_3} {SEL_4}  1.234 4.567 7.8910 2"

    result = dihedral_restraint.parseString(TEST_DATA)[0]
    assert list(result.get("atoms_1")[0]) == ["AAAA", 10, "HA"]
    assert list(result.get("atoms_2")[0]) == ["BBBB", 11, "CA"]
    assert list(result.get("atoms_3")[0]) == ["CCCC", 12, "C"]
    assert list(result.get("atoms_4")[0]) == ["DDDD", 13, "O"]

    assert result.get("energy_constant") == 1.234
    assert result.get("angle") == 4.567
    assert result.get("range") == 7.8910
    assert result.get("exponent") == 2


def test_read_multiple_dihedral_restraints():

    TEST_DATA = open(path_in_test_data(__file__, "test_2_dihedrals.tbl")).read()

    result = dihedral_restraints.ignore(XPLOR_COMMENT).parseString(TEST_DATA)

    assert len(result) == 2

    assert result[0].as_list() == [
        ["AAAA", 1, "C"],
        ["AAAA", 2, "N"],
        ["AAAA", 2, "CA"],
        ["AAAA", 2, "C"],
        1.0,
        -45.7,
        120.5,
        2,
    ]
    assert result[1].as_list() == [
        ["AAAA", 2, "N"],
        ["AAAA", 2, "CA"],
        ["AAAA", 2, "C"],
        ["AAAA", 3, "N"],
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
        dihedral_restraints.ignore(XPLOR_COMMENT).parseString(TEST_DATA, parse_all=True)

    assert "Expected end of text, found 'assign'" in str(e_info.value)


def test_read_multiple_noe_restraints():

    TEST_DATA = open(path_in_test_data(__file__, "test_2_noes.tbl")).read()

    result = distance_restraints.ignore(XPLOR_COMMENT).parseString(TEST_DATA)

    assert len(result) == 2

    assert result[0].as_list() == [
        ["AAAA", 3, "HN"],
        ["AAAA", 3, "HDA#"],
        3.6,
        3.0,
        2.4,
    ]
    assert result[1].as_list() == [
        ["AAAA", 7, "HN"],
        ["AAAA", 7, "HD1#"],
        4.0,
        3.3,
        2.7,
    ]
