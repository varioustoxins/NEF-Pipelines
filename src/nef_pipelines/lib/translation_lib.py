from dataclasses import replace

from nef_pipelines.lib.structures import AtomLabel, NewPeak

TRANSLATIONS = {
    "xplor_to_iupac": {
        "HN": "H",
    },
    "iupac_to_xplor": {
        "H": "HN",
    },
}


# this is just a place holder
def translate_atom_label(
    atom: AtomLabel, translation_scheme="xplor_to_iupac"
) -> AtomLabel:

    if isinstance(translation_scheme, str):
        if translation_scheme in TRANSLATIONS:
            translation = TRANSLATIONS[translation_scheme]
    else:
        translation = translation_scheme

    atom_name = atom.atom_name
    if atom_name in translation:
        translated_atom_name = translation[atom_name]
        atom = replace(atom, atom_name=translated_atom_name)
    return atom


def translate_new_peak(peak: NewPeak, translation_schemca="xplor_to_iupac") -> NewPeak:
    new_shifts = []
    for shift in peak.shifts:
        atom = translate_atom_label(shift.atom)
        new_shifts.append(replace(shift, atom=atom))

    result = replace(peak, shifts=new_shifts)

    return result
