import os
import re
import tempfile
from enum import Enum, auto
from pathlib import Path
from urllib.parse import urlsplit

import requests
import typer
from bs4 import BeautifulSoup
from bs4.element import Comment
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    SelectionType,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import sequences_from_frames, translate_1_to_3
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import AtomLabel, Residue, ShiftData, ShiftList
from nef_pipelines.lib.util import STDIN, exit_error, is_int
from nef_pipelines.tools.loops.trim import ChainBound
from nef_pipelines.tools.loops.trim import pipe as trim
from nef_pipelines.transcoders.shiftx2 import import_app


def tag_visible(element):
    if element.parent.name in [
        "style",
        "script",
        "head",
        "title",
        "meta",
        "[document]",
    ]:
        return False
    if isinstance(element, Comment):
        return False
    return True


deuterate = {False: 1, True: 0}
phospho = {False: 1, True: 0}
shifttype = {"all": "back-bone", 1: 1, "side-chain": 2}
output = {"tabular": 0, 1: "csv", 2: "nmr-star", 3: "nef"}
use_shifty = {False: 1, True: 0}
multiple_chains = {False: 1, True: 0}

ROOT_URL = "http://www.shiftx2.ca/cgi-bin"
CGI_URL = f"{ROOT_URL}/shiftx2.cgi"

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def shifts(
    code_or_file_name: str = typer.Argument(
        None,
        help="file name to read shift data from or alphafold / pdb code to fetch data for",
    ),
    source_chain: str = typer.Option(
        None, help="chain in the source coordinate file to predict shift data for"
    ),
    alphafold: bool = typer.Option(
        False, "--alphafold", help="use alphafold to predict structure"
    ),
    chain: str = typer.Option(
        None, "-c", "--chain", help="chain to label output shift data with"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="verbose output"),
    in_file: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [- is stdin]",
    ),
):
    """- read a shiftx2 chemical shift prediction [alpha]"""
    entry = read_or_create_entry_exit_error_on_bad_file(in_file, "shiftx2")
    entry = pipe(entry, code_or_file_name, source_chain, chain, alphafold, verbose)
    print(entry)


def pipe(
    entry: Entry,
    code_or_filename: str,
    source_chain: str,
    chain: str,
    alphafold: bool,
    verbose: bool,
) -> Entry:

    file_path = Path(code_or_filename)
    if file_path.exists():
        shifts = _read_shifts_from_file(file_path, chain)
    else:

        if alphafold:
            (
                code_or_filename,
                pdb_uniprot_start,
                pdb_uniprot_length,
                pdb_start_residue,
            ) = _pdb_code_to_uniprot_id(code_or_filename, verbose)
            use_file = True
        else:
            use_file = False

        if not chain and source_chain:
            chain = source_chain
        shifts = _get_shifts_from_server(
            code_or_filename, source_chain, chain, use_file=use_file
        )

    shift_list = ShiftList(shifts)
    frame = shifts_to_nef_frame(shift_list, "shiftx2")

    entry.add_saveframe(frame)

    if not chain and source_chain:
        chain = source_chain

    if not chain and not source_chain:
        chain = "A"

    if alphafold:
        sequence = sequences_from_frames(frame, chain)
        shiftx2_uniprot_start = min(
            [
                residue.sequence_code
                for residue in sequence
                if is_int(residue.sequence_code)
            ]
        )
        shiftx2_uniprot_end = max(
            [
                residue.sequence_code
                for residue in sequence
                if is_int(residue.sequence_code)
            ]
        )
        # shiftx2_uniprot_length = shiftx2_uniprot_end - shiftx2_uniprot_start

        pdb_uniprot_end = pdb_uniprot_start + pdb_uniprot_length

        start = pdb_uniprot_start
        end = pdb_uniprot_end

        run_trim = False
        if pdb_uniprot_start > shiftx2_uniprot_start:
            start = pdb_uniprot_start
            run_trim = True
        if pdb_uniprot_start < shiftx2_uniprot_end:
            end = pdb_uniprot_end
            run_trim = True

        if run_trim:
            chain_bounds = [ChainBound(chain, start, end)]

            chain_bounds = {chain: chain_bounds}

            entry = trim(entry, "shiftx2", SelectionType.NAME, chain_bounds)

            # offset = pdb_start - uniprot_start + 1
            #
            # entry = renumber(entry, "shiftx2", SelectionType.NAME, {chain: offset})

    return entry


class ShiftFormat(Enum):
    TABULAR = auto()
    CSV = auto()
    NMRSTAR = auto()
    NEF = auto()


def _is_nef_header(line):
    line_fields = line.split() if line else []
    return len(line_fields) == 6 and line_fields[-1] == "."


def _is_star_header(line):
    line_fields = line.split() if line else []
    return len(line_fields) == 7 and line_fields[-1] == "1"


def _read_shifts_from_file(file_path, cli_chain_code):

    with open(file_path, "r") as file:
        lines = file.read()
        shifts = _parse_text_to_shifts(lines, cli_chain_code, file_path)

    return shifts


