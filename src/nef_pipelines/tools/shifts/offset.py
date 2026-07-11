from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from fnmatch import fnmatchcase
from pathlib import Path
from typing import List, Optional, Set, Tuple

import typer
from pynmrstar import Entry

from nef_pipelines.lib.isotope_lib import ATOM_TO_ISOTOPE, CODE_TO_ISOTOPE
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.util import STDIN, exit_error, warn
from nef_pipelines.tools.shifts import shifts_app


def _get_sign_str(num):
    return "-" if num < 0 else "+"


class ShiftOffsetTarget(Enum):
    ISOTOPE = auto()
    ATOM = auto()


@dataclass(frozen=True)
class ShiftOffsetBase(ABC):
    target: str
    offset: float

    @property
    @abstractmethod
    def _data(self):
        pass

    def __str__(self) -> str:
        return f"{self._data}{_get_sign_str(self.offset)}{abs(self.offset)}"


@dataclass(frozen=True)
class IsotopeShiftOffset(ShiftOffsetBase):
    element: str
    isotope_number: Optional[int] = None

    @property
    def _data(self) -> str:
        # Handles None gracefully if isotope_number isn't provided
        iso = self.isotope_number if self.isotope_number is not None else ""
        return f"{self.element}{iso}"


@dataclass(frozen=True)
class AtomShiftOffset(ShiftOffsetBase):
    atom_selector: str

    @property
    def _data(self) -> str:
        return f"{self.atom_selector}"


@shifts_app.command()
def offset(
    in_path: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="input NEF data [- is stdin]",
    ),
    frame_selectors: List[str] = typer.Option(
        [],
        "--frame",
        "-f",
        metavar="FRAME",
        help="shift list frame(s) to apply offsets to [default: all]",
    ),
    exact_atom: bool = typer.Option(
        False,
        "--exact-atom",
        help="exact atom name matching (no wildcards): CA matches only CA, not CA1 or CA2",
    ),
    offset_specs: List[str] = typer.Argument(
        ...,
        metavar="OFFSET_SPEC",
        help="atom_pattern+value or atom_pattern-value  e.g. 'C+0.07' or 'CA-1.0'",
    ),
):
    """
    offset chemical shifts by atom name

    Each OFFSET_SPEC is atom_pattern+value or atom_pattern-value

    Atom pattern rules:
      1. atom names:        HA, HA1, CA, N, H...  atom name match with wildcards: HA matches HA, HA1 and HA2,
                            CB, CB* etc  ...
      2. isotope codes      13C, 15N              only shifts for the correct atom type and isotope
      3. exact atom names   --exact-atom          disable wildcards: CA matches only CA, not CA1, CA2


    All matching specs are accumulated.
    Multiple specs can be given as separate arguments or comma-separated in one string.
    If the isotope ane element column aren't populated the code falls back to looking for atom names...

    Examples:
    ```bash
      nef shifts offset 'C+0.07,13C+0.05,15N-0.44'         # all carbons +0.07, 13C atoms also get +0.05 (total +0.12)
      nef shifts offset 'C+0.07' '13C+0.05' '15N-0.44'     # same, space-separated
      nef shifts offset --exact-atom 'CA+1.0'              # only CA, not CA1 or CA2
      nef shifts offset 'C+1.0,C+2.0'                      # WARNING: duplicate pattern 'C', accumulates to +3.0
    ```
    """
    entry = read_entry_from_file_or_stdin_or_exit_error(in_path)
    parsed_offsets = _parse_specs_or_exit_error(offset_specs)
    result = pipe(entry, parsed_offsets, frame_selectors, exact_atom)
    print(result)


def pipe(
    entry: Entry,
    offsets: List[ShiftOffsetBase],
    frame_selectors: Optional[List[str]] = None,
    exact_atom: bool = False,
) -> Entry:
    """Apply offset to chemical shifts in NEF entry.

    Args:
        entry: NEF entry containing chemical shifts
        offsets: list of parsed ShiftOffset instances
        frame_selectors: optional list of frame name patterns to filter
        exact_atom: if True, disable automatic wildcard matching

    Returns:
        Modified NEF entry with offsets applied
    """
    if not offsets:
        warn("no offset specs provided - file will pass through unchanged")
        return entry

    for frame in _get_shift_frames(entry, frame_selectors or []):
        _apply_offsets_to_frame(frame, offsets, exact_atom)

    return entry


