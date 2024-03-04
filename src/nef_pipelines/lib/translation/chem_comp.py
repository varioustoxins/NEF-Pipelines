# # todo sort out app data lists
# # todo derived methods
# # todo remove parent links on json dump
# # todo unify tree iterators!
#

from enum import Enum, auto
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from annotated_types import Gt

#
from cachetools import LRUCache
from pydantic import BaseModel, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from pydantic_core.core_schema import no_info_after_validator_function
from strenum import StrEnum

from nef_pipelines.lib.translation.object_iter import (
    ObjectIter,
    item_only,
    object_children,
)


class PCMeta(BaseModel.__class__):
    _object_map = {}

    def __call__(self, *args, **kwargs):
        result = super(PCMeta, self).__call__(*args, **kwargs)

        if hasattr(result, "__post_init__") and isinstance(
            result.__post_init__, Callable
        ):
            result.__post_init__()

        return result


class ID(int):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls, handler(Annotated[int, Gt(0)])
        )


T = TypeVar("T")


class IDTuple(Tuple):
    is_idlist = True

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[[Any], CoreSchema]
    ) -> CoreSchema:
        args = get_args(source_type)
        if args:
            return handler(Tuple[args])
        else:
            return no_info_after_validator_function(IDTuple, handler(Tuple))


class IDList(List):
    is_idlist = True

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[[Any], CoreSchema]
    ) -> CoreSchema:
        args = get_args(source_type)
        if args:
            return handler(List[args])
        else:
            return no_info_after_validator_function(IDList, handler(List))


# these are distinguished by containing IDLists / IDTuples
# these trigger replacement of IDs by instances
IDs = Union[IDList[ID], ID]
Types = Union[List[T], T]
OptionalIDs = Optional[IDs]

# containers of a specific type [child containers] - only some of these are created on their own as indicated
ItemOfType = Annotated[T, None]
PairOfType = Tuple[T, T]  # not created standalone
TripletOfType = Tuple[T, T, T]  # not created standalone
QuartetOfType = Tuple[T, T, T, T]  # not created standalone
OneOrMoreOfType = Union[List[T], T]
OptionalOneOrMoreOfType = Optional[OneOrMoreOfType]

# containers for IDs - not used on their own
ItemOfID = Annotated[ID, None]
PairOfID = IDTuple[ID, ID]
TripletOfID = IDTuple[ID, ID, ID]
QuartetOfID = IDTuple[ID, ID, ID, ID]
OneOrMoreOfID = Union[IDList[ID], ID]
OptionalOneOrMoreOfID = Optional[OneOrMoreOfID]  # - no such instances currently

# containers of IDs or types [links]
Item = Union[T, ID]
Pair = Union[PairOfType[T], PairOfID]
Triplet = Union[TripletOfType[T], TripletOfID]
Quartet = Union[QuartetOfType[T], QuartetOfID]
OneOrMore = Union[OneOrMoreOfType[T], OneOrMoreOfID]

OptionalItem = Optional[Item[T]]
OptionalOneOrMore = Optional[OneOrMore[T]]


class Linkage(StrEnum):
    parent = auto()
    children = auto()
    link = auto()
    attribute = auto()
    implementation = auto()
    derived_link = auto()
    derived_attribute = auto()
    cross_package_link = auto()

    none = auto()


# # attribute that is a parent
Parent = Annotated[
    Optional[ItemOfType[T]], Linkage.parent
]  # optional as they are set at runtime

# attribute that is a container of a child or children
Children = Annotated[T, Linkage.children]

# attribute that is a link between objects but not a child
Link = Annotated[T, Linkage.link]

WithInverse = Annotated

Attribute = Annotated[T, Linkage.attribute]

Implementation = Annotated[T, Linkage.implementation]

DerivedLink = Annotated[
    Optional[T], Linkage.derived_link
]  # optional as they are set at runtime

CrossPackageLink = Annotated[
    Optional[T], Linkage.cross_package_link
]  # optional as they are set at runtime


