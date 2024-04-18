import pytest

from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.test_lib import read_test_data
from nef_pipelines.transcoders.xplor.psf_lib import PSFParseException, parse_xplor_PSF

A3_AB_PSF = read_test_data("3a_ab.psf", __file__)


def test_parse_3a_ab():
    result = parse_xplor_PSF(A3_AB_PSF)

    assert len(result) == 6

    EXPECTED = tuple(
        [
            SequenceResidue(chain_code="AAAA", sequence_code=1, residue_name="ALA"),
            SequenceResidue(chain_code="AAAA", sequence_code=2, residue_name="ALA"),
            SequenceResidue(chain_code="AAAA", sequence_code=3, residue_name="ALA"),
            SequenceResidue(chain_code="BBBB", sequence_code=11, residue_name="ALA"),
            SequenceResidue(chain_code="BBBB", sequence_code=12, residue_name="ALA"),
            SequenceResidue(chain_code="BBBB", sequence_code=13, residue_name="ALA"),
        ]
    )

    assert EXPECTED == result


EMPTY_PSF = read_test_data("empty.psf", __file__)


def test_parse_empty():
    with pytest.raises(PSFParseException) as excinfo:
        parse_xplor_PSF(EMPTY_PSF, "test-empty-file.psf")

    exception_message = excinfo.value.args[0]

    print(exception_message)

    assert "test-empty-file.psf" in exception_message
    assert "the first line of a PSF file should be 'PSF'" in exception_message


BAD_NATOM_FIELDS_PSF = read_test_data("bad_natom.psf", __file__)


def test_parse_bad_natom():
    with pytest.raises(PSFParseException) as excinfo:
        parse_xplor_PSF(BAD_NATOM_FIELDS_PSF, "bad_natom.psf")

    exception_message = excinfo.value.args[0]

    assert "bad_natom.psf" in exception_message
    assert "can't convert natom to an int" in exception_message


BAD_HEADER_PSF = read_test_data("bad_header.psf", __file__)


def test_parse_bad_header():
    with pytest.raises(PSFParseException) as excinfo:
        parse_xplor_PSF(BAD_HEADER_PSF, "bad_header.psf")

    exception_message = excinfo.value.args[0]

    assert "bad_header.psf" in exception_message
    assert (
        "the first line of a PSF file should be 'PSF' i got 'WIBBLE' "
        in exception_message
    )


BAD_FIELD_COUNT = read_test_data("bad_field_count.psf", __file__)


def test_parse_bad_field_count():
    with pytest.raises(PSFParseException) as excinfo:
        parse_xplor_PSF(BAD_FIELD_COUNT, "bad_field_count.psf")

    exception_message = excinfo.value.args[0]

    assert "8 fields" in exception_message
    assert "atom number 1" in exception_message
    assert "expected 9" in exception_message


BAD_RESID_FIELD = read_test_data("bad_residue_number.psf", __file__)


def test_parse_bad_resid():
    with pytest.raises(PSFParseException) as excinfo:
        parse_xplor_PSF(BAD_RESID_FIELD, "bad_residue_number.psf")

    exception_message = excinfo.value.args[0]

    assert "bad_residue_number" in exception_message
    assert "couldn't convert" in exception_message
    assert "ZZZ" in exception_message


NO_RESIDUES_FOUND = read_test_data("no_residues_found.psf", __file__)


def test_parse_no_residues_found():
    with pytest.raises(PSFParseException) as excinfo:
        parse_xplor_PSF(NO_RESIDUES_FOUND, "no_residues_found.psf")

    exception_message = excinfo.value.args[0]

    assert "no residues found" in exception_message
