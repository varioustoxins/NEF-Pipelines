import sys
import traceback
from fnmatch import fnmatch
from io import StringIO
from itertools import zip_longest
from pathlib import Path
from typing import IO, AnyStr, List, Optional, Tuple, Union

from click.testing import Result
from pynmrstar import Entry
from typer import Typer
from typer.testing import CliRunner

NOQA_E501 = "# noqa: E501"


def read_test_data(file_path: str, root_directory: Optional[str] = None) -> str:
    """
    Reads the content of a test data file from standard locations.

    This function reads the content of a test data file located at the given file path.
    If a root directory is provided, the function will consider the file path to be relative to this directory
    using the function path_in_test_data for lookup.

    Args:
        file_path (str): The path to the test data file.
        root_directory (Optional[str], optional): The root directory from which the file path is considered to be
                                                  relative.
                                                  If None, the file path is considered to be absolute.

    Returns:
        str: The content of the test data file.
    """

    file_path = (
        path_in_test_data(root_directory, file_path) if root_directory else file_path
    )
    with open(file_path) as sequence_stream:
        sequence_stream = sequence_stream.read()
    return sequence_stream


def run_and_read_pytest(args: List[str]) -> Tuple[int, str, str]:
    """
    Runs pytest with the provided arguments and captures the output.

    This function runs pytest with the given arguments and captures the return code,
    standard output, and standard error output. It temporarily redirects sys.stdout
    and sys.stderr to capture the output.

    Args:
        args (List[str]): The arguments to pass to pytest.

    Returns:
        Tuple[int, str, str]: the return code, standard output,
        and standard error output from pytest.
    """
    from pytest import main

    original_output = sys.stdout
    original_error = sys.stdout
    sys.stdout = StringIO()
    sys.stderr = StringIO()

    retcode = main(args)

    output = sys.stdout.getvalue()
    error_output = sys.stderr.getvalue()

    sys.stdout.close()
    sys.stderr.close()
    sys.stdout = original_output
    sys.stderr = original_error

    return retcode, output, error_output


def _split_test_spec(spec):
    spec_parts = spec.split("::")
    spec_parts[0] = Path(spec_parts[0])

    return spec_parts


def select_matching_tests(tests, selectors):
    results = []

    for selector in selectors:

        selector_parts = _split_test_spec(selector)
        num_selector_parts = len(selector_parts)

        if num_selector_parts == 1:
            selector = f"*::{selector_parts[0]}"
            selector_parts = _split_test_spec(selector)
            num_selector_parts = len(selector_parts)

        if num_selector_parts == 2 and selector_parts[0] == Path(""):
            selector = f"*::{selector_parts[1]}"
            selector_parts = _split_test_spec(selector)
            num_selector_parts = len(selector_parts)

        if num_selector_parts == 2 and selector_parts[1] == "":
            selector = f"{selector_parts[0]}::*"
            selector_parts = _split_test_spec(selector)
            num_selector_parts = len(selector_parts)

        selector_path_parts = selector_parts[0].parts
        num_selector_path_parts = len(selector_path_parts)

        for test in tests:

            # here we ensure we are looking for a .py file...
            if not selector_path_parts[-1].endswith("py"):
                selector_path_parts = list(selector_path_parts)
                selector_path_parts[-1] = f"{selector_path_parts[-1]}.py"
            selector_path_parts = tuple(selector_path_parts)

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


def assert_lines_match(
    expected: str, reported: str, squash_spaces: bool = True, ignore_empty=True
):
    """
    compare two multi line strings line by line with stripping and raise an assertion if they don't match
    note: empty lines are ignoresd by default, and multiple spaces are squashed
    Args:
        expected (str): the expected string
        reported (str): the input string
        squash_spaces (bool): remove duplicate spaces before comparison

    Returns:
        None
    """
    lines_expected = expected.split("\n")
    lines_reported = reported.split("\n")

    if ignore_empty:
        lines_expected = [line for line in lines_expected if len(line.strip()) != 0]
        lines_reported = [line for line in lines_reported if len(line.strip()) != 0]

    zip_lines = zip_longest(lines_expected, lines_reported, fillvalue="")
    for i, (expected_line, reported_line) in enumerate(zip_lines, start=1):

        expected_line_stripped = expected_line.strip()
        reported_line_stripped = reported_line.strip()

        if squash_spaces:
            expected_line_stripped = " ".join(expected_line_stripped.split())
            reported_line_stripped = " ".join(reported_line_stripped.split())

        if reported_line_stripped != expected_line_stripped:

            for line_no, line in enumerate(lines_expected, start=1):
                print(f"exp|{line_no}|{line}")
            print()

            for line_no, line in enumerate(lines_reported, start=1):
                print(f"rep|{line_no}|{line}")
            print()

            print("line that caused the error:")
            print()

            print(f"exp|{i}| {expected_line.strip()}|")
            print(f"rep|{i}| {reported_line.strip()}|")

        assert reported_line_stripped == expected_line_stripped


