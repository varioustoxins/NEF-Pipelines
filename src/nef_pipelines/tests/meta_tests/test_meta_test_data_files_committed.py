import ast
import shutil
import subprocess
from pathlib import Path

import pytest


def _find_project_root() -> Path:
    """\
    Find the project root by locating the directory containing src/nef_pipelines.

    Walks up from the current file until it finds the project structure.
    """
    current = Path(__file__).resolve()

    # Walk up the directory tree
    for parent in current.parents:
        if (parent / "src" / "nef_pipelines").exists():
            return parent

    # Fallback - shouldn't happen in normal usage
    raise RuntimeError("Could not find project root (src/nef_pipelines directory)")


def _extract_test_data_references(test_file: Path) -> list[str]:
    """\
    Extract all test data file references from a test file using AST.

    Finds calls to read_test_data() and path_in_test_data() and extracts
    the filename argument (first string literal).
    """
    try:
        with open(test_file) as f:
            tree = ast.parse(f.read(), filename=str(test_file))
    except SyntaxError:
        return []

    filenames = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check if it's a call to read_test_data or path_in_test_data
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in ("read_test_data", "path_in_test_data"):
                # path_in_test_data(root, file_name) — filename is args[1]
                # read_test_data(file_name, ...) — filename is args[0]
                arg_index = 1 if func_name == "path_in_test_data" else 0
                if len(node.args) > arg_index and isinstance(
                    node.args[arg_index], ast.Constant
                ):
                    if isinstance(node.args[arg_index].value, str):
                        filenames.append(node.args[arg_index].value)

    return filenames


def _get_git_tracked_filenames() -> set[str]:
    """\
    Get set of all filenames tracked by git in the tests directory.

    Returns just the filename (not full path) for simple existence checking.

    Raises:
        pytest.fail: If git is not available or fails
    """
    # Check if git is available
    if not shutil.which("git"):
        pytest.fail(
            "git command not found in PATH. This test requires git to be available."
        )

    try:
        # Get all tracked files (no path filter - works from any directory)
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
            cwd=_find_project_root(),
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        pytest.fail(f"git command failed: {e}")

    # Filter for files in tests directory and extract just the filename
    tracked_filenames = set()
    for line in result.stdout.splitlines():
        # Only include files under tests/
        if "/tests/" in line or line.startswith("tests/"):
            tracked_filenames.add(Path(line).name)

    return tracked_filenames


def test_all_test_data_files_in_git():
    """\
    Meta-test: Verify all test data files referenced in tests are tracked in git.

    Uses AST to parse test files and extract references to read_test_data() and
    path_in_test_data() calls, then verifies those files exist in git.

    Note: This checks only that the filename exists in git somewhere under tests/.
    The actual path resolution is handled by read_test_data()/path_in_test_data().
    """
    tests_dir = Path(__file__).parent.parent

    # Find all test files
    test_files = list(tests_dir.rglob("test_*.py"))

    # Get all git-tracked filenames
    git_filenames = _get_git_tracked_filenames()

    # Extract all referenced test data files
    all_references = {}
    for test_file in test_files:
        filenames = _extract_test_data_references(test_file)
        for filename in filenames:
            all_references.setdefault(filename, []).append(
                test_file.relative_to(tests_dir)
            )

    # Check which files are missing from git
    missing_files = {
        filename: test_files_list
        for filename, test_files_list in all_references.items()
        if filename not in git_filenames
    }

    # Report any missing files with debug info
    if missing_files:
        error_msg = ["Test data files referenced but not tracked in git:\n"]
        error_msg.append("\nDebug info:")
        error_msg.append(f"  Total git-tracked files found: {len(git_filenames)}")
        error_msg.append(f"  Total referenced files: {len(all_references)}")
        error_msg.append(f"  Missing files: {len(missing_files)}\n")

        # Show first 10 git-tracked filenames as sample
        error_msg.append("  Sample git-tracked filenames:")
        for filename in sorted(git_filenames)[:10]:
            error_msg.append(f"    - {filename}")
        error_msg.append("")

        # Invert the structure: group by test file instead of by filename
        missing_by_test = {}
        for filename, test_files_list in missing_files.items():
            for test_file in test_files_list:
                missing_by_test.setdefault(test_file, []).append(filename)

        # Show missing files organized by test
        error_msg.append("Missing files by test:")
        for test_file in sorted(missing_by_test.keys()):
            error_msg.append(f"  {test_file}")
            for filename in sorted(set(missing_by_test[test_file])):
                test_file_path = tests_dir / test_file
                local_test_data = test_file_path.parent / "test_data" / filename
                global_test_data = tests_dir / "test_data" / filename

                local_exists = local_test_data.exists()
                global_exists = global_test_data.exists()

                error_msg.append(f"    - {filename}")
                if local_exists or global_exists:
                    if local_exists:
                        error_msg.append(
                            f"      [EXISTS on filesystem: {local_test_data}]"
                        )
                    if global_exists:
                        error_msg.append(
                            f"      [EXISTS on filesystem: {global_test_data}]"
                        )

        pytest.fail("\n".join(error_msg))
