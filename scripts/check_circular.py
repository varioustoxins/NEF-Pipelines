"""
For each import annotated '# circular', verify a return path exists in the import graph.
"""

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/src/nef_pipelines")


def path_to_module(path: Path) -> str:
    rel = path.relative_to(ROOT.parent)
    parts = rel.with_suffix("").parts
    return ".".join(parts)


def collect_imports(path: Path) -> list[str]:
    """Return all modules imported by this file (top-level and inside functions)."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
    return imports


# Build full import graph: module -> set of modules it imports
graph: dict[str, set[str]] = defaultdict(set)
for py_file in ROOT.rglob("*.py"):
    mod = path_to_module(py_file)
    for imp in collect_imports(py_file):
        if imp.startswith("nef_pipelines"):
            graph[mod].add(imp)


def has_path(src: str, dst: str, visited=None) -> bool:
    """Does src have a transitive import path to dst?"""
    if visited is None:
        visited = set()
    if src in visited:
        return False
    visited.add(src)
    for neighbor in graph.get(src, []):
        if neighbor == dst or neighbor.startswith(dst + "."):
            return True
        if has_path(neighbor, dst, visited):
            return True
    return False


# Find all # circular annotations
print("Checking # circular annotations:\n")
for py_file in sorted(ROOT.rglob("*.py")):
    mod = path_to_module(py_file)
    try:
        source = py_file.read_text()
        tree = ast.parse(source)
    except SyntaxError:
        continue
    lines = source.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        line = lines[node.lineno - 1]
        if "# circular" not in line:
            continue
        if isinstance(node, ast.ImportFrom):
            imported = node.module or ""
        else:
            imported = node.names[0].name
        if not imported.startswith("nef_pipelines"):
            continue
        # Check return path: imported -> mod
        rel_mod = mod.replace("nef_pipelines.", "")
        has_return = has_path(imported, mod)
        status = "✓ CYCLE" if has_return else "✗ NO RETURN PATH"
        print(
            f"  {status}  {mod.split('nef_pipelines.')[-1]}  →  {imported.split('nef_pipelines.')[-1]}"
        )