class PCBaseModel(BaseModel, metaclass=PCMeta):

    ID: Implementation[Optional[int]] = (
        None  # not required by appdata maybe we need further level of base model
    )

    @classmethod
    def _get_field_annotations(cls, field_name):
        annotations = (
            cls.__annotations__[field_name] if field_name in cls.__annotations__ else []
        )
        if annotations and not isinstance(annotations, list):
            annotations = [annotations]

        return annotations

    @classmethod
    def _field_is_id_list(cls, field_name):
        annotations = cls._get_field_annotations(field_name)

        origin = get_origin(annotations)
        result = hasattr(origin, "is_idlist")

        if not result:
            args = get_args(annotations)
            arg_origins = [
                hasattr(get_origin(arg), "is_idlist") for arg in args if get_origin(arg)
            ]
            result = True in arg_origins

        return result

    def __init__(self, **kwargs):
        super(PCBaseModel, self).__init__(**kwargs)

        if self.ID is not None:
            # noinspection PyProtectedMember,PyUnresolvedReferences
            self.__class__._object_map[self.ID] = self

    def __str__(self) -> str:
        return f"<class {str(self.__class__)[8:-2]} {self.ID}>"

    __repr__ = __str__


# forward references for type system
class ChemAtom(PCBaseModel): ...


class ChemBond(PCBaseModel): ...


class ChemCompVar(PCBaseModel): ...


class ChemTorsion(PCBaseModel): ...


class LinkEnd(PCBaseModel): ...


class ChemTorsionSysName(PCBaseModel): ...


class ChemAtomSet(PCBaseModel): ...


class ChemCompSysName(PCBaseModel): ...


class NamingSystem(PCBaseModel): ...


class ChemAngle(PCBaseModel): ...


class AbstractChemAtom(PCBaseModel): ...


class LinkAtom(PCBaseModel): ...


class ChemComp(PCBaseModel): ...


class AppDataString(PCBaseModel): ...


class AppDataInt(PCBaseModel): ...


class AppDataBoolean(PCBaseModel): ...


class InverseName(str): ...


def name_annotation(name):
    return InverseName(name)


class AtomChirality(StrEnum):
    R = auto()
    S = auto()
    unknown = auto()


class Stereochemistry(PCBaseModel):
    serial: Attribute[int]  # 1..1
    stereoClass: Attribute[str]  # 1..1
    value: Attribute[str]  # 1..1

    chemAtoms: Link[
        WithInverse[
            OptionalOneOrMore[AbstractChemAtom], name_annotation("stereochemstries")
        ]
    ]  # 0..*
    chemComp: Parent[ChemComp]  # 1..1
    coreAtoms: Link[
        WithInverse[
            OptionalOneOrMore[AbstractChemAtom],
            name_annotation("coreStereochemistries"),
        ]
    ]  # 0..*
    parent: Parent[ChemComp]  # 1..1
    # package             # 0..1


class ChemAngle(PCBaseModel):
    chemAtoms: Link[
        WithInverse[Triplet[ChemAtom], name_annotation("chemAngles")]
    ]  # 3..3
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1


class AbstractChemAtom(PCBaseModel):
    name: Attribute[str]  # 1..1
    subType: Attribute[int] = 1  # 1..1

    chemAngles: Link[
        WithInverse[OptionalOneOrMore[ChemAngle], name_annotation("chemAtoms")]
    ]  # 0..*
    chemBonds: Link[
        WithInverse[OptionalOneOrMore[ChemBond], name_annotation("chemAtoms")]
    ]  # 0..*
    chemComp: Parent[ChemComp]  # 1..1
    chemCompVars: Link[
        WithInverse[OptionalOneOrMore[ChemCompVar], name_annotation("chemAtoms")]
    ]  # 0..*
    chemTorsions: Link[
        WithInverse[OptionalOneOrMore[ChemTorsion], name_annotation("chemAtoms")]
    ]  # 0..*
    coreStereochemistries: Link[
        WithInverse[OptionalOneOrMore[Stereochemistry], name_annotation("coreAtoms")]
    ]  # 0..*
    parent: Parent[ChemComp]  # 1..1
    stereochemistries: Link[
        WithInverse[OptionalOneOrMore[Stereochemistry], name_annotation("chemAtoms")]
    ]  # 0..*


