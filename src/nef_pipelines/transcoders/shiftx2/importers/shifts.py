import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from textwrap import dedent, indent
from typing import Optional
from urllib.parse import urlsplit

import requests
import typer
from bs4 import BeautifulSoup
from bs4.element import Comment
from pynmrstar import Entry
from tabulate import tabulate

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

NETWORK_200_OK = 200

PDB_UNIPROT_MAPPING_URL_TEMPLATE = (
    "https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{code_or_filename}"
)
ALPHA_FOLD_KEY = "AIzaSyCeurAJz7ZGjPQUtEaerUkBZ3TaBkXrY94"
ALPHA_FOLD_URL_TEMPLATE = (
    "https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}?key={alphafold_key}"
)

SHIFTX2_RETRY_COUNT = 10
DEFAULT_TIMEOUT = 2


@dataclass
class NetworkResult:
    network_ok: bool


@dataclass
class PdbAndUniprotIDs:
    uniprot_id: str
    pdb_code: str
    chain_code: str


@dataclass
class PbdUniprotChainMapping:
    pdb_uniprot_start: Optional[int]
    pdb_uniprot_end: Optional[int]
    pdb_start_residue: Optional[int]

    @property
    def pdb_uniprot_length(self):
        return self.pdb_uniprot_end - self.pdb_uniprot_start


@dataclass
class PdbUniprotMapping(NetworkResult, PdbAndUniprotIDs, PbdUniprotChainMapping):
    raw_data: Optional[dict]


@dataclass
class AlphafoldResult(NetworkResult, PdbAndUniprotIDs, PbdUniprotChainMapping):
    pdb_url: Optional[str]
    alphafold_id: Optional[str]
    raw_data: Optional[dict]


