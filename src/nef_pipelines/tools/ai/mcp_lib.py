import logging
import os
import sys
from dataclasses import dataclass, field
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, List, Tuple

from typer.testing import CliRunner

from nef_pipelines.main import create_nef_app
from nef_pipelines.module_registry import get_registerd_modules

logger = logging.getLogger(__name__)

_nef_app = create_nef_app()

for _module_name in get_registerd_modules():
    try:
        import_module(_module_name)
    except Exception:
        pass

_RESOURCES = files("nef_pipelines") / "resources" / "mcp_server"

_RESOURCE_NAME_SEPARATOR = " - "

# Two distinct filesystem limits matter:
#   NAME_MAX — max length of a single filename component (e.g. "foo.txt")
#   PATH_MAX — max length of a full resolved path
# We read them from the OS via pathconf where available and fall back to
# conservative defaults that are correct on Linux/macOS.
_DEFAULT_MAX_LENGTH_PATH_ELEMENT = 255
_DEFAULT_MAX_PATH_LENGTH = 1024  # macOS-style; safe on Linux too


def _max_length_path_element() -> int:
    """\
    Maximum length of a single filename component for the current cwd.
    Falls back to 255 on Windows or filesystems that don't report it.
    """
    try:
        return os.pathconf(os.getcwd(), "PC_NAME_MAX")
    except (OSError, ValueError, AttributeError):
        return _DEFAULT_MAX_LENGTH_PATH_ELEMENT


def _max_length_path() -> int:
    """\
    Maximum total path length for the current cwd.
    Falls back to 1024 on Windows or filesystems that don't report it.
    """
    try:
        return os.pathconf(os.getcwd(), "PC_PATH_MAX")
    except (OSError, ValueError, AttributeError):
        return _DEFAULT_MAX_PATH_LENGTH


def _validate_path_in_sandbox(path_str: str) -> Tuple[bool, str]:
    """\
    Check whether path_str is safe to use as a path inside the current
    working directory (the sandbox).

    Returns (True, "") on success, (False, error_message) on failure.

    The sandbox root is the current working directory. Callers are
    responsible for ensuring cwd is the intended sandbox before calling.
    """
    error = ""
    is_error = False

    candidate = None
    target = None
    root = None

    # Step 1: type check — MCP arguments arrive over JSON-RPC as strings;
    # anything else is a programming error in the caller.
    if not is_error and not isinstance(path_str, str):
        error = f"path must be a string, got {type(path_str).__name__}"
        is_error = True

    # Step 2: construct the Path — rejects some malformed inputs at construction;
    # others (e.g. NUL bytes) surface at resolve() in Step 6.
    if not is_error:
        try:
            candidate = Path(path_str)
        except ValueError as e:
            error = f"'{path_str}' is not a valid path: {e}"
            is_error = True

    # Step 3: reject absolute paths — the sandbox is defined by relative paths
    # from cwd; an absolute path bypasses that framing entirely.
    if not is_error and candidate.is_absolute():
        error = f"'{path_str}' must be a relative path, not absolute"
        is_error = True

    # Step 3a (Windows): reject drive-relative paths such as "C:foo" —
    # is_absolute() returns False for these on Windows because they lack a
    # separator after the colon, but they still anchor to a specific drive root.
    if not is_error and sys.platform == "win32":
        if len(path_str) >= 2 and path_str[0].isalpha() and path_str[1] == ":":
            error = f"'{path_str}' contains a Windows drive letter"
            is_error = True

    # Step 3b (Windows): reject UNC/network paths such as "\\\\server\\share" —
    # is_absolute() catches these on Windows too, but belt-and-suspenders.
    if not is_error and sys.platform == "win32":
        if path_str.startswith("\\\\"):
            error = f"'{path_str}' is a Windows network path"
            is_error = True

    # Step 4: reject reserved system names (CON, NUL, COM1 etc.) — no-op on
    # POSIX, future-proofing for Windows.
    if not is_error and candidate.is_reserved():
        error = f"'{path_str}' is a reserved system name"
        is_error = True

    # Step 5: per-component length check — catch offending component before
    # resolution so the error names it explicitly.
    if not is_error:
        name_max = _max_length_path_element()
        oversize_part = next((p for p in candidate.parts if len(p) > name_max), None)
        if oversize_part is not None:
            error = (
                f"path component '{oversize_part[:40]}...' "
                f"exceeds {name_max} characters "
                f"(got {len(oversize_part)})"
            )
            is_error = True

    # Step 6: resolve against cwd — collapses '..', symlinks, etc. so the
    # containment check in Step 7 works on fully-resolved paths.
    if not is_error:
        try:
            root = Path(os.getcwd()).resolve()
            target = (root / candidate).resolve()
        except (OSError, ValueError) as e:
            error = f"could not resolve '{path_str}': {e}"
            is_error = True

    # Step 7: reject paths that escape the sandbox — the structural safety check.
    if not is_error and not target.is_relative_to(root):
        error = f"'{path_str}' resolves outside the sandbox"
        is_error = True

    # Step 8: reject paths that resolve to the sandbox root itself — "", ".",
    # "foo/.." all pass Step 7 but can't be used as filenames.
    if not is_error and target == root:
        error = f"'{path_str}' resolves to the sandbox root itself"
        is_error = True

    # Step 9: total path length check — a short relative path inside a deeply
    # nested sandbox could still blow PATH_MAX.
    if not is_error:
        path_max = _max_length_path()
        target_len = len(str(target))
        if target_len > path_max:
            error = (
                f"resolved path length {target_len} exceeds " f"{path_max} characters"
            )
            is_error = True

    return (not is_error), error


