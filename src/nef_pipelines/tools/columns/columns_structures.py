"""Column-specific exceptions and data structures for the NEF columns tools."""

from dataclasses import dataclass
from enum import auto
from pathlib import Path
from typing import List, Optional, Union

from pynmrstar import Loop
from strenum import LowercaseStrEnum

from nef_pipelines.lib.structures import NEFPipelinesException

# Enums


class InsertPlacement(LowercaseStrEnum):
    BEFORE = auto()
    AFTER = auto()
    AT = auto()
    APPEND = auto()


class ExtractFormat(LowercaseStrEnum):
    CSV = auto()
    SIMPLE = auto()


class TabularFormatResult(LowercaseStrEnum):
    """Format detection results for tabular data files."""

    RAGGED_WHITESPACE = auto()
    CLEVERCSV_AUTO = auto()
    UNKNOWN_OR_MESSY = auto()


# Value Specification Structures


@dataclass
class DefaultValueSpecification:
    pass


@dataclass
class FileValueSpecification:
    path: Path
    col: Optional[str]
    skip: int = 0
    comment: str = ""


@dataclass
class RepeatValueSpec:
    value: str
    count: Optional[int]  # None = fill to row count


@dataclass
class RangeValueSpec:
    start: int
    end: int


@dataclass
class RangeFromValueSpec:
    start: int


@dataclass
class LiteralsValueSpecification:
    values: List[str]


ValueSpec = Union[
    DefaultValueSpecification,
    FileValueSpecification,
    RepeatValueSpec,
    RangeValueSpec,
    RangeFromValueSpec,
    LiteralsValueSpecification,
]


# Column Specification Structures


@dataclass
class ColumnSpecification:
    """A parsed column specification: name and optional value expression."""

    col_name: str
    value_spec: ValueSpec


@dataclass
class InsertInstruction:
    """A fully-resolved column-insertion instruction carrying its target loop."""

    column_spec: ColumnSpecification
    keyword: InsertPlacement
    position_anchor: Optional[Union[int, str]]
    loop: Loop


@dataclass
class OrderedArguments:
    """One item from the command line, in argv order. The ordered sequence is a
    List[OrderedArg] holding both placement flags and col specs."""

    offset: int
    kind: str  # "flag" or "col"
    name: Optional[
        str
    ]  # param variable name for flags ("before"/"after"/"at"); None for cols
    value: str  # anchor for flags; raw col-spec token for cols


@dataclass
class ColumnPlacement:
    """A column specification with its requested placement, before file expansion and loop
    resolution into an InsertInstruction. col_spec may still carry a 'frame.loop:' prefix
    until the specs are grouped by loop."""

    col_spec: str
    placement: InsertPlacement
    anchor: Optional[str]


# Exceptions


@dataclass
class NEFColumnsFileNotFoundException(NEFPipelinesException):
    """A file reference in a column specification could not be found."""

    path: str  # Path as string for easier serialization


@dataclass
class NEFColumnsFileIOException(NEFPipelinesException):
    """An I/O error occurred while reading a file for column data."""

    path: str
    operation: str  # e.g., "read"
    cause: Exception


@dataclass
class NEFColumnsColumnNotFoundInLoopException(NEFPipelinesException):
    """A column reference (name or index) could not be resolved in a loop."""

    ref: Union[int, str]  # column name or 1-based index
    loop_category: str
    n_columns: int


@dataclass
class NEFColumnsColumnNotFoundInFileException(NEFPipelinesException):
    """A column reference (name or index) could not be resolved in a file."""

    ref: Union[int, str]  # column name or 1-based index
    path: str
    available: List[str]


@dataclass
class NEFColumnsDuplicateLoopException(NEFPipelinesException):
    """Attempted to create a loop that already exists in the frame."""

    loop_category: str
    frame_name: str


@dataclass
class NEFColumnsTagCategoryMismatchException(NEFPipelinesException):
    """A column tag has a different category than its loop."""

    tag_name: str
    tag_category: str
    loop_category: str


@dataclass
class NEFInsertCLILoopNotDefinedException(NEFPipelinesException):
    """A column specification requires a loop but none was provided."""

    col_spec: str
    selector: Optional[str]  # None = absent; str with no '.' = frame-only (ambiguous)
    is_file_ref: bool


@dataclass
class NEFColumnsRenameColumnNotFoundException(NEFPipelinesException):
    """A column to rename was not found in the loop."""

    col_name: str
    loop_category: str

    def __str__(self) -> str:
        return f"column '{self.col_name}' not found in loop {self.loop_category}"


@dataclass
class NEFColumnsRenameParseException(NEFPipelinesException):
    """Parse error in rename argument specification."""

    error_type: str  # 'empty_tag', 'empty_new_name', 'unpaired_tag', 'missing_selector'
    arg: str  # The problematic argument
    selector: Optional[str] = None  # Value of --selector (for context)
    index: Optional[int] = None  # Argument position (for unpaired case)


class NEFColumnsException(NEFPipelinesException): ...  # noqa: E701
