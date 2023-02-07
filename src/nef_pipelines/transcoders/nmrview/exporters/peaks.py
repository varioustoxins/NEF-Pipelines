from argparse import Namespace
from collections import Counter
from enum import auto
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, List, Tuple, Union

import typer
from strenum import StrEnum
from tabulate import tabulate

from nef_pipelines.lib.constants import NEF_UNKNOWN
from nef_pipelines.lib.nef_lib import (
    loop_row_dict_iter,
    loop_row_namespace_iter,
    read_entry_from_stdin_or_exit,
)
from nef_pipelines.lib.structures import AtomLabel, Peak, PeakValues, SequenceResidue
from nef_pipelines.lib.util import exit_error, is_float, parse_comma_separated_options
from nef_pipelines.transcoders.nmrview import export_app

app = typer.Typer()


class HEADINGS(StrEnum):
    LABEL = auto()
    SHIFT = auto()
    WIDTH = auto()
    BOUND = auto()
    ERROR = auto()
    COUPLING = auto()
    COMMENT = auto()


HEADING_TRANSLATIONS = {
    HEADINGS.LABEL: "L",  # the assignment
    HEADINGS.SHIFT: "P",  # the shift
    HEADINGS.WIDTH: "W",  # width at half height in ppm
    HEADINGS.BOUND: "B",  # bound width at lowest contour level when picked in ppm, assume gaussian?
    HEADINGS.ERROR: "E",  # an error code always '++' ?
    HEADINGS.COUPLING: "J",  # always 0.00 for us
    HEADINGS.COMMENT: "U",  # user comment always currently {?}
}


# noinspection PyUnusedLocal
@export_app.command()
def peaks(
    file_name_template: str = typer.Option(
        "%s",
        help="the template for the filename to export to %s will get replaced by the axis_name of the peak frame",
        metavar="<peak-file.xpk>",
    ),
    frame_selectors: List[str] = typer.Argument(
        None, help="the names of the frames to export", metavar="<frames>"
    ),
):
    frame_selectors = parse_comma_separated_options(frame_selectors)

    if len(frame_selectors) == 0:
        frame_selectors = [
            "*",
        ]

    entry = read_entry_from_stdin_or_exit()

    SPECTRUM_CATEGORY = "nef_nmr_spectrum"
    peaks = entry.get_saveframes_by_category(SPECTRUM_CATEGORY)

    names_and_frames = {
        frame.name[len(SPECTRUM_CATEGORY) :].lstrip("_"): frame for frame in peaks
    }

    selected_frames = {}
    for frame_selector in frame_selectors:
        selection = {
            name: frame
            for name, frame in names_and_frames.items()
            if fnmatch(name, frame_selector)
        }

        selected_frames.update(selection)

    if len(selected_frames) == 0:
        for frame_selector in frame_selectors:
            selection = {
                name: frame
                for name, frame in names_and_frames.items()
                if fnmatch(name, f"*{frame_selector}*")
            }

            selected_frames.update(selection)

    if not "%s" and len(selected_frames) > 1:
        exit_error(
            f"%s is not in the filename template and there is more than one file, template {file_name_template}"
        )

    # bad_characters = '''\
    #     `:';~@$%^&().<>"
    # '''
    # replacements = '_' * len(bad_characters)
    # translation_table = str.maketrans(bad_characters, replacements)

    for frame_name, frame in selected_frames.items():
        # peak_list_name = f'''{frame_name.translate(translation_table).strip('_')}.xpk'''

        SPECTRUM_DIMESIONS = "_nef_spectrum_dimension"
        PEAKS = "_nef_peak"
        spectrum_dimensions = list(loop_row_namespace_iter(frame[SPECTRUM_DIMESIONS]))

        spectrum_name = (
            frame["ccpn_spectrum_file_path"][0]
            if "ccpn_spectrum_file_path" in frame
            else "unknown"
        )
        spectrum_name = Path(spectrum_name).parts[-1]

        result = ["label dataset sw sf"]

        axis_names = [
            dimension.axis_code
            if "axis_code" in dimension and dimension != NEF_UNKNOWN
            else "unknown"
            for dimension in spectrum_dimensions
        ]

        axis_names = _make_names_unique(axis_names)

        result.append(" ".join(axis_names))

        # TODO: issue warning if spectrum name doesn't end in nv!
        nmrview_spectrum_name = Path(spectrum_name)
        nmrview_spectrum_name = f"{nmrview_spectrum_name.stem}.nv"
        result.append(nmrview_spectrum_name)

        spectrometer_frequencies = [
            dimension.spectrometer_frequency for dimension in spectrum_dimensions
        ]
        spectrometer_frequencies = _convert_to_floats_or_exit(
            spectrometer_frequencies, "spectrometer_frequencies"
        )

        sweep_widths = [dimension.spectral_width for dimension in spectrum_dimensions]
        sweep_widths = _convert_to_floats_or_exit(sweep_widths, "sweep_widths")

        sweep_widths = [
            sweep_width * spectrometer_frequency
            for sweep_width, spectrometer_frequency in zip(
                sweep_widths, spectrometer_frequencies
            )
        ]

        sweep_widths = [f"{{{sweep_width:.3f}}}" for sweep_width in sweep_widths]
        result.append(" ".join(sweep_widths))

        spectrometer_frequencies = [
            f"{{{spectrometer_frequency:.3f}}}"
            for spectrometer_frequency in spectrometer_frequencies
        ]
        result.append(" ".join(spectrometer_frequencies))

        print("\n".join(result))

        headings = [
            f"{axis_name}.{item}" for axis_name in axis_names for item in "LPWBEJU"
        ]
        headings.extend("vol int stat comment flag0".split())
        headings.insert(0, "")

        table = [headings]

        pipeline_peaks = []
        for peak_row in list(loop_row_dict_iter(frame[PEAKS])):
            pipeline_peaks.append(_row_to_peak(axis_names, peak_row))

        for peak in pipeline_peaks:

            row = _build_nmrview_row(peak, axis_names)
            table.append(row)

        print(tabulate(table, tablefmt="plain"))


