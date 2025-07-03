import json
import traceback
from json import JSONDecodeError
from pathlib import Path
from typing import List

import xmltodict

from nef_pipelines.lib.nef_lib import UNUSED
from nef_pipelines.lib.translation.chem_comp import ChemComp
from nef_pipelines.lib.translation.object_iter import ObjectIter
from nef_pipelines.lib.util import exit_error, nef_pipelines_root


class ChemCompFormatException(Exception):
    ...


def _items_in(target):
    if isinstance(target, list):
        for index, item in enumerate(target):
            yield index, item
    elif isinstance(target, dict):
        for key, value in target.items():
            yield key, value
    else:
        yield None, target


def _clone_container(targets):
    if isinstance(targets, dict):
        result = {}
    elif isinstance(targets, list):
        result = []
    else:
        result = None
    return result


def _null_mutator(key=None, target=None, path=None):
    return target


def _reporting_mutator(path, target):
    path = [str(item) for item in path]
    target_type = str(type(target)).strip("<>").split()[1].strip("'")
    print(f'{":".join(path)} [{target_type}]: {target}')

    return target


class _Stack(list):
    def push(self, value):
        self.append(value)
        return self


class _Mutator:
    def __init__(self, mutator=_null_mutator):
        self._stack = _Stack()
        self._mutator = mutator

    @property
    def mutator(self):
        return self._mutator

    @mutator.setter
    def mutator(self, mutator):
        self._mutator = mutator

    def process_items(self, target):
        return self._process_items(
            [
                target,
            ]
        )[0]

    def _process_items(self, target):

        result = _clone_container(target)

        for key, target in _items_in(target):
            self._stack.push(key)
            if isinstance(result, list):
                target = self._mutator(self._stack, target)
                processed = self._process_items(target)
                if processed:
                    result.append(processed)
            elif isinstance(result, dict):
                target = self._mutator(self._stack, target)
                processed = self._process_items(target)
                if processed:
                    result[key] = processed
            else:
                processed = self._mutator(self._stack, target)
                if processed.__class__ != target.__class__:
                    processed = self._process_items(processed)

                result = processed
            self._stack.pop()

        return result


class _ReplaceNames:
    def __init__(self, names):
        self._names = names

    def __call__(self, stack, target):
        if isinstance(target, dict):
            for name, replacement in self._names.items():
                if name in target:
                    old = target[name]
                    del target[name]
                    target[replacement] = old

        return target


class _ReplaceAts:
    def __call__(self, stack, target):
        if isinstance(target, dict):
            replacement_names = {}
            for name in target:
                if name.startswith("@"):
                    replacement_names[name] = name[1:]

            for old_name, new_name in replacement_names.items():
                old = target[old_name]
                del target[old_name]
                target[new_name] = old

        return target


class _ReturnBranch:
    def __init__(self, path):
        self._path = path

    def _find_target(self, target):

        for elem in self._path:
            if target is not None and elem in target:
                target = target[elem]

        return target

    def __call__(self, path, target):

        return self._find_target(target)


class _IDSAsStrings:
    @staticmethod
    def _id_as_int(int_id):
        return int(int_id[1:])

    def __call__(self, path, target):

        if isinstance(target, list):
            for index, item in enumerate(target):
                if (
                    isinstance(item, str)
                    and item.startswith("_")
                    and item[1:].isdigit()
                ):
                    target[index] = self._id_as_int(item)
        elif isinstance(target, dict):
            for key, value in target.items():
                if (
                    isinstance(value, str)
                    and value.startswith("_")
                    and value[1:].isdigit()
                ):
                    target[key] = self._id_as_int(value)

        return target


class _ParseIdList:
    @staticmethod
    def _id_as_int(int_id):
        return int(int_id[1:])

    def _as_id_list(self, id_list):

        result = []
        if isinstance(id_list, str):
            for item in id_list.split():
                if item[0] == "_" and item[1:].isdigit():
                    result.append(self._id_as_int(item))
                else:
                    result = None
                    break
        return result

    def __call__(self, path, target):

        if isinstance(target, dict):
            for key, value in target.items():
                as_id_list = self._as_id_list(value)
                if as_id_list:
                    target[key] = as_id_list

        return target


