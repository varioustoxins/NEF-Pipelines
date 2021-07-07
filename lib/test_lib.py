from itertools import zip_longest
from pathlib import Path
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


def path_in_parent_directory(root: str, target: str) -> str:
    """
    given a root and a relative path find the relative file path

    Args:
        root (str): root of the path
        target (str): the relative path from the root

    Returns:
        str: the target paths as a string
    """
    parent_path = Path(root).parent
    return str(Path(parent_path, target).absolute())


def path_in_test_data(root: str, file_name: str) -> str:
    """
    given a root and a file name find the relative to the file
    in the parents test_data directory

    Args:
        root (str): root of the path
        file_name (str): the name of the file

    Returns:
        str: the target paths as a string
    """

    test_data = path_in_parent_directory(root, 'test_data')
    return str(Path(test_data, file_name).absolute())
