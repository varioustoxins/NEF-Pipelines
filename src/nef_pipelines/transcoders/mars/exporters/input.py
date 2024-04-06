# original implementation by esther
import sys
from pathlib import Path

import typer

from nef_pipelines.lib.nef_lib import read_entry_from_stdin_or_exit
from nef_pipelines.transcoders.mars import export_app

MARS_DEFAULT_FILE = "mars.inp"
STDOUT_PATH = "-"


def convert_output_to(file_name, end, extension):
    if file_name != "-":
        path = Path(file_name)
        suffixes = "".join(path.suffixes)
        result = f"{file_name[:-len(suffixes)]}{end}.{extension}"
    else:
        result = file_name

    return result


# noinspection PyUnusedLocal
@export_app.command()
def input(
    root: str = typer.Option(
        None, help="root name for files [default: <ENTRY-ID>]", metavar="<ROOT>"
    ),
    deuterated: bool = typer.Option(
        False,
        help="is the protein deuterated [default: False]",
        metavar="<DEUTERATED-PROTEIN>",
    ),
    folded: bool = typer.Option(
        True, help="is the protein folded [default: False]", metavar="<FOLDED-PROTEIN>"
    ),
    output_file: str = typer.Argument(
        None,
        help="file name to output to [default <entry_id>.inp] for stdout use -",
        metavar="<MARS-INPUT-FILENAME>",
    ),
):
    """- write  mars input fixed assignment and connectivity files"""

    entry = read_entry_from_stdin_or_exit()

    output_file = f"{entry.entry_id}_mars.inp" if output_file is None else output_file
    pred_file = (
        f"{entry.entry_id}_pred.tab"
        if output_file is None
        else convert_output_to(output_file, "_pred", "tab")
    )
    ass_file = (
        f"{entry.entry_id}_fix_ass.tab"
        if output_file is None
        else convert_output_to(output_file, "_fix_ass", "tab")
    )

    deuterated = int(deuterated)
    random_coil = int(not folded)

    root = entry.entry_id if root is None else root

    template = f"""\
        fragSize:     5               # Maximum length of pseudoresidue fragments

        cutoffCO:     0.25            # Connectivity cutoff (ppm) of CO [0.25]
        cutoffCA:     0.2             # Connectivity cutoff (ppm) of CA [0.5]
        cutoffCB:     0.5             # Connectivity cutoff (ppm) of CB [0.5]
        cutoffHA:     0.25            # Connectivity cutoff (ppm) of HA [0.25]
        cutoffHN:     0.02            # Connectivity cutoff (ppm) of HN [0.15]
        cutoffN:      0.05            # Connectivity cutoff (ppm) of N [0.10]
        cutoffnHN:    0.02            # Connectivity cutoff (ppm) of HN+1 [0.15]
        cutoffnN:     0.05            # Connectivity cutoff (ppm) of N+1 [0.10]

        fixConn:      {root}_fix_con.tab     # Table for fixing sequential connectivity
        fixAss:       {root}_fix_ass.tab     # Table for fixing residue type and(or) assignment

        pdb:          0               # 3D structure available [0/1]
        resolution:   NO              # Resolution of 3D structure [Angstrom]
        pdbName:      NO              # Name of PDB file (protons required!)
        tensor:       NO              # Method for obtaining alignment tensor [0/1/2/3/4]

        nIter:        NO              # Number of iterations [2/3/4]

        dObsExh:      NO              # Name of RDC table for exhaustive SVD (PALES format)
        dcTab:        NO              # Name of RDC table (PALES format)

        deuterated:   {deuterated}               # Protonated proteins [0]; perdeuterated proteins [1]

        rand_coil:    {random_coil}              # Folded proteins [0]; disordered proteins [1]

        sequence:     {root}.fasta       # Primary sequence (FASTA format)
        secondary:    {root}_psipred.tab # Secondary structure (PSIPRED format)
        csTab:        {root}_shifts.tab  # Chemical shift table
    """

    file_h = sys.stdout if output_file == STDOUT_PATH else open(output_file, "w")

    print(template, file=file_h)

    if output_file != STDOUT_PATH:
        print("NOTE: writing empty pred and ass files!", file=sys.stderr)
        print(f"    pred file: {pred_file}", file=sys.stderr)
        print(f"    ass file: {ass_file}", file=sys.stderr)

        with open(pred_file, "w") as fh:
            print(file=fh)

        with open(ass_file, "w") as fh:
            print(file=fh)

    if output_file != STDOUT_PATH:
        file_h.close()

        if not sys.stdout.isatty():
            print(entry)
