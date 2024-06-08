# original implementation by esther
import sys
from pathlib import Path

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import read_entry_from_stdin_or_exit
from nef_pipelines.lib.util import STDOUT, exit_if_file_has_bytes_and_no_force
from nef_pipelines.transcoders.mars import export_app

MARS_DEFAULT_FILE = "mars.inp"

TEMPLATE = """\
     fragSize:     5                      # Maximum length of pseudoresidue fragments

     cutoffCO:     0.25                   # Connectivity cutoff (ppm) of CO [0.25]
     cutoffCA:     0.2                    # Connectivity cutoff (ppm) of CA [0.5]
     cutoffCB:     0.5                    # Connectivity cutoff (ppm) of CB [0.5]
     cutoffHA:     0.25                   # Connectivity cutoff (ppm) of HA [0.25]
     cutoffHN:     0.02                   # Connectivity cutoff (ppm) of HN [0.15]
     cutoffN:      0.05                   # Connectivity cutoff (ppm) of N [0.10]
     cutoffnHN:    0.02                   # Connectivity cutoff (ppm) of HN+1 [0.15]
     cutoffnN:     0.05                   # Connectivity cutoff (ppm) of N+1 [0.10]

     fixConn:      {root}_fix_con.tab     # Table for fixing sequential connectivity
     fixAss:       {root}_fix_ass.tab     # Table for fixing residue type and(or) assignment

     pdb:          0                      # 3D structure available [0/1]
     resolution:   NO                     # Resolution of 3D structure [Angstrom]
     pdbName:      NO                     # Name of PDB file (protons required!)
     tensor:       NO                     # Method for obtaining alignment tensor [0/1/2/3/4]

     nIter:        NO                     # Number of iterations [2/3/4]

     dObsExh:      NO                     # Name of RDC table for exhaustive SVD (PALES format)
     dcTab:        NO                     # Name of RDC table (PALES format)

     deuterated:   {deuterated}           # Protonated proteins [0]; perdeuterated proteins [1]

     rand_coil:    {random_coil}          # Folded proteins [0]; disordered proteins [1]

     sequence:     {root}.fasta           # Primary sequence (FASTA format)
     secondary:    {root}_psipred.tab     # Secondary structure (PSIPRED format)
     csTab:        {root}_shifts.tab      # Chemical shift table
 """


# noinspection PyUnusedLocal
@export_app.command()
def input(
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
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="force overwrite of output file if it exists and isn't empty",
    ),
):
    """- write mars input fixed assignment and connectivity files"""

    entry = read_entry_from_stdin_or_exit()

    output_file = Path(output_file) if output_file else Path(f"{entry.entry_id}.inp")

    entry = pipe(entry, deuterated, folded, output_file, force)

    if entry:
        print(entry)


def pipe(
    entry: Entry, deuterated: bool, folded: bool, output_file: Path, force: bool
) -> Entry:

    root = output_file.stem if output_file != STDOUT else f"{entry.entry_id}"

    random_coil = not folded

    output = TEMPLATE.format(root=root, deuterated=deuterated, random_coil=random_coil)

    exit_if_file_has_bytes_and_no_force(output_file, force)

    file_h = sys.stdout if output_file == STDOUT else open(output_file, "w")

    print(output, file=file_h)

    if output_file != STDOUT:
        file_h.close()

    Path(f"{root}_fix_con.tab").touch()
    Path(f"{root}_fix_ass.tab").touch()

    result = entry if output_file != STDOUT else None

    return result
