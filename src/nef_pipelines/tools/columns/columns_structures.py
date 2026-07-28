"""Column-specific exceptions and data structures for the NEF columns tools."""

from dataclasses import dataclass, field
from enum import auto
from pathlib import Path
from typing import List, Optional, Tuple, Union

from pynmrstar import Loop
from strenum import LowercaseStrEnum

from nef_pipelines.lib.structures import Advisory, NEFPipelinesException

# Enums


class InsertPlacement(LowercaseStrEnum):
    BEFORE = auto()
    AFTER = auto()
    AT = auto()
    APPEND = auto()


class ExtractFormat(LowercaseStrEnum):
    CSV = auto()
    SIMPLE = auto()


# Value Specification Structures


@dataclass
class DefaultValueSpecification:
    pass

    def __str__(self) -> str:
        return "."


@dataclass
class FileValueSpecification:
    path: Path
    col: Optional[str]
    format: ExtractFormat = ExtractFormat.CSV

    def __str__(self) -> str:
        base = f"@{self.path}:{self.col}" if self.col else f"@{self.path}"
        if self.format != ExtractFormat.CSV:
            return f"{base} (format={self.format})"
        return base


@dataclass
class ResolvedFileValueSpecification:
    """A file reference whose column has already been read into literal values.

    Carries the originating path so row-count diagnostics can still name the file after
    the value has been resolved out of the file system.
    """

    path: Path
    values: List[str]

    def __str__(self) -> str:
        return f"@{self.path} ({len(self.values)} values)"


@dataclass
class RepeatValueSpec:
    value: str
    count: Optional[int]  # None = fill to row count

    def __str__(self) -> str:
        if self.count is None:
            return f"{self.value}*"
        return f"{self.value}*{self.count}"


@dataclass
class RangeValueSpec:
    start: int
    end: int

    def __str__(self) -> str:
        return f"{self.start}..{self.end}"


@dataclass
class RangeFromValueSpec:
    start: int

    def __str__(self) -> str:
        return f"{self.start}.."


@dataclass
class LiteralsValueSpecification:
    values: List[str]

    def __str__(self) -> str:
        if len(self.values) <= 3:
            return ",".join(self.values)
        return f"{','.join(self.values[:3])}... ({len(self.values)} values)"


ValueSpec = Union[
    DefaultValueSpecification,
    FileValueSpecification,
    ResolvedFileValueSpecification,
    RepeatValueSpec,
    RangeValueSpec,
    RangeFromValueSpec,
    LiteralsValueSpecification,
]


# File Reading Control Instructions


class ColumnHeadings(LowercaseStrEnum):
    """Whether a file's first row names its columns.

    ON and OFF are disjoint: with ON every column reference is a name, so ':1' means the column
    headed '1'; with OFF every reference is a 1-based position. AUTO leaves the decision to the
    detection rules, which warn when they had to infer it.
    """

    ON = auto()
    OFF = auto()
    AUTO = auto()


@dataclass(frozen=True)
class FileSettings:
    """The file reading state in force for a column specification, captured from the positional
    --comment/--skip/--skip-tail/--clear-comments/--use-column-headings flags at the point the
    specification appeared on the command line."""

    comment: Tuple[str, ...] = ()
    skip: int = 0
    skip_tail: int = 0
    use_column_headings: ColumnHeadings = ColumnHeadings.AUTO

    def __str__(self) -> str:
        parts = []
        if self.comment:
            parts.append(f"comment={', '.join(repr(p) for p in self.comment)}")
        if self.skip:
            parts.append(f"skip={self.skip}")
        if self.skip_tail:
            parts.append(f"skip_tail={self.skip_tail}")
        if self.use_column_headings != ColumnHeadings.AUTO:
            parts.append(f"use_column_headings={self.use_column_headings}")
        return ", ".join(parts) if parts else "defaults"


@dataclass
class CommentInstruction:
    """Set comment prefixes for subsequent file reads.

    These instructions are interspersed with InsertInstruction in the command-line order.
    When encountered during execution, they update the global comment state for all
    subsequent file reads until the next CommentInstruction.

    Args:
        prefixes: List of comment prefixes (empty list = no comment filtering)
    """

    prefixes: List[str]  # Empty list = no comments

    def __str__(self) -> str:
        if not self.prefixes:
            return "Clear comments"
        return f"Set comments: {', '.join(repr(p) for p in self.prefixes)}"


@dataclass
class SkipInstruction:
    """Set skip values for subsequent file reads.

    These instructions are interspersed with InsertInstruction in the command-line order.
    When encountered during execution, they update the global skip state for all
    subsequent file reads until the next SkipInstruction.

    Args:
        skip: Number of rows to skip after comment removal (default 0)
        skip_tail: Number of trailing rows to skip (default 0)
    """

    skip: int = 0
    skip_tail: int = 0

    def __str__(self) -> str:
        parts = []
        if self.skip:
            parts.append(f"skip={self.skip}")
        if self.skip_tail:
            parts.append(f"skip_tail={self.skip_tail}")
        return f"Set {', '.join(parts)}" if parts else "Reset skip"


@dataclass
class UseColumnHeadingsInstruction:
    """Set the column-heading mode for subsequent file reads.

    Interspersed with InsertInstruction in command-line order, exactly like
    CommentInstruction and SkipInstruction. When encountered during execution it
    replaces the global heading mode for all subsequent file reads until the next
    UseColumnHeadingsInstruction.

    Args:
        mode: ON, OFF or AUTO - see ColumnHeadings
    """

    mode: ColumnHeadings

    def __str__(self) -> str:
        return f"Set column headings: {self.mode}"


# Column Specification Structures