class _ParseBoolean:
    def __call__(self, path, target):

        if isinstance(target, dict):
            for key, value in target.items():
                if value == "true":
                    target[key] = True
                elif value == "false":
                    target[key] = False

        return target


class _FixPseudoLists:
    def __call__(self, path, target):

        if isinstance(target, dict) and len(target) == 1:
            for name in ["IMPL.Line", "IMPL.String"]:
                if isinstance(target, dict) and name in target.keys():
                    value = target[name]
                    if (
                        isinstance(value, str)
                        and value.startswith("[")
                        and value.endswith("]")
                    ):
                        # noinspection PyBroadException
                        try:
                            as_list = eval(value)
                        except Exception:
                            as_list = None

                        if isinstance(as_list, list):
                            target = as_list

        return target


class _FixSingleLineOrString:
    def __call__(self, path, target):

        if isinstance(target, dict) and len(target) == 1:
            keys = list(target.keys())
            for name in ["IMPL.Line", "IMPL.String", "IMPL.Text"]:
                if name in keys:
                    target = target[name]

        return target


class _ConvertNumbers:
    def _as_int(self, target):

        result = None
        try:
            result = int(target)
        except Exception:
            pass

        return result

    def _as_float(self, target):

        result = None
        try:
            result = float(target)
        except Exception:
            pass

        return result

    def __call__(self, path, target):

        if isinstance(target, dict):
            for key, value in target.items():
                if isinstance(value, str):
                    new_value = self._as_int(value)
                    if new_value is not None:
                        target[key] = new_value
                        continue

                    new_value = self._as_float(value)
                    if new_value is not None:
                        target[key] = new_value
                        continue

        return target


class _RemoveNestedTypes:
    def __init__(self, container_type_pairs):
        self._container_type_pairs = container_type_pairs

    def __call__(self, path, target):

        for container, type_or_types in self._container_type_pairs:
            if isinstance(target, dict) and container in target:
                new_contents = []

                types = (
                    [
                        type_or_types,
                    ]
                    if not isinstance(type_or_types, (list, tuple))
                    else type_or_types
                )

                for _type in types:

                    if (
                        isinstance(target[container], dict)
                        and _type in target[container]
                    ):

                        if type(target[container][_type]) is dict:
                            new_contents.append(target[container][_type])
                        else:
                            new_contents.extend(target[container][_type])

                if new_contents:
                    target[container] = new_contents

        return target


class _AddDisciminatorsToApplicationData:
    def __init__(self, types, discriminator="type"):
        self._types = types
        self._discriminator = discriminator

    def __call__(self, path, target):
        for _type in self._types:

            if len(path) >= len(_type) and tuple(path[-2:]) == _type:
                target_type = type(target)
                if target_type == dict:
                    target[self._discriminator] = _type[-1]
                else:
                    for elem in target:
                        elem[self._discriminator] = _type[-1]

        return target


def _atom_info(atoms_by_id, atom):
    atom = atoms_by_id[atom]
    name = atom["name"]

    subtype = ""
    if "subType" in atom:
        subtype = f"[{atom['subType']}]"

    result = f"{name}{subtype}"

    return result


