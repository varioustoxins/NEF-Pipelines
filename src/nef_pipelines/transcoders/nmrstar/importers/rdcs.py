import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import List, Union

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    loop_row_namespace_iter,
    read_entry_from_file_or_exit_error,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (  # sequence_from_entry_or_exit,
    get_chain_code_iter,
)
from nef_pipelines.lib.structures import AtomLabel, RdcRestraint, Residue
from nef_pipelines.lib.util import STDIN, exit_error, parse_comma_separated_options
from nef_pipelines.transcoders.nmrstar import import_app
from nef_pipelines.transcoders.pales.importers.rdcs import _RDCS_to_nef_saveframe


@import_app.command()
def rdcs(
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
        "--in",
        metavar="|PIPE|",
        help="file to read NEF data from [- is stdin; defaults is stdin]]",
    ),
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
    )

    print(nef_entry)


def pipe(
    nef_entry: Entry,
    chain_codes: List[str],
    frame_name: str,
    nmrstar_entry: Entry,
    file_name: Path,
    use_author: bool,
):

    # sequence_residues = sequence_from_entry_or_exit(nef_entry)

    # sequence_residues_by_residue = {
    #     Residue.from_sequence_residue(sequence_residue): sequence_residue
    #     for sequence_residue in sequence_residues
    # }

    # residues = set(sequence_residues_by_residue.keys())

    rdc_lists, name_info = _rdcs_from_star_frame(nmrstar_entry, use_author, file_name)

    entity_id_to_chain_code = _build_entity_ids_to_chain_codes(chain_codes, rdc_lists)

    rdc_lists = _replace_shift_entity_ids_with_chain_codes(
        rdc_lists, entity_id_to_chain_code
    )

    for rdc_list, name_info in zip(rdc_lists, name_info):
        frame_name = name_info.entry_id + "_" + str(name_info.identifier).lstrip("_")
        rdcs_frame = _RDCS_to_nef_saveframe(rdc_list, frame_name)
        nef_entry.add_saveframe(rdcs_frame)

    return nef_entry


@dataclass
class ShiftListNameInfo:
    entry_id: str
    identifier: Union[int, str]


ELEMENT_TO_ISOTOPE = {"C": 13, "N": 15, "P": 31, "H": 1, "F": 19, "D": 2}


def _element_to_isotope(element):
    return ELEMENT_TO_ISOTOPE[element] if element in ELEMENT_TO_ISOTOPE else None


