import string
import sys
from enum import auto
from pathlib import Path
from typing import List

import requests
import typer
from fyeah import f
from pynmrstar import Entry
from requests.exceptions import HTTPError
from strenum import LowercaseStrEnum
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    read_entry_from_file_or_exit_error,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import get_chain_code_iter
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    is_int,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.nmrstar import import_app
from nef_pipelines.transcoders.nmrstar.importers.sequence import pipe as sequence_pipe
from nef_pipelines.transcoders.nmrstar.importers.shifts import pipe as shift_pipe
from nef_pipelines.transcoders.nmrstar.nmrstar_lib import StereoAssignmentHandling

app = typer.Typer()

BMRB_URL_TEMPLATE = "https://bmrb.io/ftp/pub/bmrb/entry_directories/bmr{entry_number}/bmr{entry_number}_3.str"


class EntrySource(LowercaseStrEnum):
    FILE = auto()
    WEB = auto()
    AUTO = auto()


SHORTCUTS = {
    "UBIQUITIN": "bmr5387",
    "GB1": "bmr7280",
    "GB3": "bmr25910",
    "MBP": "bmr4354",
    "MSG": "bmr5471",
    "INSULIN": "bmr1000",
}

SHORTCUT_ENTRYS = {name: id.lower()[3:] for name, id in SHORTCUTS.items()}
SHORTCUT_URLS = {
    name: f(BMRB_URL_TEMPLATE) for name, entry_number in SHORTCUT_ENTRYS.items()
}
SHORTCUT_NAMES = ", ".join({name.lower(): name for name in SHORTCUTS.keys()})

NO_CHAIN_START_HELP = """\
don't include the start chain link type on a chain for the first residue [linkage will be
middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
option multiple times to set chain starts for multiple chains
"""

NO_CHAIN_END_HELP = """\
don't include the end chain link type on a chain for the last residue [linkage will be
middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
option multiple times to set chain ends for multiple chains
"""

STEREO_HELP = """\
    how to handle stereo assignments the choices are:
    - ambiguous: assume all stereo assignments are ambiguous
    - as-assigned: use the stereo assignments as they are in the file
    - auto: use as assigned if some geminal stereo assignments are present, otherwise assume all are ambiguous
"""


FILE_PATH_HELP = f"""\
the file to read, if it is is one of the shortcuts {SHORTCUT_NAMES}, of the form bmr<NUMBER> or is just a number or
appears to be a url the program will attempt to fetch the entry from the bmrb or the web first before looking
for a file on disc unless this behaviour overridden by the --source option
"""


@import_app.command()
def project(
    ctx: typer.Context,
    chain_codes: List[str] = typer.Option(
        [],
        "--chains",
        help="""chain codes to use for the imported chains, can be a comma separated list or can be called
                multiple times if no chain codes are provided they will be named A B C...""",
        metavar="<CHAIN-CODES>",
    ),
    no_chain_starts: List[str] = typer.Option(
        [], "--no-chain-start", help=NO_CHAIN_START_HELP
    ),
    no_chain_ends: List[str] = typer.Option(
        [], "--no-chain-end", help=NO_CHAIN_END_HELP
    ),
    source: EntrySource = typer.Option(
        EntrySource.AUTO, help="the source of the entry"
    ),
    use_author: bool = typer.Option(False, help="use author field for sequence codes"),
    stereo_mode: StereoAssignmentHandling = typer.Option("auto", help=STEREO_HELP),
    entry_name: str = typer.Option(
        None, help="a name for the entry (defaults to the bmr{entry_number})"
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="file to read NEF data from [- is stdin; defaults is stdin]",
    ),
    url_template: str = typer.Option(
        BMRB_URL_TEMPLATE,
        help=f"template for the bmrb url [default {BMRB_URL_TEMPLATE}]",
    ),
    list_shortcuts: bool = typer.Option(
        False, "--list-shortcuts", help="list the available shortcuts and exit"
    ),
    file_paths: List[str] = typer.Argument(None, help=FILE_PATH_HELP),
):
    """- convert as much as possible from an NMR-STAR file to NEF [shifts & sequences] [alpha]"""

    if list_shortcuts:
        _list_shortcuts_and_exit()

    file_paths = parse_comma_separated_options(file_paths)
    file_paths = [
        SHORTCUTS[file_path.upper()] if file_path.upper() in SHORTCUTS else file_path
        for file_path in file_paths
    ]

    if not file_paths:
        typer.echo(ctx.get_help())
        exit_error("missing file path argument")

    for file_path in file_paths:
        chain_codes = parse_comma_separated_options(chain_codes)
        chain_codes = get_chain_code_iter(chain_codes)

        no_chain_starts = parse_comma_separated_options(no_chain_starts)
        if not no_chain_starts:
            no_chain_starts = [False]

        no_chain_ends = parse_comma_separated_options(no_chain_ends)
        if no_chain_ends:
            no_chain_ends = [False]

        is_bmrb = False
        if source in (EntrySource.AUTO, EntrySource.WEB):
            url, is_bmrb = _get_path_as_url_or_none(file_path, url_template)

            exit_on_error = True if source == EntrySource.WEB else False
            possible_entry = _get_bmrb_entry_from_web_or_none(url, exit_on_error)

            nmrstar_entry = _parse_text_to_star_or_none(possible_entry)

        if (
            source == EntrySource.AUTO and not nmrstar_entry
        ) or source == EntrySource.FILE:
            nmrstar_entry = read_entry_from_file_or_exit_error(file_path)

        if not nmrstar_entry:
            msg = f"could not read entry from {file_path}"
            exit_error(msg)

        entry_name = nmrstar_entry.entry_id if not entry_name else entry_name
        entry_name = f"bmr{entry_name}" if is_bmrb else entry_name
        nef_entry = read_or_create_entry_exit_error_on_bad_file(
            input, entry_name=entry_name
        )

        entry = pipe(
            nef_entry,
            nmrstar_entry,
            chain_codes,
            no_chain_starts,
            no_chain_ends,
            use_author,
            stereo_mode,
            file_path,
        )

        print(entry)


