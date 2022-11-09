# todo sort out appdatalists
# todo derived methods
# todo remove parent links on json dump
# todo unify tree iteerators!

import typing
from enum import auto
from typing import List, Union, Optional, Literal, TypeVar, Callable, Annotated, get_origin, Tuple, get_args

from cachetools import LRUCache
from pydantic import BaseModel, Field
from strenum import StrEnum
from lib.translation.object_iter import ObjectIter, object_children, item_only, return_entity



class PCMeta(BaseModel.__class__):
    _object_map = {}

    def __call__(self, *args, **kwargs):
        result = super(PCMeta, self).__call__(*args, **kwargs)

        if hasattr(result, '__post_init__') and isinstance(result.__post_init__, Callable):
            result.__post_init__()

        return result

class ID(int):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):

        try:
            result = cls(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f'invalid ID format [should look like an integer: {v} error was: {e}],')

        return result

T = TypeVar('T')


class IDTuple(Tuple):
    is_idlist = True
    pass


class IDList(List):
    is_idlist = True
    pass


# these are distinguished by containing IDLists / IDTuples
# these trigger replacement of IDs by instances
# IDs = Union[IDList[ID], ID]
# Types = Union[List[T], T]
# OptionalIDs = Optional[IDs]

# containers of a specific type [child containers] - only some of these are created on their own as indicated
ItemOfType = Annotated[T, None]
PairOfType = Tuple[T, T] # not created standalone
TripletOfType = Tuple[T, T, T] # not created standalone
QuartetOfType = Tuple[T, T, T, T] # not created standalone
OneOrMoreOfType = Union[List[T], T]
OptionalOneOrMoreOfType = Optional[OneOrMoreOfType]

# containers for IDs - not used on their own
ItemOfID = Annotated[ID, None]
PairOfID = IDTuple[ID, ID]
TripletOfID = IDTuple[ID, ID, ID]
QuartetOfID = IDTuple[ID, ID, ID, ID]
OneOrMoreOfID = Union[IDList[ID], ID]
# OptionalOneOrMoreOfID = Optional[OneOrMoreOfID] - no such instances currently

# containers of IDs or types [links]
Item = Union[T, ID]
Pair = Union[PairOfType[T], PairOfID]
Triplet = Union[TripletOfType[T], TripletOfID]
Quartet = Union[QuartetOfType[T], QuartetOfID]
OneOrMore = Union[OneOrMoreOfType[T], OneOrMoreOfID]

OptionalItem = Optional[Item[T]]
OptionalOneOrMore = Optional[OneOrMore[T]]


class Linkage(StrEnum):
    parent =  auto()
    children =  auto()
    link = auto()
    attribute = auto()
    implementation = auto()
    derived_link = auto()
    derived_attribute = auto()
    cross_package_link = auto()

    none = auto()

# attribute that is a parent
Parent = Annotated[Optional[ItemOfType[T]], Linkage.parent] # optional as they are set at runtime

# attribute that is a container of a child or children
Children = Annotated[T, Linkage.children]

# attribute that is a link between objects but not a child
Link = Annotated[T, Linkage.link]

Attribute = Annotated[T, Linkage.attribute]

Implementation = Annotated[T, Linkage.implementation]

DerivedLink = Annotated[Optional[T], Linkage.derived_link] # optional as they are set at runtime

CrossPackageLink = Annotated[Optional[T], Linkage.cross_package_link] # optional as they are set at runtime

class PCBaseModel(BaseModel, metaclass=PCMeta):

    ID: Implementation[Optional[int]] = None  # not required by appdata maybe we need further level of base model

    @classmethod
    def _get_field_annotations(cls, field_name):
        annotations = cls.__annotations__[field_name] if field_name in cls.__annotations__ else []
        if annotations and not isinstance(annotations, list):
            annotations = [annotations]

        return annotations

    @classmethod
    def _field_is_id_list(cls, field_name):
        annotations = cls._get_field_annotations(field_name)


        origin = get_origin(annotations)
        result = hasattr(origin, 'is_idlist')

        if not result:
            args = typing.get_args(annotations)
            arg_origins = [hasattr(get_origin(arg), 'is_idlist') for arg in args if get_origin(arg)]
            result = True in arg_origins

        return result


    def __init__(self, *args, **kwargs):
        super(PCBaseModel, self).__init__(*args, **kwargs)

        if self.ID is not None:
            # noinspection PyProtectedMember,PyUnresolvedReferences
            self.__class__._object_map[self.ID] = self

    def __str__(self) -> str:
        return f'<class {str(self.__class__)[8:-2]} {self.ID}>'

    __repr__ = __str__

