import pytest

from nef_pipelines.lib.isotope_lib import Isotope, convert_isotopes


@pytest.mark.parametrize(
    "input, expected",
    [
        ("13C", [Isotope.C13]),
        ("C13", [Isotope.C13]),
        ("12C", ["12C"]),
        (
            Isotope.C13,
            [Isotope.C13],
        ),
        ([Isotope.C13, Isotope.N15], [Isotope.C13, Isotope.N15]),
    ],
)
def test_convert_isotopes(input, expected):
    result = convert_isotopes(input)

    assert result == expected
