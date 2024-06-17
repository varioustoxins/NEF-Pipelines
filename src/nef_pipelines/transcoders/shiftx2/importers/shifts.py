from pathlib import Path

import requests
import typer
from bs4 import BeautifulSoup
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import AtomLabel, Residue, ShiftData, ShiftList
from nef_pipelines.lib.util import STDIN, is_float, is_int
from nef_pipelines.transcoders.shiftx2 import import_app

deuterate = {False: 1, True: 0}
phospho = {False: 1, True: 0}
shifttype = {"all": "back-bone", 1: 1, "side-chain": 2}
output = {"tabular": 0, 1: "csv", 2: "nmr-star", 3: "nef"}
use_shifty = {False: 1, True: 0}
multipl_chains = {False: 1, True: 0}

ROOT_URL = "http://www.shiftx2.ca/cgi-bin"
CGI_URL = f"{ROOT_URL}/shiftx2.cgi"

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def shifts(
    pdb_code: str = typer.Argument(None),
    in_file: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="input to read NEF data from [- is stdin]",
    ),
):
    """- read a shiftx2 chemical shift prediction"""
    entry = read_or_create_entry_exit_error_on_bad_file(in_file, "shiftx2")
    entry = pipe(entry, pdb_code)
    print(entry)


def pipe(entry, pdb_code) -> Entry:
    data = {
        "deuterate": 1,
        "ph": 7,
        "temper": 298,
        "phospho": 1,
        "shifttype": 0,
        "format": 3,
        "shifty": 0,
        "pdbid": pdb_code,
        "filename": "",
        "nonoverlap": 1,
    }
    r = requests.request("POST", CGI_URL, data=data)

    soup = BeautifulSoup(r.text, features="html.parser")
    link = soup.find_all("a", href=True, string="download predictions")[0]["href"]

    data_url = f"{ROOT_URL}/{link}"
    data_r = requests.get(data_url)

    shifts = []
    for line in data_r.text.split("\n"):
        fields = line.split()
        if len(fields) != 6:
            continue
        chain_code = fields[0]

        sequence_code = fields[1]
        if not is_int(sequence_code):
            continue

        residue_name = fields[2]
        atom_name = fields[3]
        shift = fields[4]
        if not is_float(shift):
            continue
        shift_error = fields[5]
        if not (shift_error == UNUSED or is_float(shift_error)):
            continue

        residue = Residue(
            chain_code=chain_code,
            sequence_code=sequence_code,
            residue_name=residue_name,
        )
        atom = AtomLabel(residue, atom_name)
        shift = ShiftData(atom=atom, value=shift, value_uncertainty=shift_error)
        shifts.append(shift)

    shift_list = ShiftList(shifts)
    frame = shifts_to_nef_frame(shift_list, "shiftx2")
    entry.add_saveframe(frame)
    return entry
