# What is the Structure of NEF-Pipelines and What Are the Common Design Features

NEF-Pipelines is a collection of python scripts that are designed to be chained together in a unix pipeline to provide manipulation of NMR Exchange Format (NEF) based data. The scripts are designed to collaborate with each other because they share a common base command line interface (CLI) and a common data format in the form of NEF files or a stream of NEF text. This simple design which combines with the UNIX Tools Philosophy [^1] provides an approach to data manipulation that is both powerful and flexible and allows the inclusion of external programs and builtin unix commands in the pipeline

The base component of a nef pipeline is a _pipe_ which is a single program that takes a NMR Exchange
Format based text data stream which it manipulates, modifies and usually finally outputs back to the
pipeline or terminal. In NEF-Pipelines these pipeline elements are single python scripts which share
a common command structure provided by the _typer_ library's implementation of sub commands.

## The Typer library and the NEF-Pipelines command line interface
The Typer Library [^2] is a python library that provides a simple way to build command line interfaces
for python programs. It is based on the _click_ library and provides a simple way to build commands
using type annotations.

As each subcommand is based on _typer_ their entry points are defined by a single function
which is decorated with type annotations and typer based parameters defining arguments and options
and registered as a sub command of the main application which is called _nef_. A typical nef pipeline
command is shown below [details of the sub command registration process are discussed below]

```python
from typing import List
import typer
from nef_pipelines.transcoders.fasta import export_app
from nef_pipelines.lib.util import STDIN, STDOUT
from pathlib import Path

@export_app.command()
def sequence(
    chain_codes: List[str] = typer.Option(
        [],
        "-c",
        "--chain_code",
        help=...,
        metavar="<CHAIN-CODE>",
    ),
    in_file: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read nef data from", metavar="<NEF-FILE>"
    ),
    output_file: str = typer.Argument(
        None,
        '-o',
        '--output',
        help="file name to output to [default <entry_id>.fasta] for stdout use -",
        metavar="<FASTA-SEQUENCE-FILE>",
    ),
):
    """- convert nef sequence to fasta"""
    ...
```

In this case the command being defined is _sequence_ which is a sub command of the
`export` which itself is a subcommand of the `fasta` command of the `nef` application.
The command would be called somewhat as follows

```bash
  nef ... previous command ...                     \
| nef fasta export sequence --chain A  -o output.fasta   \
| nef ... next command ...
```

Internally the command line interface is designed to be built as simply as possible with the
minimum of programming knowledge as each command is a single function and no
classes or inheritance are required. The help for each command is generated from the
help for each parameter of the _typer_ function and the `doc string` for the function
itself [in this case the overall help is '- convert nef sequence to fasta'].

However, to allow the commands to be used as python libraries an extra level of
function calls is added. This is because, for example, the `sequence` command above
only processes text parameters required by the command line interface which is not suitable
for a programming environment. Therefore, sequence then calls a function `pipe` which does the actual
work. Generally this command is called `pipe` as it is part of a pipeline, but it can also be a command for
a standalone `command` such as nef_pipelines.about.command which provides information about the
NEF-Pipelines system. This is shown below in outline for the `nef fasta export sequence` subcommand.

```python
from typing import List
import typer
from nef_pipelines.transcoders.fasta import export_app
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.types import PipeReturn
from pynmrstar import Entry
from pathlib import Path

@export_app.command()
def sequence(
    chain_codes: List[str] = typer.Option(...),
    in_file: Path = typer.Option(...),
    output_file: str = typer.Argument(...),
):
    """- convert nef sequence to fasta"""

    entry = read_entry_from_file_or_stdin_or_exit_error(in_file)

    ... # more code here to convert command line parameters to function parameters

    result = pipe(entry, chain_codes, output_file)

    for warning in result.warnings:
        warn(warning)

    if result.entry:
        print(result.entry)

def pipe(entry: Entry, chain_codes: List[str], output_file: Path) -> PipeReturn:

    ... # the implementation of the command

    return PipeReturn(entry=entry)
```

Thus while `sequence` is not suitable for use as a python library function the `pipe`
function inside `nef_pipelines.transcoders.fasta.importers.sequence` could be
imported into a python program and used as follows

```python
from pynmrstar import Entry
from nef_pipelines.transcoders.fasta.importers.sequence import pipe as import_sequence
from tabulate import tabulate

with open('input.nef') as nef_file:
    nef_data = nef_file.read()

entry = Entry.from_string(nef_data)
result = import_sequence(entry, ['A'], 'output.fasta')
entry = result.entry

molecular_system = entry.get_loops_by_category('nef_sequence')[0]
table = [row for row in molecular_system]
print(tabulate(table, headers=molecular_system.tags))

```

