import sys
from itertools import zip_longest
from pathlib import Path
from typing import Optional

from pynmrstar import Entry
from io import StringIO
from fnmatch import fnmatch

def run_and_read_pytest(args):
    from pytest import main
    original_output = sys.stdout
    original_error = sys.stdout
    sys.stdout = StringIO()
    sys.stderr = StringIO()

    main(args)

    output = sys.stdout.getvalue()
    error_output = sys.stderr.getvalue()

    sys.stdout.close()
    sys.stderr.close()
    sys.stdout = original_output
    sys.stderr = original_error

    return output, error_output


def _split_test_spec(spec):
    spec_parts = spec.split('::')
    spec_parts[0] = Path(spec_parts[0])

    return spec_parts


def select_matching_tests(tests, selectors):
    results = []

    for selector in selectors:

        selector_parts = _split_test_spec(selector)
        num_selector_parts = len(selector_parts)

        if num_selector_parts == 1:
            selector = f'*::{selector_parts[0]}'
            selector_parts = _split_test_spec(selector)
            num_selector_parts = len(selector_parts)

        if num_selector_parts == 2 and selector_parts[0] == Path(''):
            selector = f'*::{selector_parts[1]}'
            selector_parts = _split_test_spec(selector)
            num_selector_parts = len(selector_parts)

        if num_selector_parts ==  2 and selector_parts[1] == '':
            selector = f'{selector_parts[0]}::*'
            selector_parts = _split_test_spec(selector)
            num_selector_parts = len(selector_parts)

        selector_path_parts = selector_parts[0].parts
        num_selector_path_parts = len(selector_path_parts)

        for test in tests:

            test_parts = _split_test_spec(test)
            num_test_parts = len(test_parts)
            test_path_parts = test_parts[0].parts
            num_test_path_parts = len(test_path_parts)

            paths_equal = False
            if num_selector_path_parts <= num_test_path_parts:
                selector_path = selector_path_parts[-num_selector_path_parts:]
                test_path = test_path_parts[-num_selector_path_parts:]
                paths_equal = selector_path == test_path


            path = str(test_parts[0])
            path_test = str(selector_parts[0])

            if not paths_equal:
                paths_equal = fnmatch(path, path_test)

            test_names_equal = False
            if (num_selector_parts == 2) and (num_test_parts == 2):
                test_names_equal = fnmatch(test_parts[-1], selector_parts[-1])

            if paths_equal and test_names_equal:
                results.append(test)
    return results


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
