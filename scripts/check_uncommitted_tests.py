#!/usr/bin/env python3
"""\
Check uncommitted test files and their test_data.

Shows parent-child relationships (pytest files → test_data) to help you
consolidate and commit the right files together.

Usage:
    python scripts/check_uncommitted_tests.py
"""

import ast
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


def find_project_root() -> Path:
    """\
    Find project root containing src/nef_pipelines.
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src" / "nef_pipelines").exists():
            return parent
    raise RuntimeError("Could not find project root")


def extract_test_data_references(test_file: Path) -> List[str]:
    """\
    Extract test data filenames from test file using AST.
    """
    try:
        with open(test_file) as f:
            tree = ast.parse(f.read(), filename=str(test_file))
    except SyntaxError:
        return []

    filenames = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in ("read_test_data", "path_in_test_data"):
                # These functions take (__file__, filename) - extract second argument
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    if isinstance(node.args[1].value, str):
                        filenames.append(node.args[1].value)

    return filenames


def get_git_status(project_root: Path):
    """\
    Get git file statuses.

    Returns: (untracked, modified, staged, committed) sets of absolute paths
    """
    if not shutil.which("git"):
        print("Error: git not found", file=sys.stderr)
        sys.exit(1)

    try:
        # Untracked files
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root,
        )
        untracked = {project_root / line for line in result.stdout.splitlines() if line}

        # Modified files (unstaged)
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root,
        )
        modified = {project_root / line for line in result.stdout.splitlines() if line}

        # Staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root,
        )
        staged = {project_root / line for line in result.stdout.splitlines() if line}

        # Committed files (all tracked files)
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root,
        )
        committed = {project_root / line for line in result.stdout.splitlines() if line}
        # Remove uncommitted from committed set
        committed = committed - untracked - modified - staged

        return untracked, modified, staged, committed

    except subprocess.CalledProcessError as e:
        print(f"Error: git command failed: {e}", file=sys.stderr)
        sys.exit(1)


def find_test_data_file(tests_dir: Path, test_file: Path, filename: str) -> Path | None:
    """\
    Find test_data file path (local test_data/ dir first, then global).
    """
    local_path = test_file.parent / "test_data" / filename
    if local_path.exists():
        return local_path.resolve()

    global_path = tests_dir / "test_data" / filename
    if global_path.exists():
        return global_path.resolve()

    return None


def get_file_status(file_path: Path, untracked, modified, staged, committed) -> str:
    """\
    Get display status for a file.
    """
    if file_path in untracked:
        return "UNTRACKED"
    elif file_path in modified:
        return "MODIFIED"
    elif file_path in staged:
        return "STAGED"
    elif file_path in committed:
        return "committed"
    else:
        return "UNKNOWN"


def main():
    project_root = find_project_root()
    tests_dir = project_root / "src" / "nef_pipelines" / "tests"

    print("Checking uncommitted tests and test_data...")
    print(f"Project: {project_root}\n")

    # Step 1: Get git status
    untracked, modified, staged, committed = get_git_status(project_root)

    # Step 2: Find all pytest files
    pytest_files = list(tests_dir.rglob("test_*.py"))

    # Step 3: Find all test_data files
    test_data_files = set()
    for pattern in [
        "**/test_data/*.nef",
        "**/test_data/*.txt",
        "**/test_data/*.tab",
        "**/test_data/*.tbl",
        "**/test_data/*.str",
        "**/test_data/*.pdb",
    ]:
        test_data_files.update(tests_dir.rglob(pattern))

    # Step 4: Build pytest → test_data mapping
    pytest_to_data = {}  # {pytest_file: [(data_filename, data_path, status)]}
    data_to_pytest = {}  # {data_path: [pytest_files]}

    for pytest_file in pytest_files:
        referenced = extract_test_data_references(pytest_file)
        data_info_set = set()  # Use set to deduplicate

        for filename in referenced:
            data_path = find_test_data_file(tests_dir, pytest_file, filename)
            if data_path:
                status = get_file_status(
                    data_path, untracked, modified, staged, committed
                )
                data_info_set.add((filename, data_path, status))
                data_to_pytest.setdefault(data_path, []).append(pytest_file)
            else:
                data_info_set.add((filename, None, "NOT_FOUND"))

        if data_info_set:
            # Convert set back to sorted list for consistent output
            pytest_to_data[pytest_file] = sorted(data_info_set, key=lambda x: x[0])

    # Find orphaned test_data (no pytest file references them)
    referenced_data = set(data_to_pytest.keys())
    orphaned_data = test_data_files - referenced_data

    # Categorize pytest files
    untracked_pytest = [f for f in pytest_files if f in untracked]
    modified_pytest = [f for f in pytest_files if f in modified]
    staged_pytest = [f for f in pytest_files if f in staged]
    committed_pytest = [f for f in pytest_files if f in committed]

    # Display results
    issues_found = False

    # Category 1: Uncommitted pytest files (untracked/modified) with their test_data
    uncommitted_pytest = untracked_pytest + modified_pytest
    if uncommitted_pytest:
        issues_found = True
        print("=" * 80)
        print("UNCOMMITTED PYTEST FILES (and their test_data)")
        print("=" * 80)
        print("These need to be staged/committed together:\n")

        for status_name, file_list in [
            ("UNTRACKED", untracked_pytest),
            ("MODIFIED", modified_pytest),
        ]:
            if file_list:
                print(f"\n{status_name} ({len(file_list)}):")
                for pytest_file in sorted(file_list):
                    print(f"\n  {pytest_file.relative_to(project_root)}")
                    if pytest_file in pytest_to_data:
                        # Only show uncommitted/problematic test data
                        uncommitted_data = [
                            (filename, data_path, status)
                            for filename, data_path, status in pytest_to_data[
                                pytest_file
                            ]
                            if status != "committed"
                        ]
                        if uncommitted_data:
                            print("    Test data:")
                            for filename, data_path, status in uncommitted_data:
                                if data_path:
                                    marker = (
                                        " ⚠️"
                                        if status in ["UNTRACKED", "MODIFIED"]
                                        else ""
                                    )
                                    print(f"      • {filename} [{status}]{marker}")
                                else:
                                    print(f"      • {filename} [NOT_FOUND] ⚠️")

    # Category 2: Staged pytest files with their test_data
    # Only show files that are STAGED but NOT modified (to avoid duplicates)
    staged_only_pytest = [f for f in staged_pytest if f not in modified]
    if staged_only_pytest:
        issues_found = True
        print("\n" + "=" * 80)
        print("STAGED PYTEST FILES (verify test_data is also staged)")
        print("=" * 80)
        print("Check that all test_data is staged too:\n")

        for pytest_file in sorted(staged_only_pytest):
            print(f"\n  {pytest_file.relative_to(project_root)}")
            if pytest_file in pytest_to_data:
                # Only show uncommitted/problematic test data
                uncommitted_data = [
                    (filename, data_path, status)
                    for filename, data_path, status in pytest_to_data[pytest_file]
                    if status != "committed"
                ]
                if uncommitted_data:
                    print("    Test data:")
                    for filename, data_path, status in uncommitted_data:
                        if data_path:
                            marker = (
                                " ⚠️"
                                if status != "STAGED" and status != "committed"
                                else ""
                            )
                            print(f"      • {filename} [{status}]{marker}")
                        else:
                            print(f"      • {filename} [NOT_FOUND] ⚠️")

    # Category 3: Committed pytest with uncommitted/staged test_data (PROBLEM!)
    problem_pytest = []
    for pytest_file in committed_pytest:
        if pytest_file in pytest_to_data:
            has_uncommitted_data = any(
                status in ["UNTRACKED", "MODIFIED", "STAGED"]
                for _, data_path, status in pytest_to_data[pytest_file]
                if data_path
            )
            if has_uncommitted_data:
                problem_pytest.append(pytest_file)

    if problem_pytest:
        issues_found = True
        print("\n" + "=" * 80)
        print("COMMITTED PYTEST WITH UNCOMMITTED TEST_DATA (PROBLEM!)")
        print("=" * 80)
        print("These test_data files should have been committed:\n")

        for pytest_file in sorted(problem_pytest):
            print(f"\n  {pytest_file.relative_to(project_root)}")
            print("    Test data:")
            for filename, data_path, status in pytest_to_data[pytest_file]:
                if data_path and status in ["UNTRACKED", "MODIFIED", "STAGED"]:
                    print(f"      • {filename} [{status}] ⚠️⚠️")

    # Category 4: Orphaned test_data files
    orphaned_uncommitted = [
        f for f in orphaned_data if f in (untracked | modified | staged)
    ]
    if orphaned_uncommitted:
        issues_found = True
        print("\n" + "=" * 80)
        print("ORPHANED TEST_DATA (no pytest file references them)")
        print("=" * 80)
        print("These files aren't used by any test:\n")

        for data_file in sorted(orphaned_uncommitted):
            status = get_file_status(data_file, untracked, modified, staged, committed)
            print(f"  {data_file.relative_to(project_root)} [{status}]")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total pytest files: {len(pytest_files)}")
    print(f"  - Uncommitted: {len(uncommitted_pytest)}")
    print(f"  - Staged: {len(staged_pytest)}")
    print(f"  - Committed with uncommitted data: {len(problem_pytest)}")
    print(f"Total test_data files: {len(test_data_files)}")
    print(f"  - Orphaned: {len(orphaned_uncommitted)}")

    if not issues_found:
        print("\n✓ All tests and test_data are properly committed")
        return 0
    else:
        print("\n⚠️  Found uncommitted tests or test_data")
        return 1


if __name__ == "__main__":
    sys.exit(main())
