from itertools import zip_longest
from typing import Optional

from pynmrstar import Entry


def assert_lines_match(expected: str, reported: str,  display:bool=False):
    """
    compare two multi line strings line by line with stripping

    Args:
        expected (str): the expected string
        reported (str): the input string

    Returns:
        None
    """
    zip_lines = zip_longest(expected.split('\n'), reported.split('\n'), fillvalue='')
    for i,(expected_line, header_line) in enumerate(zip_lines):
        if display:
            print(f'exp|{i}|',expected_line.strip())
            print(f'rep|{i}',header_line.strip())
            print()

        assert expected_line.strip() == header_line.strip()


def isolate_frame(target: Entry, name: str) -> Optional[str]:
    """
    Extract one frame from a NEF file by name as a sting
    Args:
        target (Entry): target NEF entry
        name (str): name of the save frame

    Returns:
        Optional[str]: the entry or a None if not found
    """
    entry = None
    try:
        entry = Entry.from_string(target.stdout)
        entry = str(entry.get_saveframe_by_name(name))
    except:
        pass

    return entry