Thus, it is possible to use the nef pipeline commands as a python library and
build complex programs using nef-pipeline commands as building blocks inside any
python program. In this case the program reads a NEF file, imports a fasta sequence
into a `pynmrstar` `Entry` as chain `A` and then prints the sequence as a table using tabulate.
It should be noted that provision of the python command interface also opens up the possibility of
building a GUI interface to the NEF-Pipelines commands using the same methodology.

> [!NOTE]
> Nota bene: `pipe` is used for all commands that process a NEF stream, commands
> that can just be called are called `command`. Also it should be noted that this
> python script is a bit redundant as the `tabulate` sub command already provides
> the ability to tabulate NEF loops using the NEF-Pipelines library.


## Separation of CLI and Library Concerns

A core architectural principle of NEF-Pipelines is the **separation between CLI functions and library functions**.
This separation ensures that library functions (like `pipe`) remain reusable in programmatic contexts, while CLI
functions handle all user interaction and I/O concerns.

### Library Functions (pipe, helper functions)

**Library functions are silent and pure** — they transform data and either return a structured result or raise
exceptions. They never:

* Print to stdout/stderr (except for legitimate output like NEF streams)
* Print warnings or informational messages
* Call `exit_error()` or other termination functions
* Have side effects beyond their documented purpose

**Library functions should:**