def _get_shift_frames(entry: Entry, frame_selectors: List[str]):
    """Yield shift frames matching selectors."""
    for frame in entry.frame_dict.values():
        if frame.category != "nef_chemical_shift_list":
            continue
        if frame_selectors and not any(
            fnmatchcase(frame.name, s) for s in frame_selectors
        ):
            continue
        try:
            frame.get_loop("nef_chemical_shift")
            yield frame
        except KeyError:
            continue


def _apply_offsets_to_frame(frame, offsets: List[ShiftOffsetBase], exact_atom: bool):
    """Apply offsets to all atoms in a shift frame."""
    loop = frame.get_loop("nef_chemical_shift")

    atom_idx = loop.tag_index("atom_name")
    val_idx = loop.tag_index("value")
    element_idx = loop.tag_index("element")
    isotope_idx = loop.tag_index("isotope_number")

    # Warn about missing columns
    if element_idx is None:
        warn(
            f"frame '{frame.name}': element column missing - "
            + "extracting elements from atom names"
        )

    if isotope_idx is None and _has_isotope_offsets(offsets):
        warn(
            f"frame '{frame.name}': isotope_number column missing - "
            + "isotope-specific patterns will not match"
        )

    # Apply offsets to each row
    for row in loop:
        if row[val_idx] in (UNUSED, ".", ""):
            continue

        atom = row[atom_idx]
        atom_element = (
            row[element_idx]
            if element_idx is not None
            else _extract_element_from_atom_name(atom)
        )
        atom_isotope = row[isotope_idx] if isotope_idx is not None else None

        total_offset = _calculate_total_offset(
            atom, atom_element, atom_isotope, offsets, exact_atom
        )

        if total_offset != 0.0:
            row[val_idx] = str(float(row[val_idx]) + total_offset)


def _has_isotope_offsets(offsets: List[ShiftOffsetBase]) -> bool:
    """Check if any isotope-specific patterns were requested."""
    return any(
        isinstance(o, IsotopeShiftOffset) and o.isotope_number is not None
        for o in offsets
    )


def _calculate_total_offset(
    atom: str,
    atom_element: str,
    atom_isotope: Optional[str],
    offsets: List[ShiftOffsetBase],
    exact_atom: bool,
) -> float:
    """Sum all matching offsets for an atom."""
    return sum(
        spec.offset
        for spec in offsets
        if _atom_matches_spec(spec, atom, atom_isotope, atom_element, exact_atom)
    )


def _parse_specs_or_exit_error(raw: List[str]) -> List[ShiftOffsetBase]:
    """Parse 'atom+value' or 'atom-value' specs into ShiftOffset instances.

    Args:
        raw: List of raw spec strings (can contain comma-separated specs)

    Returns:
        List of ShiftOffsetBase instances (IsotopeShiftOffset or AtomShiftOffset)
    """
    result = []
    seen_patterns: Set[Tuple[str, Optional[int]]] = set()

    for item in raw:
        for spec in item.split(","):
            spec = spec.strip()
            if not spec:
                continue

            pattern, value = _split_spec_pattern_and_value_exit_error(spec)
            offset_instance = _create_offset_from_pattern(pattern, value)
            pattern_key = _get_pattern_key(offset_instance)

            _check_and_warn_duplicate(pattern_key, seen_patterns, pattern)
            seen_patterns.add(pattern_key)
            result.append(offset_instance)

    return result


def _split_spec_pattern_and_value_exit_error(spec: str) -> tuple[str, float]:
    """Split spec into pattern and value parts.

    Args:
        spec: Spec string like 'C+1.0' or 'HA*-0.5'

    Returns:
        Tuple of (pattern, value)
    """
    # Find the last +/- sign (it's the delimiter)
    split_idx = -1
    for i in range(len(spec) - 1, 0, -1):
        if spec[i] in ("+", "-"):
            split_idx = i
            break

    if split_idx == -1:
        exit_error(
            f"offset spec {spec!r} must be atom_pattern+value or atom_pattern-value "
            + "e.g. 'C+0.07' or 'CA-1.0'"
        )

    pattern = spec[:split_idx].strip()
    val_str = spec[split_idx:].strip()

    if not pattern:
        exit_error(f"missing atom pattern in spec {spec!r}")

    try:
        value = float(val_str)
    except ValueError:
        exit_error(f"offset value {val_str!r} is not a number in spec {spec!r}")

    return pattern, value


