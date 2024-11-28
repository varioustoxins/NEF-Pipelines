import string
import sys

import requests
from fyeah import f
from pynmrstar import Entry
from requests.exceptions import HTTPError
from tabulate import tabulate

from nef_pipelines.lib.util import exit_error, is_int
from nef_pipelines.transcoders.nmrstar.importers.project_shortcuts import (
    SHORTCUT_URLS,
    SHORTCUTS,
)
from nef_pipelines.transcoders.nmrstar.importers.sequence import pipe as sequence_pipe
from nef_pipelines.transcoders.nmrstar.importers.shifts import pipe as shift_pipe


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