* Return a standardised `PipeReturn` container carrying the transformed `Entry`, any auxiliary `output`, and any
  collected `warnings` (see [The PipeReturn Communication Contract](#the-pipereturn-communication-contract))
* Raise custom exceptions (inheriting from `NEFPipelinesException`) when errors occur
* Be pure, testable functions that can be composed programmatically
* Accept structured parameters (dataclasses, typed arguments) not raw CLI strings

### CLI Functions (typer-decorated command functions)

**CLI functions handle all user interaction**. They are responsible for:

* Parsing command-line arguments into structured parameters
* Catching exceptions from library functions and formatting user-friendly error messages via `exit_error()`
* Inspecting the returned `PipeReturn` and printing warnings (via `warn()`) to stderr
* Reading from stdin/files and writing to stdout/files
* Printing the final NEF stream or routing auxiliary output

### CLI and Pipe functions are high level

The `typer` cli and `pipe` functions are high level functions. They should therefore contain a series of high level
function calls that define how the cli should be processed and validated and in the case of the `pipe` function how
the data is processed. They should read somewhat like pseudo code!

**Example Pattern:**

```python
@columns_app.command()
def rename(
    arguments: List[str] = typer.Argument(...),
    input: Path = typer.Option(STDIN, "--in"),
) -> None:
    """- rename columns"""
    # CLI: Read input
    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # CLI: Parse arguments, catch exceptions, call exit_error
    try:
        rename_pairs = _parse_rename_arguments(arguments, selector)
    except RenameParseError as e:
        exit_error(str(e))

    # CLI: Validate and warn about edge cases
    _warn_if_duplicate_targets(rename_pairs)

    # CLI: Call library function, catch exceptions, call exit_error
    try:
        result = pipe(entry, rename_pairs)
    except ColumnNotFoundException as e:
        exit_error(str(e))

    # CLI: Route warnings collected by the library to stderr
    for warning in result.warnings:
        warn(warning)

    # CLI: Print output
    if result.entry:
        print(result.entry)


def pipe(entry: Entry, rename_pairs: List[Tuple[FrameLoopAndTagSelectors, str]]) -> PipeReturn:
    """Library function: silent transformation, returns PipeReturn, raises exceptions on error."""
    # Pure transformation - no printing, no exit_error, warnings collected not printed
    warnings = []

    if not rename_pairs:
        warnings.append("No rename specifications provided; entry left unmodified.")
        return PipeReturn(entry=entry, warnings=warnings)

    _raise_if_selectors_dont_have_single_tag(rename_pairs)
    renames_by_loop = _group_renames_by_loop(rename_pairs)
    _apply_renames_to_entry(entry, renames_by_loop)

    return PipeReturn(entry=entry, warnings=warnings)
```

This separation ensures that `pipe` can be imported and used in any Python program without unexpected
side effects, while the CLI function provides a user-friendly command-line interface with appropriate
error handling and feedback.

### CLI Design: --force vs --quiet (File vs Stream modification)

NEF-Pipelines follows Unix conventions for when to require explicit confirmation vs when to proceed by default:

**--force: Reserved for File Operations (Persistent State)**

The `--force` flag is used **only** for operations that modify persistent state (such as files on disk). These
operations are destructive and irreversible:

```bash
# File operations need --force
nef save output.nef --force           # Overwrite existing file
```

**Rationale:** Writing to disk is permanent. If you overwrite `output.nef`, the old file is gone. The `--force` flag
makes this destructive intent explicit, following Unix conventions (`rm -f`, `cp -f`, `mv -f`).

**--quiet: For Stream Operations (Transient State)**

For operations on **in-memory objects** (typically NEF streams), the default behavior is to **succeed and warn**
if there will be surprising behaviour such as overwriting a saveframe that already exists. Such operations do not require
a `--force` flag because these operations are:

* Transient (in-memory only, nothing written to disk)
* Reversible (discard the stream and start over)
* Composable (pipelines transform streams without asking permission)

In general, CLI warnings can be suppressed via a `--quiet` flag.

```bash
# Stream operations: succeed by default with warning
nef frames create nef_chemical_shift_list.myshifts
# WARNING: Frame nef_chemical_shift_list_myshifts already exists, replacing it

# Use --quiet to suppress warnings (for scripting)
nef frames create nef_chemical_shift_list.myshifts --quiet
# (silent success)
```

This follows the Unix tools philosophy: protect permanent state, make temporary operations frictionless and quiet
unless there is a problem that prevents an operation from succeeding [e.g. a file read fails; causes exit with an error
message] or unexpected behaviour can occur [creating a new saveframe erases an existing one; leads to a warning].

**`pipe()` functions and CLI functions**

Generally CLI functions warn for operations that need warnings using the `warn` function. However, the underlying pipes
generally succeed without warnings, as warnings in scripts and programs can be an annoyance. For example, the
following pipe just succeeds if a frame already exists:

```python
def pipe(entry: Entry, frames_to_create: List[Tuple[str, str]]) -> Entry:
    """Create frames, replacing any existing frames with the same name."""
    for category, id_part in frames_to_create:
        framecode = _build_framecode(category, id_part)
        _delete_save_frame_if_exists(entry, framecode)   # Delete if exists
        _add_save_frame(category, entry, id_part)        # Create new
    return entry
```

whereas the CLI function gives a warning:

```python
@frames_app.command()
def create(..., quiet: bool = False) -> None:
    """Create empty NEF saveframes."""
    entry = read_or_create_entry_exit_error_on_bad_file(input)

    # Warn about replacements (unless --quiet)
    if not quiet:
        for category, id_part in pairs:
            framecode = _build_framecode(category, id_part)
            if is_save_frame_name_in_entry(entry, framecode):
                warn(f"frame {framecode} already exists, replacing it")

    entry = pipe(entry, pairs)  # Always succeeds
    print(entry)
```

### The _or_raise / _or_exit_error Pattern

A common pattern for separating library logic from CLI error handling is the **`raise` / `exit_error` function pair**:

- **`_or_raise` functions**: Library functions that raise dataclass exceptions with structured data
- **`_or_exit_error` functions**: CLI wrappers that catch exceptions, format user-friendly messages, and call `exit_error()`

**Exception Structure:**

Exceptions inherit from `NEFPipelinesException`, carrying only the data needed to describe the error. If the data is
complex they can also be `@dataclass` classes:

```python
@dataclass
class NEFColumnsRenameParseException(NEFPipelinesException):
    """Parse error in rename argument specification."""

    error_type: str  # 'empty_tag', 'empty_new_name', 'unpaired_tag', 'missing_selector'
    arg: str  # The problematic argument
    selector: Optional[str] = None  # Value of --selector (for context)
    index: Optional[int] = None  # Argument position (for unpaired case)
```

**Library Function (raises with data only):**

```python
def _parse_rename_arguments_or_raise(
    arguments: List[str], selector: str = None
) -> List[Tuple[FrameLoopAndTagSelectors, str]]:
    """Parse rename arguments into structured pairs.

    Raises:
        NEFColumnsRenameParseException: if arguments are malformed
    """
    # ... parsing logic ...
    if not tag_part:
        raise NEFColumnsRenameParseException("empty_tag", arg, selector)
    # Returns structured data, no user-facing strings
```

**Formatting Helper (transforms data to user message):**

```python
def _build_rename_parse_error_message(
    e: NEFColumnsRenameParseException,
    entry: Optional[Entry] = None,
    input_file: Optional[Path] = None,
) -> str:
    """Format exception into user-friendly message with context."""
    if e.error_type == "empty_tag":
        msg = f"tag name is empty in rename spec '{e.arg}'"
    # ... other error types ...

    # Add context if available
    context_parts = []
    if entry:
        context_parts.append(f"entry '{entry.entry_id}'")
    if input_file and input_file != STDIN:
        context_parts.append(f"file '{input_file}'")

    if context_parts:
        msg = f"{msg} [{', '.join(context_parts)}]"

    return msg
```

**CLI Wrapper (catches, formats, exits):**

```python
def _parse_rename_arguments_or_exit_error(
    arguments: list[str], selector: str, entry: Entry, input_file: Path
) -> list[tuple[FrameLoopAndTagSelectors, str]]:
    """Parse rename arguments or exit with formatted error message."""
    try:
        return _parse_rename_arguments_or_raise(arguments, selector)
    except NEFColumnsRenameParseException as e:
        msg = _build_rename_parse_error_message(e, entry, input_file)
        exit_error(msg)
```

**Benefits:**

- **Reusability**: Library functions can be called programmatically without CLI dependencies
- **Testability**: Exceptions carry structured data that's easy to inspect in tests
- **Flexibility**: Error formatting can vary by context (include file/entry info when available)
- **Maintainability**: Error messages centralized in formatting functions, not scattered through parsing logic


## The PipeReturn Communication Contract

To completely untangle data transformation from terminal input/output, all library-level `pipe` functions return a
structured `PipeReturn` object rather than a bare `Entry`. This lets a `pipe` transform data _and_ communicate
non-fatal telemetry (warnings and auxiliary text output) back up to the caller without ever touching a stream itself.
The CLI layer is then solely responsible for deciding how that telemetry reaches the terminal, a file, or is
suppressed entirely.

The `PipeReturn` covers only the **non-fatal** path. A `pipe` signals a **fatal** error by *raising* an exception
derived from `NEFPipelinesException` — it never calls `exit_error()` and never returns a `PipeReturn` describing a
failure. The two channels are therefore complementary and unambiguous: recoverable conditions are collected on
`result.warnings` (and the pipe still returns), while unrecoverable ones are raised as structured
`NEFPipelinesException` subclasses for the CLI wrapper to catch and turn into a user-facing `exit_error()` message.
This keeps the library layer pure — a caller embedding a `pipe` in its own program catches the exception rather
than having the process exit from under it.

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pynmrstar import Entry

@dataclass
class PipeReturn:
    entry: Optional[Entry]
    """The modified NEF entry to be passed down the pipeline.
    Only a *sink* — a pipe that terminates the NEF stream rather than passing it
    on (e.g. an export or display writing to stdout) — returns None here.
    Every other pipe returns the entry so the pipeline keeps flowing."""

    output: Dict[str, str] = field(default_factory=dict)
    """Text output to emit, keyed by destination. A filename writes to that file;
    '-' and '@stdout' write to standard output; '@stderr' writes to standard error.
    The value is the text content sent to that destination."""

    warnings: List[str] = field(default_factory=list)
    """Non-fatal execution warnings collected during processing,
    to be routed cleanly to stderr by the CLI layer."""
```

Note the use of `field(default_factory=...)` for the `output` and `warnings` fields — this avoids Python's mutable
default argument gotcha, so every `PipeReturn` gets its own fresh dict and list.

**Key Structural Benefits:**

- **No stream pollution**: Third-party programs importing NEF-Pipelines as a library are never surprised by
  unsolicited printing to `sys.stderr` or `sys.stdout`.
- **Deterministic interception**: Calling code retains full control to filter, format, suppress, or forward warnings
  programmatically.
- **Streamlined testing**: `pytest` can assert directly against `result.warnings` or `result.output` without setting
  up `capsys` stream-redirection fixtures or mocking the file system.

The CLI wrapper is the "operator" that translates the contents of a `PipeReturn` into standard UNIX stream behaviour.
The general shape is always the same: call `pipe`, drain `result.warnings` to `warn()`, then print or route
`result.entry` / `result.output`.

### Dispatching a PipeReturn by default

Because that shape is identical for almost every command, it is wrapped in a single support routine in
`nef_pipelines.lib.cli_lib` so that a CLI can simply hand off the whole `PipeReturn` and have it dealt with
correctly by default, rather than writing the warning loop and output routing out by hand each time:

```python
from nef_pipelines.lib.cli_lib import output_pipe_return_or_exit_error

result = pipe(entry, ...)
output_pipe_return_or_exit_error(result, out=out, force=force)
```

`output_pipe_return_or_exit_error` performs the whole default hand-off, in order:

1. Drains `result.warnings` to `warn()`, so every warning reaches stderr.
2. Routes `result.output` to its destinations — a filename to that file, `-`/`@stdout` to stdout, `@stderr` to
   stderr — and prints `result.entry` down the pipeline when it is not `None` (i.e. when the command is not a
   sink). This step reuses the existing `print_output_or_exit_error` routing, which already handles the
   stdout / file / stderr and TTY cases correctly, and exits via `exit_error()` on an unwritable or already-existing
   file.

A command only needs to route output by hand when it wants behaviour the default hand-off does not cover; otherwise
the one-liner above is preferred, since it keeps every CLI wrapper uniform and confines all stream and file handling
to a single well-tested routine.

Fatal errors remain on the exception channel: a `pipe` surfaces them by *raising* a `NEFPipelinesException`, and
`output_pipe_return_or_exit_error` only handles the non-fatal `PipeReturn` it is given. To fold the fatal catch into
the same one-liner — so a CLI does not have to write its own `try/except` — call the `run_pipe_or_exit_error`
runner, which wraps the `pipe` call, converts a raised `NEFPipelinesException` into an `exit_error()`, and then
dispatches the resulting `PipeReturn`:

```python
from nef_pipelines.lib.cli_lib import run_pipe_or_exit_error

# equivalent to: try: result = pipe(...) except NEFPipelinesException: exit_error(...)
#                output_pipe_return_or_exit_error(result, out=out, force=force)
run_pipe_or_exit_error(pipe, entry, ..., out=out, force=force)
```

This keeps the two error channels distinct — fatal via `raise`, non-fatal via `PipeReturn` — while still reducing
the whole CLI tail to a single call. Prefer `run_pipe_or_exit_error` when the CLI needs no custom error formatting;
drop to an explicit `try/except` around `pipe` only when a command wants to catch specific exception types and build
a bespoke message.

```python
def test_pipe_warns_on_missing_frames():
    entry = create_mock_entry()

    # No stream capture hooks needed!
    result = pipe(entry, frame_selectors=["missing_frame_99"])

    assert result.entry is not None
    assert len(result.warnings) == 1
    assert "missing_frame_99" in result.warnings[0]
```


## Types of NEF-Pipelines `Pipes` and their Common Structural Features

There are effectively three types of _pipe_ commands

* __Input `pipes`__: These commands read data of some sort convert it to a NEF stream. An example  \
                     would be the command `nef fasta import sequence` which imports a protein / DNA  \
                     or RNA sequence from a fasta file and adds it into the NEF stream.


* __Filter `pipes`__: These commands take a NEF stream and filter it or manipulate in some way. An  \
                      example would be the command `nef frames unassign` which unassigns the `chains`  \
                      `residues` and `atoms` found in one or more `NEF` frames.


* __Output `pipes`__: These commands take a NEF stream and convert it to some other format. An example  \
                      would be the command `nef fasta export sequence` which converts the `NEF` sequence  \
                      data to a fasta file which is the output to disk or stdout.

All three share the same contract: the `pipe` function is silent and returns a `PipeReturn`, while the CLI wrapper
drains `result.warnings` to `warn()` and then routes `result.entry` / `result.output`.

### The Structure of an Input Pipe

The basic structure of an input pipe is as follows:

```python
from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.util import STDIN, warn
from nef_pipelines.lib.types import PipeReturn
from nef_pipelines.transcoders.fasta import import_app

from pynmrstar import Entry

import typer

from pathlib import Path
from typing import List

@import_app.command()
def sequence(
    entry_name: str = typer.Option("fasta", help="a name for the entry if required"),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [- is stdin]",
    ),
    # other options
    file_paths: List[Path] = typer.Argument(
        ...,
        help="list of files to read fasta data from",
        metavar="<FASTA-FILE>.fasta",
    ),
):
    """- import fasta sequence into nef"""

    ... # Any work to convert command line parameters to function parameters goes here

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name=entry_name)

    result = pipe(entry, file_paths, ...)

    for warning in result.warnings:
        warn(warning)

    if result.entry:
        print(result.entry)