def _rdcs_from_star_frame(nmrstar_entry, use_author, file_name):

    raw_rdc_lists = nmrstar_entry.get_saveframes_by_category("RDC_constraints")

    if len(raw_rdc_lists) == 0:
        msg = f"""\
        there are no saveframes of assigned chemical shifts in the file {file_name}
        """

        exit_error(msg)

    # for i, raw_rdc_list in enumerate(raw_rdc_lists):
    #     category = raw_rdc_lists[0].get_tag("Sf_category")[0]
    #     entry_id = raw_rdc_lists[0].get_tag("Entry_ID")[0]
    #     frame_code = raw_rdc_lists[0].get_tag("Sf_framecode")[0]
    #     list_identifier = frame_code[len(category) + 1:].lstrip("_")
    #     name_info = ShiftListNameInfo(entry_id, list_identifier)
    #     print(category, entry_id, frame_code, list_identifier, name_info)

    name_info_list = []
    rdc_lists = []
    for i, raw_rdc_list in enumerate(raw_rdc_lists):
        category = raw_rdc_list.get_tag("Sf_category")[0]
        entry_id = raw_rdc_list.get_tag("Entry_ID")[0]
        frame_code = raw_rdc_list.get_tag("Sf_framecode")[0]
        list_identifier = frame_code[len(category) + 1 :].lstrip("_")
        name_info = ShiftListNameInfo(entry_id, list_identifier)
        name_info_list.append(name_info)

        try:
            rdc_loop = raw_rdc_list.get_loop("_RDC_constraint")

        except KeyError:
            msg = f"""\
                warning the saveframe {raw_rdc_list.get_tag('Sf_framecode')[0]}
                does not contain a loop with the tag _Atom_chem_shift
                """
            print(msg, file=sys.stderr)
            continue

        # TODO add warnings and check all required fields are present
        rdc_list = []
        rdc_lists.append(rdc_list)
        for row in loop_row_namespace_iter(rdc_loop):

            chain_code_1 = row.Entity_assembly_ID_1
            chain_code_2 = row.Entity_assembly_ID_2

            if use_author:
                atom_id_1 = row.Auth_atom_ID_1
                seq_id_1 = row.Auth_seq_ID_1
                comp_id_1 = row.Auth_comp_ID_1

                atom_id_2 = row.Auth_atom_ID_2
                seq_id_2 = row.Auth_seq_ID_2
                comp_id_2 = row.Auth_comp_ID_2
            else:
                atom_id_1 = row.Atom_ID_1
                seq_id_1 = row.Seq_ID_1
                comp_id_1 = row.Comp_ID_1

                atom_id_2 = row.Atom_ID_2
                seq_id_2 = row.Seq_ID_2
                comp_id_2 = row.Comp_ID_2

            if atom_id_1 == UNUSED and use_author:
                atom_id_1 = row.Atom_ID_1
            if atom_id_2 == UNUSED and use_author:
                atom_id_2 = row.Atom_ID_2

            if seq_id_1 == UNUSED and use_author:
                seq_id_1 = row.Seq_ID_1
            if seq_id_2 == UNUSED and use_author:
                seq_id_2 = row.Seq_ID_2

            if comp_id_1 == UNUSED and use_author:
                comp_id_1 = row.Comp_ID_1
            if comp_id_2 == UNUSED and use_author:
                comp_id_2 = row.Comp_ID_2

            val = row.RDC_val
            sdev = row.RDC_val_err

            lower_bound = row.RDC_lower_bound
            upper_bound = row.RDC_upper_bound
            if val == UNUSED:
                val = (lower_bound + upper_bound) / 2
                val_range_d2 = (upper_bound - lower_bound) / 2
                if sdev < val_range_d2 or sdev == UNUSED:
                    sdev = val_range_d2

            weight = (
                row.RDC_val_scale_factor if row.RDC_val_scale_factor != UNUSED else None
            )

            element_1 = row.Atom_type_1
            element_2 = row.Atom_type_2
            isotope_1 = (
                row.Atom_isotope_number_1
                if row.Atom_isotope_number_1 != UNUSED
                else _element_to_isotope(element_1)
            )
            isotope_2 = (
                row.Atom_isotope_number_2
                if row.Atom_isotope_number_2 != UNUSED
                else _element_to_isotope(element_2)
            )

            residue_1 = Residue(chain_code_1, seq_id_1, comp_id_1)
            atom_1 = AtomLabel(residue_1, atom_id_1, element_1, isotope_1)

            residue_2 = Residue(chain_code_2, seq_id_2, comp_id_2)
            atom_2 = AtomLabel(residue_2, atom_id_2, element_2, isotope_2)

            if upper_bound == UNUSED and lower_bound == UNUSED:
                rdc = RdcRestraint(atom_1, atom_2, val, sdev)
            else:
                rdc = RdcRestraint(
                    atom_1,
                    atom_2,
                    val,
                    sdev,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    weight=weight,
                )
            rdc_list.append(rdc)

    return rdc_lists, name_info_list


#
def _replace_shift_entity_ids_with_chain_codes(rdc_lists, entity_id_to_chain_code):

    for list_index, rdc_list in enumerate(rdc_lists):
        for rdc_index, rdc_restraint in enumerate(rdc_list):
            atom_1 = rdc_restraint.atom_1
            residue_1 = atom_1.residue
            residue_1 = replace(
                residue_1, chain_code=entity_id_to_chain_code[residue_1.chain_code]
            )
            atom_1 = replace(atom_1, residue=residue_1)

            atom_2 = rdc_restraint.atom_2
            residue_2 = atom_2.residue
            residue_2 = replace(
                residue_2, chain_code=entity_id_to_chain_code[residue_2.chain_code]
            )
            atom_2 = replace(atom_2, residue=residue_2)

            rdc_restraint = replace(rdc_restraint, atom_1=atom_1)
            rdc_restraint = replace(rdc_restraint, atom_2=atom_2)
            rdc_list[rdc_index] = rdc_restraint

    return rdc_lists


def _build_entity_ids_to_chain_codes(chain_codes, rdc_lists: List[RdcRestraint]):
    all_entity_ids_to_chain_codes = {}
    for rdc_list in rdc_lists:

        entity_ids_1 = OrderedSet(
            sorted([rdc.atom_1.residue.chain_code for rdc in rdc_list])
        )
        entity_ids_2 = OrderedSet(
            sorted([rdc.atom_2.residue.chain_code for rdc in rdc_list])
        )
        entity_ids = entity_ids_1.union(entity_ids_2)

        chain_code_iter = get_chain_code_iter(chain_codes)
        entity_ids_to_chain_codes = {
            entity_id: chain_code
            for entity_id, chain_code in zip(entity_ids, chain_code_iter)
        }
        all_entity_ids_to_chain_codes.update(entity_ids_to_chain_codes)
    return entity_ids_to_chain_codes
