from dataclasses import replace
from enum import auto
from typing import Tuple

from strenum import LowercaseStrEnum

from nef_pipelines.lib.structures import AtomLabel, NewPeak


# this is just a place holder
class NamingScheme(LowercaseStrEnum):
    XPLOR = auto()
    IUPAC = auto()


TranslationScheme = Tuple[NamingScheme, NamingScheme]

XPLOR_IUPAC = NamingScheme.XPLOR, NamingScheme.IUPAC
IUPAC_XPLOR = NamingScheme.IUPAC, NamingScheme.XPLOR
TRANSLATIONS = {
    XPLOR_IUPAC: {
        "HN": "H",
    },
    IUPAC_XPLOR: {
        "H": "HN",
    },
}


def translate_atom_label(
    atom: AtomLabel, translation_scheme: TranslationScheme = XPLOR_IUPAC
) -> AtomLabel:
    """
    Translate an atom name form on sheme to another e.g xplor to iupac
    :param atom: the atom label to translate
    :param translation_scheme: the translation scheme which is a tuple of NamingSchemes defining a translation from the
                                first to the second
    :return: the renamed atom label which is a new instance
    """
    if translation_scheme in TRANSLATIONS:
        translation = TRANSLATIONS[translation_scheme]
    else:
        translation = translation_scheme

    atom_name = atom.atom_name
    if atom_name in translation:
        translated_atom_name = translation[atom_name]
        atom = replace(atom, atom_name=translated_atom_name)
    return atom


def translate_new_peak(
    peak: NewPeak, translation_scheme: TranslationScheme = XPLOR_IUPAC
) -> NewPeak:
    """
    Translate the atom names in a new peak to use a different naming convention according the the translation schema
    :param peak: the peak whose labels need renaming
    :param translation_scheme: the translation scheme which is a tuple of NamingSchemes defining a translation from the
                                first to the second
    :return: the peak with renamed atom labels this is a new instance
    """
    new_shifts = []
    for shift in peak.shifts:
        atom = translate_atom_label(shift.atom, translation_scheme)
        new_shifts.append(replace(shift, atom=atom))

    result = replace(peak, shifts=new_shifts)

    return result
