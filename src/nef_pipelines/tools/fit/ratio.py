from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry, Loop, Saveframe
from uncertainties import ufloat

from nef_pipelines.lib.nef_frames_lib import NEF_PIPELINES_NAMESPACE
from nef_pipelines.lib.nef_lib import (
    NEF_RELAXATION_VERSION,
    UNUSED,
    create_nef_save_frame,
    get_frame_id,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.shift_lib import IntensityMeasurementType
from nef_pipelines.lib.util import parse_comma_separated_options
from nef_pipelines.tools.fit import fit_app
from nef_pipelines.tools.fit.fit_lib import (
    _build_spectrum_peak_id_to_axis_atoms,
    _exit_if_isotope_axes_are_not_unique,
    _exit_if_isotope_frequencies_are_not_unique,
    _exit_if_no_frame_selectors,
    _exit_if_no_frequencies_found,
    _exit_if_no_series_frames_selected,
    _get_unique_isotope_frequencies,
    _select_relaxation_series_or_exit,
    _series_frame_to_data_id_to_spectrum_peak_id,
    _series_frame_to_id_series_data,
    _series_frame_to_spectrum_frames,
    frequencies_to_field_strength,
    spectra_to_isotope_axes,
    spectra_to_isotope_frequencies,
)


@fit_app.command()
def ratio(
    input: Path = typer.Option(
        None,
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="read NEF data from a file instead of stdin",
    ),
    noise_level: float = typer.Option(
        ...,
        "-n",
        "--noise",
        help="noise level to use instead of value from spectra",
    ),
    data_type: IntensityMeasurementType = typer.Option(
        IntensityMeasurementType.HEIGHT, "-d", "--data-type", help="data type to fit"
    ),
    frames_selectors: List[str] = typer.Argument(None, help="select frames to fit"),
):
    """- calculate ratio of peak intensities with error propagation" [alpha]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frame_selectors = parse_comma_separated_options(frames_selectors)

    if not frames_selectors:
        series_frames = entry.get_saveframes_by_category("nef_series_list")
        if len(series_frames) == 1:
            frame_selectors = [
                series_frames[0].name,
            ]

    _exit_if_no_frame_selectors(frame_selectors)

    series_frames = _select_relaxation_series_or_exit(entry, frames_selectors)

    _exit_if_no_series_frames_selected(series_frames, frame_selectors)

    entry = pipe(entry, series_frames, noise_level, data_type)

    print(entry)


def pipe(
    entry: Entry,
    series_frames: List[Saveframe],
    noise_level,
    intensity_measurement_type: IntensityMeasurementType,
) -> Entry:

    for series_frame in series_frames:
        id_series_data = _series_frame_to_id_series_data(
            series_frame, NEF_PIPELINES_NAMESPACE, entry
        )

        id_xy_data = {
            id: (series_datum.variable_values, series_datum.values)
            for id, series_datum in id_series_data.items()
        }

        results = _ratio_calculation(id_xy_data, noise_level)

        ratios = {id: result[0] for id, result in results.items()}
        errors = {id: result[0] for id, result in results.items()}

        results_frame = _ratio_results_as_frame(
            series_frame, NEF_PIPELINES_NAMESPACE, entry, ratios, errors, noise_level
        )

        entry.add_saveframe(results_frame)

    return entry


def _ratio_calculation(id_xy_data, error):

    result = {}
    for id, xy_data in id_xy_data.items():
        xy_data = id_xy_data[id]

        x_data = xy_data[0]
        y_data = xy_data[1]

        on_index = [i for i, val in enumerate(x_data) if bool(val)][0]
        off_index = [i for i, val in enumerate(x_data) if not bool(val)][0]

        on_value = ufloat(y_data[on_index], error)
        off_value = ufloat(y_data[off_index], error)

        ratio = on_value / off_value

        result[id] = ratio.nominal_value, ratio.std_dev

    return result


def _ratio_results_as_frame(
    series_frame,
    prefix,
    entry,
    ratios,
    errors,
    noise_level,
):

    spectrum_frames = _series_frame_to_spectrum_frames(series_frame, prefix, entry)

    data_id_to_spectrum_peak_ids = _series_frame_to_data_id_to_spectrum_peak_id(
        series_frame, prefix
    )

    spectrum_peak_id_to_axis_atoms = _build_spectrum_peak_id_to_axis_atoms(
        spectrum_frames
    )

    isotope_axes = spectra_to_isotope_axes(spectrum_frames)

    _exit_if_isotope_axes_are_not_unique(isotope_axes, spectrum_frames, entry.entry_id)

    isotope_frequencies = spectra_to_isotope_frequencies(spectrum_frames)

    _exit_if_isotope_frequencies_are_not_unique(
        isotope_frequencies, spectrum_frames, entry.entry_id
    )

    isotope_frequencies = _get_unique_isotope_frequencies(isotope_frequencies)

    _exit_if_no_frequencies_found(isotope_frequencies, series_frame, entry)

    field_strength = frequencies_to_field_strength(isotope_frequencies)

    frame_id = get_frame_id(series_frame)

    result_frame = create_nef_save_frame(
        f"{prefix}_relaxation_list", f"{frame_id}_fitted"
    )

    result_frame.add_tag("version", NEF_RELAXATION_VERSION)
    result_frame.add_tag("experiment_type", series_frame.get_tag("experiment_type")[0])
    result_frame.add_tag("field_strength", field_strength)
    result_frame.add_tag("value_unit", UNUSED)
    result_frame.add_tag("relaxation_atom_id", UNUSED)
    result_frame.add_tag("ref_value", UNUSED)
    result_frame.add_tag("source", "experimental")
    comment = f"""
        noise_estimate {noise_level}
    """

    result_frame.add_tag("comment", comment)

    relaxation_loop = Loop.from_scratch(f"{prefix}_relaxation")
    result_frame.add_loop(relaxation_loop)

    RELAXATION_LOOP_TAGS = "index data_id data_combination_id value value_error".split()
    RELAXATION_LOOP_ATOM_TAGS = (
        "chain_code_{axis} sequence_code_{axis} residue_name_{axis} atom_name_{axis}"
    )

    all_tags = [
        *RELAXATION_LOOP_TAGS,
    ]
    for axis in range(1, len(isotope_axes) + 1):
        all_tags.append(RELAXATION_LOOP_ATOM_TAGS.format(axis=axis).split())

    relaxation_loop.add_tag(all_tags)

    data = []
    for index, (data_id, ratio) in enumerate(ratios.items(), start=1):
        data_row = {"index": index, "data_id": index, "data_combination_id": UNUSED}

        peak_atoms = []
        atom_key = next(iter(data_id_to_spectrum_peak_ids[data_id]))
        for axis_atoms in spectrum_peak_id_to_axis_atoms[atom_key].values():
            peak_atoms.extend(axis_atoms)

        for i, atom in enumerate(peak_atoms, start=1):
            residue = atom.residue
            data_row.update(
                {
                    f"chain_code_{i}": residue.chain_code,
                    f"sequence_code_{i}": residue.sequence_code,
                    f"residue_name_{i}": residue.residue_name,
                    f"atom_name_{i}": atom.atom_name,
                }
            )
        data.append(data_row)
        data_row.update(
            {
                "value": f"{ratio:.20f}",
                "value_error": f"{errors[data_id]:.20f}",
            }
        )

    relaxation_loop.add_data(data)

    return result_frame


# implementation thoughts
# 1. having a spectrometer frequency and field strength in the same construct is a pain, what do we dfeine as the
#    conversion ratio i took  alue in cavanagh and cross-checked it with from https://www.kherb.io/docs/nmr_table.html
#    which uses the codata value for 1H [but not for 15N and 13C which use the IAEA values]
# 2. if we have 1H and 15N and 13C spectrometer frequencies which should we use to
#    calculate the field strength? i chose the one with the highest gamma, but note my gamma ratios do not those in
#    https://www.kherb.io/docs/nmr_table.html exacly
# 3. do we need the value type should it be Nz for a 15N experiment, what are I and S defined as in this context
# 4. how do we determine the relaxation_atom_id shouldn't also be available on the series data or come from the series
#    data as it's the type of experiment and the experimenta series that determine this, currently choose lowest gamma!
# 5. the value doesn't have a type just a unit, should it?
# 6. the source maybe should be on the data series rather than the relaxation list -  it knoes what its is
#    the relaxation list doesn't need tow
# 7. the nef_relaxation doesn't leave room for other fit values e.g I or the baseline offset for a 3 point fit...
# 8. room for a comment on each fit would be good...
# 9. when would the index and data_id in a nef_relaxation_list be different?
# 10. we should say the value error is sigma
# 11. why are some of our constants capitalised and others not - we should be consistent
#     e.g. experimental | simulated | theoretical vs OnePhaseDecay | ExponentialDecay | InversionRecovery | other