def pipe(entry: Entry, file_paths: List[Path], *other_args_here) -> PipeReturn:

    ... # the implementation of the command

    return PipeReturn(entry=entry)
```
As can be seen an input pipe is defined by a function which is decorated with `@import_app.command()` from a
NEF-Pipelines `pipe`. The function takes a number of parameters which are defined by the `typer.Option` and
`typer.Argument` functions. The function then calls the `pipe` function which does the actual work of the
command. The input commands CLI always takes an input file which is defined by the command line options
`-i` or `--in` which is a NEF stream and the name of the entry which is defined by the `entry_name`
parameter. The correct NEF entry is then created by the python function `read_or_create_entry_exit_error_on_bad_file` that either creates a new entry [named from the parameter]
if in_file is `STDIN` [-] or reads an existing entry from input. The function `read_or_create_entry_exit_error_on_bad_file`
calls `exit_error` if the input file is not of the correct format which takes any actions required
to shut down the pipeline. The `pipe` function then does the actual work of the command and returns a
`PipeReturn` whose `entry` is then printed to stdout by the command line function, after any collected
`warnings` have been routed to stderr. It should be noted that the
main parameters for the function, in this case a list of Paths to fasta files, are passed to the CLI
function as an Argument.


### The Structure of a Filter Pipe

The basic structure of a filter pipe is as follows, and is similar to the input pipe with some
minor differences. Here is an example of a _pipe_ which implements the frames filter pipe:

```python
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.util import STDIN, warn
from nef_pipelines.lib.types import PipeReturn
from nef_pipelines.tools.frames import frames_app