def load_xml_chem_comp_as_json(file_name, verbose=False):

    xml = open(file_name, "rb")
    chemcomp = xmltodict.parse(xml)

    mutator = _Mutator(_ReturnBranch("_StorageUnit:CHEM.StdChemComp".split(":")))
    chemcomp = mutator.process_items(chemcomp)

    name_table = {
        "CHEM.ChemComp.chemAtomSets": "chemAtomSets",
        "CHEM.ChemAtomSet": "ChemAtomSet",
        "CHEM.ChemComp.chemAtoms": "chemAtoms",
        "CHEM.ChemAtom": "ChemAtom",
        "CHEM.ChemComp.chemBonds": "chemBonds",
        "CHEM.ChemBond": "ChemBond",
        "CHEM.ChemComp.chemCompVars": "chemCompVars",
        "CHEM.ChemCompVar": "ChemCompVar",
        "CHEM.ChemComp.chemTorsions": "chemTorsions",
        "CHEM.ChemTorsion": "ChemTorsion",
        "CHEM.ChemComp.linkEnds": "linkEnds",
        "CHEM.LinkEnd": "LinkEnd",
        "CHEM.ChemComp.namingSystems": "namingSystems",
        "CHEM.NamingSystem": "NamingSystem",
        "CHEM.LinkAtom": "LinkAtom",
        "CHEM.ChemCompVar.descriptor": "descriptor",
        "CHEM.ChemComp.commonNames": "commonNames",
        "CHEM.ChemComp.name": "name",
        "CHEM.ChemAtomSet.chemAtoms": "chemAtoms",
        "CHEM.ChemAtomSet.chemAtomSets": "chemAtomSets",
        "CHEM.AbstractChemAtom.chemBonds": "chemBonds",
        "CHEM.AbstractChemAtom.chemCompVars": "chemCompVars",
        "CHEM.AbstractChemAtom.chemTorsions": "chemTorsions",
        "CHEM.ChemAtom.boundLinkEnds": "boundLinkEnds",
        "CHEM.ChemCompVar.stereoSmiles": "stereoSmiles",
        "CHEM.ChemCompVar.chemAtoms": "chemAtoms",
        "CHEM.LinkAtom.boundLinkEnd": "boundLinkEnd",
        "CHEM.ChemAtom.remoteLinkEnds": "remoteLinkEnds",
        "CHEM.LinkAtom.remoteLinkEnd": "remoteLinkEnd",
        "CHEM.ChemBond.chemAtoms": "chemAtoms",
        "CHEM.ChemTorsion.chemAtoms": "chemAtoms",
        "CHEM.ChemTorsion.sysNames": "sysNames",
        "CHEM.LinkEnd.boundLinkAtom": "boundLinkAtom",
        "CHEM.LinkEnd.remoteLinkAtom": "remoteLinkAtom",
        "CHEM.NamingSystem.atomSetVariantSystems": "atomSetVariantSystems",
        "CHEM.NamingSystem.atomSysNames": "atomSysNames",
        "CHEM.AtomSysName": "AtomSysName",
        "CHEM.AtomSysName.sysName": "sysName",
        "CHEM.AtomSysName.altSysName": "altSysName",
        "CHEM.NamingSystem.atomVariantSystems": "atomVariantSystems",
        "CHEM.NamingSystem.chemCompSysName": "chemCompSysNames",
        "CHEM.AtomSysName.altSysNames": "altSysNames",
        "CHEM.NamingSystem.chemCompSysNames": "chemCompSysNames",
        "CHEM.ChemCompSysName": "ChemCompSysName",
        "CHEM.NamingSystem.chemTorsionSysNames": "chemTorsionSysNames",
        "CHEM.ChemTorsionSysName": "ChemTorsionSysName",
        "IMPL.DataObject.applicationData": "applicationData",
        "IMPL.AppDataString": "AppDataString",
        "IMPL.AppDataInt": "AppDataInt",
        "IMPL.AppDataBoolean": "AppDataBoolean",
        "IMPL.AppDataString.value": "value",
        "IMPL.ApplicationData.application": "application",
        "IMPL.ApplicationData.keyword": "keyword",
    }

    replacer = _Mutator(_ReplaceNames(name_table))
    chemcomp = replacer.process_items(chemcomp)

    deatter = _Mutator(_ReplaceAts())
    chemcomp = deatter.process_items(chemcomp)

    replacer = _Mutator(_ReplaceNames({"_ID": "ID"}))
    chemcomp = replacer.process_items(chemcomp)

    id_fixer = _Mutator(_IDSAsStrings())
    chemcomp = id_fixer.process_items(chemcomp)

    id_list_fixer = _Mutator(_ParseIdList())
    chemcomp = id_list_fixer.process_items(chemcomp)

    boolean_fixer = _Mutator(_ParseBoolean())
    chemcomp = boolean_fixer.process_items(chemcomp)

    pseudo_list_fixer = _Mutator(_FixPseudoLists())
    chemcomp = pseudo_list_fixer.process_items(chemcomp)

    pseudo_lines_or_strings = _Mutator(_FixSingleLineOrString())
    chemcomp = pseudo_lines_or_strings.process_items(chemcomp)

    number_converter = _Mutator(_ConvertNumbers())
    chemcomp = number_converter.process_items(chemcomp)

    ATOM_TYPES = {("chemAtoms", "ChemAtom"), ("chemAtoms", "LinkAtom")}

    add_discriminators = _Mutator(_AddDisciminatorsToApplicationData(ATOM_TYPES))
    chemcomp = add_discriminators.process_items(chemcomp)

    APPLICATION_DATA_TYPES = {
        ("applicationData", "AppDataInt"),
        ("applicationData", "AppDataString"),
        ("applicationData", "AppDataBoolean"),
    }

    add_discriminators = _Mutator(
        _AddDisciminatorsToApplicationData(APPLICATION_DATA_TYPES)
    )
    chemcomp = add_discriminators.process_items(chemcomp)

    NESTED_TYPES = (
        ("chemAtoms", ("ChemAtom", "LinkAtom")),
        ("chemBonds", "ChemBond"),
        ("chemTorsions", "ChemTorsion"),
        ("atomSysNames", "AtomSysName"),
        ("chemCompSysNames", "ChemCompSysName"),
        ("chemTorsionSysNames", "ChemTorsionSysName"),
        ("chemCompSysNames", "ChemCompSysName"),
        ("namingSystems", "NamingSystem"),
        ("chemAtomSets", "ChemAtomSet"),
        ("linkEnds", "LinkEnd"),
        ("chemCompVars", "ChemCompVar"),
        ("applicationData", ("AppDataInt", "AppDataString", "AppDataBoolean")),
    )

    remove_nested_types = _Mutator(_RemoveNestedTypes(NESTED_TYPES))
    chemcomp_data = remove_nested_types.process_items(chemcomp)

    if "CHEM.NonStdChemComp" in chemcomp_data:
        raise ValueError(
            f"Error: Non standard chem comps are not currently supported {file_name}"
        )

    return ChemComp(**chemcomp_data)


