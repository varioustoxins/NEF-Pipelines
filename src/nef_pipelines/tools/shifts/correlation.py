from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import typer
from pynmrstar import Entry, Saveframe

from nef_pipelines.lib.nef_lib import (
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.shift_lib import nef_frames_to_shifts
from nef_pipelines.lib.structures import UNUSED, AtomLabel
from nef_pipelines.lib.util import STDIN, exit_error, info, warn
from nef_pipelines.tools.shifts import shifts_app

# Defer matplotlib import to avoid issues at module load time


FILE_FORMATS = {
    "svgz": "Scalable Vector Graphics",
    "ps": "Postscript",
    "emf": "Enhanced Metafile",
    "rgba": "Raw RGBA bitmap",
    "raw": "Raw RGBA bitmap",
    "pdf": "Portable Document Format",
    "svg": "Scalable Vector Graphics",
    "eps": "Encapsulated Postscript",
    "png": "Portable Network Graphics",
}


_out = None
_verbose = False


@shifts_app.command()
def correlation(
    frame_selectors: List[str] = typer.Argument(
        None, help="frame_names to correlate there shoudl be 2!"
    ),
    in_path: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    output: Path = typer.Option(
        "cs_correlation_{entry}_{frame_1}_{frame_2}",
        "-o",
        "--out",
        help="output template for plot and summary file name",
    ),
    atom_types: List[str] = typer.Option(
        None,
        "--atom-types",
        help="atom types to include (e.g. N, CA, CB), if none specified, all atoms are included",
    ),
    residue_types: List[str] = typer.Option(
        None,
        "--residue-types",
        help="residue types to include (e.g. ALA, GLY), if none specified, all residues are included",
    ),
    chain_codes: List[str] = typer.Option(
        None,
        "--chain-codes",
        help="chain codes to include (e.g. A, B), if none specified, all chains are included",
    ),
    show_labels: bool = typer.Option(
        False,
        "--show-labels",
        help="show atom labels on the plot",
    ),
    title: str = typer.Option(
        None,
        "--title",
        help="plot title (default: 'Chemical Shift Correlation: {frame_1} vs {frame_2}')",
    ),
    # replace with page sizes and orientations
    width: float = typer.Option(
        8.0,
        "--width",
        help="plot width in inches",
    ),
    height: float = typer.Option(
        6.0,
        "--height",
        help="plot height in inches",
    ),
    file_format: str = typer.Option(
        ".pdf", help=f"file formats which are ', {', '.join(FILE_FORMATS)}"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="produce verbose output"),
):
    """- create a correlation plot comparing chemical shifts from two shift frame_names α"""

    # Check for plotting dependencies
    try:
        import matplotlib.pyplot as plt  # noqa: F401
        import numpy as np  # noqa: F401
    except ImportError as e:
        exit_error(
            f"Plotting functionality not available. Please install matplotlib and numpy.\nError: {e}"
        )

    entry = read_entry_from_file_or_stdin_or_exit_error(in_path)

    if not frame_selectors:
        frame_selectors = [
            "*",
        ]
    frame_names = set()
    for frame_selector in frame_selectors:
        found_frame_names = [
            frame.name for frame in _find_chemical_shift_frame(entry, frame_selector)
        ]
        frame_names.update(found_frame_names)

    if len(frame_names) != 2:
        frame_names = "\n".join([f"\t{frame.name}" for frame in frame_names])
        msg = f"you must select 2 frame_names if got {len(frame_names)}\n {frame_names}"
        exit_error(msg)

    # Sort frame names - default frame first if present, otherwise alphabetically
    frame_list = list(frame_names)
    default_frames = [f for f in frame_list if f.endswith("_default")]
    non_default_frames = [f for f in frame_list if not f.endswith("_default")]

    if default_frames:
        # Put default frame first
        sorted_frames = default_frames + sorted(non_default_frames)
    else:
        # Sort alphabetically
        sorted_frames = sorted(frame_list)

    frame_id_1, frame_id_2 = sorted_frames[0], sorted_frames[1]

    # Extract shifts from both frame_names
    shifts_1 = _extract_shifts_dict(entry[frame_id_1])
    shifts_2 = _extract_shifts_dict(entry[frame_id_2])

    if verbose:
        info(
            f" shift counts {frame_id_1}: {len(shifts_1)}, {frame_id_2}: {len(shifts_2)}"
        )

    if not chain_codes:
        chain_codes_1 = {atom_label.residue.chain_code for atom_label in shifts_1}
        chain_codes_2 = {atom_label.residue.chain_code for atom_label in shifts_2}
        chain_codes = {*chain_codes_1, *chain_codes_2}

    if not residue_types:
        residue_types_1 = {atom_label.residue.residue_name for atom_label in shifts_1}
        residue_types_2 = {atom_label.residue.residue_name for atom_label in shifts_2}
        residue_types = {*residue_types_1, *residue_types_2}

    atom_types_1 = {atom_label.atom_name for atom_label in shifts_1}
    atom_types_2 = {atom_label.atom_name for atom_label in shifts_2}
    found_atom_types = atom_types_1.intersection(atom_types_2)

    if not atom_types:
        atom_types = found_atom_types
    elif atom_types == [
        "BB",
    ]:
        bb_atom_types = {"H", "N", "CA", "CB", "C", "HA"}
        atom_types = bb_atom_types.intersection(found_atom_types)
    else:
        atom_types = set(atom_types)
        atom_types = atom_types.intersection(found_atom_types)

    # Apply filters and find common atoms
    common_shifts = _find_common_shifts(
        shifts_1,
        shifts_2,
        atom_types=atom_types,
        residue_types=residue_types,
        chain_codes=chain_codes,
    )

    # Create the correlation plot
    # TODO: isolate
    frame_1 = entry[frame_id_1]
    frame_name_1 = frame_1.name[len(frame_1.category) :].lstrip("_")
    frame_2 = entry[frame_id_2]
    frame_name_2 = frame_2.name[len(frame_2.category) :].lstrip("_")

    if len(common_shifts) == 0:
        msg = f"""
            For entry {entry.entry_id} No common chemical shifts found between the two frame_names {frame_name_1}
            {frame_name_2} with the specified filters
        """
        _info(msg)
        warn(msg)
        exit(0)

    output = str(output).format(
        entry=entry.entry_id, frame_1=frame_name_1, frame_2=frame_name_2
    )
    _setup_text_output(verbose, output)

    _info(f"entry: {entry.entry_id}")
    _info("correlation frames")
    _info(f"frame 1: {frame_name_1}")
    _info(f"frame 2: {frame_name_2}")
    _info(f"atoms: {', '.join(atom_types)}")

    _create_correlation_plot(
        common_shifts,
        frame_name_1,
        frame_name_2,
        output,
        entry.entry_id,
        show_labels=show_labels,
        title=title,
        width=width,
        height=height,
        file_format=file_format,
    )

    # Print summary
    _info(f"Created correlation plot: {output}")
    _info(f"Number of common shifts plotted: {len(common_shifts)}")

    # Calculate individual atom type correlations
    atoms = [atom for atom, _, _ in common_shifts]
    atom_types = sorted(list(set(atom.atom_name for atom in atoms)))
    values_1 = [shift_1 for _, shift_1, _ in common_shifts]
    values_2 = [shift_2 for _, _, shift_2 in common_shifts]

    correlations = []
    weights = []
    atom_correlations = {}  # Store for min/max determination

    # First pass: calculate all correlations
    for atom_type in atom_types:
        atom_indices = [
            i for i, atom in enumerate(atoms) if atom.atom_name == atom_type
        ]
        if len(atom_indices) > 1:  # Need at least 2 points for correlation
            x_vals = [values_1[i] for i in atom_indices]
            y_vals = [values_2[i] for i in atom_indices]
            atom_correlation = np.corrcoef(x_vals, y_vals)[0, 1]
            if not np.isnan(atom_correlation):  # Only include valid correlations
                correlations.append(atom_correlation)
                weights.append(len(atom_indices))  # Weight by number of data points
                atom_correlations[atom_type] = (atom_correlation, len(atom_indices))
            else:
                atom_correlations[atom_type] = (float("nan"), len(atom_indices))
        else:
            atom_correlations[atom_type] = (float("nan"), len(atom_indices))

    # Find min and max correlations
    valid_correlations = {
        k: v[0] for k, v in atom_correlations.items() if not np.isnan(v[0])
    }
    min_corr = min(valid_correlations.values()) if valid_correlations else None
    max_corr = max(valid_correlations.values()) if valid_correlations else None

    _info("\nIndividual atom type correlations:")
    for atom_type in atom_types:
        correlation, n_points = atom_correlations[atom_type]
        if not np.isnan(correlation):
            indicator = ""
            if correlation == min_corr and correlation != max_corr:
                indicator = " (min)"
            elif correlation == max_corr and correlation != min_corr:
                indicator = " (max)"
            elif correlation == min_corr and correlation == max_corr:
                indicator = " (min/max)"
            _info(f"  {atom_type}: {correlation:.3f} (n={n_points}){indicator}")
        else:
            _info(f"  {atom_type}: N/A (n={n_points})")

    # Calculate weighted mean and standard deviation of correlations
    if correlations:
        correlations = np.array(correlations)
        weights = np.array(weights)

        # Weighted mean
        weighted_mean = np.average(correlations, weights=weights)

        # Weighted standard deviation
        weighted_variance = np.average(
            (correlations - weighted_mean) ** 2, weights=weights
        )
        weighted_std = np.sqrt(weighted_variance)

        _info("\nWeighted correlation statistics:")
        _info(f"  Mean correlation: {weighted_mean:.3f} ± {weighted_std:.3f}")
    else:
        _info("\nNo valid correlations calculated")

    print(entry)


def _find_chemical_shift_frame(entry: Entry, frame_name: str) -> Optional[Saveframe]:
    """Find a chemical shift frame by name"""
    frames = select_frames(entry, [frame_name], SelectionType.ANY)

    return [frame for frame in frames if frame.category == "nef_chemical_shift_list"]


def _extract_shifts_dict(frame: Saveframe) -> Dict[AtomLabel, float]:
    """Extract chemical shifts from a frame into a dictionary keyed by AtomLabel"""
    shifts = nef_frames_to_shifts([frame])
    shifts_dict = {}

    for shift in shifts:
        # sometimes isotope and element are set sometimes they aren't
        key = replace(shift.atom, isotope_number=UNUSED, element=UNUSED)
        shifts_dict[key] = shift.value

    return shifts_dict


def _find_common_shifts(
    shifts_1: Dict[AtomLabel, float],
    shifts_2: Dict[AtomLabel, float],
    atom_types: List[str] = None,
    residue_types: List[str] = None,
    chain_codes: List[str] = None,
) -> List[Tuple[AtomLabel, float, float]]:
    """Find common shifts between two dictionaries, applying filters"""
    # TODO: doesn't allow for % or %x and %y etc

    common_shifts = []

    for atom_label, shift_1 in shifts_1.items():
        if atom_label in shifts_2:
            shift_2 = shifts_2[atom_label]

            # Apply filters
            if atom_label.atom_name not in atom_types:
                continue
            if atom_label.residue.residue_name not in residue_types:
                continue
            if atom_label.residue.chain_code not in chain_codes:
                continue

            common_shifts.append((atom_label, shift_1, shift_2))

    return common_shifts


def _create_correlation_plot(
    common_shifts: List[Tuple[AtomLabel, float, float]],
    frame_1_name: str,
    frame_2_name: str,
    output_path: Path,
    entry_id: str,
    show_labels: bool = False,
    title: str = None,
    width: float = 8.0,
    height: float = 6.0,
    file_format=".pdf",
):
    """Create and save the correlation plot with subplots for each atom type"""

    # Import plotting libraries inside function
    import warnings

    import matplotlib.pyplot as plt
    import numpy as np

    warnings.simplefilter("ignore", np.RankWarning)
    warnings.simplefilter("ignore", np.ComplexWarning)

    # Extract data for plotting
    atoms = [atom for atom, _, _ in common_shifts]
    values_1 = [shift_1 for _, shift_1, _ in common_shifts]
    values_2 = [shift_2 for _, _, shift_2 in common_shifts]

    # Group data by atom type
    atom_types = sorted(list(set(atom.atom_name for atom in atoms)))
    atom_data = {}

    for atom_type in atom_types:
        atom_indices = [
            i for i, atom in enumerate(atoms) if atom.atom_name == atom_type
        ]
        x_vals = [values_1[i] for i in atom_indices]
        y_vals = [values_2[i] for i in atom_indices]
        atom_labels = [atoms[i] for i in atom_indices]
        atom_data[atom_type] = {"x": x_vals, "y": y_vals, "labels": atom_labels}

    # Calculate grid dimensions
    n_types = len(atom_types)
    if n_types == 1:
        n_cols, n_rows = 1, 1
    elif n_types <= 4:
        n_cols, n_rows = 2, 2
    elif n_types <= 6:
        n_cols, n_rows = 3, 2
    elif n_types <= 9:
        n_cols, n_rows = 3, 3
    else:
        n_cols = 4
        n_rows = (n_types + n_cols - 1) // n_cols

    # Create figure with subplots
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(width * n_cols / 2, height * n_rows / 2)
    )

    # Handle single subplot case
    if n_types == 1:
        axes = [axes]
    else:
        axes = axes.flatten() if n_types > 1 else [axes]

    # Plot each atom type in its own subplot
    for i, atom_type in enumerate(atom_types):
        ax = axes[i]
        data = atom_data[atom_type]

        # Calculate min/max for this specific atom type data from plotted values
        if data["x"] and data["y"]:
            x_min, x_max = min(data["x"]), max(data["x"])
            y_min, y_max = min(data["y"]), max(data["y"])
            data_min = min(x_min, y_min)
            data_max = max(x_max, y_max)
            # Add small padding
            padding = (data_max - data_min) * 0.05
            axis_min = data_min - padding
            axis_max = data_max + padding
        else:
            axis_min, axis_max = 0, 1  # fallback

        # Plot scatter
        ax.scatter(data["x"], data["y"], alpha=0.7, s=30)  # , label=atom_type)

        # Add labels if requested (limit to avoid overcrowding)
        if (
            show_labels and len(data["x"]) <= 50
        ):  # Only show labels if not too many points
            for atom, x, y in zip(data["labels"], data["x"], data["y"]):
                label = (
                    f"{atom.residue.sequence_code}"  # Just sequence number, no chain
                )
                ax.annotate(
                    label,
                    (x, y),
                    xytext=(2, 2),
                    textcoords="offset points",
                    fontsize=5,
                    alpha=0.6,
                )

        # Add diagonal line and 3-sigma bands if we have data
        if data["x"] and data["y"] and len(data["x"]) > 1:
            # Calculate linear regression
            x_vals = np.array(data["x"])
            y_vals = np.array(data["y"])
            slope, intercept = np.polyfit(x_vals, y_vals, 1)

            # Calculate residuals and standard deviation
            y_pred = slope * x_vals + intercept
            residuals = y_vals - y_pred
            std_residual = np.std(residuals)

            # Calculate line points for confidence bands using this plot's axis range
            x_line = np.array([axis_min, axis_max])
            y_line = slope * x_line + intercept

            # Plot 3-sigma confidence bands
            y_upper = y_line + 3 * std_residual
            y_lower = y_line - 3 * std_residual
            ax.fill_between(
                x_line, y_lower, y_upper, alpha=0.2, color="gray", label="3σ band"
            )

            # Perfect correlation line (diagonal)
            ax.plot(
                [axis_min, axis_max],
                [axis_min, axis_max],
                "k--",
                alpha=0.3,
                linewidth=1,
                label="Perfect correlation",
            )

            # Find outliers (more than 3 sigma away from regression line)
            outlier_indices = np.abs(residuals) > 3 * std_residual

            # Determine if we have multiple chains
            chains = set(atom.residue.chain_code for atom in data["labels"])
            multiple_chains = len(chains) > 1

            # Label outliers with non-overlapping positioning
            outlier_points = []
            outlier_labels = []
            for j, is_outlier in enumerate(outlier_indices):
                if is_outlier:
                    atom = data["labels"][j]
                    x, y = data["x"][j], data["y"][j]
                    if multiple_chains:
                        label = (
                            f"{atom.residue.chain_code}.{atom.residue.sequence_code}"
                        )
                    else:
                        label = f"{atom.residue.sequence_code}"
                    outlier_points.append((x, y))
                    outlier_labels.append(label)

            # Position labels above and to the left of points
            for i, ((x, y), label) in enumerate(zip(outlier_points, outlier_labels)):
                # Always position labels above and to the left (-15, +15)
                offset_x = -8
                offset_y = 8
                ax.annotate(
                    label,
                    (x, y),
                    xytext=(offset_x, offset_y),
                    textcoords="offset points",
                    fontsize=6,
                    fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.9),
                )

            # Add atom type title in top-left corner (14pt)
            ax.text(
                0.05,
                0.95,
                f"{atom_type}",
                transform=ax.transAxes,
                verticalalignment="top",
                fontsize=14,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7),
            )

            # Calculate correlation for this atom type (bottom-right box)
            with np.errstate(divide="ignore", invalid="ignore"):
                correlation = np.corrcoef(data["x"], data["y"])[0, 1]
            ax.text(
                0.95,
                0.05,
                f"R={correlation:.2f}",
                transform=ax.transAxes,
                verticalalignment="bottom",
                horizontalalignment="right",
                fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7),
            )

        # Set equal axis limits for this subplot (same min/max for both x and y)
        if axis_min != axis_max:
            ax.set_xlim(axis_min, axis_max)
            ax.set_ylim(axis_min, axis_max)
        else:
            warn(f"equal axis min and max for {entry_id} {atom_type}")

        # Set identical tick locations for both axes
        import matplotlib.ticker as ticker

        tick_locator = ticker.MaxNLocator(nbins=6, prune="both")
        ax.xaxis.set_major_locator(tick_locator)
        ax.yaxis.set_major_locator(tick_locator)

        # Force the same tick locations on both axes
        ax.set_xticks(ax.get_xticks())
        ax.set_yticks(ax.get_xticks())  # Use x-ticks for y-axis too

        # Format tick labels to show integers only
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))

        # Set labels with frame names
        ax.set_xlabel(f"{frame_1_name} (ppm)", fontsize=10)
        ax.set_ylabel(f"{frame_2_name} (ppm)", fontsize=10)

        # Grid
        ax.grid(True, alpha=0.3)

        # Equal aspect ratio
        ax.set_aspect("equal", adjustable="box")

    # Hide unused subplots
    for i in range(n_types, len(axes)):
        axes[i].set_visible(False)

    # Overall title
    if title is None:

        # Get unique chain codes from the data
        chain_codes = sorted(
            list(set(atom.residue.chain_code for atom, _, _ in common_shifts))
        )
        chain_str = (
            f"Chain{'s' if len(chain_codes) > 1 else ''} {', '.join(chain_codes)}"
        )

        title = f"Chemical Shift Correlation: {entry_id} - {chain_str} {frame_1_name} vs {frame_2_name}"

    fig.suptitle(title, fontsize=14, fontweight="bold")

    # Adjust layout
    plt.subplots_adjust(
        top=0.90, hspace=0.4, wspace=0.3
    )  # Make room for suptitle and spacing

    # Save the plot
    plt.savefig(f"{output_path}{file_format}", dpi=300)
    plt.close()


def _setup_text_output(verbose, output):
    global _out, _verbose
    _verbose = verbose
    _out = open(f"{output}.txt", "w")


def _tear_down_output():
    _out.close()


def _info(msg):
    if _verbose:
        info(msg)
    if _out:
        print(msg, file=_out)