class ChemAtom(AbstractChemAtom):
    type: Attribute[Literal["ChemAtom"]]
    chirality: Attribute[OptionalItem[AtomChirality]]  # 0..1
    elementSymbol: Attribute[str]  # 1..1
    nuclGroupType: Attribute[Optional[str]]  # 0..1
    shortVegaType: Attribute[Optional[str]]  # 0..1
    waterExchangeable: Attribute[bool] = False  # 1..1

    boundLinkEnds: Link[
        WithInverse[OptionalOneOrMore[LinkEnd], name_annotation("boundChemAtom")]
    ]  # 0..*
    chemAtomSet: Link[
        WithInverse[OptionalItem[ChemAtomSet], name_annotation("chemAtoms")]
    ]  # 0..1
    chemComp: Parent[ChemComp]  # 1..1
    # chemElement # derived                               # 1..1
    parent: Parent[ChemComp]  # 1..1
    remoteLinkEnds: Link[
        WithInverse[OptionalOneOrMore[LinkEnd], name_annotation("remoteChemAtom")]
    ]  # 0..*


class LinkAtom(AbstractChemAtom):
    type: Literal["LinkAtom"]
    elementSymbol: Optional[str] = None  # 0..1

    boundLinkEnd: Link[
        WithInverse[OptionalItem[LinkEnd], name_annotation("boundLinkAtom")]
    ]  # 0..1
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1
    remoteLinkEnd: Link[
        WithInverse[OptionalItem[LinkEnd], name_annotation("remoteLinkAtom")]
    ]  # 0..1


class ChemTorsion(PCBaseModel):
    name: Attribute[str]  # 0..1

    chemAtoms: Link[
        WithInverse[Quartet[ChemAtom], name_annotation("chemTorsions")]
    ]  # 4..4
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1
    sysNames: Link[
        WithInverse[
            OptionalOneOrMore[ChemTorsionSysName], name_annotation("chemTorsion")
        ]
    ]  # 0..*


class ChemAtomSet(PCBaseModel):
    distCorr: Attribute[float] = 0.0  # 1..1
    # elementSymbol  #  derived                            # 1..1
    isEquivalent: Attribute[Optional[bool]]  # 0..1
    isProchiral: Attribute[
        Optional[bool]
    ]  # 1..1  # no default value but not always present
    name: Attribute[str]  # 1..1
    subType: Attribute[int] = 1  # 1..1

    chemAtomSet: Link[
        WithInverse[OptionalItem[ChemAtomSet], name_annotation("chemAtomSets")]
    ]  # 0..1
    chemAtomSets: Link[
        WithInverse[OptionalOneOrMore[ChemAtomSet], name_annotation("chemAtomSet")]
    ]  # 0..*
    chemAtoms: Link[
        WithInverse[OptionalOneOrMore[ChemAtom], name_annotation("chemAtomSet")]
    ]  # 1..1
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

    chemAtoms: Link[WithInverse[Pair[ChemAtom], name_annotation("chemBonds")]]  # 2..2
    chemComp: Parent[ChemComp]  # 1..1
    parent: Parent[ChemComp]  # 1..1


class ChemCompLinking(StrEnum):
    start = auto()
    middle = auto()
    end = auto()
    free = auto()
    none = auto()
    any = auto()


class ChemCompSysName(PCBaseModel):
    sysName: Attribute[str]  # 1..1

    # chemCompVars # derived                                # 0..*
    namingSystem: Parent[NamingSystem]  # 1..1
    # TODO this name is incorrect...
    specificChemCompvars: Link[
        WithInverse[OptionalOneOrMore[ChemCompVar], name_annotation("specificSysNames")]
    ]  # 0..*
    parent: Parent[NamingSystem]  # 1..1


class ChemCompVar(PCBaseModel):
    descriptor: Attribute[str]  # 1..1
    formalCharge: Attribute[Optional[int]]  # 1..1 but apparently no default...
    # formula # derived str
    glycoCtCode: Attribute[Optional[str]]  # 0..1
    isAromatic: Attribute[bool] = False  # 1..1 but apparently no default...
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
    chemAtoms: Link[
        WithInverse[
            OptionalOneOrMore[AbstractChemAtom], name_annotation("chemCompVars")
        ]
    ]  # 0..*
    # chemBonds     derived                                   # 0..*
    chemComp: Parent[ChemComp]  # 1..1
    # chemCompSysNames derived                                # 0..*
    # chemTorsions derived                                    # 0..*
    # linkEnds derived                                        # 0..*
    parent: Parent[ChemComp]  # 1..1
    specificSysNames: Link[
        WithInverse[
            OptionalOneOrMore[ChemCompSysName], name_annotation("specificChemCompVars")
        ]
    ]  # 0..*