# forward references for type system
class ChemAtom(PCBaseModel):
    ...


class ChemBond(PCBaseModel):
    ...


class ChemCompVar(PCBaseModel):
    ...


class ChemTorsion(PCBaseModel):
    ...


class LinkEnd(PCBaseModel):
    ...


class ChemTorsionSysName(PCBaseModel):
    ...


class ChemAtomSet(PCBaseModel):
    ...


class ChemCompSysName(PCBaseModel):
    ...


class NamingSystem(PCBaseModel):
    ...


class ChemAngle(PCBaseModel):
    ...


class AbstractChemAtom(PCBaseModel):
    ...

class ChemComp(PCBaseModel):
    ...

# add UML cardinality comments..

class AtomChirality(StrEnum):
    R = auto()
    S = auto()
    unknown = auto()


class Stereochemistry(PCBaseModel):
    serial: Attribute[int]  # 1..1
    stereoClass: Attribute[str]  # 1..1
    value: Attribute[str]  # 1..1

    chemAtoms: Link[OptionalOneOrMore[AbstractChemAtom]]  # 0..*
    chemComp: Parent[ChemComp] # 1..1
    coreAtoms: Link[OptionalOneOrMore[AbstractChemAtom]]  # 0..*
    parent: Parent[ChemComp] # 1..1                                            # 1..1
    # refStereoChemistry  external to package             # 0..1


class ChemAngle(PCBaseModel):
    chemAtoms: Link[Triplet[ChemAtom]]  # 3..3
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1

class AbstractChemAtom(PCBaseModel):
    name: Attribute[str]  # 1..1
    subType: Attribute[int] = 1  # 1..1

    chemAngles: Link[OptionalOneOrMore[ChemAngle]]  # 0..*
    chemBonds: Link[OptionalOneOrMore[ChemBond]]  # 0..*
    chemComp: Parent[ChemComp]  # 1..1
    chemCompVars: Link[OptionalOneOrMore[ChemCompVar]]  # 0..*
    chemTorsions: Link[OptionalOneOrMore[ChemTorsion]]  # 0..*
    coreStereochemistries: Link[OptionalOneOrMore[Stereochemistry]]  # 0..*
    parent: Parent[ChemComp]  # 1..1
    stereochemistries: Link[OptionalOneOrMore[Stereochemistry]]  # 0..*


class ChemAtom(AbstractChemAtom):
    type: Attribute[Literal['ChemAtom']]
    chirality: Attribute[OptionalItem[AtomChirality]]  # 0..1
    elementSymbol: Attribute[str]  # 1..1
    nuclGroupType: Attribute[Optional[str]]  # 0..1
    shortVegaType: Attribute[Optional[str]]  # 0..1
    waterExcangeable: Attribute[bool] = False  # 1..1

    boundLinkEnds: Link[OptionalOneOrMore[LinkEnd]]  # 0..*
    chemAtomSet: Link[OptionalItem[ChemAtomSet]]  # 0..1
    chemComp: Parent[ChemComp]  # 1..1
    # chemElement # derived                               # 1..1
    parent: Parent[ChemComp]  # 1..1
    remotelinkEnd: Link[OptionalOneOrMore[LinkEnd]]  # 0..*


class LinkAtom(AbstractChemAtom):
    type: Literal['LinkAtom']
    elementSymbol: Optional[str]  # 0..1
    boundLinkEnd: Link[OptionalItem[LinkEnd]]  # 0..1
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1
    remotelinkEnd: Link[OptionalItem[LinkEnd]]  # 0..1


class ChemTorsion(PCBaseModel):
    name: Attribute[str]  # 0..1

    chemAtoms: Link[Quartet[ChemAtom]]  # 4..4
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1
    sysNames: Link[OptionalOneOrMore[ChemTorsionSysName]]  # 0..*


