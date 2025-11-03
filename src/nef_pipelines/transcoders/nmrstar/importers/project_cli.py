import string
from enum import auto
from pathlib import Path
from textwrap import dedent
from typing import List

import typer
from lazy_import import lazy_module
from pynmrstar.exceptions import ParsingError
from strenum import LowercaseStrEnum

from nef_pipelines.lib.nef_lib import (
    read_entry_from_file_or_raise,
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
from nef_pipelines.transcoders.nmrstar.importers.project_shortcuts import (
    BMRB_AUTO_MIRROR,
    BMRB_ITALY_URL_TEMPLATE,
    BMRB_JAPAN_URL_TEMPLATE,
    BMRB_URL_TEMPLATE,
    SHORTCUT_NAMES,
    SHORTCUTS,
)
from nef_pipelines.transcoders.nmrstar.nmrstar_lib import StereoAssignmentHandling

project_module = lazy_module("nef_pipelines.transcoders.nmrstar.importers.project")

app = typer.Typer()


class EntrySource(LowercaseStrEnum):
    FILE = auto()
    WEB = auto()
    AUTO = auto()


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


class Mirror(LowercaseStrEnum):
    AUTO = auto()
    USA = auto()
    JAPAN = auto()
    ITALY = auto()
    EUROPE = auto()
    ASIA = auto()


MIRROR_URLS = {
    Mirror.AUTO: BMRB_AUTO_MIRROR,
    Mirror.USA: BMRB_URL_TEMPLATE,
    Mirror.JAPAN: BMRB_JAPAN_URL_TEMPLATE,
    Mirror.ITALY: BMRB_ITALY_URL_TEMPLATE,
    Mirror.EUROPE: BMRB_ITALY_URL_TEMPLATE,
    Mirror.ASIA: BMRB_JAPAN_URL_TEMPLATE,
}

AUTO_MIRRORS = (
    MIRROR_URLS[Mirror.USA],
    MIRROR_URLS[Mirror.EUROPE],
    MIRROR_URLS[Mirror.ASIA],
)

URL_HELP = f"""
template for the bmrb url [default {BMRB_URL_TEMPLATE}],
note if a mirror is chosen than overrides a custom url
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
        None,
        help=URL_HELP,
    ),
    list_shortcuts: bool = typer.Option(
        False, "--list-shortcuts", help="list the available shortcuts and exit"
    ),
    mirror: Mirror = typer.Option(None, help="select the mirror website to use"),
    verbose: bool = typer.Option(False, help="print verbose output"),
    timeout: int = typer.Option(10, help="timeout (seconds)  for http responses"),
    file_paths: List[str] = typer.Argument(None, help=FILE_PATH_HELP),
):
    """- convert as much as possible from an NMR-STAR file to NEF [shifts & sequences] [alpha]"""

    if list_shortcuts:
        project_module._list_shortcuts_and_exit()

    file_paths = parse_comma_separated_options(file_paths)
    file_paths = [
        SHORTCUTS[file_path.upper()] if file_path.upper() in SHORTCUTS else file_path
        for file_path in file_paths
    ]

    if not file_paths:
        typer.echo(ctx.get_help())
        exit_error("missing file path argument")

    if not url_template and not mirror:
        mirror = Mirror.AUTO

    if url_template and mirror:
        exit_error("cannot set both a url template and a mirror")
    elif mirror == Mirror.AUTO:
        url_templates = AUTO_MIRRORS
    elif mirror:
        if mirror not in MIRROR_URLS:
            msg = f"mirror must be one of {MIRROR_URLS.keys()}, i got {mirror}"
            exit_error(msg)
        url_templates = [
            MIRROR_URLS[mirror],
        ]
    else:
        url_templates = [
            MIRROR_URLS[Mirror.USA],
        ]

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
            urls, is_bmrb = project_module._get_path_as_url_or_none(
                file_path, url_templates
            )

            exit_on_error = True if source == EntrySource.WEB else False

            possible_entry = project_module._get_bmrb_entry_from_web_or_none(
                urls, exit_on_error, verbose=verbose, timeout=timeout
            )

            nmrstar_entry = project_module._parse_text_to_star_or_none(possible_entry)

        if (
            source == EntrySource.AUTO and not nmrstar_entry
        ) or source == EntrySource.FILE:
            try:
                nmrstar_entry = read_entry_from_file_or_raise(file_path)
            except Exception as e:
                _notify_failed_read_and_exit(file_path, e)

        if not nmrstar_entry:
            msg = f"could not read entry from {file_path}"
            exit_error(msg)

        entry_name = nmrstar_entry.entry_id if not entry_name else entry_name
        entry_name = f"bmr{entry_name}" if is_bmrb else entry_name
        nef_entry = read_or_create_entry_exit_error_on_bad_file(
            input, entry_name=entry_name
        )

        entry = project_module.pipe(
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


def _notify_failed_read_and_exit(file_path, e):
    file_path = Path(file_path)
    if file_path.exists() and file_path.is_file():
        if isinstance(e, PermissionError):
            # Check file permissions more specifically
            try:
                stat_info = file_path.stat()
                file_mode = stat_info.st_mode

                # Check if file has any read permission bits set
                if not (
                    file_mode & 0o444
                ):  # No read permission for owner, group, or other
                    msg = f"couldn't read from {file_path} because you don't have read permission. Try: chmod +r {file_path}"
                elif not (file_mode & 0o400):  # Owner doesn't have read permission
                    msg = f"couldn't read from {file_path} because the owner doesn't have read permission. Try: chmod u+r {file_path}"
                else:
                    # File has read permissions but still can't read - likely ownership or other restrictions
                    msg = f"couldn't read from {file_path} due to permission restrictions. Check file ownership and permissions."
            except OSError:
                msg = f"couldn't read from {file_path} due to permission error. Check file permissions and ownership."
        else:
            msg = f"couldn't read from {file_path} even though it exists, do you have permission to read it?"
        exit_error(msg, e)
    if file_path.exists() and not file_path.is_file():
        msg = f"couldn't read from {file_path}, it exists but isn't a file"
        exit_error(msg, e)
    if is_int(str(file_path)) or is_int(str(file_path).lstrip(string.ascii_letters)):
        msg = f"""
                the file name {file_path} looks like a bmrb code but I couldn't read it
                from the bmrb website, is it correct, is you network up, is the bmrb up?
            """
        exit_error(dedent(msg))
    if not file_path.exists():
        msg = f"the file name {file_path} doesn't look like an entry on the bmrb website and doesn't exist on disk..."
        exit_error(msg)
    if isinstance(e, ParsingError):
        msg = f"failed to parse the file {file_path} because {e}"
        exit_error(msg)

    msg = f"failed to read the file {file_path} because {e}, please contact the developers"
    exit_error(msg)