class LinkEnd(PCBaseModel):
    linkCode: Attribute[str]  # should be enum                         # 1..1

    boundChemAtom: Link[
        WithInverse[OptionalItem[ChemAtom], name_annotation("boundLinkEnds")]
    ]  # 1..1 is required but not always present?
    boundLinkAtom: Link[
        WithInverse[OptionalItem[LinkAtom], name_annotation("boundLinkEnd")]
    ]  # 1..1 is required but not always present?
    chemComp: Parent[ChemComp]  # 1..1
    # chemCompVars derived
    parent: Parent[ChemComp]  # 1..1
    remoteChemAtom: Link[
        WithInverse[OptionalItem[ChemAtom], name_annotation("remoteLinkEnds")]
    ]  # 1..1 is required but not always present?
    remoteLinkAtom: Link[
        WithInverse[OptionalItem[LinkAtom], name_annotation("remoteLinkEnd")]
    ]  # 1..1 is required but not always present?


class AtomSysName(PCBaseModel):
    altSysName: Attribute[OptionalOneOrMore[str]]  # 0..*
    atomName: Attribute[str]  # 1..1
    atomSubType: Attribute[int] = 1  # 1..1
    sysName: Attribute[Optional[str]]  # 1..1 is required but not always present?

    namingSystem: Parent[NamingSystem]  # 1..1
    parent: Parent[NamingSystem]  # 1..1


class ChemTorsionSysName(PCBaseModel):
    sysName: Attribute[Optional[str]]  # 1..1
    chemTorsion: Link[
        WithInverse[OptionalItem[ChemTorsion], name_annotation("sysNames")]
    ]  # 1..1 is required but not always present?
    namingSystem: Parent[NamingSystem]  # 1..1
    parent: Parent[NamingSystem]  # 1..1


class NamingSystem(PCBaseModel):
    name: Attribute[str]  # 1..1

    atomReference: Link[
        WithInverse[OptionalItem[NamingSystem], name_annotation("atomVariantSystems")]
    ]  # 0..1
    atomSetReference: Link[
        WithInverse[
            OptionalItem[NamingSystem], name_annotation("atomSetVariantSystems")
        ]
    ]  # 0..1
    atomSetVariantSystems: Link[
        WithInverse[
            OptionalOneOrMore[NamingSystem], name_annotation("atomSetReference")
        ]
    ]  # 0..*
    atomSysNames: Children[OptionalOneOrMore[AtomSysName]]  # 0..*
    atomVariantSystems: Link[
        WithInverse[OptionalOneOrMore[NamingSystem], name_annotation("atomReference")]
    ]  # 0..*
    chemComp: Parent[ChemComp]  # 1..1
    chemCompSysNames: Children[OptionalOneOrMore[ChemCompSysName]]  # 0..*
    chemTorsionSysNames: Children[OptionalOneOrMore[ChemTorsionSysName]]  # 0..*
    # mainChemCompSysName # derived                            # 0..1
    parent: Parent[ChemComp]  # 1..1


class ApplicationData(PCBaseModel):
    application: Attribute[str]  # 1..1
    keyword: Attribute[str]  # 1..1

    def __str__(self):
        return f"{self.__class__} {self.application}:{self.keyword}"

    __repr__ = __str__


class AppDataStr(ApplicationData):
    type: Literal["AppDataString"]
    value: Attribute[
        OneOrMore[str]
    ]  # 1..1 we are getting lists of strings here where it should be lists of AppDataString...


class AppDataInt(ApplicationData):
    type: Literal["AppDataInt"]
    value: Attribute[
        OneOrMore[int]
    ]  # 1..1 we are getting lists of ints here where it should be lists of AppDataString...