def _create_offset_from_pattern(pattern: str, value: float) -> ShiftOffsetBase:
    """Create appropriate offset instance from pattern and value.

    Args:
        pattern: Pattern like '13C', 'C', or 'HA*'
        value: Offset value

    Returns:
        IsotopeShiftOffset or AtomShiftOffset instance
    """
    if pattern in CODE_TO_ISOTOPE:
        # Isotope code like "13C" or "15N"
        isotope = CODE_TO_ISOTOPE[pattern]
        element = str(isotope).lstrip("0123456789")
        isotope_number = int(str(isotope).rstrip(element))
        return IsotopeShiftOffset(
            target=ShiftOffsetTarget.ISOTOPE.name,
            offset=value,
            element=element,
            isotope_number=isotope_number,
        )

    # Check if it's a simple element (single letter)
    if len(pattern) == 1 and pattern in ATOM_TO_ISOTOPE:
        return IsotopeShiftOffset(
            target=ShiftOffsetTarget.ISOTOPE.name,
            offset=value,
            element=pattern,
            isotope_number=None,
        )

    # Atom name pattern like "CA", "HA*", etc.
    return AtomShiftOffset(
        target=ShiftOffsetTarget.ATOM.name,
        offset=value,
        atom_selector=pattern,
    )


def _get_pattern_key(offset_spec: ShiftOffsetBase) -> Tuple[str, Optional[int]]:
    """Get pattern key for duplicate detection.

    Args:
        offset_spec: ShiftOffset instance

    Returns:
        Tuple of (pattern_string, isotope_number or None)
    """
    if isinstance(offset_spec, IsotopeShiftOffset):
        return offset_spec.element, offset_spec.isotope_number
    elif isinstance(offset_spec, AtomShiftOffset):
        return offset_spec.atom_selector, None
    else:
        raise TypeError(f"Unknown offset type: {type(offset_spec)}")


def _check_and_warn_duplicate(
    pattern_key: Tuple[str, Optional[int]], seen_patterns: Set, pattern: str
):
    """Check for duplicate pattern and warn if found.

    Args:
        pattern_key: Pattern key tuple
        seen_patterns: Set of already seen pattern keys
        pattern: Original pattern string for warning message
    """
    if pattern_key in seen_patterns:
        warn(f"duplicate pattern {pattern!r} - offsets will be accumulated")


def _extract_element_from_atom_name(atom_name: str) -> str:
    """Extract element symbol from atom name using isotope_lib knowledge.

    Args:
        atom_name: atom name like CA, CB, HA, N, H

    Returns:
        element symbol (C, H, N, etc.)

    Examples:
        CA → C
        CB → C
        HA → H
        N → N
    """
    if not atom_name:
        return ""

    # Try known single-letter elements from ATOM_TO_ISOTOPE
    first_char = atom_name[0].upper()
    if first_char in ATOM_TO_ISOTOPE:
        return first_char

    # For unknown elements, return first character
    return first_char


def _atom_matches_spec(
    offset_spec: ShiftOffsetBase,
    atom: str,
    atom_isotope: Optional[str],
    atom_element: str,
    exact_atom: bool = False,
) -> bool:
    """Check if an atom matches the given offset specification.

    Args:
        offset_spec: IsotopeShiftOffset or AtomShiftOffset specification
        atom: atom name from the shift list (e.g., 'CA', 'CB', 'N')
        atom_isotope: isotope number from the shift row (as string) or None/empty
        atom_element: element symbol from row or extracted from atom name
        exact_atom: if True, use exact matching (no automatic wildcard)

    Returns:
        True if the atom matches the offset specification
    """
    if isinstance(offset_spec, IsotopeShiftOffset):
        # Check isotope constraint if specified AND atom has isotope data
        if (
            offset_spec.isotope_number is not None
            and atom_isotope
            and atom_isotope not in (".", "")
        ):
            try:
                atom_isotope_int = int(atom_isotope)
            except ValueError:
                return False
            if atom_isotope_int != offset_spec.isotope_number:
                return False

        # Check if atom's element matches
        if not fnmatchcase(atom_element, offset_spec.element):
            return False

        # For isotope specs, match by element (e.g., "13C" matches all C atoms)
        if exact_atom:
            return fnmatchcase(atom, offset_spec.element)
        return fnmatchcase(atom, offset_spec.element + "*")

    elif isinstance(offset_spec, AtomShiftOffset):
        # Extract element from atom selector
        element = _extract_element_from_atom_name(offset_spec.atom_selector.rstrip("*"))

        # Check if atom's element matches
        if not fnmatchcase(atom_element, element):
            return False

        # Match by atom name pattern
        if exact_atom:
            return fnmatchcase(atom, offset_spec.atom_selector)
        return fnmatchcase(atom, offset_spec.atom_selector + "*")

    return False
