from enum import auto
from pathlib import Path
from textwrap import dedent, indent
from typing import List

import typer
from fyeah import f
from pynmrstar import Entry, Loop, Saveframe
from runstats import Statistics
from strenum import LowercaseStrEnum
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    SelectionType,
    create_nef_save_frame,
    get_frame_ids,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.peak_lib import frame_to_peaks
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.tools.shifts import shifts_app

UPDATE_POLICY_HELP = (
    "how to update spectrum frame shift list to reflect the the calculated shift list"
)


class UpdatePolicy(LowercaseStrEnum):
    UPDATE = auto()
    UPDATE_UNDEFINED = auto()
    LEAVE = auto()


@shifts_app.command()
def average(
    in_path: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    # selectors: str = typer.Argument(None, help="selectors to match shifts from [default is Spectra]"),
    # target: str = typer.Argument(None, help="shift list to put shifts in"),
    force: bool = typer.Option(False, help="if target peak list exists replace it"),
    frame_name: str = typer.Option("{entry_id}", help="the shift list to write to"),
    update_policies: List[UpdatePolicy] = typer.Option(
        [], "--update-policies", help=UPDATE_POLICY_HELP
    ),
    selectors: List[str] = typer.Argument(
        None, help="selectors for frames to average shifts from [default is all]"
    ),
):
    """- average chemical shifts from spectra [peaks] into a nef chemical shift frame [alpha]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(in_path)

    selection_type = SelectionType.ANY
    if not selectors:
        selectors = "nef_nmr_spectrum"
        selection_type = SelectionType.CATEGORY

    frames = select_frames(entry, selectors, selection_type)

    if not update_policies:
        update_policies = [
            UpdatePolicy.UPDATE_UNDEFINED,
        ]

    _exit_if_bad_frame_types_selected(frames)

    entry = pipe(entry, frames, frame_name, force, update_policies=update_policies)

    print(entry)


def pipe(
    entry: Entry,
    frames: List[Saveframe],
    frame_name: str,
    force: bool,
    update_policies=(UpdatePolicy.UPDATE_UNDEFINED,),
) -> Entry:

    entry_id = entry.entry_id  # noqa: F841
    frame_name = f(frame_name)

    peaks = []
    for frame in frames:
        peaks.extend(frame_to_peaks(frame))
        _update_shift_list_name(frame, frame_name, update_policies)

    shifts = {}
    for peak in peaks:
        for shift in peak.shifts:
            shifts.setdefault(shift.atom, Statistics()).push(shift.value)

    results_frame = create_nef_save_frame("nef_chemical_shift_list", frame_name)

    loop = Loop.from_scratch("nef_chemical_shift")
    loop.add_tag(
        "chain_code sequence_code residue_name atom_name value value_uncertainty".split()
    )
    results_frame.add_loop(loop)

    for atom, stats in sorted(shifts.items()):
        stddev = stats.stddev() if len(stats) > 1 else UNUSED

        # filter on empty chain codes or sequence codes which are "" in the structures.Peak
        if not atom.residue.chain_code or not atom.residue.sequence_code:
            continue

        data = [
            {
                "chain_code": atom.residue.chain_code,
                "sequence_code": atom.residue.sequence_code,
                "residue_name": atom.residue.residue_name,
                "atom_name": atom.atom_name,
                "value": stats.mean(),
                "value_uncertainty": stddev,
            }
        ]
        loop.add_data(data)

    if frame_name in get_frame_ids(entry) and not force:
        exit_error(
            f"the frame {frame_name} already exists in the entry {entry.entry_id}, use --force to overwrite"
        )
    elif frame_name in get_frame_ids(entry) and force:
        old_saveframe = entry.get_saveframe_by_name(
            f"nef_chemical_shift_list_{frame_name}"
        )
        entry.remove_saveframe(old_saveframe)

    entry.add_saveframe(results_frame)

    return entry


def _update_shift_list_name(frame: Saveframe, shift_list_frame_name, update_policies):

    if (
        UpdatePolicy.UPDATE_UNDEFINED in update_policies
        and frame.get_tag("chemical_shift_list")[0] == UNUSED
    ):
        frame.add_tags(
            [
                (
                    "chemical_shift_list",
                    f"nef_chemical_shift_list_{shift_list_frame_name}",
                ),
            ],
            update=True,
        )
    else:
        msg = f"""
             the only supported update policy is currently {UpdatePolicy.UPDATE_UNDEFINED},
             you gave {', '.join(update_policies)} bug gary!
        """
        exit_error(msg)


def _exit_if_bad_frame_types_selected(frames):
    bad_frames = []
    for frame in frames:
        if frame.category not in [
            "nef_nmr_spectrum",
        ]:  # 'nef_chemical_shift_list']:
            bad_frames.append(frame)
    if bad_frames:
        bad_frame_table = []

        for frame in bad_frames:
            frame_name = frame.name
            frame_category = frame.category
            frame_name = frame_name[len(frame_category) :]
            if frame_name == "":
                frame_name = "**SINGLETON**"
            bad_frame_table.append([f"{frame_name}", f"[{frame.category}]"])

        msg = """
            Some of the selected frames are not chemical shift lists or spectra [peak lists]
            the bad frames and categories are:

        """
        msg = dedent(msg)
        msg += indent(
            tabulate(bad_frame_table, headers=["frame name", "category"]), "    "
        )
        msg += "\n"
        msg = f(msg)
        exit_error(msg)
