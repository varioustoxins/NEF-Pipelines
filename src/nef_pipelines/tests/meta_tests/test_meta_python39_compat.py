"""Meta-test for Python 3.9 compatibility - catches Python 3.10+ syntax."""

import ast
from pathlib import Path


def test_no_pipe_union_in_type_hints():
    """
    Ensure no Python 3.10+ union syntax (X | Y) is used in type hints.

    Python 3.9 requires Union[X, Y] instead of X | Y.
    This test catches accidental use of the newer syntax.
    """
    # Go up to nef_pipelines src root (tests/meta_tests -> tests -> nef_pipelines)
    src_dir = Path(__file__).parent.parent.parent
    violations = []

    for py_file in src_dir.rglob("*.py"):
        # Skip test files and __pycache__
        if "__pycache__" in str(py_file):
            continue

        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
        except SyntaxError:
            # Skip files with syntax errors (they'll fail their own tests)
            continue

        # Walk the AST looking for BinOp with BitOr in annotation contexts
        for node in ast.walk(tree):
            # Check function annotations
            if isinstance(node, ast.FunctionDef):
                # Return annotation
                if isinstance(node.returns, ast.BinOp) and isinstance(
                    node.returns.op, ast.BitOr
                ):
                    violations.append(
                        f"{py_file.relative_to(src_dir)}:{node.lineno} "
                        f"- Function '{node.name}' return type uses '|' instead of Union"
                    )
                # Argument annotations
                for arg in (
                    node.args.args + node.args.posonlyargs + node.args.kwonlyargs
                ):
                    if isinstance(arg.annotation, ast.BinOp) and isinstance(
                        arg.annotation.op, ast.BitOr
                    ):
                        violations.append(
                            f"{py_file.relative_to(src_dir)}:{node.lineno} "
                            f"- Function '{node.name}' argument '{arg.arg}' uses '|' instead of Union"
                        )

            # Check variable annotations
            if isinstance(node, ast.AnnAssign):
                if isinstance(node.annotation, ast.BinOp) and isinstance(
                    node.annotation.op, ast.BitOr
                ):
                    violations.append(
                        f"{py_file.relative_to(src_dir)}:{node.lineno} "
                        f"- Variable annotation uses '|' instead of Union"
                    )

    if violations:
        msg = (
            "\nFound Python 3.10+ union syntax (X | Y) in type hints.\n"
            "Use Union[X, Y] for Python 3.9 compatibility:\n\n"
            + "\n".join(f"  {v}" for v in violations)
        )
        raise AssertionError(msg)