class ChemAtomSet(PCBaseModel):
    distCorr: Attribute[float] = 0.0  # 1..1
    # elementSymbol  #  derived                            # 1..1
    isEquivalent: Attribute[Optional[bool]]  # 0..1
    isProchiral: Attribute[Optional[bool]]  # 1..1  # no default value bu not always present
    name: Attribute[str]  # 1..1
    subType: Attribute[int] = 1  # 1..1

    chemAtomSet: Link[OptionalItem[ChemAtomSet]]  # 0..1
    chemAtomSets: Link[OptionalOneOrMore[ChemAtomSet]]  # 0..*
    chemAtoms: Link[OptionalOneOrMore[ChemAtom]]  # 1..1
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1

class BondType(StrEnum):
    single = auto()
    double = auto()
    triple = auto()
    aromatic = auto()
    dative = auto()
    singleplanar = auto()


class BondStereochemistry(StrEnum):
    E = auto()
    Z = auto()
    unknown = auto()


class ChemBond(PCBaseModel):
    bondType: Attribute[BondType] = BondType.single  # 1..1
    stereochem: Attribute[Optional[BondStereochemistry]]  # 0..1

    chemAtoms: Link[Pair[ChemAtom]]  # 2..2
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1

class ChemCompLinking(StrEnum):
    start = auto()
    middle = auto()
    end = auto()
    none = auto()
    any = auto()


class ChemCompSysName(PCBaseModel):
    sysName: Attribute[str]  # 1..1

    # chemCompVars # derived                                # 0..*
    namingSystem: Parent[NamingSystem]  # 1..1
    specificChemCompvars: Link[OptionalOneOrMore[ChemCompVar]]  # 0..*
    parent: Parent[NamingSystem]  # 1..1



class ChemCompVar(PCBaseModel):
    descriptor: Attribute[str]  # 1..1
    formalCharge: Attribute[Optional[int]]  # 1..1 but apparently no default...
    # formula # derived str
    glycoCtCode: Attribute[Optional[str]]  # 0..1
    isAromatic: Attribute[bool]  = False  # 1..1 but apparently no default...
    isDefaultVar: Attribute[bool] = False  # 1..1
    isParamagnetic: Attribute[bool] = False  # 1..1 but apparently no default...
    linking: Attribute[ChemCompLinking]  # 1..1
    # molecularMass derived                                   # 1..1
    # name derived                                            # 0..1
    nonStereoSmiles: Attribute[Optional[str]]  # 0..1
    stereoSmiles: Attribute[Optional[str]]  # 0..1
    varName: Attribute[Optional[str]]  # 0..1

    # chemAngles    derived                                   # 0..*
    # chemAtomSets  derived                                   # 0..*
    chemAtoms: Link[OptionalOneOrMore[AbstractChemAtom]]  # 0..*
    # chemBonds     derived                                   # 0..*
    chemComp: Parent[ChemComp]  # 1..1
    # chemCompSysNames derived                                # 0..*
    # chemTorsions derived                                    # 0..*
    # linkEnds derived                                        # 0..*
    parent: Parent[ChemComp]  # 1..1
    specificSysNames: Link[OptionalOneOrMore[ChemCompSysName]]  # 0..*


class LinkEnd(PCBaseModel):
    linkCode: Attribute[str]  # should be enum                         # 1..1

    boundChemAtom: Link[OptionalItem[ChemAtom]]  # 1..1 is required but not always present?
    boundLinkAtom: Link[OptionalItem[LinkAtom]]  # 1..1 is required but not always present?
    chemComp: Parent[ChemComp]  # 1..1
    remoteChemAtom: Link[OptionalItem[ChemAtom]]  # 1..1 is required but not always present?
    remoteLinkAtom: Link[OptionalItem[LinkAtom]]  # 1..1 is required but not always present?
    parent: Parent[ChemComp]  # 1..1


class AtomSysName(PCBaseModel):
    altSysName: Attribute[OptionalOneOrMore[str]]  # 0..*
    atomName: Attribute[str]  # 1..1
    atomSubType: Attribute[int] = 1  # 1..1
    sysName: Attribute[Optional[str]]  # 1..1 is required but not always present?

    namingSystem: Parent[NamingSystem]  # 1..1
    parent: Parent[NamingSystem]  # 1..1


class ChemTorsionSysName(PCBaseModel):
    sysName: Attribute[Optional[str]] # 1..1
    chemTorsion: Link[OptionalItem[ChemTorsion]]  # 1..1 is required but not always present?
    namingSystem: Parent[NamingSystem]  # 1..1
    parent: Parent[NamingSystem]  # 1..1


