import sys
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import List, Union

import hjson
import typer
from fyeah import f
from ordered_set import OrderedSet
from pynmrstar import Entry
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    loop_row_namespace_iter,
    read_entry_from_file_or_exit_error,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    get_chain_code_iter,
    sequence_from_entry_or_exit,
)
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import AtomLabel, Residue, ShiftData, ShiftList
from nef_pipelines.lib.translation.chem_comp import ID, ChemCompLinking
from nef_pipelines.lib.util import (
    STDIN,
    chunks,
    exit_error,
    flatten,
    nef_pipelines_root,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.nmrstar import import_app


class StereoAssignmentHandling(Enum):
    ALL_AMBIGUOUS = "all-ambiguous"
    AS_ASSIGNED = "as-assigned"
    AUTO = "auto"

    def __str__(self):
        return self._name_.lower().replace("_", "-")


STEREO_HELP = """\
    how to handle stereo assignments the choices are:
    - ambiguous: assume all stereo assignments are ambiguous
    - as-assigned: use the stereo assignments as they are in the file
    - auto: use as assigned if some geminal stereo assignments are present, otherwise assume all are ambiguous
"""


@import_app.command()
def shifts(
    chain_codes: List[str] = typer.Option(
        None,
        "--chains",
        help="chain codes as a list of names separated by commas, repeated calls will add further chains [default A]",
        metavar="<CHAIN-CODES>",
    ),
    frame_name: str = typer.Option(
        None,
        "-f",
        "--frame-name",
        help="a name for the frame, default is the name nmrstar entry",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="file to read NEF data from [- is stdin; defaults is stdin]]",
    ),
    stereo_mode: StereoAssignmentHandling = typer.Option("auto", help=STEREO_HELP),
    use_author: bool = typer.Option(
        False, help="use author fields for chain_code, sequence_code and residue_name"
    ),
    file_path: Path = typer.Argument(
        ..., help="input files of type shifts.txt", metavar="<NMR-STAR-shifts>.str"
    ),
):
    """- convert nmrstar shift file <nmr-star>.str to NEF [alpha]"""

    nmrstar_entry = read_entry_from_file_or_exit_error(file_path)

    chain_codes = parse_comma_separated_options(chain_codes)

    nef_entry = read_entry_from_file_or_stdin_or_exit_error(input)

    nef_entry = pipe(
        nef_entry,
        chain_codes,
        frame_name,
        nmrstar_entry,
        file_path,
        use_author,
        stereo_mode,
    )

    print(nef_entry)


def pipe(
    nef_entry: Entry,
    chain_codes: List[str],
    frame_name: str,
    nmrstar_entry: Entry,
    file_name: Path,
    use_author: bool,
    stereo_mode: StereoAssignmentHandling,
):

    sequence_residues = sequence_from_entry_or_exit(nef_entry)

    sequence_residues_by_residue = {
        Residue.from_sequence_residue(sequence_residue): sequence_residue
        for sequence_residue in sequence_residues
    }

    residues = set(sequence_residues_by_residue.keys())

    denormalised_shifts, ambiguities, name_info = _chemical_shifts_from_star_frame(
        nmrstar_entry, use_author, file_name
    )

    stereo_mode = _get_stereo_mode(ambiguities, stereo_mode)

    entity_id_to_chain_code = _build_entity_ids_to_chain_codes(
        chain_codes, denormalised_shifts
    )

    denormalised_shifts = _replace_shift_entity_ids_with_chain_codes(
        denormalised_shifts, entity_id_to_chain_code
    )

    per_residue_and_atom_shifts = _organise_shifts_by_residue_and_atom_names(
        denormalised_shifts
    )

    shift_residues = set(per_residue_and_atom_shifts.keys())

    _exit_error_if_missing_residues(residues, shift_residues, file_name)

    residue_names = sorted(
        list(set([residue.residue_name for residue in per_residue_and_atom_shifts]))
    )

    ambiguities = _replace_atom_dict_entity_ids_with_chain_codes(
        ambiguities, entity_id_to_chain_code
    )

    per_residue_ambiguities = _organise_ambiguities_by_residue(ambiguities)

    per_residue_and_atom_shifts = _replace_atoms_with_duplicated_shifts(
        per_residue_and_atom_shifts,
        sequence_residues_by_residue,
        per_residue_ambiguities,
    )

    all_stereo_pairs = _get_geminal_pairs(residue_names)

    _apply_stereo_assignment_ambiguities(
        per_residue_and_atom_shifts,
        all_stereo_pairs,
        sequence_residues_by_residue,
        per_residue_ambiguities,
        stereo_mode,
    )

    all_shifts = sorted(
        flatten(
            [
                list(residue_shifts.values())
                for residue_shifts in per_residue_and_atom_shifts.values()
            ]
        )
    )

    if not frame_name:
        frame_name = name_info.entry_id + "__" + str(name_info.identifier)

    shifts_frame = shifts_to_nef_frame(ShiftList(all_shifts), frame_name)

    return add_frames_to_entry(
        nef_entry,
        [
            shifts_frame,
        ],
    )


def _get_chem_atom_set_atoms(chem_atom_set, chem_comp):
    chem_atom_set_by_id = {
        chem_atom_set.ID: chem_atom_set for chem_atom_set in chem_comp.chemAtomSets
    }

    if isinstance(chem_atom_set, ID):
        result = [chem_atom_set]
    else:
        result = list(chem_atom_set.chemAtoms) if chem_atom_set.chemAtoms else []

        if chem_atom_set.chemAtomSets:
            for nested_set in chem_atom_set.chemAtomSets:
                result.extend(chem_atom_set_by_id[nested_set].chemAtoms)

    id_and_values_result = {item.ID: item for item in result}
    return list(id_and_values_result.values())


def _get_geminal_pairs(residue_names):

    ambiguity_translations_path = (
        Path(nef_pipelines_root())
        / "nef_pipelines"
        / "data"
        / "ambiguity_translations.json"
    )

    with open(ambiguity_translations_path, "r") as f:
        all_prochiral_pairs = hjson.loads(f.read())

    # import nef_pipelines.lib.translation.io as converter_io
    # converter_io.load_chem_comps()
    # all_prochiral_pairs = {}
    #
    # # for residue_name in residue_names:
    # residue_names = [chem_comp for chem_comp in converter_io.CHEM_COMPS]
    for residue_name in residue_names:
        if residue_name in all_prochiral_pairs:
            continue

        # TODO:  this would be a lot neater if data was only loaded on first access
        import nef_pipelines.lib.translation.io as converter_io

        converter_io.load_chem_comps()

        # TODO: add the ability to add unknown chem comps
        _exit_if_unknown_chem_comp(residue_name)

        residue_linkings = {}
        all_prochiral_pairs[residue_name] = residue_linkings

        converter_io.load_chem_comps()

        _exit_if_unknown_chem_comp(residue_name)

        chem_comp = converter_io.CHEM_COMPS[residue_name]

        chem_atoms_by_id = {
            chem_comp_atom.ID: chem_comp_atom for chem_comp_atom in chem_comp.chemAtoms
        }
        atom_sets_by_id = {
            chem_atom_set.ID: chem_atom_set for chem_atom_set in chem_comp.chemAtomSets
        }

        active_chem_comp_vars = [
            chem_comp_var
            for chem_comp_var in chem_comp.chemCompVars
            if chem_comp_var.isDefaultVar
            and chem_comp_var.linking in ["start", "middle", "end"]
        ]

        chem_atom_set_atoms = {}
        atom_sets_by_key = {
            (chem_atom_set.name, chem_atom_set.subType): chem_atom_set
            for chem_atom_set in chem_comp.chemAtomSets
        }
        for chem_atom_set in chem_comp.chemAtomSets:
            chem_atom_set_atoms[(chem_atom_set.name, chem_atom_set.subType)] = (
                _get_chem_atom_set_atoms(chem_atom_set, chem_comp)
            )

        active_chem_atom_sets_by_linking = {}
        for chem_comp_var in active_chem_comp_vars:
            linking = chem_comp_var.linking
            active_chem_atom_sets_by_linking[chem_comp_var.linking.value] = []
            active_chem_comp_atom_ids = set(chem_comp_var.chemAtoms)
            for atom_set_name, atom_set_atom_ids in chem_atom_set_atoms.items():
                if atom_set_atom_ids.issubset(active_chem_comp_atom_ids):
                    active_chem_atom_sets_by_linking[linking].append(atom_set_name)

        for linking, active_atom_set_keys in active_chem_atom_sets_by_linking.items():
            new_and_old_names = all_prochiral_pairs[residue_name].setdefault(
                linking, {}
            )
            for atom_set_key in active_atom_set_keys:
                chem_atom_set = atom_sets_by_key[atom_set_key]
                if chem_atom_set.isEquivalent:
                    continue

                chem_atoms = (
                    [chem_atoms_by_id[id].name for id in chem_atom_set.chemAtoms]
                    if chem_atom_set.chemAtoms
                    else []
                )
                atom_sets = (
                    [atom_sets_by_id[id].name for id in chem_atom_set.chemAtomSets]
                    if chem_atom_set.chemAtomSets
                    else []
                )

                if "|" in chem_atom_set.name:
                    continue

                active_pair = sorted(chem_atoms or atom_sets)

                replacements = ["x", "y"]

                # TODO: will need to patch for ''s etc
                pair_values = new_and_old_names.setdefault(chem_atom_set.name, {})
                for i, name in enumerate(active_pair):
                    if name[-1] == "*":
                        new_name = f"{name[:-2]}{replacements[i]}%"
                    else:
                        new_name = f"{name[:-1]}{replacements[i]}"
                    pair_values[name] = new_name

        # print(residue_name, all_prochiral_pairs[residue_name])
    # import json
    # with open(ambiguity_translations_path, 'w') as fh:
    #     fh.write(json.dumps(all_prochiral_pairs))
    # print(f'wrote {ambiguity_translations_path}')
    # sys.exit(0)
    # print(all_prochiral_pairs.keys())
    return all_prochiral_pairs


def _get_atom_sets_by_residue(residue_names):

    equivalent_atoms_path = (
        Path(nef_pipelines_root())
        / "nef_pipelines"
        / "data"
        / "default_atom_sets_by_comp_and_linking.json"
    )
    with open(equivalent_atoms_path, "r") as f:
        equivalent_atoms_by_residue = hjson.loads(f.read())

    for residue_name in residue_names:

        if residue_name in equivalent_atoms_by_residue:
            continue

        # TODO:  this would be a lot neater if data was only loaded on first access
        import nef_pipelines.lib.translation.io as converter_io

        converter_io.load_chem_comps()

        # TODO: add the ability to add unknown chem comps
        _exit_if_unknown_chem_comp(residue_name)

        chem_comp = converter_io.CHEM_COMPS[residue_name]

        chem_atoms_by_id = {
            chem_comp_atom.ID: chem_comp_atom for chem_comp_atom in chem_comp.chemAtoms
        }

        chem_atom_set_atoms = {}
        for chem_atom_set in chem_comp.chemAtomSets:
            chem_atom_set_atoms[(chem_atom_set.name, chem_atom_set.subType)] = (
                _get_chem_atom_set_atoms(chem_atom_set, chem_comp)
            )

        active_chem_comp_vars = [
            chem_comp_var
            for chem_comp_var in chem_comp.chemCompVars
            if chem_comp_var.isDefaultVar
            and chem_comp_var.linking in ["start", "middle", "end"]
        ]

        active_chem_comp_vars_atom_sets = {}
        for chem_comp_var in active_chem_comp_vars:

            active_chem_comp_atom_ids = set(
                [chem_atom.ID for chem_atom in chem_comp_var.chemAtoms]
            )

            for atom_set_name, atom_set_atoms in chem_atom_set_atoms.items():
                atom_set_atom_ids = set([atom.ID for atom in atom_set_atoms])
                if atom_set_atom_ids.issubset(active_chem_comp_atom_ids):
                    atom_set_chem_atoms = [
                        chem_atoms_by_id[id].name for id in atom_set_atom_ids
                    ]
                    name = atom_set_name[0]
                    name = (
                        name if name != "HD*|HE*" else "QR"
                    )  # i don't think NEF accepts HD*|HE* as a name
                    name = (
                        "f{name[:-1}%" if name[-1] == "*" else name
                    )  # NEF prioritises % over *
                    active_chem_comp_vars_atom_sets.setdefault(
                        chem_comp_var.linking.value, []
                    ).append((name, atom_set_chem_atoms))

        equivalent_atoms_by_residue[residue_name] = active_chem_comp_vars_atom_sets

    return equivalent_atoms_by_residue


LINKING_BY_NAME = {
    "free": ChemCompLinking.free,
    "start": ChemCompLinking.start,
    "middle": ChemCompLinking.middle,
    "end": ChemCompLinking.end,
}
NAME_BY_LINKING = {linking: name for name, linking in LINKING_BY_NAME.items()}


class BmrbShiftAmbiguities(Enum):
    UNIQUE = 1
    ALIPHATIC_GEMINAL = 2
    AROMATIC_GEMINAL = 3
    INTRA_RESIDUE = 4
    INTER_RESIDUE = 5
    INTER_MOLECULAR = 6
    UNKNOWN = 9


def rmsd(values):
    mean = sum(values) / len(values)
    squared_values = [(value - mean) ** 2 for value in values]
    mean_of_squared_values = sum(squared_values) / len(squared_values)
    return mean_of_squared_values**0.5


def _apply_stereo_assignment_ambiguities(
    per_residue_and_atom_shifts,
    all_stereo_pairs,
    sequence_residues_by_residue,
    per_residue_ambiguities,
    stereo_mode,
):
    for residue, chemical_shifts_by_atom_names in per_residue_and_atom_shifts.items():
        sequence_residue = sequence_residues_by_residue[residue]
        geminal_pairs_for_residue = all_stereo_pairs[sequence_residue.residue_name]
        linking = sequence_residue.linking.lower()
        ambiguous_pairs = geminal_pairs_for_residue[linking]

        for ambiguous_pair in ambiguous_pairs.values():
            found_pairs = {}
            for before_atom_name in ambiguous_pair:
                if before_atom_name in chemical_shifts_by_atom_names:
                    found_pairs[before_atom_name] = chemical_shifts_by_atom_names[
                        before_atom_name
                    ]

            if len(found_pairs) == 2:
                found_pairs = dict(
                    sorted(found_pairs.items(), key=lambda item: item[1])
                )
                if stereo_mode is StereoAssignmentHandling.ALL_AMBIGUOUS:
                    for before, old_shift in found_pairs.items():
                        new_atom_name = ambiguous_pair[before]
                        atom = old_shift.atom
                        atom = replace(atom, atom_name=new_atom_name)
                        new_shift = replace(old_shift, atom=atom)
                        del chemical_shifts_by_atom_names[before]
                        chemical_shifts_by_atom_names[new_atom_name] = new_shift


def _replace_atoms_with_duplicated_shifts(
    per_residue_and_atom_shifts, sequence_residues_by_residue, per_residue_ambiguities
):

    residue_names = set(
        [residue.residue_name for residue in per_residue_and_atom_shifts.keys()]
    )

    atom_sets_by_residue = _get_atom_sets_by_residue(residue_names)
    for residue, chemical_shifts_by_atom_names in per_residue_and_atom_shifts.items():

        sequence_residue = sequence_residues_by_residue[residue]

        # ambiguity_keys = list(per_residue_ambiguities.keys())

        linking = sequence_residue.linking.value.lower()
        related_atom_sets = atom_sets_by_residue[sequence_residue.residue_name][linking]

        # active_atom_names = {shift.atom.atom_name for shift in chemical_shifts}

        # we do them by longest first so we get the most general match first
        related_atom_sets_by_length = reversed(
            sorted(related_atom_sets, key=lambda item: len(item[1]))
        )

        for atom_set_name, related_atoms in related_atom_sets_by_length:
            # print(residue, 'atom set name', atom_set_name, 'related atoms', related_atoms)
            shifts = [
                chemical_shifts_by_atom_names[atom]
                for atom in related_atoms
                if atom in chemical_shifts_by_atom_names
            ]

            if len(shifts) != len(related_atoms):
                continue

            new_ambiguities = set(
                [per_residue_ambiguities[residue][atom] for atom in related_atoms]
            )

            if len(new_ambiguities) != 1:
                # we need to choose a small set of atoms to remove the ambiguous ambiguity!...
                continue

            else:
                new_ambiguity = new_ambiguities.pop()

            rmsd_val = rmsd([shift.value for shift in shifts])
            if rmsd_val < 1e-7:
                chemical_shifts_by_atom_names[atom_set_name] = shifts[0]
                for atom in related_atoms:
                    del chemical_shifts_by_atom_names[atom]

                residue_ambiguities = per_residue_ambiguities[residue]
                residue_ambiguities[atom_set_name] = new_ambiguity
                for atom in related_atoms:
                    del residue_ambiguities[atom]

                atom_set_shift = chemical_shifts_by_atom_names[atom_set_name]
                atom_set_shift_atom = atom_set_shift.atom
                atom_set_shift_atom = replace(
                    atom_set_shift_atom, atom_name=atom_set_name
                )
                atom_set_shift = replace(atom_set_shift, atom=atom_set_shift_atom)
                chemical_shifts_by_atom_names[atom_set_name] = atom_set_shift

    return per_residue_and_atom_shifts


def _get_stereo_mode(ambiguities, stereo_mode):
    if stereo_mode == StereoAssignmentHandling.AUTO and any(
        [
            value == BmrbShiftAmbiguities.ALIPHATIC_GEMINAL.value
            for value in ambiguities.values()
        ]
    ):
        stereo_mode = StereoAssignmentHandling.AS_ASSIGNED
    else:
        stereo_mode = StereoAssignmentHandling.ALL_AMBIGUOUS
    return stereo_mode


@dataclass
class ShiftListNameInfo:
    entry_id: str
    identifier: Union[int, str]


def _chemical_shifts_from_star_frame(nmrstar_entry, use_author, file_name):

    shift_lists = nmrstar_entry.get_saveframes_by_category("assigned_chemical_shifts")

    if len(shift_lists) == 0:
        msg = f"""\
        there are no saveframes of assigned chemical shifts in the file {file_name}
        """

        exit_error(msg)

    # can there be more than one? I guess yes
    ambiguities = {}
    denormalised_shifts = []

    frame_code = shift_lists[0].get_tag("Sf_framecode")[0]
    category = shift_lists[0].get_tag("Sf_category")[0]
    entry_id = shift_lists[0].get_tag("Entry_ID")[0]
    list_identifier = frame_code[len(category) + 1 :].lstrip("_")
    name_info = ShiftListNameInfo(entry_id, list_identifier)

    for i, shift_list in enumerate(shift_lists):

        try:
            shifts_loop = shift_list.get_loop("_Atom_chem_shift")

        except KeyError:
            msg = f"""\
                warning the saveframe {shift_list.get_tag('Sf_framecode')[0]}
                does not contain a loop with the tag _Atom_chem_shift
                """
            print(msg, file=sys.stderr)
            continue

        # TODO add warnings and check all required fields are present
        for row in loop_row_namespace_iter(shifts_loop):
            chain_code = row.Entity_assembly_ID
            if use_author:
                atom_id = row.Auth_atom_ID
                seq_id = row.Auth_seq_ID
                comp_id = row.Auth_comp_ID
            else:
                atom_id = row.Atom_ID
                seq_id = row.Seq_ID
                comp_id = row.Comp_ID

            if atom_id == UNUSED and use_author:
                atom_id = row.Atom_ID
            if seq_id == UNUSED and use_author:
                seq_id = row.Seq_ID
            if comp_id == UNUSED and use_author:
                comp_id = row.Comp_ID

            shift = row.Val
            sdev = row.Val_err
            element = row.Atom_type
            isotope = row.Atom_isotope_number
            ambiguity_code = row.Ambiguity_code

            residue = Residue(chain_code, seq_id, comp_id)
            atom = AtomLabel(residue, atom_id, element, isotope)

            shift = ShiftData(atom, shift, sdev)
            denormalised_shifts.append(shift)
            ambiguities[atom] = ambiguity_code

    return denormalised_shifts, ambiguities, name_info


def _exit_if_unknown_chem_comp(residue_name):
    import nef_pipelines.lib.translation.io as converter_io

    if not (residue_name) in converter_io.CHEM_COMPS:
        exit_error(
            f"the residue / molecule {residue_name} is not found in the chemical components dictionary"
        )


def _organise_shifts_by_residue_and_atom_names(denormalised_shifts):
    per_residue_shifts = {}
    for shift in denormalised_shifts:
        residue = shift.atom.residue
        per_residue_shifts.setdefault(residue, []).append(shift)
    per_residue_and_atom_shifts = {}
    for residue, shifts in per_residue_shifts.items():
        per_residue_and_atom_shifts[residue] = {
            shift.atom.atom_name: shift for shift in shifts
        }
    return per_residue_and_atom_shifts


def _organise_ambiguities_by_residue(ambiguities):
    # print(type(ambiguities))
    per_residue_ambiguities = {}
    for atom, ambiguity in ambiguities.items():
        residue = atom.residue
        # print(residue)
        per_residue_ambiguities.setdefault(residue, {})[atom.atom_name] = ambiguity
    return per_residue_ambiguities


def _replace_shift_entity_ids_with_chain_codes(
    denormalised_shifts, entity_id_to_chain_code
):
    for i, shift in enumerate(denormalised_shifts):
        atom = shift.atom
        residue = atom.residue
        residue = replace(
            residue, chain_code=entity_id_to_chain_code[residue.chain_code]
        )
        atom = replace(atom, residue=residue)
        denormalised_shifts[i] = replace(shift, atom=atom)

    return denormalised_shifts


def _replace_atom_dict_entity_ids_with_chain_codes(
    ambiguities, entity_id_to_chain_code
):
    result = {}
    for atom, ambiguity in ambiguities.items():
        residue = atom.residue
        residue = replace(
            residue, chain_code=entity_id_to_chain_code[residue.chain_code]
        )
        atom = replace(atom, residue=residue)
        result[atom] = ambiguity

    return result


def _build_entity_ids_to_chain_codes(chain_codes, denormalised_shifts):
    entity_ids = list(
        OrderedSet(
            sorted([shift.atom.residue.chain_code for shift in denormalised_shifts])
        )
    )
    chain_code_iter = get_chain_code_iter(chain_codes)
    entity_id_to_chain_code = {
        entity_id: chain_code
        for entity_id, chain_code in zip(entity_ids, chain_code_iter)
    }
    return entity_id_to_chain_code


def _exit_error_if_missing_residues(residues, shift_residues, file_name):

    # could do more here and see if there is a match by sequence...
    if not shift_residues.issubset(residues):
        msg = """\
            warning the residues in the shift list from {file_name} are not all present in the sequence you read
            from the NEF entry, the missing residues are
            {missing_residue_table}
            """
        msg = dedent(msg)
        missing_residues = sorted(shift_residues - residues)
        residue_names = [
            f"@{residue.chain_code}#{residue.sequence_code}.{residue.residue_name}"
            for residue in missing_residues
        ]
        residue_name_table = chunks(residue_names, 10)
        missing_residue_table = tabulate(  # noqa: F841
            residue_name_table, tablefmt="plain"
        )
        msg = f(msg)
        exit_error(msg)