def _parse_text_to_shifts(text, cli_chain_code, source):

    lines = []
    for i, line in enumerate(text.split("\n")):
        if i == 0:
            if "BACKBONE ATOMS" in line:
                file_format = ShiftFormat.TABULAR
            elif "," in line:
                file_format = ShiftFormat.CSV
            elif _is_nef_header(line):
                file_format = ShiftFormat.NEF
            elif _is_star_header(line):
                file_format = ShiftFormat.NMRSTAR
            else:
                msg = f"""
                        When reading shiftx2 shifts could not determine format of source {source}
                        the first line in the file was
                        {line}
                        """
                exit_error(msg)
        lines.append(line)

    columns = {
        ShiftFormat.CSV: {
            "chain_code": None,
            "sequence_code": 0,
            "residue_name": 1,
            "atom_name": 2,
            "shift": 3,
        },
        ShiftFormat.NMRSTAR: {
            "chain_code": None,
            "sequence_code": 1,
            "residue_name": 2,
            "atom_name": 3,
            "shift": 4,
        },
        ShiftFormat.NEF: {
            "chain_code": 0,
            "sequence_code": 1,
            "residue_name": 2,
            "atom_name": 3,
            "shift": 4,
        },
        ShiftFormat.TABULAR: {
            "chain_code": None,
            "sequence_code": 0,
            "residue_name": 1,
            "atom_name": 2,
            "shift": 3,
        },
    }
    if file_format == ShiftFormat.CSV:

        for i, line in enumerate(lines):
            if i == 0:
                continue
            lines[i] = line.replace(",", " ")
    if file_format == ShiftFormat.TABULAR:
        lines = _tabular_lines_to_csv_layout(lines)

    result = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if "NUM," in line:
            # TODO we should parse it!
            continue

        fields = line.split()

        column_indices = columns[file_format]

        chain_code_index = column_indices["chain_code"]
        sequence_index = column_indices["sequence_code"]
        residue_name_index = column_indices["residue_name"]
        atom_name_index = column_indices["atom_name"]
        shift_index = column_indices["shift"]

        chain_code = fields[chain_code_index] if chain_code_index else cli_chain_code
        chain_code = chain_code if chain_code else "A"

        sequence_code = fields[sequence_index]
        sequence_code = int(sequence_code) if is_int(sequence_code) else sequence_code

        residue_name = fields[residue_name_index] if residue_name_index else UNUSED
        residue_name = (
            translate_1_to_3(residue_name)[0]
            if residue_name != UNUSED and len(residue_name) == 1
            else residue_name
        )
        atom_name = fields[atom_name_index]

        shift = float(fields[shift_index])

        residue = Residue(
            chain_code=chain_code,
            sequence_code=sequence_code,
            residue_name=residue_name,
        )
        atom = AtomLabel(residue, atom_name)
        shift = ShiftData(atom=atom, value=shift)
        result.append(shift)

    return result


def _tabular_lines_to_csv_layout(lines):

    headers = None
    result = []
    next_line_read_headers = False

    for i, line in enumerate(lines):

        line = line.strip()

        if not line:
            continue

        if line in ["BACKBONE ATOMS", "SIDECHAIN CARBON", "SIDECHAIN PROTON"]:
            next_line_read_headers = True
            continue

        if next_line_read_headers:
            headers = {header: index for index, header in enumerate(line.split())}
            atom_names = [header for header in headers if header not in ["Num", "RES"]]
            next_line_read_headers = False
            continue

        fields = line.split()
        for atom_name in atom_names:
            sequence_code = fields[headers["Num"]]
            residue_name_1_let = fields[headers["RES"]]
            residue_name_3_let = translate_1_to_3(residue_name_1_let)[0]
            shift = fields[headers[atom_name]]
            if shift == "****":
                continue

            new_line = f"{sequence_code} {residue_name_3_let} {atom_name} {shift}"
            result.append(new_line)

    return result


def _get_shifts_from_server(
    pdb_file_or_code, chain_code, cli_chain_code, use_file=False
):

    data = {
        "deuterate": 1,
        "ph": 7,
        "temper": 298,
        "phospho": 1,
        "shifttype": 0,
        "format": 3,
        "shifty": 0,
        "pdbid": "",
        "nonoverlap": 1,
    }
    files = {}
    fh = None
    if use_file:
        fh = open(pdb_file_or_code, "rb")
        files = {"file": fh}
    else:
        pdb_file_or_code = (
            f"{pdb_file_or_code}{chain_code}" if chain_code else pdb_file_or_code
        )
        data["pdbid"] = pdb_file_or_code

    if use_file:
        r = requests.request("POST", CGI_URL, data=data, files=files)

    else:
        r = requests.request("POST", CGI_URL, data=data)

    if fh:
        fh.close()

    _exit_if_bad_html_request(pdb_file_or_code, r)

    _exit_if_error_calculating_shifts(pdb_file_or_code, r)

    soup = BeautifulSoup(r.text, features="html.parser")
    link = soup.find_all("a", href=True, string="download predictions")[0]["href"]
    data_url = f"{ROOT_URL}/{link}"
    data_r = requests.get(data_url)
    text = data_r.text

    shifts = _parse_text_to_shifts(text, cli_chain_code, CGI_URL)

    return shifts