@dataclass
class CommandResult:
    """Result of a single in-process command execution."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        """True when exit_code is 0."""
        return self.exit_code == 0


@dataclass
class PipelineResult:
    """Result of a multi-step pipeline execution."""

    stdout: str = ""
    stderr: List[str] = field(default_factory=list)
    exit_code: int = 0
    steps: List[List[str]] = field(default_factory=list)
    steps_completed: int = 0

    @property
    def success(self) -> bool:
        """True when exit_code is 0."""
        return self.exit_code == 0


def _execute_command_in_process(
    args: List[str],
    nef_input: str = "",
) -> CommandResult:
    """
    Execute a NEF command in-process with stdin/stdout streaming.

    Returns a CommandResult with stdout, stderr, and exit_code.
    """
    invoke_kwargs: Dict[str, Any] = dict(input=nef_input if nef_input else None)
    try:
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(_nef_app.app, list(args), **invoke_kwargs)
        stdout, stderr = result.output or "", result.stderr or ""
    except TypeError:
        runner = CliRunner()
        result = runner.invoke(_nef_app.app, list(args), **invoke_kwargs)
        stdout = result.output or ""
        stderr = ""
        if hasattr(result, "stderr") and result.stderr:
            stderr = result.stderr

    if stderr:
        stdout = (stdout + stderr) if stdout else stderr

    return CommandResult(stdout=stdout, stderr=stderr, exit_code=result.exit_code)


def _get_resource_name_from_filename(filename: str) -> str:
    """Return the resource name from a filename: stem text before the first ' - ', lowercased.

    The separator is space-hyphen-space so resource names that contain hyphens (e.g.
    'cli-idioms', 'nmr-data') are preserved intact.
    """
    stem = Path(filename).stem
    return stem.split(_RESOURCE_NAME_SEPARATOR, 1)[0].strip().lower()


def _get_resource_description_from_filename(filename: str) -> str:
    """Return the resource description from a filename: stem text after the first ' - '."""
    stem = Path(filename).stem
    parts = stem.split(_RESOURCE_NAME_SEPARATOR, 1)
    return parts[1].strip() if len(parts) > 1 else f"{parts[0].strip()} reference"


def _find_resource_file(name: str):
    """Find the resource file in _RESOURCES whose name matches the given resource name."""
    for f in _RESOURCES.iterdir():
        if f.name.endswith(".md") and _get_resource_name_from_filename(f.name) == name:
            return f
    return None