class NamingSystem(PCBaseModel):
    name: Attribute[str]  # 1..1

    atomReference: Link[OptionalItem[NamingSystem]]  # 0..1
    atomSetReference: Link[OptionalItem[NamingSystem]]  # 0..1
    atomSetVariantSystems: Link[OptionalOneOrMore[NamingSystem]]  # 0..*
    atomSysNames: Children[OptionalOneOrMore[AtomSysName]]  # 0..*
    atomVariantSystems: Link[OptionalOneOrMore[NamingSystem]]  # 0..*
    chemComp: Parent[ChemComp]  # 1..1
    chemCompSysNames: Children[OptionalOneOrMore[ChemCompSysName]]  # 0..*
    chemTorsionSysNames: Children[OptionalOneOrMore[ChemTorsionSysName]]  # 0..*
    # mainChemCompSysName # derived                            # 0..1
    parent: Parent[ChemComp]  # 1..1


class ApplicationData(PCBaseModel):
    application: Attribute[str]  # 1..1
    keyword: Attribute[str]  # 1..1

    def __str__(self):
        return f'{self.__class__} {self.application}:{self.keyword}'

    __repr__ = __str__


class AppDataStr(ApplicationData):
    type: Literal['AppDataString']
    value: Attribute[OneOrMore[str]]  # 1..1 we are getting lists of strings here where it should be lists of AppDataString...


class AppDataInt(ApplicationData):
    type: Literal['ApplicationDataInt']
    value: Attribute[OneOrMore[int]]  # 1..1 we are getting lists of ints here where it should be lists of AppDataString...


class AppDataBoolean(ApplicationData):
    type: Literal['AppDataBoolean']
    value: Attribute[bool]  # 1..1 seems to be correct here...


AppDataTypes = Union[AppDataStr, AppDataInt, AppDataBoolean]


def object_children_root_only(target, parent):

    linkage = get_linkage(parent.target, parent.selector)
    elems = object_children(target, parent)

    if isinstance(target, (list, PCBaseModel)):
        if linkage in (Linkage.link, Linkage.parent):
            for elem in elems:
                elem.is_leaf = True

    return elems

class MolType(StrEnum):
    protein = auto()
    DNA = auto()
    RNA = auto()
    carbohydrate = auto()
    other = auto()

# inspect.get_annotations only available in 3.10
class Annotations_Cache:

    def __init__(self, size):
        self._cache = LRUCache(size)


    def get_annotations(self, o):


        object_id = (o.__class__.__name__, o.__class__.__module__, id(o))

        if object_id in self._cache:
             result = self._cache[object_id]

        else:
            if isinstance(o, type):
                attr_dict = getattr(o, '__dict__', {})
                result = attr_dict.get('__annotations__', {})
            else:
                result = getattr(o, '__annotations__', {})

            if result is None:
                result = {}

            self._cache[object_id] = result

        return result

# inspect.get_annotations recreates the data everytime so cache it !!!
annotation_cache = Annotations_Cache(30)

def get_annotations(o: object, include_super_classes:bool = True) -> typing.Dict[str, type]:

    annotations = annotation_cache.get_annotations(o)

    if include_super_classes:
        for super_class in o.__class__.mro():
            super_class_annotations = annotation_cache.get_annotations(super_class)

            super_class_annotations.update(annotations)
            annotations =  super_class_annotations

    return annotations


def get_item_linkage(item: ObjectIter.Entry) -> Linkage:
    return get_linkage(item.target, item.selector)


def get_linkage(target: PCBaseModel, selector: str) -> Linkage:

    annotations = get_annotations(target)

    result = Linkage.none
    if selector and selector in annotations:
        annotation = annotations[selector]
        if (get_origin(annotation) is typing.Annotated):
            args = set(get_args(annotation))

            link_type = args.intersection(Linkage.__members__.keys())
            result = next(iter(link_type)) if len(link_type) else Linkage.none

    return result


