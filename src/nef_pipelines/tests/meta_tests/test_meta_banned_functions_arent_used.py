"""Meta test to check for banned function calls in the codebase.

This test uses AST parsing to detect calls to functions that should not be used,
such as fnmatch.fnmatch which has platform-dependent case sensitivity.
"""

import ast
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

# Banned functions: (module_name, function_name) -> reason
BANNED_FUNCTIONS: Dict[Tuple[str, str], str] = {
    ("fnmatch", "fnmatch"): (
        "Use fnmatchcase instead. fnmatch.fnmatch is case-insensitive on Windows "
        "and case-sensitive on Unix, causing platform-specific bugs. "
        "fnmatchcase is always case-sensitive on all platforms."
    ),
}


class BannedFunctionChecker(ast.NodeVisitor):
    """AST visitor that detects calls to banned functions."""

    def __init__(self, banned_functions: Dict[Tuple[str, str], str]):
        """Initialise the checker with a dictionary of banned functions.

        Args:
            banned_functions: Dictionary mapping (module, function) tuples to reason strings
        """
        self.banned_functions = banned_functions
        self.violations: List[Tuple[int, str, str, str]] = []
        self.imports: Dict[str, str] = {}  # alias -> module
        self.from_imports: Dict[str, str] = {}  # name -> module

    def visit_Import(self, node: ast.Import) -> None:
        """Track import statements like 'import fnmatch'."""
        for alias in node.names:
            module_name = alias.name
            import_alias = alias.asname if alias.asname else alias.name
            self.imports[import_alias] = module_name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track from-import statements like 'from fnmatch import fnmatch'."""
        if node.module:
            for alias in node.names:
                func_name = alias.name
                import_alias = alias.asname if alias.asname else alias.name
                self.from_imports[import_alias] = node.module

                # Check if this is a banned from-import
                if (node.module, func_name) in self.banned_functions:
                    reason = self.banned_functions[(node.module, func_name)]
                    self.violations.append(
                        (node.lineno, node.module, func_name, reason)
                    )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls against banned list."""
        module_name = None
        func_name = None

        if isinstance(node.func, ast.Name):
            # Direct call: fnmatch(...)
            func_name = node.func.id
            if func_name in self.from_imports:
                module_name = self.from_imports[func_name]

        elif isinstance(node.func, ast.Attribute):
            # Attribute call: fnmatch.fnmatch(...)
            func_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                alias = node.func.value.id
                if alias in self.imports:
                    module_name = self.imports[alias]

        if module_name and func_name:
            if (module_name, func_name) in self.banned_functions:
                reason = self.banned_functions[(module_name, func_name)]
                self.violations.append((node.lineno, module_name, func_name, reason))

        self.generic_visit(node)


def get_python_files(root_path: Path) -> List[Path]:
    """Get all Python files in the source directory.

    Args:
        root_path: Root directory to search

    Returns:
        List of Python file paths
    """
    src_path = root_path / "src" / "nef_pipelines"
    return list(src_path.rglob("*.py"))


def check_file_for_banned_functions(
    file_path: Path, banned_functions: Dict[Tuple[str, str], str]
) -> List[Tuple[int, str, str, str]]:
    """Check a single Python file for banned function calls.

    Args:
        file_path: Path to the Python file
        banned_functions: Dictionary of banned functions

    Returns:
        List of violations as (line_number, module, function, reason) tuples
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        checker = BannedFunctionChecker(banned_functions)
        checker.visit(tree)
        return checker.violations
    except SyntaxError:
        # Skip files with syntax errors
        return []


def test_no_banned_functions():
    """Test that no banned functions are used in the codebase.

    This test uses AST parsing to detect calls to functions that should not be used.
    Currently checks for fnmatch.fnmatch which has platform-dependent case sensitivity.
    """
    # Find the repository root
    test_file = Path(__file__)
    repo_root = test_file.parent.parent.parent.parent.parent

    # Get all Python files
    python_files = get_python_files(repo_root)

    # Check each file
    all_violations: Dict[Path, List[Tuple[int, str, str, str]]] = {}
    for py_file in python_files:
        violations = check_file_for_banned_functions(py_file, BANNED_FUNCTIONS)
        if violations:
            all_violations[py_file] = violations

    # Report violations
    if all_violations:
        error_message = "Found banned function calls:\n\n"
        for file_path, violations in all_violations.items():
            rel_path = file_path.relative_to(repo_root)
            for line_no, module, func, reason in violations:
                error_message += (
                    f"  {rel_path}:{line_no}: {module}.{func}\n"
                    f"    Reason: {reason}\n\n"
                )
        pytest.fail(error_message)