def convert_xml_chem_comps(
    chem_comp_paths: List[Path], out_dir: Path = None, force=False
):
    for path in chem_comp_paths:
        # if path.parts[-1] == 'DNA+I+msd_ccpnRef_2007-12-11-10-13-17_00002.xml':
        _convert_xml_chem_comp(path, out_dir, force=force)


def type_children(target, parent):

    result = ()
    if hasattr(target, "__origin__"):
        result = result = tuple(
            [ObjectIter.Entry(target, i, arg) for i, arg in enumerate(target.__args__)]
        )

    elif isinstance(target, (list, tuple)):
        result = tuple(
            [ObjectIter.Entry(target, i, elem) for i, elem in enumerate(target)]
        )

    elif isinstance(target, dict):
        result = tuple(
            [ObjectIter.Entry(target, key, value) for key, value in target.items()]
        )

    return result


def _convert_xml_chem_comp(chem_comp_path: Path, out_dir: Path = None, force=False):
    # print(chem_comp_path)
    file_iter = chem_comp_path.iterdir()
    if chem_comp_path.is_file():
        file_iter = [chem_comp_path]

    if out_dir:
        out_dir = Path(_chem_comp_root_dir(), *out_dir)
        if not out_dir.exists():
            out_dir.mkdir()
        if not out_dir.is_dir():
            exit_error(f"output directory must be a directory {out_dir} isn't")

    for file_path in file_iter:
        if file_path.suffix == ".xml":

            ok = False
            try:

                chem_comp = load_xml_chem_comp_as_json(file_path)
                json_chem_comp = file_path.with_suffix(".json")
                if out_dir:
                    json_chem_comp = out_dir / json_chem_comp.parts[-1]

                if json_chem_comp.exists() and not force:
                    exit_error(
                        f"file {json_chem_comp} exists to overwite use then force option"
                    )

                raw_json = chem_comp.json()
                with open(json_chem_comp, "w") as fh:
                    json_dict = json.loads(raw_json)
                    json_formatted = json.dumps(json_dict, indent=4)
                    fh.write(json_formatted)

                ok = True

            except Exception as e:
                caught = e
                if (
                    "Error: Non standard chem comps are not currently supported"
                    not in caught.args[0]
                ):
                    print(traceback.format_exc())
                    print(f"Error: loading {file_path} failed because {e}")

            if ok:
                print(f"OK: converted {file_path} to json")
                print(f"    new file  {json_chem_comp}")
            else:
                if (
                    "Error: Non standard chem comps are not currently supported"
                    not in caught.args[0]
                ):
                    print(f"Error: loading {file_path} failed")