class AppDataBoolean(ApplicationData):
    type: Literal["AppDataBoolean"]
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
class AnnotationsCache:
    def __init__(self, size):
        self._cache = LRUCache(size)

    def get_annotations(self, o):

        # object_id = (o.__class__.__name__, o.__class__.__module__, id(o))

        # if object_id in self._cache:
        #      result = self._cache[object_id]
        #
        # else:
        if isinstance(o, type):
            attr_dict = getattr(o, "__dict__", {})
            result = attr_dict.get("__annotations__", {})
        else:
            result = getattr(o, "__annotations__", {})

        if result is None:
            result = {}

        # self._cache[object_id] = result

        return result


# inspect.get_annotations recreates the data everytime so cache it !!!
annotation_cache = AnnotationsCache(3000)


def get_annotations(o: object, include_super_classes: bool = True) -> Dict[str, type]:

    annotations = annotation_cache.get_annotations(o)

    if include_super_classes:
        for super_class in o.__class__.mro():
            super_class_annotations = annotation_cache.get_annotations(super_class)

            super_class_annotations.update(annotations)
            annotations = super_class_annotations

    return annotations


def get_item_linkage(item: ObjectIter.Entry) -> Linkage:
    return get_linkage(item.target, item.selector)


def get_linkage(target: object, selector: str) -> Linkage:

    annotations = get_annotations(target)

    result = Linkage.none
    if selector and selector in annotations:
        annotation = annotations[selector]
        if get_origin(annotation) is Annotated:
            args = set(get_args(annotation))

            link_type = args.intersection(Linkage.__members__.keys())
            result = next(iter(link_type)) if len(link_type) else Linkage.none

    return result


def get_item_opposite(item: ObjectIter.Entry) -> Tuple[str, List[type]]:
    return get_opposite_and_types(item.target, item.selector)


def get_item_opposite_selector(item: ObjectIter.Entry) -> Optional[str]:
    return get_opposite_selector(item.target, item.selector)


def get_opposite_selector(target: object, selector: str) -> Optional[str]:
    annotations = get_annotations(target)

    result = None
    if selector and selector in annotations:
        annotation = annotations[selector]
        if get_origin(annotation) is Annotated:
            args = set(get_args(annotation))

            result = [arg for arg in args if type(arg) == InverseName]

            if len(result) > 1:
                raise Exception(f"unexpected multiple opposites {result}")

    return result[0] if len(result) == 1 else None


def get_opposite_and_types(target: object, selector: str) -> Tuple[str, List[type]]:

    annotations = get_annotations(target)

    inverse = None
    opposite_types = []
    if selector and selector in annotations:
        annotation = annotations[selector]
        if get_origin(annotation) is Annotated:
            args = set(get_args(annotation))

            inverse = [arg for arg in args if type(arg) == InverseName]
            opposite_type = [arg for arg in args if type(arg) != InverseName]

            inverse = inverse[0] if len(inverse) > 0 else None

            if Linkage.link in opposite_type:
                opposite_type.remove(Linkage.link)
                opposite_type = opposite_type[0]

            if get_origin(opposite_type) == Union:
                opposite_type = get_args(opposite_type)

            opposite_types = [
                get_origin(arg) if get_origin(arg) else arg for arg in opposite_type
            ]

    return inverse, opposite_types


def id_in_iter(iterable, object_id):
    result = False
    for value in iterable:
        if isinstance(value, ID) and value == object_id:
            result = True
            break
    return result


def origin_or_value(annotations):
    return [
        get_origin(annotation) if get_origin(annotation) is not None else annotation
        for annotation in annotations
    ]


def strip_annotation(annotations):
    current_annotations = annotations

    do_strip = True
    while do_strip:
        if get_origin(current_annotations) == Annotated:
            current_annotations = get_args(current_annotations)[0]
            continue
        if get_origin(current_annotations) == Union:
            current_annotations = get_args(current_annotations)
            do_strip = False
            continue

        do_strip = False
        continue

    annotations_are_iterable = isinstance(current_annotations, (list, tuple))
    result = (
        origin_or_value(current_annotations)
        if annotations_are_iterable
        else [get_origin(current_annotations)]
    )

    return result


