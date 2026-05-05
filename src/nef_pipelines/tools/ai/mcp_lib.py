import logging
import os
import subprocess
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
_RESOURCES_ROOT = files("nef_pipelines") / "resources"

_RESOURCE_NAME_SEPARATOR = " - "


@dataclass
class StartupContext:
    """Sandbox configuration captured at server startup for relaying to the AI."""

    sandbox_path: str = ""
    is_temporary: bool = False
    will_be_cleaned: bool = False
    warning: str = ""


_STARTUP_CONTEXT = StartupContext()


def _build_startup_notice(ctx: StartupContext) -> str:
    """\
    Format a StartupContext into a markdown notice block for inclusion in
    MCP instructions and nef_read_me_first() information.
    """
    if ctx.will_be_cleaned:
        sandbox_type = "⚠ **Temporary** — will be **deleted** on exit"
    elif ctx.is_temporary:
        sandbox_type = "Temporary — will be **preserved** on exit (--preserve)"
    else:
        sandbox_type = "Persistent — files will **not** be deleted on exit"

    lines = [
        "## Sandbox Status — tell the user this immediately",
        "",
        f"- **Directory**: `{ctx.sandbox_path}`",
        f"- **Type**: {sandbox_type}",
    ]

    if ctx.warning:
        lines.append(f"- **⚠ Warning**: {ctx.warning}")

    return "\n".join(lines)


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


@dataclass
class OperationResult:
    """Base for file I/O and resource operations; success = no error."""

    error: str = ""

    @property
    def success(self) -> bool:
        """True when error is empty."""
        return not bool(self.error)


@dataclass
class CommandResult:
    """Base for command executions; success = exit_code == 0."""

    exit_code: int = 0
    stderr: str = ""

    @property
    def success(self) -> bool:
        """True when exit_code is 0."""
        return self.exit_code == 0


@dataclass
class UploadResult(OperationResult):
    """Result of nef_upload_file."""

    name: str = ""
    bytes_written: int = 0


@dataclass
class DownloadResult(OperationResult):
    """Result of nef_download_file."""

    name: str = ""
    content: str = ""
    available_files: List[str] = field(default_factory=list)


@dataclass
class ListFilesResult(OperationResult):
    """Result of nef_list_files.

    unexpected_entries elements are formatted as 'name (type)',
    e.g. 'tmp_dir (directory)'. error is non-empty and success=False
    whenever unexpected_entries is non-empty.
    """

    files: List[str] = field(default_factory=list)
    cwd: str = ""
    unexpected_entries: List[str] = field(default_factory=list)


@dataclass
class ChangeSandboxResult(OperationResult):
    """Result of nef_change_sandbox."""

    new_path: str = ""


@dataclass
class NefStartupResult(OperationResult):
    """Result of nef_read_me_first and nef_resources_read.

    information — if non-empty, show this to the user verbatim before anything else.
    It carries startup warnings and sandbox status that the AI must relay.
    """

    content: str = ""
    information: str = ""


@dataclass
class CommandTableResult(CommandResult):
    """Result of nef_list_commands."""

    commands_table: str = ""


@dataclass
class CommandHelpResult(CommandResult):
    """Result of nef_get_command_help."""

    help_text: str = ""


def _execute_command_in_process(
    args: List[str],
    nef_input: str = "",
) -> PipelineResult:
    """\
    Execute a single NEF command in-process.

    Returns a PipelineResult with stderr as a single-element list.
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

    exit_code = result.exit_code
    return PipelineResult(
        stdout=stdout,
        stderr=[stderr],
        exit_code=exit_code,
        steps=[list(args)],
        steps_completed=1 if exit_code == 0 else 0,
    )


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


def _get_native_directory(initial_dir: str = ""):
    """\
    Triggers a native OS directory picker and returns the path.
    Returns None if the user cancels.
    Returns dict with 'error' key if there's an error.

    initial_dir - starting directory for the picker (optional)
    """
    system = sys.platform

    try:
        if system == "darwin":  # macOS
            if initial_dir:
                # Use default folder to set starting location
                cmd = (
                    f"osascript -e 'POSIX path of (choose folder "
                    f'with prompt "Select your MCP Sandbox:" '
                    f'default location POSIX file "{initial_dir}")\''
                )
            else:
                cmd = "osascript -e 'POSIX path of (choose folder with prompt \"Select your MCP Sandbox:\")'"
        elif system == "win32":
            # Uses PowerShell to call the FolderBrowserDialog
            if initial_dir:
                cmd = (
                    "powershell -ExecutionPolicy Bypass -Command "
                    '"Add-Type -AssemblyName System.Windows.Forms; '
                    "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                    "$f.Description = 'Select your MCP Sandbox'; "
                    f"$f.SelectedPath = '{initial_dir}'; "
                    "if($f.ShowDialog() -eq 'OK') { $f.SelectedPath }\""
                )
            else:
                cmd = (
                    "powershell -ExecutionPolicy Bypass -Command "
                    '"Add-Type -AssemblyName System.Windows.Forms; '
                    "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                    "$f.Description = 'Select your MCP Sandbox'; "
                    "if($f.ShowDialog() -eq 'OK') { $f.SelectedPath }\""
                )
        elif system == "linux":
            # Requires zenity to be installed
            if initial_dir:
                path_option = f"--filename='{initial_dir}/'"
            else:
                path_option = ""
            cmd = f"zenity --file-selection --directory {path_option} --title='Select your MCP Sandbox'"
        else:
            return {"error": "Unsupported Operating System"}

        # Run command and capture output
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        path = proc.stdout.strip()

        return path if path else None

    except Exception as e:
        return {"error": str(e)}
