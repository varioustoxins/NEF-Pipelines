from typing import NamedTuple


class SequenceResidue(NamedTuple):
    chain: str
    residue_number: int
    residue_name: str
