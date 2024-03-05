import string
from enum import auto

from strenum import UppercaseStrEnum


class Isotope(UppercaseStrEnum):
    H1 = auto()
    H2 = auto()
    H3 = auto()
    N15 = auto()
    C13 = auto()
    O17 = auto()
    F19 = auto()
    P31 = auto()

    def __str__(self):
        element = self.name.rstrip(string.digits)
        isotope_number = self.name[len(element) :]
        return f"{isotope_number}{element}"


# fmt: off
GAMMA_RATIOS = {
    # Nuc	        ratio	        # (MHz⋅T−1)
    Isotope.H1:     1.0,            # 42.58
    Isotope.H2:     0.153508386,    # 6.54
    Isotope.H3:     1.066643718,    # 45.42
    Isotope.C13:    0.251503855,    # 10.71
    Isotope.N15:    0.101368145,    # -4.32 - should really be negative !
    Isotope.O17:    0.135564627,    # -5.77 - should really be negative !
    Isotope.F19:    0.94129576,     # 40.08
    Isotope.P31:    0.404791467,    # 17.24
}

ATOM_TO_ISOTOPE = {
    # Nuc   Isotope
    "H": Isotope.H1,
    "D": Isotope.H2,
    "T": Isotope.H3,
    "C": Isotope.C13,
    "N": Isotope.N15,
    "O": Isotope.O17,
    "F": Isotope.F19,
    "P": Isotope.P31,
}
# fmt: on
