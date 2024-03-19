from enum import Enum


class StereoAssignmentHandling(Enum):
    ALL_AMBIGUOUS = "all-ambiguous"
    AS_ASSIGNED = "as-assigned"
    AUTO = "auto"

    def __str__(self):
        return self._name_.lower().replace("_", "-")
