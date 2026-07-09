# What is the Structure of NEF-Pipelines and What Are the Common Design Features

NEF-Pipelines is a collection of python scripts that are designed to be chained together in a unix pipeline to provide manipulation of NMR Exchange Format (NEF) based data. The scripts are designed to collaborate with each other because they share a common base command line interface (CLI) and a common data format in the form of NEF files or a stream of NEF text. This simple design which combines with the UNIX Tools Philosophy [^1] provides an approach to data manipulation that is both powerful and flexible and allows the inclusion of external programs and builtin unix commands in the pipeline

The base component of a nef pipeline is a _pipe_ whichis a single program that takes a NMR Exchange
Format based text data stream which it maniuplates, modifies and usually finally outputs back to the
pipeline or terminal. In NEF-Pipelines hese pipeline elements are single python scripts which share
a common command structure provided by the _typer_ libraries implimentation of sub commands.

## The Typer library and the NEF-Pipelines command line interface
The Typer Library [^2] is a python library that provides a simple way to build command line interfaces
for python programs. It is based on the _click_ library and provides a simple way to build command
using type annotations.

As each subcommand is based on _typer_ their entry points are defined by a single function
which is decorated with type annotations and typer based paramaters defining arguments and options
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
work. Geneally this command is called `pipe` as it is part of a pipeline, but it can also be command for
a standalone `command` such as nef_pipelines.about.command which provides information about the
NEF-Pipelines system. This is shown  below in outline for the `nef fasta export sequence` subcommand.

```python
from typing import List
import typer
from nef_pipelines.transcoders.fasta import export_app
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
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

    entry = pipe(entry, chain_codes, output_file)

    if entry:
        print(entry)

def pipe(entry: Entry, chain_codes: List[str], output_file: Path) -> Entry:

    ... # the implementation of the command

    return entry
```

Thus while `sequence` is not suitable for use as a python library function the `pipe`
function inside `nef_pipelines.transcoders.fasta.importers.sequence `and could be
imported into a python program and used as follows

```python
from pynmrstar import Entry
from nef_pipelines.transcoders.fasta.importers.sequence import pipe as import_sequence
from tabulate import tabulate

with open('input.nef') as nef_file:
    nef_data = nef_file.read()

entry = Entry.from_string(nef_data)
entry = import_sequence(entry, ['A'], 'output.fasta')

molecular_system = entry.get_loops_by_category('nef_sequence')[0]
table = [row for row in molecular_system]
print(tabulate(table, headers=molecular_system.tags))

```

Thus, it is possible to use the nef pipeline commands as a python library and
build  complex programs using  nef-pipeline commands as building blocks inside any
python program. In this case the program reads a NEF file, imports a fasta sequence
into a `pynmrstar` `Entry` as chain `A` and then prints the sequence as a table using tabulate.
It should be noted that provision of the python command interface also opens up the possibility of
building a GUI interface to the NEF-Pipelines commands using the same methodology.

> [!NOTE]
> Nota bene: `pipe` is used for all commands that process a NEF stream, commands
> that can just be called are called `command`. Also is it should be noted that this
> python script is a bit redundant as the `tabulate` sub command already provides
> the ability to tabulate NEF loops using the NEF-Pipelines library.


## Separation of CLI and Library Concerns

A core architectural principle of NEF-Pipelines is the **separation between CLI functions and library functions**.
This separation ensures that library functions (like `pipe`) remain reusable in programmatic contexts, while CLI
functions handle all user interaction and I/O concerns.

### Library Functions (pipe, helper functions)

**Library functions are silent** — they transform data and either return results or raise exceptions. They never:

* Print to stdout/stderr (except for legitimate output like NEF streams)
* Print warnings or informational messages
* Call `exit_error()` or other termination functions
* Have side effects beyond their documented purpose

**Library functions should:**

* Raise custom exceptions (inheriting from `NEFPipelinesException`) when errors occur
* Return transformed data structures
* Be pure, testable functions that can be composed programmatically
* Accept structured parameters (dataclasses, typed arguments) not raw CLI strings

### CLI Functions (typer-decorated command functions)