def _peak_to_atom_labels(row: Namespace) -> List[AtomLabel]:
    result = []
    for i in range(1, 15):
        dim_chain_code = f"chain_code_{i}"
        dim_sequence_code = f"sequence_code_{i}"
        dim_residue_name = f"residue_name_{i}"
        dim_atom_name = f"atom_name_{i}"

        if (
            dim_chain_code in row
            and dim_sequence_code in row
            and dim_residue_name in row
            and dim_atom_name in row
        ):
            chain_code = getattr(row, dim_chain_code)
            sequence_code = getattr(row, dim_sequence_code)
            residue_name = getattr(row, dim_residue_name)
            atom_name = getattr(row, dim_atom_name)

            result.append(
                AtomLabel(
                    SequenceResidue(chain_code, sequence_code, residue_name), atom_name
                )
            )

    return result


def _atom_label_to_nmrview(label: AtomLabel) -> str:
    return f"{{{label.residue.sequence_code}.{label.atom_name}}}"


def _convert_to_floats_or_exit(
    putative_floats: List[str], thing_types: str
) -> List[float]:
    are_floats = [
        is_float(spectrometer_frequency) for spectrometer_frequency in putative_floats
    ]
    if not all(are_floats):
        bad_dims = [
            dim
            for dim, is_float_value in enumerate(are_floats, start=1)
            if not is_float_value
        ]
        bad_values = [
            value
            for is_float_value, value in zip(are_floats, putative_floats)
            if not is_float_value
        ]
        message = f"""\
                the following {thing_types} frequencies which cannot be converted to floats
                dims: {', '.join(bad_dims)}
                bad values: {', '.join(bad_values)}
            """

        exit_error(message)

    return [float(value) for value in putative_floats]


def _row_to_peak(
    axis_names: Tuple[str], row: Dict[str, Union[int, str, float]]
) -> Peak:
    peak_id = row["peak_id"]
    volume = row["volume"] if row["volume"] != NEF_UNKNOWN else None
    volume_uncertainty = (
        row["volume_uncertainty"] if row["volume_uncertainty"] != NEF_UNKNOWN else None
    )
    height = row["height"] if row["height"] != NEF_UNKNOWN else None
    height_uncertainty = (
        row["height_uncertainty"] if row["height_uncertainty"] != NEF_UNKNOWN else None
    )

    positions = {}
    position_uncertainties = {}
    for axis_index, axis_name in enumerate(axis_names, start=1):
        position_tag = f"position_{axis_index}"
        position_uncertainty_tag = f"position_uncertainty_{axis_index}"
        positions[axis_name] = row[position_tag]
        position_uncertainties[axis_name] = (
            row[position_uncertainty_tag]
            if row[position_uncertainty_tag] != NEF_UNKNOWN
            else None
        )
        position_uncertainties[axis_name]

    assignments = {}
    for axis_index, axis_name in enumerate(axis_names, start=1):
        assignment_chain_code_tag = f"chain_code_{axis_index}"
        assignment_sequence_code_tag = f"sequence_code_{axis_index}"
        assignment_residue_name_tag = f"residue_name_{axis_index}"
        assignment_atom_name_tag = f"atom_name_{axis_index}"

        chain_code = row[assignment_chain_code_tag]
        sequence_code = row[assignment_sequence_code_tag]
        residue_name = row[assignment_residue_name_tag]
        atom_name = row[assignment_atom_name_tag]

        is_assigned = (
            chain_code != NEF_UNKNOWN
            and sequence_code != NEF_UNKNOWN
            and atom_name != NEF_UNKNOWN
        )
        atom_labels = (
            [
                AtomLabel(
                    SequenceResidue(chain_code, sequence_code, residue_name), atom_name
                ),
            ]
            if is_assigned
            else []
        )

        assignments[axis_name] = atom_labels

    uncertainties_none = [
        uncertainty is None for uncertainty in position_uncertainties.values()
    ]
    if all(uncertainties_none):
        position_uncertainties = None

    peak_values = PeakValues(
        serial=peak_id + 1,
        volume=volume,
        height=height,
        volume_uncertainty=volume_uncertainty,
        height_uncertainty=height_uncertainty,
    )
    return Peak(
        id=peak_id,
        values=peak_values,
        positions=positions,
        position_uncertainties=position_uncertainties,
        assignments=assignments,
    )


