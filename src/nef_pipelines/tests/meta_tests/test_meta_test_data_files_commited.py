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

            if func_name == "read_test_data":
                # read_test_data(filename, __file__) - filename is first arg
                if node.args and isinstance(node.args[0], ast.Constant):
                    if isinstance(node.args[0].value, str):
                        filenames.append(node.args[0].value)
            elif func_name == "path_in_test_data":
                # path_in_test_data(__file__, filename) - filename is second arg
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    if isinstance(node.args[1].value, str):
                        filenames.append(node.args[1].value)

    return filenames


def _get_git_tracked_paths() -> set[Path]:
    """\
    Get set of all paths tracked by git in the tests directory.

    Returns relative paths from project root for exact path matching.

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

    # Filter for files in tests directory and return as Path objects
    tracked_paths = set()
    for line in result.stdout.splitlines():
        # Only include files under tests/
        if "/tests/" in line or line.startswith("tests/"):
            tracked_paths.add(Path(line))

    return tracked_paths


def test_all_test_data_files_in_git():
    """\
    Meta-test: Verify all test data files referenced in tests are tracked in git.

    Uses AST to parse test files and extract references to read_test_data() and
    path_in_test_data() calls, then verifies those files exist in git at the
    expected location (following path_in_test_data's resolution logic).
    """
    project_root = _find_project_root()
    tests_dir = Path(__file__).parent.parent  # Go up from meta_tests/ to tests/

    # Find all test files
    test_files = list(tests_dir.rglob("test_*.py"))

    # Get all git-tracked paths
    git_tracked_paths = _get_git_tracked_paths()

    # Extract all referenced test data files and check each one
    missing_files = {}
    for test_file in test_files:
        filenames = _extract_test_data_references(test_file)
        for filename in filenames:
            # Determine expected path (local test_data/ then global test_data/)
            local_test_data = test_file.parent / "test_data" / filename
            global_test_data = tests_dir / "test_data" / filename

            # Convert to relative path from project root
            local_relative = local_test_data.relative_to(project_root)
            global_relative = global_test_data.relative_to(project_root)

            # Check if either path is tracked in git
            if (
                local_relative not in git_tracked_paths
                and global_relative not in git_tracked_paths
            ):
                # File is missing - record it (deduplicate by filename)
                test_relative = test_file.relative_to(tests_dir)
                if test_relative not in missing_files:
                    missing_files[test_relative] = {}

                # Only add if not already recorded for this test
                if filename not in missing_files[test_relative]:
                    missing_files[test_relative][filename] = {
                        "local_path": local_test_data,
                        "global_path": global_test_data,
                        "local_exists": local_test_data.exists(),
                        "global_exists": global_test_data.exists(),
                    }

    # Report any missing files
    if missing_files:
        error_msg = ["Test data files referenced but not tracked in git:\n"]
        error_msg.append(f"  Total git-tracked test files: {len(git_tracked_paths)}")
        error_msg.append(f"  Test files with missing data: {len(missing_files)}\n")

        for test_file in sorted(missing_files.keys()):
            error_msg.append(f"  {test_file}:")
            for filename in sorted(missing_files[test_file].keys()):
                info = missing_files[test_file][filename]
                error_msg.append(f"    - {filename}")
                if info["local_exists"]:
                    error_msg.append(f"      [UNTRACKED: {info['local_path']}]")
                elif info["global_exists"]:
                    error_msg.append(f"      [UNTRACKED: {info['global_path']}]")
                else:
                    error_msg.append(
                        f"      [MISSING: expected at {info['local_path']} or {info['global_path']}]"
                    )

        pytest.fail("\n".join(error_msg))