def isolate_frame(target: str, frame_name: str) -> Optional[str]:
    """
    Extract one frame from a NEF file by name as a string
    Args:
        target (Entry): target NEF entry
        frame_name (str): name of the save frame

    Returns:
        Optional[str]: the entry or a None if not found
    """

    entry = Entry.from_string(target)
    try:
        frame = entry.get_saveframe_by_name(frame_name)
    except KeyError as e:
        msg = f"""
             the save frame {frame_name} wasn't found in the entry {entry.entry_id} the
             available_frame names are {','.join([frame.name for frame in entry.frame_list])}'
         """
        raise KeyError(msg) from e

    return str(frame)


def isolate_loop(target: str, frame_name: str, loop_category: str) -> Optional[str]:
    """
    Extract one frame from a NEF file by name as a string
    Args:
        target (Entry): target NEF entry
        frame_name (str): name of the save frame
        loop_category (str): the name of the loop

    Returns:
        Optional[str]: the frame as a string or None if it is not found
    """

    entry = Entry.from_string(target)

    try:
        frame = entry.get_saveframe_by_name(frame_name)
    except KeyError as e:
        msg = f"""
            the save frame {frame_name} wasn't found in the entry {entry.entry_id} the
            available_frame names are {','.join([frame.name for frame in entry.frame_list])}'
        """
        raise KeyError(msg) from e

    try:
        loop = str(frame.get_loop(loop_category))
    except KeyError as e:
        msg = f"""
            the loop  {loop_category} wasn't found in the frame {frame.name} in entry {entry.entry_id} the
            available_loop categories are {','.join([loop.category for loop in frame.loops])}'
        """
        raise KeyError(msg) from e

    return str(loop)


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
    """given a path work up the directory structure till you find the
    directory containing the nef executable

    initial_path (str): the path to start searching from
    """

    target = Path(initial_path)

    belt_and_braces = 100  # noqa: F841 this appears to be a bug
    while (
        not (Path(target.root) == target)
        and not (target / "nef_pipelines" / "main.py").is_file()
    ):
        target = target.parent
        belt_and_braces -= 1
        if belt_and_braces < 0:
            msg = f"""\
                Error, while search for the rot of the path {initial_path} i walked up 100
                directories this looks like a bug!
            """
            raise Exception(msg)

    target /= "nef_pipelines"

    return target


# TODO: remove local we now use a hierarchical search
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

    test_data_root = root_path(root) / "tests" / "test_data"
    test_data_local = path_in_parent_directory(root, "test_data")

    if (Path(test_data_local) / file_name).is_file():
        test_data = test_data_local
    else:
        test_data = test_data_root

    # TODO: add an error on shadowing global files

    return str(Path(test_data, file_name).absolute())


def run_and_report(
    typer_app: Typer,
    args: List[str],
    input: IO[AnyStr] = None,
    expected_exit_code: int = 0,
) -> Result:
    """
    run a typer app in the typer test harness and report exceptions and stdout to screen if there is an error
    :param typer_app: the typer app hosting the application
    :param args: command line arguments for the app
    :param input: an input stream if required
    :param expected_exit_code: what exit code to expect if the app is expected to end with an error
    :return: results object
    """

    runner = CliRunner()
    result = runner.invoke(typer_app, args, input=input)

    if result.exit_code != expected_exit_code:
        print("\n", "-" * 40, "-stdout-", "-" * 40)
        print(result.stdout)
        if result.exception:
            print("-" * 40, "exception", "-" * 40)
            formatted = list(traceback.TracebackException(*result.exc_info).format())

            # TODO: this is a hack, I would love to have a better solution!
            if "SystemExit" in formatted[-1]:
                for i, line in enumerate(reversed(formatted)):
                    if (
                        "During handling of the above exception, another exception occurred"
                        in line
                    ):
                        break
                formatted = formatted[: -i - 2]
            print("".join(formatted))

        print("-" * 40, "-" * 9, "-" * 40)

    assert result.exit_code == expected_exit_code

    return result


def assert_frame_category_exists(
    entry: Union[Entry, str], category: str, count: int = 1, exact: bool = False
):
    """
    Asserts that the specified category exists in the given entry and
    additionally that the number of frames in that category is greater than the
    expected count if the count is specified. If you want to use an exact count
    set exact to True.

    Args:
        entry (Entry): The NEF entry to check.
        category (str): The category to look for in the entry.
        count (int, optional): The expected number of frames in the category. Defaults to 1.
        exact (bool, optional): If True, the number of frames with the category must match the expected count exactly.
    Raises:
        AssertionError: If the number of frames with the category does not match the expected count.
    """

    """
      Asserts that the specified category exists in the given entry and that the number of frames in that category
      matches the expected count [default >1].

      This function checks if the specified category exists in the given NEF entry. If the category exists, it then
      checks if the number of frames in that category is greater than or equal to the expected count. If the 'exact'
      parameter is set to True, the function checks if the number of frames in the category exactly matches
      the expected count.

      Args:
          entry (Union[Entry, str]): The NEF entry to check. This can be an Entry object or a string.
          category (str): The category to look for in the entry.
          count (int, optional): The expected number of frames in the category. Defaults to 1.
          exact (bool, optional): If True, the number of frames with the category must match the expected
          count exactly. Defaults to False.

      Raises:
          AssertionError: If the number of frames with the category does not match the expected count.
      """

    if isinstance(entry, str):
        entry = Entry.from_string(entry)
    globals_frames = entry.get_saveframes_by_category(category)
    if exact:
        assert len(globals_frames) == count
    else:
        assert len(globals_frames) >= count
