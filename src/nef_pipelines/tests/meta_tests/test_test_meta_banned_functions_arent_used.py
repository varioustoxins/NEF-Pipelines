"""Tests for the BannedFunctionChecker AST visitor logic.

This tests the checker itself, not the codebase.
"""

import ast
from textwrap import dedent

from nef_pipelines.tests.meta_tests.test_meta_banned_functions_arent_used import (
    BannedFunctionChecker,
)


def test_checker_detects_cli_runner_invoke_pattern():
    """Test that checker detects CliRunner() + .invoke() in same function."""
    code = """
        from typer.testing import CliRunner

        def test_function():
            runner = CliRunner()
            result = runner.invoke(app, [])
    """
    code = dedent(code)
    tree = ast.parse(code)
    source_lines = code.splitlines()
    checker = BannedFunctionChecker({}, source_lines)
    checker.visit(tree)

    EXPECTED_REASON = (
        "Use run_and_report from nef_pipelines.lib.test_lib instead. "
        + "CliRunner.invoke does not provide proper error reporting. "
        + "Add '# allowed' comment to exception this check if absolutely necessary."
    )
    EXPECTED = [
        (6, "CliRunner", "invoke", EXPECTED_REASON),
    ]

    assert checker.violations == EXPECTED


def test_checker_ignores_invoke_without_cli_runner():
    """Test that checker ignores .invoke() when CliRunner not instantiated in function."""
    code = """
        def test_function():
            result = runner.invoke(app, [])  # runner from elsewhere
    """
    code = dedent(code)
    tree = ast.parse(code)
    source_lines = code.splitlines()
    checker = BannedFunctionChecker({}, source_lines)
    checker.visit(tree)

    assert len(checker.violations) == 0


def test_checker_respects_allowed_comment():
    """Test that checker respects # allowed comment."""
    code = """
from typer.testing import CliRunner

def test_function():
    runner = CliRunner()
    result = runner.invoke(app, [])  # allowed
"""
    tree = ast.parse(code)
    source_lines = code.splitlines()
    checker = BannedFunctionChecker({}, source_lines)
    checker.visit(tree)

    assert len(checker.violations) == 0


def test_checker_scopes_to_function():
    """Test that checker only flags violations within same function scope."""
    code = """
        from typer.testing import CliRunner

        def setup():
            runner = CliRunner()
            return runner

        def test_function(runner):
            result = runner.invoke(app, [])  # Should NOT be flagged - different function
    """
    code = dedent(code)
    tree = ast.parse(code)
    source_lines = code.splitlines()
    checker = BannedFunctionChecker({}, source_lines)
    checker.visit(tree)

    assert len(checker.violations) == 0


def test_checker_handles_nested_functions():
    """Test that checker handles nested function scopes correctly."""
    code = """
        from typer.testing import CliRunner

        def outer():
            runner = CliRunner()

            def inner():
                result = runner.invoke(app, [])  # Should NOT be flagged - different scope

            inner()
    """
    code = dedent(code)
    tree = ast.parse(code)
    source_lines = code.splitlines()
    checker = BannedFunctionChecker({}, source_lines)
    checker.visit(tree)

    # Should not flag because inner() doesn't instantiate CliRunner
    assert len(checker.violations) == 0


def test_checker_detects_banned_module_functions():
    """Test that checker detects other banned functions from the dict."""
    code = """
        from fnmatch import fnmatch

        def test_function():
            result = fnmatch(name, pattern)
    """
    code = dedent(code)
    tree = ast.parse(code)
    source_lines = code.splitlines()

    banned_functions = {("fnmatch", "fnmatch"): "Use fnmatchcase instead"}

    checker = BannedFunctionChecker(banned_functions, source_lines)
    checker.visit(tree)

    EXPECTED_REASON = "Use fnmatchcase instead"
    EXPECTED_VIOLATIONS = [
        (2, "fnmatch", "fnmatch", EXPECTED_REASON),
        (5, "fnmatch", "fnmatch", EXPECTED_REASON),
    ]

    assert checker.violations == EXPECTED_VIOLATIONS


def test_checker_multiple_violations_same_function():
    """Test that checker detects multiple .invoke() calls in same function."""
    code = """
        from typer.testing import CliRunner

        def test_function():
            runner = CliRunner()
            result1 = runner.invoke(app, [])
            result2 = runner.invoke(app, ["arg"])
    """
    code = dedent(code)
    tree = ast.parse(code)
    source_lines = code.splitlines()
    checker = BannedFunctionChecker({}, source_lines)
    checker.visit(tree)

    EXPECTED_REASON = (
        "Use run_and_report from nef_pipelines.lib.test_lib instead. "
        + "CliRunner.invoke does not provide proper error reporting. "
        + "Add '# allowed' comment to exception this check if absolutely necessary."
    )

    EXPECTED_VIOLATIONS = [
        (6, "CliRunner", "invoke", EXPECTED_REASON),
        (7, "CliRunner", "invoke", EXPECTED_REASON),
    ]

    assert checker.violations == EXPECTED_VIOLATIONS