**CLI functions handle all user interaction**. They are responsible for:

* Parsing command-line arguments into structured parameters
* Catching exceptions from library functions and formatting user-friendly error messages via `exit_error()`
* Printing warnings (via `warn()`) about edge cases or potentially problematic input
* Reading from stdin/files and writing to stdout/files
* Printing the final NEF stream or other output

### CLI and Pipe functions are high level

The `typer` cli and  `pipe` fucntions are high level functions. They should therefore contain a series of  hogh level
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
        entry = pipe(entry, rename_pairs)
    except ColumnNotFoundException as e:
        exit_error(str(e))

    # CLI: Print output
    print(entry)


def pipe(entry: Entry, rename_pairs: List[Tuple[FrameLoopAndTagSelectors, str]]) -> Entry:
    """Library function: silent transformation, raises exceptions on error."""
    # Pure transformation - no printing, no exit_error, no warnings
    _raise_if_selectors_dont_have_single_tag(rename_pairs)
    renames_by_loop = _group_renames_by_loop(rename_pairs)
    _apply_renames_to_entry(entry, renames_by_loop)
    return entry
```

This separation ensures that `pipe` can be imported and used in any Python program without unexpected
side effects, while the CLI function provides a user-friendly command-line interface with appropriate
error handling and feedback.

### The _or_raise / _or_exit_error Pattern

A common pattern for separating library logic from CLI error handling is the **`raise` /  `exit_error` function pair**:

- **`_or_raise` functions**: Library functions that raise dataclass exceptions with structured data
- **`_or_exit_error` functions**: CLI wrappers that catch exceptions, format user-friendly messages, and call `exit_error()`

**Exception Structure:**

Exceptions inherit from `NEFPipelinesException` , carrying only the data needed to describe the error. If the data is
complex tjhey can also be `@dataclass` classes:

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


## Types of NEF-Pipelines `Pipes` and there Common Structural Features

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

### The Structure of an Input Pipe

The basic structure of an input pipe is as follows:

```python
from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.util import STDIN
from nef_pipelines.transcoders.fasta import import_app

from pynmrstar import Entry

import typer

from pathlib import Path
from typing import List

@import_app
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
    entry = pipe(entry, file_paths, ...)
    print(entry)

def pipe(entry: Entry, file_paths: List[Path], *other_args_here) -> Entry:

    ... # the implementation of the command

    return entry
```
As can be seen an input pipe is defined by a function which is decorated with the `@import_app` from a
NEF-Pipelines `pipe`. The function takes a number of parameters which are defined by the `typer.Option` and
`typer.Argument` functions. The function then calls the `pipe` function which does the actual work of the
command. The input commands CLI always takes an input file which is defined by the command line options
`-i` `-i` or `--in` which is a NEF stream and the name of the entry which is defined by the `entry_name`
parameter. The correct NEF entry is then created by the python function `read_or_create_entry_exit_error_on_bad_file` that either creates a new entry [named from the parameter]
if in_file is `STDIN` [-] or reads an existing entry from input. The function `read_or_create_entry_exit_error_on_bad_file`
calls `exit_error` if the input file is not of the correct format which takes any actions required
to shut down the pipeline. The `pipe` function then does the actual work of the command and returns the
NEF entry which then gets printed to stdout by the command line function. It should be noted that the
main parameters for the function, in this case a list of Paths to fasta files, are passed to the CLI
function as an Argument.


### The Structure of a Filter Pipe

The basic structure of a filter pipe is as follows, and is similar to the input pipe with some
minor differences. Here is an example of a _pipe_ which implements the frames filter pipe:

```python
from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.util import STDIN
from nef_pipelines.tools.frames import frames_app

from pynmrstar import Entry

import typer

from pathlib import Path
from typing import List

@frames_app
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

    entry = read_or_create_entry_exit_error_on_bad_file(input)
    entry = pipe(entry, frame_selectors, ...)
    print(entry)

def pipe(entry: Entry, frame_selectors: List[str], *other_args_here) -> Entry:

    ... # the implementation of the command

    return entry