class ContainerTypes(Enum):
    SINGLETON = auto()
    ORDERED = auto()  # a tuple
    UNORDERED = auto()  # a list
    unordered_unique = auto()  # a set - but we currently use a list
    ordered_unique = auto()  # an ordered set - but we currently use a list


def get_link_container_type(target: object, selector: str) -> ContainerTypes:
    link_types = strip_annotation(get_annotations(target)[selector])

    if list in link_types:
        result = ContainerTypes.UNORDERED
    elif tuple in link_types:
        result = ContainerTypes.ORDERED
    elif any([PCBaseModel in link_type.mro() for link_type in link_types]):
        result = ContainerTypes.SINGLETON
    else:
        raise Exception(f"unexpected types {link_types}")

    return result


def get_item_link_container_type(item: ObjectIter.Entry) -> ContainerTypes:

    return get_link_container_type(item.target, item.selector)


class ChemComp(PCBaseModel):
    pass

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
    keywords: Attribute[OptionalOneOrMore[str]]  # 0..*
    merckCode: Attribute[Optional[str]]  # 0..1
    molType: Attribute[MolType]  # 1..1
    name: Attribute[Optional[str]]  # 0..1
    sigmaAldrichCode: Attribute[Optional[str]]  # 0..1
    stdChemCompCode: Attribute[Optional[str]]  # 0..1
    #
    # TODO: should be in parent class...
    guid: Attribute[str]
    createdBy: Attribute[str]
    #
    chemAngles: Children[OptionalOneOrMoreOfType[ChemAngle]]  # 0..*
    chemAtomSets: Children[OptionalOneOrMoreOfType[ChemAtomSet]]  # 0..*
    chemAtoms: Children[
        List[Annotated[Union[ChemAtom, LinkAtom], Field(discriminator="type")]]
    ]  # 0..*
    chemBonds: Children[OptionalOneOrMoreOfType[ChemBond]]  # 0..*
    chemCompVars: Children[OptionalOneOrMoreOfType[ChemCompVar]]  # 0..*
    chemTorsions: Children[OptionalOneOrMoreOfType[ChemTorsion]]  # 0..*
    #     memopsRoot: Parent[object]  # Parent[MemopsRoot] parent - not implemented # 1..1
    linkEnds: Children[OptionalOneOrMoreOfType[LinkEnd]]  # 0..*
    namingSystems: Children[OptionalOneOrMoreOfType[NamingSystem]]  # 0..*
    parent: Parent[object]  # : Parent[MemopsRoot]  # 1..1
    # residueTypeProbabilities - out of package not implemented                            # 0..*
    # stdChemComp  #derived                                                                # 0..1
    stereochemistries: Children[OptionalOneOrMoreOfType[Stereochemistry]]  # 0..*

    applicationData: Children[
        OptionalOneOrMore[Annotated[AppDataTypes, Field(discriminator="type")]]
    ]

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
            setattr(
                item.target,
                item.selector,
                object_iter.get_parent(object_iter.get_parent(item)).target,
            )

        for j, item in enumerate(for_children):

            value = item.value

            link_container_type = get_item_link_container_type(item)

            if link_container_type is ContainerTypes.SINGLETON:

                replacement_value = self.__class__._object_map[item.value]

                setattr(item.target, item.selector, replacement_value)

            elif link_container_type is ContainerTypes.ORDERED:

                new_value = [None] * len(value)
                for i, elem in enumerate(item.value):
                    if isinstance(elem, ID):
                        new_value[i] = self.__class__._object_map[elem]
                    elif isinstance(elem, PCBaseModel):
                        new_value[i] = elem
                    else:
                        raise Exception("unexpected")
                setattr(item.target, item.selector, tuple(new_value))
            elif link_container_type is ContainerTypes.UNORDERED:

                if isinstance(item.value, PCBaseModel):
                    setattr(item.target, item.selector, [item.value])
                elif isinstance(item.value, ID):
                    setattr(
                        item.target,
                        item.selector,
                        [self.__class__._object_map[item.value]],
                    )
                else:
                    for i, elem in enumerate(item.value):
                        if isinstance(elem, ID):
                            value[i] = self.__class__._object_map[elem]
                        elif isinstance(elem, PCBaseModel):
                            value[i] = elem
                        else:
                            raise Exception("unexpected")
            else:
                raise Exception("unexpected")

            # now iterate again setting opposite links...
            opposite_selector = get_item_opposite_selector(item)

            new_value = getattr(item.target, item.selector)

            if link_container_type is ContainerTypes.UNORDERED:
                if not isinstance(new_value, list):
                    raise Exception("unexpected")
            if link_container_type is ContainerTypes.ORDERED:
                if not isinstance(new_value, tuple):
                    raise Exception("unexpected")

            elif link_container_type in (
                ContainerTypes.UNORDERED,
                ContainerTypes.ORDERED,
            ):

                if len(new_value) > 0:

                    for elem in new_value:

                        self._ensure_opposite_container(elem, opposite_selector, item)

                        opposite_container_type = get_link_container_type(
                            new_value[0], opposite_selector
                        )

                        if opposite_container_type is ContainerTypes.SINGLETON:
                            self._setup_singleton_opposite(
                                elem, opposite_selector, item
                            )

                        elif opposite_container_type in (
                            ContainerTypes.UNORDERED,
                            ContainerTypes.ORDERED,
                        ):

                            self._setup_container_opposite(
                                elem, opposite_selector, opposite_container_type, item
                            )

    def _setup_container_opposite(
        self, elem, opposite_selector, opposite_container_type, item
    ):

        opposite_values = getattr(elem, opposite_selector)

        target_values = (
            list(opposite_values)
            if opposite_container_type is ContainerTypes.ORDERED
            else opposite_values
        )

        if len(target_values) > 0 and isinstance(target_values[0], ID):
            for i, target_value in enumerate(target_values):
                if isinstance(target_value, ID):
                    target_values[i] = self.__class__._object_map[target_value]

        # this looks a little odd but object comparison currently fails and needs looking at
        is_correct_id = [elem.ID == item.target.ID for elem in target_values]
        needs_append = not any(is_correct_id)

        if needs_append and opposite_container_type is ContainerTypes.ORDERED:
            raise Exception("unexpected for ordered container")
        if needs_append:
            raise Exception("had to append")
            # target_values.append(item.target)

        if opposite_container_type is ContainerTypes.ORDERED:
            setattr(elem, opposite_selector, tuple(target_values))

        # ids = [new_elem.ID for new_elem in getattr(elem, opposite_selector)]
        # if not item.target.ID in ids:
        #     raise Exception('Unexpected')

    def _setup_singleton_opposite(self, elem, opposite_selector, item):

        opposite_value = getattr(elem, opposite_selector)

        if isinstance(opposite_value, ID):
            new_opposite_value = self.__class__._object_map[opposite_value]
        elif opposite_value is None:
            new_opposite_value = item.target
        else:
            new_opposite_value = opposite_value

        setattr(elem, opposite_selector, new_opposite_value)

        if getattr(elem, opposite_selector).ID != item.target.ID:
            raise Exception(
                f"unexpected mismatch! {getattr(elem, opposite_selector).ID}, {item.target.ID}"
            )

    def _ensure_opposite_container(
        self, elem, opposite_selector, opposite_container_type
    ):
        opposite_value = getattr(elem, opposite_selector)

        need_list = (
            opposite_container_type is ContainerTypes.UNORDERED
            and not isinstance(opposite_value, list)
        )
        need_tuple = (
            opposite_container_type is ContainerTypes.ORDERED
            and not isinstance(opposite_value, tuple)
        )

        if need_list or need_tuple:

            new_opposite_value = []
            if opposite_value is not None:
                new_opposite_value.append(opposite_value)

                if need_tuple:
                    new_opposite_value = tuple(new_opposite_value)
                setattr(elem, opposite_selector, new_opposite_value)

    def json(self, original=False):

        if original:
            result = super(ChemComp, self).json()
        else:
            copy_of_data = self.model_copy(deep=True)
            copy_of_data.unlink()
            result = copy_of_data.json(original=True)
        return result

    def unlink(self):
        object_iter = ObjectIter(
            result_generator=item_only, child_lister=object_children_root_only
        )
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

        # for object in self.__class__.__opposites__:
        #     print(object)