CHEM_COMP_REL_PATH = ["nef_pipelines", "data", "chem_comp"]
JSON_CHEM_COMP_SUB_PATH = (".",)
XML_CHEM_COMP_SUB_PATH = ("xml",)


def _chem_comp_root_dir():
    return Path(nef_pipelines_root(), *CHEM_COMP_REL_PATH)


def find_chem_comps(rel_path=JSON_CHEM_COMP_SUB_PATH, extension="json") -> List[Path]:

    result = []
    for file_path in Path(_chem_comp_root_dir(), *rel_path).iterdir():
        if file_path.suffix == f".{extension}":
            result.append(file_path)

    return result


MOL_TYPES = set()
CHEM_COMPS = {}


# rough costs
# read + parse std chem comps 0.218489s with v2 expected to be 0.054-0.004s typically 0.012s
# just read chem comps 0.010838s
# without linking 0.160787s (linking oh 0.058s ie 26%)
def load_chem_comps():
    chem_comp_paths = find_chem_comps()

    for chem_comp_path in chem_comp_paths:
        try:
            with open(chem_comp_path, "r") as f:
                chemcomp_data = json.load(f)
                chem_comp = ChemComp(**chemcomp_data)
                mol_type = chem_comp.molType
                MOL_TYPES.add(mol_type.upper())
                key = (
                    chem_comp.code3Letter
                    if chem_comp.code3Letter != UNUSED
                    else chem_comp.ccpCode
                )
                CHEM_COMPS[key] = chem_comp
        except JSONDecodeError as e:
            msg = f"""\
                while reading the chemical component {chem_comp_path} the following erro occured
                {e}
            """
            raise ChemCompFormatException(msg)


if __name__ == "__main__":

    # xml_chem_comp_paths = find_chem_comps(rel_path=XML_CHEM_COMP_SUB_PATH,extension='xml')
    #
    # convert_xml_chem_comps(xml_chem_comp_paths, JSON_CHEM_COMP_SUB_PATH, force=True)
    #
    # print(CHEM_COMPS)

    load_chem_comps()
    # print(CHEM_COMPS)
    #
    # for type,residue in CHEM_COMPS:
    #     print(type, residue)
    #     name = f'{type.lower()}_{residue.lower()}_test.json'
    #     path = Path(_chem_comp_root_dir()) / name
    #     chem_comp = CHEM_COMPS[type,residue]
    #     chem_comp_json = chem_comp.json()
    #     print(path)
    #     with open(path,'w') as fh:
    #         fh.write(json.dumps(json.loads(chem_comp_json), indent=4))
    # print()

    print(CHEM_COMPS["PROTEIN", "ILE"].namingSystems[0].atomReference.name)
