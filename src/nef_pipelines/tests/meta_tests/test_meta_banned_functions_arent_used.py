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
    ("typer.testing.CliRunner", "invoke"): (
        "Use run_and_report from nef_pipelines.lib.test_lib instead. "
        "CliRunner.invoke does not provide proper error reporting. "
        "Add '# allowed' comment to exception this check if absolutely necessary."
    ),
}


class BannedFunctionChecker(ast.NodeVisitor):
    """AST visitor that detects calls to banned functions."""

    def __init__(
        self, banned_functions: Dict[Tuple[str, str], str], source_lines: List[str]
    ):
        """Initialise the checker with a dictionary of banned functions.

        Args:
            banned_functions: Dictionary mapping (module, function) tuples to reason strings
            source_lines: List of source code lines for checking '# allowed' comments
        """
        self.banned_functions = banned_functions
        self.violations: List[Tuple[int, str, str, str]] = []
        self.imports: Dict[str, str] = {}  # alias -> module
        self.from_imports: Dict[str, str] = {}  # name -> module
        self.source_lines = source_lines
        self.cli_runner_in_current_function = (
            False  # Track CliRunner() in current function scope
        )

    def _is_allowed(self, line_no: int) -> bool:
        """Check if a line has the '# allowed' comment to exempt it from the ban.

        Args:
            line_no: Line number (1-indexed)

        Returns:
            True if the line has '# allowed' comment
        """
        if 0 < line_no <= len(self.source_lines):
            line = self.source_lines[line_no - 1]
            return "# allowed" in line
        return False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function entry and reset CliRunner tracking."""
        # Save previous state
        prev_cli_runner = self.cli_runner_in_current_function
        self.cli_runner_in_current_function = False

        # Visit function body
        self.generic_visit(node)

        # Restore previous state
        self.cli_runner_in_current_function = prev_cli_runner

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function entry and reset CliRunner tracking."""
        # Save previous state
        prev_cli_runner = self.cli_runner_in_current_function
        self.cli_runner_in_current_function = False

        # Visit function body
        self.generic_visit(node)

        # Restore previous state
        self.cli_runner_in_current_function = prev_cli_runner

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

        # Check if this is CliRunner() instantiation
        if isinstance(node.func, ast.Name):
            # Direct call: fnmatch(...) or CliRunner()
            func_name = node.func.id
            if func_name in self.from_imports:
                module_name = self.from_imports[func_name]
                # Check if this is CliRunner being instantiated
                if func_name == "CliRunner" and module_name == "typer.testing":
                    self.cli_runner_in_current_function = True

        elif isinstance(node.func, ast.Attribute):
            # Attribute call: fnmatch.fnmatch(...) or runner.invoke(...)
            func_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                alias = node.func.value.id
                if alias in self.imports:
                    module_name = self.imports[alias]

            # Special case: ban .invoke() call if CliRunner was instantiated in this function
            # This catches runner.invoke() where runner is a CliRunner instance
            if func_name == "invoke" and isinstance(node.func.value, ast.Name):
                if self.cli_runner_in_current_function and not self._is_allowed(
                    node.lineno
                ):
                    reason = (
                        "Use run_and_report from nef_pipelines.lib.test_lib instead. "
                        "CliRunner.invoke does not provide proper error reporting. "
                        "Add '# allowed' comment to exception this check if absolutely necessary."
                    )
                    # Use a generic marker for runner.invoke
                    self.violations.append((node.lineno, "CliRunner", "invoke", reason))

        if module_name and func_name:
            if (module_name, func_name) in self.banned_functions:
                # Skip if line has '# allowed' comment
                if not self._is_allowed(node.lineno):
                    reason = self.banned_functions[(module_name, func_name)]
                    self.violations.append(
                        (node.lineno, module_name, func_name, reason)
                    )

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
            source_code = f.read()
            source_lines = source_code.splitlines()
            tree = ast.parse(source_code, filename=str(file_path))

        checker = BannedFunctionChecker(banned_functions, source_lines)
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
