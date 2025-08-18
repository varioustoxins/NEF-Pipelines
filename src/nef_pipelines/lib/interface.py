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


@dataclass
class NoiseInfo:
    source: Optional[NoiseInfoSource]
    noise: float
    fraction_error_in_noise: Optional[float] = None
    num_replicates: int = 0
    requested_noise_source: Optional[NoiseInfoSource] = None
