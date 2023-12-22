import sys
from dataclasses import replace

import pydantic

from nef_pipelines.lib.structures import AtomLabel, SequenceResidue
from nef_pipelines.lib.translation.io import CHEM_COMPS, load_chem_comps
from nef_pipelines.lib.util import exit_error

TRANSLATION_CACHE = {}


def exit_no_naming_system(system):
    msg = f" the atom name translator can't find the naming system {system}"
    exit_error(msg)


def translate_from(
    atom: AtomLabel, system: str, mol_type: str = "protein"
) -> AtomLabel:

    cache_key = atom, mol_type, system

    if cache_key in TRANSLATION_CACHE:
        translated_atom_name = TRANSLATION_CACHE[cache_key]
    else:

        key = mol_type.upper(), atom.residue.residue_name.upper()
        chem_comp = CHEM_COMPS[key]

        sought_naming_system = None
        for naming_system in chem_comp.namingSystems:
            if naming_system.name.upper() == system.upper():
                sought_naming_system = naming_system

        if sought_naming_system is None:
            exit_no_naming_system(system)

        atom_name = atom.atom_name.upper()
        translated_atom_name = atom_name

        ambiguity_mappings = [
            app_data
            for app_data in chem_comp.applicationData
            if app_data.application == "ccpNmr"
            and app_data.keyword == "ambiguityMapping"
        ]
        mapping = [
            ambiguity_mapping.value[1]
            for ambiguity_mapping in ambiguity_mappings
            if ambiguity_mapping.value[0].upper() == atom_name.upper()
        ]

        if len(mapping) == 1:
            translated_atom_name = mapping[0]
        elif len(mapping):
            print(f"unexpected multiple mapping {mapping}", file=sys.stderr)
        else:
            for atom_sys_name in sought_naming_system.atomSysNames:
                if atom_sys_name.sysName.upper() == atom_name.upper():
                    translated_atom_name = atom_sys_name.atomName

        TRANSLATION_CACHE[cache_key] = translated_atom_name

    return (
        replace(atom, atom_name=translated_atom_name)
        if translated_atom_name != atom.atom_name
        else atom
    )


if __name__ == "__main__":

    from codetiming import Timer

    print(pydantic.version.version_info())

    with Timer():
        load_chem_comps()

    atom = AtomLabel(SequenceResidue("A", 1, "VAL"), "HG1##")
    print("start", atom)
    with Timer():
        print("translate", translate_from(atom, "xplor"))
else:
    load_chem_comps()