class ChemComp(PCBaseModel):



    baseGlycoCode: Attribute[Optional[str]]  # 0..1
    beilsteinCode: Attribute[Optional[str]]  # 0..1
    caseRegCode: Attribute[Optional[str]]  # 0..1
    ccpCode: Attribute[str]  # 1..1
    code1Letter: Attribute[Optional[str]]  # 0..1
    code3Letter: Attribute[Optional[str]]  # 0..1
    commonNames: Attribute[OptionalOneOrMore[str]]  # 0..*
    details: Attribute[Optional[str]]  # 0..1
    hasStdChirality: Attribute[Optional[bool]]  # 0..1
    # isLinearPolymer: bool   derived                        # 1..1
    keywords: Attribute[OptionalOneOrMore[str]] # 0..*
    merckCode: Attribute[Optional[str]]  # 0..1
    molType: Attribute[MolType]  # 1..1
    name: Attribute[Optional[str]]  # 0..1
    sigmaAldrichCode: Attribute[Optional[str]]  # 0..1
    stdChemCompCode: Attribute[Optional[str]]  # 0..1

    # should be in parent class...
    guid: Attribute[str]
    createdBy: Attribute[str]

    chemAngles: Children[OptionalOneOrMoreOfType[ChemAngle]]  # 0..*
    chemAtomSets:  Children[OptionalOneOrMoreOfType[ChemAtomSet]]  # 0..*
    chemAtoms:  Children[List[Annotated[Union[ChemAtom, LinkAtom], Field(discriminator='type')]]]  # 0..*
    chemBonds:  Children[OptionalOneOrMoreOfType[ChemBond]]  # 0..*
    chemCompVars: Children[OptionalOneOrMoreOfType[ChemCompVar]] # 0..*
    chemTorsions:  Children[OptionalOneOrMoreOfType[ChemTorsion]]  # 0..*
    memopsRoot: Parent[object] # Parent[MemopsRoot] parent - not implemented # 1..1
    linkEnds: Children[OptionalOneOrMoreOfType[LinkEnd]]  # 0..*
    namingSystems: Children[OptionalOneOrMoreOfType[NamingSystem]]  # 0..*
    parent: Parent[object] # : Parent[MemopsRoot]  # 1..1
    # residueTypeProbabilities - out of package not implemented                            # 0..*
    # stdChemComp  #derived                                                                # 0..1
    stereochemistries:  Children[OptionalOneOrMoreOfType[Stereochemistry]]  # 0..*

    applicationData:  Children[OptionalOneOrMore[Annotated[AppDataTypes, Field(discriminator='type')]]]

    def __post_init__(self):
        self._make_links()

    def _make_links(self):
        object_iter = ObjectIter(result_generator=item_only)
        for_parent = []
        for_children = []

        for i, item in enumerate(object_iter.iter(self)):
            linkage = get_item_linkage(item)

            if linkage == Linkage.parent:
                for_parent.append(item)
            elif linkage == Linkage.link:
                if item.value is not None:
                    for_children.append(item)

        for item in for_parent:
            setattr(item.target, item.selector, object_iter.get_parent(object_iter.get_parent(item)).target)

        for j, item in enumerate(for_children):
            value = item.value
            if isinstance(value, ID):

                setattr(item.target, item.selector, self.__class__._object_map[item.value])
            elif isinstance(value, tuple):

                new_value = [None] * len(value)
                for i, elem in enumerate(item.value):
                    if isinstance(elem, ID):
                        new_value[i] = self.__class__._object_map[elem]
                setattr(item.target, item.selector, tuple(new_value))
            elif isinstance(value, list):

                for i, elem in enumerate(item.value):
                    if isinstance(elem, ID):
                        value[i] = self.__class__._object_map[elem]

    def json(self, original=False):

        if original:
            result = super(ChemComp, self).json()
        else:
            copy_of_data = self.copy(deep=True)
            copy_of_data.unlink()
            result = copy_of_data.json(original=True)
        return result


    def unlink(self):
        object_iter = ObjectIter(result_generator=item_only, child_lister=object_children_root_only)
        for_parent = []
        for_children = []
        for i, item in enumerate(object_iter.iter(self)):

            linkage = get_item_linkage(item)

            if linkage == Linkage.parent:
                for_parent.append(item)
            elif linkage == Linkage.link:
                if item.value is not None:
                    for_children.append(item)

        for item in for_parent:
            setattr(item.target, item.selector, None)
        for j, item in enumerate(for_children):

            value = item.value
            if isinstance(value, PCBaseModel):

                setattr(item.target, item.selector, value.ID)
            elif isinstance(value, tuple):

                new_value = [None] * len(value)
                for i, elem in enumerate(item.value):

                    if isinstance(elem, PCBaseModel):
                        new_value[i] = elem.ID
                setattr(item.target, item.selector, tuple(new_value))

            elif isinstance(value, list):

                for i, elem in enumerate(item.value):
                    if isinstance(elem, PCBaseModel):
                        value[i] = elem.ID