```

As can be seen the input parameter to the CLI is still present but because the command is a filter it
won't be creating a new NEF stream and so doesn't need a name for the NEF stream [Entity]. Also, when
reading the NEF stream it uses the function `read_entry_from_file_or_stdin_or_exit_error` which will
exit with an error if the stream can't be read as it needs a set of frames to filter [this may not be
true for filters].

### The Structure of as Export Pipe

The basic structure of a exort pipe is shown below, and is similar to the previous examples, again with
some differences. The example  _pipe_ implements the fasta export sequences CLI command:

```python
from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.util import STDIN, STDOUT, exit_error
from nef_pipelines.transcoders.fasta import export_app

from pynmrstar import Entry

from fyeah import f

import typer

from pathlib import Path
import sys

FASTA_FILE_TEMPLATE =  '{entry_name}.fasta'

@export_app
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

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    entry_name =  entry.entry_id
    output_file = f(FASTA_FILE_TEMPLATE) if not output_file else output_file

    ... # Any work to convert command line parameters to function parameters goes here

    entry = pipe(entry, output_file, ...)
    if entry:
        print(entry)

def pipe(entry: Entry, output_file: str, *other_args_here) -> Entry:

    ... # the implementation of the command

    fasta_text =  ...

    try:
        out_handle = sys.stdout if output_file == STDOUT else open(output_file, 'w')
    except Exception as e:
        msg = f"Error opening output file {output_file} for writing fasa file because {e}"
        exit_error(msg, e)

    print(fasta_text, file=out_handle)

    if output_file != STDOUT:
        out_handle.close()

    return None if output_file == STDOUT else entry
```

As can be seen the input parameter to the CLI is still present but because the command is an output it
it again won't be creating a new NEF stream and so doesn't need a name for the NEF stream [Entity]. Also,
when reading the NEF stream it uses the function `read_entry_from_file_or_stdin_or_exit_error` which will
exit with an error if the stream can't be read as it needs a molecular system frames to output sequences from.
The output file is defined by the `output_file` parameter which is defined as None [disk using the fasta
file name template] by default. The name of the output file is defined by the FASTA_FILE_TEMPLATE if the
output is to the default and the file is written to the current working directory. Users can also provide
their own filename and include the entry_name template parameter {entry_name} in the filename.

> [!WARNING]
> The way filename templates are currently supported makes NEF-Pipelines insecure to use as web service as
> the internal data can be leaked from the program and arbitary code run as part of file name templates.
> This will be adressed in a future version of NEF-Pipelines if there is a need or a request is recieved
> to use it as part of a web service.

> [!NOTE]
> Nota bene: note how the output of the fasta files text is structured with the output text being
> sent to `sys.stdout` if the output file is `STDOUT` and to a file otherwise. Also, especially note how the
> pipe function arranges for the output file to be closed if it is not `STDOUT` as not closing the output
> file creates warnings during testing. It should also be noted that if the output file is `STDOUT` the
> pipe returns `None` and the CLI doesn't print anything as STDOUT is no longer a NEF stream.

### Handling Display Output: `print_output_or_exit_error`

Display commands (e.g. `nef frames display`) produce human-readable text that is not a NEF
stream. This creates a routing problem: the text needs to go somewhere useful depending on
whether stdout is a terminal or a pipe, and the caller may also want the underlying NEF entry
to continue flowing down the pipeline.

The utility function `print_output_or_exit_error` in `nef_pipelines.lib.cli_lib` encapsulates
this routing logic so it never needs to be written inline:

```python
from nef_pipelines.lib.cli_lib import print_output_or_exit_error

print_output_or_exit_error(entry, out, output_dict, force)
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

### How the NEF-Pipelines is Tested and How the Tests are Organised

### How NEF-Pipelines Cleany Shutsdown the Pipeline When an Error Occurs

### The Structure of the NEF-Pipelines Repositiory and Distribution

### The NEF-Pipelines Library and How it is Used in NEF-Pipelines

[^1]:  https://en.wikipedia.org/wiki/Unix_philosophy ↩
[^2]:  https://typer.tiangolo.com