@dataclass
class PDBDownloadResult(NetworkResult, PdbAndUniprotIDs, PbdUniprotChainMapping):
    file_system_ok: bool
    pdb_url: str
    alphafold_id: str
    pdb_file_path: Optional[Path]


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

    if not source_chain:
        source_chain = "A"

    if not chain:
        chain = source_chain

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

    if not chain and source_chain:
        chain = source_chain

    file_path = Path(code_or_filename)
    if file_path.exists():
        shifts = _read_shifts_from_file(file_path, chain)
    else:

        if alphafold:
            pdb_file_info = _pdb_code_to_alphafold_pdb_file(
                code_or_filename, source_chain, verbose
            )
            code_or_filename = pdb_file_info.pdb_file_path
            use_file = True
        else:
            use_file = False

        timeout = DEFAULT_TIMEOUT
        for i in range(1, SHIFTX2_RETRY_COUNT + 1):
            shifts, request = _get_shifts_from_server(
                code_or_filename, source_chain, chain, use_file=use_file
            )
            time.sleep(timeout)
            if shifts:
                break
            elif verbose:
                _note_if_bad_html_request(code_or_filename, request)
                _note_if_error_calculating_shifts(code_or_filename, request)
                _warn(f"retrying shiftx2 ...[{i}]")
            if "server" in request.text.lower() and "busy" in request.text.lower():
                old_timeout = timeout
                timeout = _increment_timeout(timeout)
                if verbose:
                    _warn(
                        f"timeout too short increase timeout from {old_timeout}s -> {timeout}"
                    )

        _exit_if_too_many_attempted_connections(
            shifts, code_or_filename, SHIFTX2_RETRY_COUNT
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

        run_trim = False
        if pdb_file_info.pdb_uniprot_start > shiftx2_uniprot_start:
            start = pdb_file_info.pdb_uniprot_start
            run_trim = True
        else:
            start = shiftx2_uniprot_start

        if pdb_file_info.pdb_uniprot_start < shiftx2_uniprot_end:
            end = pdb_file_info.pdb_uniprot_end
            run_trim = True
        else:
            end = shiftx2_uniprot_end

        if run_trim:
            chain_bounds = [ChainBound(chain, start, end)]

            chain_bounds = {chain: chain_bounds}

            entry = trim(entry, "shiftx2", SelectionType.NAME, chain_bounds)

    return entry


def _increment_timeout(timeout):
    if timeout == 0:
        timeout = 1
    else:
        timeout = timeout * 2
    return timeout


def _exit_if_too_many_attempted_connections(shifts, code_or_filename, RETRY_COUNT):
    if not shifts:
        msg = f"""\
            couldn't get a shiftx2 prediction for {code_or_filename} after {RETRY_COUNT} retries
            """
        exit_error(msg.strip())


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
        request = requests.request("POST", CGI_URL, data=data, files=files)

    else:
        request = requests.request("POST", CGI_URL, data=data)

    if fh:
        fh.close()

    soup = BeautifulSoup(request.text, features="html.parser")
    shifts = ""
    putative_links = soup.find_all("a", href=True, string="download predictions")
    if putative_links:
        link = putative_links[0]["href"]
        data_url = f"{ROOT_URL}/{link}"
        data_r = requests.get(data_url)
        text = data_r.text

        shifts = _parse_text_to_shifts(text, cli_chain_code, CGI_URL)

    return shifts, request


def _warn(msg):
    msg = dedent(msg)
    msg = f"WARNING: {msg}"
    msg = indent(msg, "   ")
    print(msg, file=sys.stderr)


def _note(msg, verbose):

    if verbose:
        msg = f"NOTE: {msg}"
        out_file = sys.stderr
        msg = dedent(msg)
        print(msg, file=out_file)


def _note_if_bad_html_request(pdb_code, request):
    if request.status_code != 200:
        msg = f"""\
        failed to download shifts from {CGI_URL} for pdb code {pdb_code}
        is you network connection working?
        """
        _warn(msg)


def _note_if_error_calculating_shifts(pdb_code, request):

    if "Error" in request.text:
        soup = BeautifulSoup(request.text, features="html.parser")
        texts = soup.findAll(string=True)
        visible_texts = filter(tag_visible, texts)
        text = " ".join(t.strip() for t in visible_texts)
        text = _spaces_to_single(text)
        text = _dedent_all(text)
        text = _select_text_between(text, "SHIFTX2 PREDICTIONS", "Please try again")
        msg = f"""\
        failed to calculate shifts from {CGI_URL} for pdb code {pdb_code}
        the msg was:

       {text}
        """
        _warn(msg)


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


def _exit_if_alphafold_network_bad(alphafold_result):
    if not alphafold_result.network_ok:
        msg = f"""
           failed to get alphafold structure url using uniprot id {alphafold_result.uniprot_id} which was
           mapped from pdb code {alphafold_result.pdb_code}. The url
           {ALPHA_FOLD_URL_TEMPLATE.format(uniprot_id=alphafold_result.uniprot_id, alphafold_key=ALPHA_FOLD_KEY)}
           could not be accessed is there a network problem?
        """

        exit_error(msg)


def _exit_if_pdb_download_bad(pdb_file_data: PDBDownloadResult):

    msg = None
    if not pdb_file_data.network_ok:
        msg = f"""
            The alphafold structure {pdb_file_data.alphafold_id} derived from {pdb_file_data.pdb_code} with chain
            {pdb_file_data.chain_code} could not be download from the url:
            {pdb_file_data.pdb_url}
            is there a network problem
            """

    if not pdb_file_data.file_system_ok:
        msg = f"""
            The pdb file for the alphafold structure {pdb_file_data.alphafold_id} derived from {pdb_file_data.pdb_code}
            with chain  {pdb_file_data.chain_code} could not be saved to the file system at the path, is your disk full?
            """

    if msg:
        exit_error(msg)


def _pdb_code_to_alphafold_pdb_file(code_or_filename, source_chain, verbose):

    mapping = _convert_pdb_code_to_uniprot_id(code_or_filename, source_chain)

    _exit_if_pdb_to_uniprot_network_failure(mapping)
    _exit_if_pdb_to_uniprot_mapping_fails(code_or_filename, mapping)

    alphafold_result = _get_alphafold_pdb_url_from_uniprot_id(mapping)

    _exit_if_alphafold_network_bad(alphafold_result)
    _exit_if_alphafold_uniprot_to_pdb_url_fails(alphafold_result)

    _note_uniprot_mapping_if_verbose(alphafold_result, verbose)

    pdb_file_data = _download_pdb_file(alphafold_result)

    _exit_if_pdb_download_bad(pdb_file_data)

    return pdb_file_data


def _note_uniprot_mapping_if_verbose(mapping, verbose):
    if mapping:
        pdb_start = mapping.pdb_start_residue
        uniprot_start = mapping.pdb_uniprot_start
        msg = (
            f"uniprot mapping, pdb:{mapping.pdb_code}:{pdb_start} -> uniprot:{mapping.uniprot_id}:{uniprot_start}"
            " ->  alphafold:{mapping.alphafold_id}:{uniprot_start}"
        )

        _note(msg, verbose)

        if not verbose:
            print(f"# shiftx2 {msg}")


def _download_pdb_file(alphafold_result: AlphafoldResult) -> PDBDownloadResult:

    response = requests.get(alphafold_result.pdb_url)

    network_ok = response.status_code == NETWORK_200_OK

    data = response.text

    if data:
        pdb_filename = _get_filename_from_url(alphafold_result.pdb_url)
        tmpdirname = tempfile.mkdtemp()
        file_path = Path(tmpdirname) / pdb_filename
        with open(file_path, "w") as fp:
            fp.write(data)

    result = PDBDownloadResult(
        network_ok=network_ok,
        file_system_ok=file_path.is_file(),
        pdb_url=alphafold_result.pdb_url,
        pdb_code=alphafold_result.pdb_code,
        chain_code=alphafold_result.chain_code,
        uniprot_id=alphafold_result.uniprot_id,
        alphafold_id=alphafold_result.alphafold_id,
        pdb_file_path=file_path,
        pdb_uniprot_start=alphafold_result.pdb_uniprot_start,
        pdb_uniprot_end=alphafold_result.pdb_uniprot_end,
        pdb_start_residue=alphafold_result.pdb_start_residue,
    )
    return result


def _get_alphafold_pdb_url_from_uniprot_id(
    mapping: PdbUniprotMapping,
) -> AlphafoldResult:

    alphafold_url = ALPHA_FOLD_URL_TEMPLATE.format(
        uniprot_id=mapping.uniprot_id, alphafold_key=ALPHA_FOLD_KEY
    )

    response = requests.get(alphafold_url)

    network_ok = response.status_code == NETWORK_200_OK

    raw_data = response.json() if network_ok and response.text else None

    uniprot_id = mapping.uniprot_id
    entry = None
    alphafold_pdb_url = None
    alphafold_entry_id = None
    if raw_data:
        entry = raw_data[0]
        alphafold_pdb_url = entry["pdbUrl"]
        alphafold_entry_id = entry["entryId"]

    alphafold_result = AlphafoldResult(
        network_ok=network_ok,
        pdb_url=alphafold_pdb_url,
        uniprot_id=uniprot_id,
        pdb_code=mapping.pdb_code,
        chain_code=mapping.chain_code,
        raw_data=entry,
        alphafold_id=alphafold_entry_id,
        pdb_uniprot_start=mapping.pdb_uniprot_start,
        pdb_uniprot_end=mapping.pdb_uniprot_end,
        pdb_start_residue=mapping.pdb_start_residue,
    )

    return alphafold_result


def _exit_if_alphafold_uniprot_to_pdb_url_fails(alphafold_result):
    if not alphafold_result.pdb_url:
        msg = f"""
           failed to get alphafold structure url using uniprot id {alphafold_result.uniprot_id} which was
           mapped from pdb code {alphafold_result.pdb_code}. Is thisfor a structure not in the embl database
           [eg a virus, or a bacterium like E.coli]?
           """
        exit_error(msg)


def _convert_pdb_code_to_uniprot_id(
    code_or_filename, source_chain
) -> PdbUniprotMapping:

    response = requests.get(
        PDB_UNIPROT_MAPPING_URL_TEMPLATE.format(code_or_filename=code_or_filename)
    )

    network_ok = response.status_code == NETWORK_200_OK

    raw_mapping_data = response.json() if network_ok and response.text else None

    uniprot_id = None
    if raw_mapping_data:
        code_or_filename = code_or_filename.lower()

        for putative_uniprot_id, mapping_element in raw_mapping_data[code_or_filename][
            "UniProt"
        ].items():
            for mapping in mapping_element["mappings"]:
                if (
                    mapping["chain_id"]
                    and source_chain
                    and (mapping["chain_id"].lower() == source_chain.lower())
                ):
                    uniprot_id = putative_uniprot_id
                    break

    pdb_uniprot_start = None
    pdb_uniprot_end = None
    pdb_start_residue = None
    if uniprot_id:

        chain_info = raw_mapping_data[code_or_filename]["UniProt"][uniprot_id]
        first_mapping = next(iter(chain_info["mappings"]))

        pdb_uniprot_start = int(first_mapping["unp_start"])
        pdb_uniprot_end = int(first_mapping["unp_end"])
        pdb_start_residue = int(
            first_mapping["start"]["residue_number"]
        )  # as opposed to 'author_residue_number'

    result = PdbUniprotMapping(
        network_ok=network_ok,
        pdb_code=code_or_filename,
        chain_code=code_or_filename,
        uniprot_id=uniprot_id,
        pdb_uniprot_start=pdb_uniprot_start,
        pdb_uniprot_end=pdb_uniprot_end,
        pdb_start_residue=pdb_start_residue,
        raw_data=raw_mapping_data,
    )

    return result


def _exit_if_pdb_to_uniprot_network_failure(mapping: PdbUniprotMapping):

    if not mapping.network_ok:
        msg = f"""
        failed to get uniprot id from pdb code {mapping.pdb_code}
        it appears there was a network problem accessing the url:

        {PDB_UNIPROT_MAPPING_URL_TEMPLATE.format(code_or_filename=mapping.pdb_code)}
        """
        exit_error(msg)


def _exit_if_pdb_to_uniprot_mapping_fails(code, mapping: PdbUniprotMapping):

    if mapping.uniprot_id is None:
        mapping_table = []
        for putative_uniprot_id, mapping_element in mapping.raw_data[mapping.pdb_code][
            "UniProt"
        ].items():
            for mapping in mapping_element["mappings"]:
                mapping_table.append(
                    (
                        putative_uniprot_id,
                        mapping["chain_id"],
                        mapping["unp_start"],
                        mapping["unp_end"],
                    )
                )

        headings = [
            "uniprot id",
            "chain code",
            "sequence code start",
            "sequence code end",
        ]
        mapping_table = tabulate(mapping_table, headers=headings)

        msg = """
            using pdb code {code_or_filename} and chain {source_chain} I couldn't find a mapping,
            the available mappings are

            {mapping_table}
            """
        msg = dedent(msg)
        msg = msg.format(
            code_or_filename=code.upper(),
            source_chain=mapping["chain_id"],
            mapping_table=mapping_table,
        )
        exit_error(msg)
