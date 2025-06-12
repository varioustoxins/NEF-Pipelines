import string
import sys

import requests
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

    nef_entry = shift_pipe(
        nef_entry, [], None, nmrstar_entry, file_path, use_author, stereo_mode
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


def _get_bmrb_entry_from_web_or_none(
    urls, exit_on_error=True, verbose=False, timeout=10
):
    possible_entry = None

    have_data = False
    if urls:

        for i, url in enumerate(urls, start=1):
            error = False
            if verbose:
                print(f"{i}. trying to from download {url}", file=sys.stderr)
            try:
                try:
                    response = requests.get(url, timeout=timeout)
                    response.raise_for_status()
                    possible_entry = response.content
                except requests.exceptions.SSLError:
                    print(
                        f"NOTE: using weaker SSL key as long keys not supported by some mirrors [{url}]",
                        file=sys.stderr,
                    )
                    requests.packages.urllib3.disable_warnings()
                    requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += (
                        "HIGH:!DH:!aNULL"
                    )
                    try:
                        requests.packages.urllib3.contrib.pyopenssl.DEFAULT_SSL_CIPHER_LIST += (
                            "HIGH:!DH:!aNULL"
                        )
                    except AttributeError:
                        # no pyopenssl support used / needed / available
                        pass
                    response = requests.get(url, verify=False, timeout=timeout)
                    response.raise_for_status()
                    possible_entry = response.content

            except HTTPError as http_err:
                if verbose:
                    msg = f"WARNING: while trying to download the url {url} there was an http error {http_err}"
                    print(msg, file=sys.stderr)
                    error = True

            except Exception as err:
                if verbose:
                    msg = f"WARNING: while trying to download the url {url} there was an error {err}"
                    print(msg, file=sys.stderr)
                    error = True

            if not error:
                have_data = True
                break

    if not have_data:
        if exit_on_error:
            urls = " /n".join(urls)
            msg = f"""\
            could not download the entry from

            {urls}
            """
            exit_error(msg)

    return possible_entry


def _get_path_as_url_or_none(file_path, url_templates):
    urls = []
    is_bmrb = False
    if file_path.startswith("https://"):
        urls = [
            file_path,
        ]
    elif file_path.startswith("bmr"):
        entry_number = file_path[3:]
        entry_check = entry_number.lstrip(string.digits)
        if len(entry_check) == 0:
            urls = [
                url_template.format(entry_number=entry_number)
                for url_template in url_templates
            ]
            is_bmrb = True
    elif is_int(file_path):
        entry_number = file_path
        urls = [
            url_template.format(entry_number=entry_number)
            for url_template in url_templates
        ]
        is_bmrb = True

    return urls, is_bmrb