def _peak_to_nmrview_label(atom_label: AtomLabel, default_chain=None):
    result = []

    nmrview_chain = (
        atom_label.residue.chain_code
        if atom_label.residue.chain_code != NEF_UNKNOWN
        else default_chain
    )
    if nmrview_chain is not None:
        result.append(nmrview_chain)

    nmrview_residue = (
        atom_label.residue.sequence_code
        if atom_label.residue.sequence_code != NEF_UNKNOWN
        else "{?}"
    )

    result.append(str(nmrview_residue))

    nmrview_atom = atom_label.atom_name
    result.append(nmrview_atom)

    return f'{{{".".join(result)}}}'


def _build_nmrview_row(peak, axis_names):

    # TODO: are we handling peak serials correctly...
    result = [peak.id]
    nmrview_assignments = _peak_to_assignments(peak, axis_names)
    for axis_name in axis_names:
        for heading, letter in HEADING_TRANSLATIONS.items():
            if heading == HEADINGS.LABEL:
                assignment = nmrview_assignments[axis_name]
                if len(assignment.strip()) == 0:
                    assignment = "{?}"
                result.append(assignment)

            if heading == HEADINGS.SHIFT:
                result.append(f"{peak.positions[axis_name]:.3f}")

            # TODO need default values per isotope and some calculations
            if heading == HEADINGS.WIDTH:
                # TODO: place holder
                result.append("0.024")

            # TODO need default values per isotope and some calculations or
            if heading == HEADINGS.BOUND:
                # TODO: place holder
                result.append("0.051")

            if heading == HEADINGS.ERROR:
                # TODO: is this the correct value for a correct peak
                # most probably the best we can do is presume all peaks are good
                result.append("++")

            if heading == HEADINGS.COUPLING:
                result.append("0.000")

            if heading == HEADINGS.COMMENT:
                # TODO: is there a peak axis comment in ccpn/nef
                result.append("{?}")

    volume = peak.values.volume if peak.values.volume else 0.000
    result.append(f"{volume:.3f}")

    height = peak.values.height if peak.values.height else 0.000
    result.append(f"{height:.3f}")

    # status
    result.append("0")

    if peak.values.comment != "":
        result.append(f"{{{peak.values.comment}}}")
    else:
        result.append("{?}")

    # flag0
    result.append("0")

    return result


def _peak_to_assignments(peak: Peak, axis_names: Tuple[str]) -> List[str]:
    # print(peak)
    num_assignments = [len(peak.assignments[axis]) for axis in axis_names]
    max_num_assignments = max(num_assignments)

    # print('assignments', peak.assignments)

    if max_num_assignments == 0:
        result = {axis_name: "{?}" for axis_name in axis_names}
    else:
        result = {}
        for axis_name in axis_names:
            result[axis_name] = " ".join(
                [
                    _peak_to_nmrview_label(atom_label)
                    for atom_label in peak.assignments[axis_name]
                ]
            )

    return result


def _make_names_unique(axis_names: List[str]) -> List[str]:

    seen = Counter()
    for axis_name in axis_names:
        seen[axis_name] += 1

    result = []
    modified = Counter()
    for axis_name in axis_names:
        if seen[axis_name] > 1:
            modified[axis_name] += 1
            axis_name = f"{axis_name}_{modified[axis_name]}"
        result.append(axis_name)

    return result