from pynmrstar import Entry

import typer

from pathlib import Path
from typing import List

@frames_app.command()
def manipulate(
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [- is stdin]",
    ),
    frame_selectors: List[str] = typer.Argument(..., help='list of frames to filter'),

    # other parameters
):
    """- filter a nef stream """

    ... # Any work to convert command line parameters to function parameters goes here

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    result = pipe(entry, frame_selectors, ...)

    for warning in result.warnings:
        warn(warning)

    if result.entry:
        print(result.entry)

def pipe(entry: Entry, frame_selectors: List[str], *other_args_here) -> PipeReturn:

    warnings = []

    ... # the implementation of the command; append to warnings for non-fatal edge cases

    return PipeReturn(entry=entry, warnings=warnings)
```

As can be seen the input parameter to the CLI is still present but because the command is a filter it
won't be creating a new NEF stream and so doesn't need a name for the NEF stream [Entity]. Also, when
reading the NEF stream it uses the function `read_entry_from_file_or_stdin_or_exit_error` which will
exit with an error if the stream can't be read as it needs a set of frames to filter [this may not be
true for all filters]. Note how a filter that encounters a non-fatal edge case — for example a selector
that matches no frames — collects a message on the `warnings` list rather than printing it, leaving the CLI
to route it to stderr.

### The Structure of an Export Pipe

The basic structure of an export pipe is shown below, and is similar to the previous examples, again with
some differences. The example _pipe_ implements the fasta export sequences CLI command. Note that under the
`PipeReturn` contract the `pipe` function no longer opens or writes files itself: it generates the text and
places it in `result.output`, and the CLI layer performs all file-system side effects. This keeps the library
function pure and removes the unclosed-file-descriptor warnings that the old inline approach produced during testing.
The manual side-effect block below is spelled out to show exactly what happens; in practice a CLI hands the whole
result to `output_pipe_return_or_exit_error` (see [Dispatching a PipeReturn by default](#dispatching-a-pipereturn-by-default))
and does not write this routing itself.

```python
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.util import STDIN, STDOUT, exit_error, warn
from nef_pipelines.lib.types import PipeReturn
from nef_pipelines.transcoders.fasta import export_app