@dataclass
class ColumnSpecification:
    """A parsed column specification: name and optional value expression."""

    col_name: str
    value_spec: ValueSpec


@dataclass
class InsertInstruction:
    """A fully-resolved column-insertion instruction carrying its target loop.

    Carries no file-reading state of its own. apply_column_instructions() derives the
    comment/skip/heading state in force for this instruction by walking the instruction
    stream up to this point - see CommentInstruction, SkipInstruction and
    UseColumnHeadingsInstruction.

    Source tracking fields allow precise error reporting without rescanning/reparsing the
    original spec strings. spec_arg_index is the 0-based position in the argv specs list;
    spec_sub_index handles cases where a single spec (e.g., wildcard) expands to multiple
    instructions (0 for first match, 1 for second, etc.).
    """

    column_spec: ColumnSpecification
    keyword: InsertPlacement
    position_anchor: Optional[Union[int, str]]
    loop: Loop
    spec_arg_index: int
    spec_sub_index: int

    def __str__(self) -> str:
        loop_name = self.loop.category.lstrip("_")
        col_name = self.column_spec.col_name
        value_spec_str = str(self.column_spec.value_spec)

        if self.keyword == InsertPlacement.APPEND:
            placement = "append"
        else:
            placement = f"{self.keyword.value} {self.position_anchor}"

        return f"Insert '{col_name}' = {value_spec_str} into {loop_name} ({placement})"


# The instruction stream applied by apply_column_instructions, in command-line order.
Instruction = Union[
    CommentInstruction, SkipInstruction, UseColumnHeadingsInstruction, InsertInstruction
]


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
class HeadingsInferredAdvisory(Advisory):
    """The heading mode for a file was inferred from how its columns were referenced.

    Carries only the facts of the inference. The wording, and any mention of the option that
    would state the mode explicitly, belongs to whatever renders this.

    Args:
        path: The file that was read
        has_header: The mode that was inferred - True if its first row was read as headings
        is_mixed: Whether the references mixed position and name, which is what made the
            inference ambiguous rather than merely implicit
    """

    path: Path
    has_header: bool
    is_mixed: bool = False


@dataclass
class ColumnPlacement:
    """A column specification with its requested placement, before file expansion and loop
    resolution into an InsertInstruction. col_spec may still carry a 'frame.loop:' prefix
    until the specs are grouped by loop.

    spec_arg_index tracks the 0-based position in the original argv specs list for error
    reporting.
    """

    col_spec: str
    placement: InsertPlacement
    anchor: Optional[str]
    spec_arg_index: int
    file_settings: FileSettings = field(default_factory=FileSettings)


# Exceptions


@dataclass
class NEFColumnsFileNotFoundException(NEFPipelinesException):
    """A file reference in a column specification could not be found."""

    path: str  # Path as string for easier serialization
    instruction: Optional["InsertInstruction"] = None


@dataclass
class NEFColumnsFileIOException(NEFPipelinesException):
    """An I/O error occurred while reading a file for column data."""

    path: str
    operation: str  # e.g., "read"
    cause: Exception
    instruction: Optional["InsertInstruction"] = None


@dataclass
class NEFColumnsColumnNotFoundInLoopException(NEFPipelinesException):
    """A column reference (name or index) could not be resolved in a loop."""

    ref: Union[int, str]  # column name or 1-based index
    loop_category: str
    n_columns: int
    instruction: Optional["InsertInstruction"] = None


@dataclass
class NEFColumnsColumnNotFoundInFileException(NEFPipelinesException):
    """A column reference (name or index) could not be resolved in a file."""

    ref: Union[int, str]  # column name or 1-based index
    path: str
    available: List[str]
    line_number: Optional[int] = (
        None  # Line number in original file where header was expected
    )
    instruction: Optional["InsertInstruction"] = None


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


@dataclass
class NEFColumnsReorderMissingSelectorException(NEFPipelinesException):
    """Missing loop selector specification."""

    provided: Optional[str] = None

    def __str__(self) -> str:
        if self.provided:
            result = f"invalid loop selector: '{self.provided}'"
        else:
            result = "missing loop selector"

        return result


@dataclass
class NEFColumnsReorderInvalidPolicyException(NEFPipelinesException):
    """Invalid policy specified (not exact/append/prepend)."""

    policy: str
    valid_policies: List[str]

    def __str__(self) -> str:
        valid_str = ", ".join(self.valid_policies)
        return f"invalid policy '{self.policy}'; valid policies are: {valid_str}"


@dataclass
class NEFColumnsReorderUnknownColumnsException(NEFPipelinesException):
    """Specified columns don't exist in loop."""

    unknown_columns: List[str]
    selector: str
    available_columns: List[str]

    def __str__(self) -> str:
        unknown_str = ", ".join(self.unknown_columns)
        available_str = ", ".join(self.available_columns)
        return f"columns not found in loop {self.selector}: {unknown_str}; available columns: {available_str}"


@dataclass
class NEFColumnsReorderDuplicateColumnsException(NEFPipelinesException):
    """Duplicate columns in reorder specification."""

    duplicate_columns: List[str]
    selector: str = ""

    def __str__(self) -> str:
        dupes_str = ", ".join(self.duplicate_columns)
        if self.selector:
            return f"duplicate columns in reorder specification for {self.selector}: {dupes_str}"
        return f"duplicate columns in reorder specification: {dupes_str}"


@dataclass
class NEFColumnsReplaceInvalidFormatException(NEFPipelinesException):
    """Invalid replace specification format."""

    arg: str
    expected_format: str = "selector @file:col or col @file:col"

    def __str__(self) -> str:
        return f"invalid replace format '{self.arg}'; expected: {self.expected_format}"


class NEFColumnsException(NEFPipelinesException): ...  # noqa: E701
