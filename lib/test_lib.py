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
    for i, (expected_line, header_line) in enumerate(zip_lines):
        if display:
            print(f'exp|{i}|', expected_line.strip())
            print(f'rep|{i}|', header_line.strip())
            print()

        assert expected_line.strip() == header_line.strip()


def isolate_frame(target: str, name: str) -> Optional[str]:
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
        entry = Entry.from_string(target)
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


def root_path(initial_path: str):
    """ given a path wotk up the directory structure till you find the d
        directory containg the nef executable

        initial_path (str): the path to start searching from
    """

    target = Path(initial_path)

    while not (target / 'nef').is_file():
        target = target.parent

    return target



def path_in_test_data(root: str, file_name: str, local: bool = True) -> str:
    """
    given a root and a file name find the relative to the file
    in the parents test_data directory

    Args:
        root (str): root of the path
        file_name (str): the name of the file
        local (bool): whether to use the directory of the tool
        or read from the global test data

    Returns:
        str: the target paths as a string
    """

    if not local:
        test_data = root_path(root) / 'test_data'
    else:
        test_data = path_in_parent_directory(root, 'test_data')

    return str(Path(test_data, file_name).absolute())