from pynmrstar import Entry

import typer

from pathlib import Path
import sys

FASTA_FILE_TEMPLATE = '{entry_name}.fasta'

@export_app.command()
def sequence(
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [- is stdin]",
    ),
    output_file: Path = typer.Argument(
        None,
        help="file name to output to [default {entry_name}.fasta] for stdout use -",
        metavar="<FASTA-SEQUENCE-FILE>",
    ),
    # other parameters
):
    """- output the molecular system from a nef stream as a fasta file"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # Resolve the output filename at the CLI layer
    entry_name = entry.entry_id
    output_file = FASTA_FILE_TEMPLATE.format(entry_name=entry_name) if not output_file else output_file

    ... # Any work to convert command line parameters to function parameters goes here

    result = pipe(entry, ...)

    for warning in result.warnings:
        warn(warning)

    # CLI layer performs all file-system / stream side effects
    fasta_text = result.output.get("-", "")
    if output_file == STDOUT:
        sys.stdout.write(fasta_text)
    else:
        try:
            with open(output_file, 'w') as out_handle:
                out_handle.write(fasta_text)
        except Exception as e:
            msg = f"Error opening output file {output_file} for writing fasta file because {e}"
            exit_error(msg, e)

    # Forward the intact entry down the pipeline unless output went to stdout
    if output_file != STDOUT and result.entry:
        print(result.entry)

def pipe(entry: Entry, *other_args_here) -> PipeReturn:

    ... # the implementation of the command

    fasta_text = ...

    return PipeReturn(entry=entry, output={"-": fasta_text})
```

As can be seen the input parameter to the CLI is still present but because the command is an output it
again won't be creating a new NEF stream and so doesn't need a name for the NEF stream [Entity]. Also,
when reading the NEF stream it uses the function `read_entry_from_file_or_stdin_or_exit_error` which will
exit with an error if the stream can't be read as it needs a molecular system frame to output sequences from.
The output file is defined by the `output_file` parameter which is `None` [disk using the fasta
file name template] by default. The name of the output file is defined by the `FASTA_FILE_TEMPLATE` if the
output is the default and the file is written to the current working directory. Users can also provide
their own filename and include the entry_name template parameter {entry_name} in the filename.

> [!WARNING]
> The way filename templates are currently supported makes NEF-Pipelines insecure to use as a web service as
> the internal data can be leaked from the program and arbitrary code run as part of file name templates.
> This will be addressed in a future version of NEF-Pipelines if there is a need or a request is received
> to use it as part of a web service.

> [!NOTE]
> Nota bene: note how, under the `PipeReturn` contract, the `pipe` function only generates the fasta text and
> places it in `result.output`, while the CLI decides whether that text goes to `sys.stdout` or to a file. Keeping
> the file open/write/close logic in the CLI layer means the `pipe` function has no file handles to leak, which
> removes the unclosed-descriptor warnings the old inline approach produced during testing. It should also be
> noted that when output is written to a file the CLI forwards the intact `result.entry` down the pipeline, whereas
> when output goes to `STDOUT` nothing further is printed as STDOUT is no longer a NEF stream.

### Handling Display Output: `print_output_or_exit_error`

Display commands (e.g. `nef frames display`) produce human-readable text that is not a NEF
stream. This creates a routing problem: the text needs to go somewhere useful depending on
whether stdout is a terminal or a pipe, and the caller may also want the underlying NEF entry
to continue flowing down the pipeline.

The utility function `print_output_or_exit_error` in `nef_pipelines.lib.cli_lib` encapsulates
this routing logic so it never needs to be written inline. It pairs naturally with the `output`
dictionary of a `PipeReturn`, which can be passed straight in as `output_dict`:

```python
from nef_pipelines.lib.cli_lib import print_output_or_exit_error

result = pipe(entry, ...)
print_output_or_exit_error(result.entry, out, result.output, force)
```

**Parameters**

| Parameter | Type | Description |
|---|---|---|
| `entry` | `Entry \| None` | NEF entry to print to stdout when display output is routed elsewhere; pass `None` if not applicable |
| `out` | `str \| None` | Value of the `--out` CLI option |
| `output_dict` | `Dict[str, str]` | Mapping of output key → display text; `"-"` is the default key |
| `force` | `bool` | If `True`, overwrite existing files without error |

**Routing behaviour**

| `--out` value | Display text | NEF entry |
|---|---|---|
| `None` or `"@auto"` | → stdout if stdout is a TTY | — |
| `None` or `"@auto"` (piped) | → stderr | → stdout |
| `"-"` or `"@out"` | → stdout | — |
| `"@err"` | → stderr | → stdout |
| file path | → file | → stdout |

When routing to a file, the function exits with an error if the file already exists and
`force` is `False`.

**TTY detection**

The function uses `nef_pipelines.lib.util.is_stdout_tty()` rather than
`sys.stdout.isatty()` directly. Tests should therefore patch
`nef_pipelines.lib.cli_lib.is_stdout_tty`, not `sys.stdout.isatty`.

### How the Subcommands in NEF-Pipelines are Created, Organised and Discovered

### How NEF-Pipelines is Tested and How the Tests are Organised

### How NEF-Pipelines Cleanly Shuts Down the Pipeline When an Error Occurs

### The Structure of the NEF-Pipelines Repository and Distribution

### The NEF-Pipelines Library and How it is Used in NEF-Pipelines

## Evolutionary History: Transitioning to PipeReturn

### Design Note: Transition from Legacy Raw Returns

In early iterations of NEF-Pipelines, library `pipe` functions always used the same simple signature — a pipe's a
pipe: an `Entry` goes in and an `Entry` comes out, keeping the stream flowing — and handled warnings and auxiliary
file output inline:

```python
# LEGACY PATTERN (deprecated)
def pipe(entry: Entry, *args) -> Entry:
    # Warnings were printed inline here to sys.stderr
    # Auxiliary files were opened and written directly here
    return entry
```

The one awkward exception to "entry in, entry out" was the original `export` pipe acting as a **sink**: when output
went to `STDOUT` it opened, wrote, and closed the output stream itself and returned `None`, because stdout was no
longer a NEF stream. It worked, but it both coupled the library layer to the terminal and file system and quietly
broke the uniform `-> Entry` contract — which is part of what motivated `PipeReturn`, where `entry` becoming `None`
is now explicit and expected. Only a sink returns `None`; every other pipe returns its entry so the stream keeps
flowing.

**Why the legacy pattern was replaced**

- **Testing side-effects**: Inline printing to `sys.stderr` and direct file writing forced tests to constantly
  mock the file system and capture `stdout`/`stderr`, making the test suite rigid and prone to resource leaks
  (e.g. unclosed file descriptors flagging warnings in `pytest`).
- **Library pollution**: Programs importing NEF-Pipelines as a raw Python library had their standard error
  streams involuntarily polluted by internal pipeline telemetry.
- **Loss of control**: The calling interface had no programmatically safe way to intercept, suppress, or reformat
  warnings generated deep within a `pipe` function.

The `PipeReturn` contract shifts all stream routing, file opening, and terminal formatting strictly to the
`@app.command()` CLI boundaries, ensuring the underlying library remains pure, silent, and easily embeddable.
There is no compatibility shim: existing pipes that still return a bare `Entry` remain exactly as they are.
Because the Python library interface is not yet published and is a work in progress, there is no external
contract to preserve, so pipes can be migrated to `PipeReturn` incrementally as they are touched.

## Design Decisions and Rejected Alternatives

This section records design choices made while shaping the `PipeReturn` contract, including alternatives that
were considered and deliberately not adopted. It exists so the reasoning behind the current design is not lost,
and so the same alternatives are not silently reintroduced later.

### Progressive (generator) telemetry — rejected

An alternative to returning a single `PipeReturn` at the end of a `pipe` was for a `pipe` to `yield` warnings and
outputs progressively, generator-style, as a long-running operation proceeds. This was rejected as too much
complication for too little benefit. Because a bare `yield` carries no type information, yielded values would need
an out-of-band convention to say what each one is — for example treating a `str` as a line bound for stdout and a
`tuple` as a file destination — and that implicit protocol makes the pipeline harder to debug. The single
`PipeReturn` object keeps destinations explicit through the `output` dict keys and avoids introducing generator
control-flow into every pipe.

### The `output` dictionary convention — decided

The `output` field of `PipeReturn` maps a destination to the text to send there:

- A **filename** key writes the value to that file.
- `-` and `@stdout` write the value to standard output.
- `@stderr` writes the value to standard error.
- The **value** in every case is the file contents / text emitted to that destination.

Note that this key set is intentionally distinct from the `--out` CLI option values (`@auto`, `@out`, `@err`)
consumed by `print_output_or_exit_error`: the `output` dict keys describe where a `pipe` wants its text to go,
whereas `--out` is a user-facing routing option handled entirely at the CLI layer.

### No compatibility shim — decided

No shim was added to translate legacy bare-`Entry` pipes into `PipeReturn` (see *Evolutionary History* above).
Old pipes remain exactly as they are; because the Python library interface is unpublished and a work in progress,
there is no external contract to preserve and migration can happen incrementally.

### Filename-template web-service exposure — deferred

The filename-template mechanism remains insecure for use as a public web service (see the warning under *The
Structure of an Export Pipe*). This is deliberately left as-is and treated as a future item, to be addressed only
if a genuine web-service need arises.

### Folding fatal exceptions into `PipeReturn` — considered, rejected

It was considered whether a `pipe` should catch `NEFPipelinesException` internally and hand the error back inside the
`PipeReturn` (e.g. an `error` field) rather than raising, so that a caller always receives a `PipeReturn` and never
has to write a `try/except`. This was rejected.

The point of a fatal error being an exception is that it *cannot be ignored*: a `raise` unwinds the stack so no
caller can accidentally keep processing, whereas an error carried in a return field relies on every caller
remembering to check it before trusting `result.entry`. It also creates an ambiguous half-state — if `pipe` catches
at the top level and returns, `entry` holds a partially-mutated, untrustworthy value that nonetheless looks like a
normal result. And converting exceptions to values is un-idiomatic in Python; a library user embedding `pipe()`
expects `try/except`, not a Go-style value check. Keeping fatal (raise) and non-fatal (`PipeReturn.warnings`) on
two distinct channels is precisely what makes the model easy to reason about.

The real motivation behind the idea — removing the `try/except` boilerplate from every CLI — is better solved by
the `run_pipe_or_exit_error` runner (see [Dispatching a PipeReturn by default](#dispatching-a-pipereturn-by-default)),
which wraps the `pipe` call, turns a raised `NEFPipelinesException` into an `exit_error()`, and dispatches the
resulting `PipeReturn` — keeping the two channels distinct while still giving a one-line call site.

The one case where capturing errors *as data* is genuinely correct is batch / per-item work ("import 50 files, 3
failed, report all 3 and continue"). Those are not fatal errors but a collection of recoverable ones, and they
belong in an optional `errors` (or extended `warnings`) list with the `pipe` choosing to continue — not the single
top-level fatal exception being swallowed.

> note one way to structure this is
>
> ```python
> def run_pipe_or_exit_error(pipe, *args, error_formatter=str, out=None, force=False, **kwargs):
>      try:
>          result = pipe(*args, **kwargs)
>      except NEFPipelinesException as e:
>          exit_error(error_formatter(e))
>      output_pipe_return_or_exit_error(result, out=out, force=force)
>
>  # caller supplies context via partial:
>  run_pipe_or_exit_error(
>      pipe, entry, rename_pairs,
>      error_formatter=partial(_build_rename_parse_error_message, entry=entry, input_file=input_file),
>      out=out, force=force,
>  )
>
> ```
>
> or you could just pass in an exception formatter funtion as well as `pipe`

### Open questions

Five sections of this document remain stubs and are deferred: subcommand creation/discovery; the testing strategy;
clean pipeline shutdown on error; repository structure and distribution; and the library-integration deep-dive.

[^1]:  https://en.wikipedia.org/wiki/Unix_philosophy ↩
[^2]:  https://typer.tiangolo.com