def _exit_if_bad_html_request(pdb_code, r):
    if r.status_code != 200:
        msg = f"""
        failed to download shifts from {CGI_URL} for pdb code {pdb_code}
        is you network connection working?
        """
        exit_error(msg)


def _exit_if_error_calculating_shifts(pdb_code, r):

    if "Error in Calculating Chemical Shifts" in r.text:
        soup = BeautifulSoup(r.text, features="html.parser")
        texts = soup.findAll(string=True)
        visible_texts = filter(tag_visible, texts)
        text = " ".join(t.strip() for t in visible_texts)
        text = _spaces_to_single(text)
        text = _dedent_all(text)
        text = _select_text_between(text, "SHIFTX2 PREDICTIONS", "Please try again")
        msg = f"""
        failed to calculate shifts from {CGI_URL} for pdb code {pdb_code}
        the msg was:

        {text}
        """
        exit_error(msg)


def _exit_if_pdb_code_bad(pdb_code):
    if len(pdb_code) != 4:
        msg = f"""
        the code {pdb_code} is not a valid pdb code, they should be 4 letters long e.g. 1UBQ [ubiquitin]
        """
        exit_error(msg)


def _text_from_html(body):

    soup = BeautifulSoup(body, "html.parser")
    texts = soup.findAll(text=True)
    visible_texts = filter(tag_visible, texts)
    return " ".join(t.strip() for t in visible_texts)


def _select_text_between(text, start, end):
    start_index = text.find(start)
    start_index = start_index + len(start) if start != -1 else 0

    end_index = text.find(end)

    return text[start_index:end_index]


def _dedent_all(text):
    lines = []
    for line in text.split("\n"):
        lines.append(line.lstrip())

    return "\n".join(lines)


def _spaces_to_single(text):
    whitespace = re.compile(r"\s+")
    return " ".join(whitespace.split(text))


def _get_filename_from_url(url=None):
    if url is None:
        return None
    urlpath = urlsplit(url).path
    return os.path.basename(urlpath)


def _pdb_code_to_uniprot_id(code_or_filename, verbose):
    msg = [f"# alphafold: {code_or_filename}->"]
    url = f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{code_or_filename}"
    response = requests.get(url)

    ok = True
    if response.status_code != 200:
        ok = False

    if ok:
        data = response.json()
        if not data:
            ok = False

    if not ok:
        msg = f"""
        failed to get uniprot id from pdb code {code_or_filename}
        is the network ok or could the pdb code be incorrect?
        """
        exit_error(msg)

    # more validation needed here
    code_or_filename = code_or_filename.lower()
    uniprot_id = next(iter(data[code_or_filename]["UniProt"].keys()))
    msg.append(f"{uniprot_id}->")
    chain_info = data[code_or_filename]["UniProt"][uniprot_id]
    first_mapping = next(iter(chain_info["mappings"]))

    pdb_uniprot_start = int(first_mapping["unp_start"])
    pdb_uniprot_end = int(first_mapping["unp_end"])
    pdb_start_residue = int(
        first_mapping["start"]["residue_number"]
    )  # as opposed to 'author_residue_number'
    pdb_uniprot_length = pdb_uniprot_end - pdb_uniprot_start

    key = "AIzaSyCeurAJz7ZGjPQUtEaerUkBZ3TaBkXrY94"
    alphafold_url = f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}?key={key}"

    response = requests.get(alphafold_url)

    ok = True
    if response.status_code != 200:
        ok = False

    if ok:
        data = response.json()
        if not data:
            ok = False

    if not ok:
        msg = f"""
           failed to get uniprot structure using pdb code {code_or_filename}
           is the network ok or could the pdb code be incorrect or for a structure not in the embl database?
           """
        exit_error(msg)

    entry = data[0]
    alphafold_pdb_url = entry["pdbUrl"]
    alphafold_entry_id = entry["entryId"]

    if verbose:
        msg.append(alphafold_entry_id)

    response = requests.get(alphafold_pdb_url)

    ok = True
    if response.status_code != 200:
        ok = False

    if ok:
        data = response.text
        if not data:
            ok = False

    if not ok:
        msg = f"""
               failed to get alphafold structure using pdb code {code_or_filename} mapped to uniprot id {uniprot_id}
               is the network ok or could the pdb code be incorrect or for a structure not in the embl database?
               """
        exit_error(msg)

    pdb_filename = _get_filename_from_url(alphafold_pdb_url)

    tmpdirname = tempfile.mkdtemp()
    file_path = Path(tmpdirname) / pdb_filename
    with open(file_path, "w") as fp:
        fp.write(data)

    if verbose:
        print("".join(msg), alphafold_url)

    return file_path, pdb_uniprot_start, pdb_uniprot_length, pdb_start_residue
