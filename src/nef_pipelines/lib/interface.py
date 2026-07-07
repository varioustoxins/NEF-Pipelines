"""
    Shared interface types: logging levels, fit-type enums, noise-info dataclass used across CLI commands.
"""

# TODO these snhould most probably move to structures

from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Optional

from strenum import LowercaseStrEnum


class LoggingLevels(IntEnum):
    WARNING = 0
    INFO = 1
    DEBUG = 2
    ALL = 3


class FitType(LowercaseStrEnum):
    NON_LINEAR = auto()
    LINEAR = auto()


class NoiseInfoSource(LowercaseStrEnum):
    CLI = auto()
    REPLICATES = auto()
    NONE = auto()


class FailureHandling(LowercaseStrEnum):
    FAIL = auto()  # Raise exception when fit fails DOF check
    WARN = auto()  # Log warning and continue


class FailureOutput(LowercaseStrEnum):
    COMMENT = auto()  # Output row with UNUSED values and fit_status="insufficient_dof"
    SKIP = auto()  # Skip row entirely, no output


@dataclass
class NoiseInfo:
    source: Optional[NoiseInfoSource]
    noise: float
    fraction_error_in_noise: Optional[float] = None
    num_replicates: int = 0
    requested_noise_source: Optional[NoiseInfoSource] = None