def pipe(
    nef_entry,
    nmrstar_entry,
    chain_codes,
    no_chain_starts,
    no_chain_ends,
    use_author,
    stereo_mode,
    file_path,
):

    # def pipe(
    #         nef_entry: Entry,
    #         chain_codes: List[str],
    #         starts: List[str],
    #         no_chain_starts: List[str],
    #         no_chain_ends: List[str],
    #         entry_name: str,
    #         nmrstar_entry: Entry,
    #         file_path: Path,
    #         use_author: bool,
    # ):

    entry_id = nef_entry.entry_id
    nef_entry = sequence_pipe(
        nef_entry,
        chain_codes,
        [],
        no_chain_starts,
        no_chain_ends,
        entry_id,
        nmrstar_entry,
        file_path,
        use_author,
    )

    # def pipe(
    #         nef_entry: Entry,
    #         chain_codes: List[str],
    #         frame_name: str,
    #         nmrstar_entry: Entry,
    #         file_name: Path,
    #         use_author: bool,
    #         stereo_mode: StereoAssignmentHandling,
    # ):

    nef_entry = shift_pipe(
        nef_entry, [], entry_id, nmrstar_entry, file_path, use_author, stereo_mode
    )

    return nef_entry


def _list_shortcuts_and_exit():
    print("The available shortcuts are:\n", file=sys.stderr)
    shortcuts = [
        [shortcut.lower(), entry, SHORTCUT_URLS[shortcut]]
        for shortcut, entry in SHORTCUTS.items()
    ]
    HEADERS = ["name", "entry id.", "url"]
    print(tabulate(shortcuts, headers=HEADERS), file=sys.stderr)
    print("\nexiting...", file=sys.stderr)
    sys.exit(0)


def _parse_text_to_star_or_none(possible_entry):
    nmrstar_entry = None
    if possible_entry and possible_entry.startswith(b"data_"):
        try:
            nmrstar_entry = Entry.from_string(possible_entry.decode("utf-8"))
        except Exception:
            pass
    return nmrstar_entry


def _get_bmrb_entry_from_web_or_none(url, exit_on_error=True):
    possible_entry = None
    error = False
    exception = None
    if url:
        try:
            response = requests.get(url)
            response.raise_for_status()
            possible_entry = response.content
        except HTTPError as http_err:
            msg = f"while trying to download the url {url} there was an http error {http_err}"
            exception = http_err
        except Exception as err:
            msg = f"while trying to download the url {url} there was an error {err}"
            exception = err

    if error:
        if exit_on_error:
            exit_error(msg, exception)
        else:
            print(f"WARNING: {msg}, trying to read as a local file", file=sys.stderr)

    return possible_entry


def _get_path_as_url_or_none(file_path, url_template):
    url = None
    is_bmrb = False
    if file_path.startswith("https://"):
        url = file_path
    elif file_path.startswith("bmr"):
        entry_number = file_path[3:]
        entry_check = entry_number.lstrip(string.digits)
        if len(entry_check) == 0:
            url = f(url_template)
            is_bmrb = True
    elif is_int(file_path):
        entry_number = file_path
        url = f(url_template)
        is_bmrb = True

    return url, is_bmrb
