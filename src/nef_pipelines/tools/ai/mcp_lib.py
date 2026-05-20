import asyncio
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple, Union

from typer.testing import CliRunner

import nef_pipelines
from nef_pipelines.lib.util import warn
from nef_pipelines.nef_app_runner import create_nef_app
from nef_pipelines.tools.ai.sandbox_audit import SandboxViolation, audit_sandbox_writes
from nef_pipelines.tools.ai.sandbox_lib import is_path_in_sandbox, validate_sandbox_path

logger = logging.getLogger(__name__)


def create_nef_pipelines_app():
    from nef_pipelines.nef_app_runner import load_nef_modules_and_build_failure

    create_nef_app()  # idempotent; populates nef_pipelines.nef_app singleton
    failure_message = load_nef_modules_and_build_failure()
    if failure_message:
        warn(failure_message)


_RESOURCES = files("nef_pipelines") / "resources" / "mcp_server"
_RESOURCES_ROOT = files("nef_pipelines") / "resources"

_RESOURCE_NAME_SEPARATOR = " - "

_EXPERIMENTAL_HEADER = """\
⚠️  **EXPERIMENTAL - USE WITH CAUTION**  ⚠️

The NEF-Pipelines MCP server is EXPERIMENTAL software. It is still under development!\
"""

_LIABILITY = (
    "**THE AUTHORS ACCEPT NO LIABILITY FOR BUGS, DATA LOSS OR UNINTENDED FILE ACCESS.**"
)

_AI_INSTRUCTION = "**⚠️ AI: You MUST show the following to the user as the last thing in your current response. ⚠️**"


@dataclass
class StartupContext:
    """Sandbox configuration captured at server startup for relaying to the AI."""

    sandbox_path: str = ""
    is_temporary: bool = False
    will_be_cleaned: bool = False
    no_sandbox: bool = False
    path_source: str = ""
    warning: str = ""


_STARTUP_CONTEXT = StartupContext()


def _is_sandboxed() -> bool:
    """Return True if the server is running in sandbox mode (i.e. --no-sandbox was NOT passed).
    Reads _STARTUP_CONTEXT at call time so it reflects the value set by server.py at startup.
    """
    return not _STARTUP_CONTEXT.no_sandbox


def _build_startup_notice(ctx: Optional[StartupContext] = None) -> str:
    """\
    Format a StartupContext into a markdown notice block for inclusion in
    MCP instructions and nef_read_me_first() information.
    Defaults to the module-level _STARTUP_CONTEXT so callers always get
    the current server state even when _STARTUP_CONTEXT is replaced at startup.
    """
    if ctx is None:
        ctx = _STARTUP_CONTEXT
    if ctx.no_sandbox:
        body = f"""\
            This server is running **without a sandbox; --no-sandbox was passed**. The AI has direct,
            unsupervised access to your filesystem and can **READ, WRITE and OVERWRITE** files anywhere
            the operating system allows without further confirmation.

            **BEFORE using this server you should:**
              - Ensure you restrict the server so it won't overwrite important files
                [are you using a container or an isolated server?]
              - Understand which AI model and client will connect
              - Never expose this server on a public network interface
              - Review the commands available via: `nef help commands`

            {_LIABILITY}
        """
        body = dedent(body.strip())
    elif ctx.sandbox_path:
        if ctx.will_be_cleaned:
            cleanup = dedent(
                """\
                **⚠️ THE SANDBOX IS A TEMPORARY DIRECTORY AND WILL BE DELETED AT SERVER / AI SHUTDOWN.**

                Ask the AI to change the sandbox to another directory if you want more permanent storage.
            """
            ).strip()
        elif ctx.is_temporary:
            cleanup = dedent(
                """\
                **⚠️ THE SANDBOX WILL NOT BE CLEARED AT SHUTDOWN** (--preserve-sandbox was used).
                A new sandbox will be created on next server start.
                The sandbox may be cleared at computer reboot.
                This option is mainly present for debugging.
            """
            ).strip()
        else:
            cleanup = dedent(
                f"""\
                The server is using a **user defined sandbox**
                defined by the **{ctx.path_source}**.
                The AI is restricted to this user supplied directory.
            """
            ).strip()

        warning_line = f"\n\n⚠️ **Warning**: {ctx.warning}" if ctx.warning else ""

        current_sandbox = Path.cwd()
        body = f"""\
The server is in **sandbox mode**. The AI is restricted to a single directory:

**`{current_sandbox}`**

It can **READ, WRITE and OVERWRITE** files within this directory without further confirmation.

{cleanup}

{_LIABILITY}{warning_line}"""

    else:
        body = dedent(
            f"""\
            In **sandbox mode** (default) the AI is restricted to a single directory.
            With **--no-sandbox** it has direct, unsupervised access to your filesystem and can
            **READ, WRITE and OVERWRITE** files anywhere without further confirmation.

            {_LIABILITY}
        """
        ).strip()

    return f"""\
{_AI_INSTRUCTION}

---

{_EXPERIMENTAL_HEADER}

{body}"""


def _build_full_orientation(skip_header: str = "") -> str:
    """\
    Build the complete orientation message: preamble + warnings.
    Used by both MCP instructions and nef_read_me_first() for consistency.

    skip_header: Optional header to add (for nef_read_me_first only)
    """
    from importlib.resources import files

    preamble_file = files("nef_pipelines") / "resources" / "preamble.md"
    preamble = preamble_file.read_text() if preamble_file.is_file() else ""

    resource_footer = (
        "\n\n---\n\n"
        "**Resources unavailable via `nef://`?**\n"
        "Use nef_resources_list to list resource names and what they do\n"
        "Use `nef_resources_read(name)` to fetch any resource document\n"
    )

    # Always use _build_startup_notice
    startup_notice = _build_startup_notice(_STARTUP_CONTEXT)

    parts = []
    if skip_header:
        parts.append(skip_header)
    parts.extend([preamble, resource_footer, "\n\n", startup_notice])

    return "".join(parts)


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


def _validate_sandbox() -> Tuple[bool, str]:
    """
    Validate that the current working directory is a usable sandbox.

    The cwd is the single source of truth for the sandbox location. It is
    process-global, so all AI clients connected to the same server process
    share one sandbox. The typical deployment (one server process per AI
    session) means this is not a concern in practice.

    Returns (True, "") on success, (False, error_message) on failure.
    """
    validation_error = validate_sandbox_path(Path.cwd())
    if validation_error:
        return False, f"Sandbox is invalid: {validation_error}"
    return True, ""


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

    # Step 4: reject reserved system names (CON, NUL, COM1 etc.) — Windows only,
    # always a no-op on POSIX. os.path.isreserved() (3.13+) replaces the deprecated
    # PurePath.is_reserved() which is removed in Python 3.15.
    if not is_error and sys.platform == "win32":
        if hasattr(os.path, "isreserved"):
            is_reserved = os.path.isreserved(str(candidate))
        else:
            is_reserved = candidate.is_reserved()
        if is_reserved:
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
    if not is_error and not is_path_in_sandbox(target, root):
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
class OperationResult:
    """Base for file I/O and resource operations; success = no error."""

    error: str = ""

    @property
    def success(self) -> bool:
        """True when error is empty."""
        return not bool(self.error)


@dataclass
class PipelineResult(OperationResult):
    """Result of a multi-step pipeline execution."""

    stdout: str = ""
    stderr: List[str] = field(default_factory=list)
    exit_code: int = 0
    steps: List[List[str]] = field(default_factory=list)
    steps_completed: int = 0

    @property
    def success(self) -> bool:
        """True when exit_code is 0 and no error."""
        return self.exit_code == 0 and not bool(self.error)


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
    sandboxed: bool = True
    unexpected_entries: List[str] = field(default_factory=list)


@dataclass
class ChangeSandboxResult(OperationResult):
    """Result of nef_change_sandbox."""

    new_path: str = ""


@dataclass
class ImportFailure:
    """A single file that could not be imported, with a structured reason."""

    name: str
    reason: str


@dataclass
class ImportFilesResult(OperationResult):
    """Result of nef_import_files.

    imported  - filenames successfully copied into the sandbox.
    failures  - one ImportFailure(name, reason) per file that could not be imported.
    error     - non-empty whenever the operation did not complete fully.

    Three distinct outcomes:
      Full success:       imported non-empty, failures empty,  error empty.
      Validation failure: imported empty,     failures non-empty (all bad files listed),
                          error non-empty — nothing was copied.
      Copy error:         imported may be non-empty (files copied before the fault),
                          failures has exactly one entry (the file that failed and why),
                          error non-empty — copying stopped at the first OS error.
    """

    imported: List[str] = field(default_factory=list)
    failures: List[ImportFailure] = field(default_factory=list)


@dataclass
class NefStartupResult(OperationResult):
    """Result of nef_read_me_first.

    information — if non-empty, the AI MUST show this to the user verbatim before anything else.
    It carries startup warnings and sandbox status that must be relayed immediately.
    """

    content: str = ""
    information: str = ""


@dataclass
class WarningsShownResult(OperationResult):
    """Result of nef_warnings_shown."""

    success: bool = False


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
    Execute a single NEF command in-process with sandbox write auditing.

    Returns a PipelineResult with stderr as a single-element list.
    """

    result = None
    if args and args[0] != "nef":
        return PipelineResult(
            error="only nef and it sub commands are currently supported"
        )
    elif args:
        # CliRunner.invoke expects arguments after the program name.
        # If "nef" is present as the first argument, we strip it.
        args = args[1:]

        # Get current sandbox path (already changed to sandbox by caller)
        sandbox_path = Path.cwd()

        invoke_kwargs: Dict[str, Any] = dict(input=nef_input if nef_input else None)

        # Wrap execution in audit context to monitor file writes
        violation_error = None
        with audit_sandbox_writes(sandbox_path) as audit_state:
            try:
                runner = CliRunner(mix_stderr=False)
                result = runner.invoke(
                    nef_pipelines.nef_app.app, list(args), **invoke_kwargs
                )
                stdout, stderr = result.output or "", result.stderr or ""
            except SandboxViolation as e:
                # Audit hook caught a sandbox violation (or backstop re-raised it)
                violation_error = str(e)
            except TypeError:
                runner = CliRunner()
                result = runner.invoke(
                    nef_pipelines.nef_app.app, list(args), **invoke_kwargs
                )
                stdout = result.output or ""
                stderr = ""
                if hasattr(result, "stderr") and result.stderr:
                    stderr = result.stderr

            # CliRunner swallowed the SandboxViolation; record it and clear it so
            # the backstop in audit_sandbox_writes.__exit__ does not re-raise
            # after we've already handled it.
            if audit_state.violation_error and not violation_error:
                violation_error = audit_state.violation_error
                audit_state.violation_error = None

        if violation_error:
            return PipelineResult(
                stdout="",
                stderr=[violation_error],
                exit_code=1,
                steps=[list(args)],
                steps_completed=0,
            )

        exit_code = result.exit_code
        result = PipelineResult(
            stdout=stdout,
            stderr=[stderr],
            exit_code=exit_code,
            steps=[list(args)],
            steps_completed=1 if exit_code == 0 else 0,
        )
    return result


def _safe_execute_step(args: List[str], nef_input: str) -> PipelineResult:
    """Execute one pipeline step, returning a PipelineResult even on exception."""
    try:
        result = _execute_command_in_process(args, nef_input)
    except Exception as e:
        result = PipelineResult(
            stdout="", stderr=[f"Exception: {type(e).__name__}: {e}"], exit_code=-1
        )
    return result


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


def _get_native_directory(
    initial_dir: str = "",
) -> Union[str, None, Dict[str, str]]:
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


def select_multiple_files() -> Union[List[Path], None, Dict[str, str]]:
    """\
    Open a native OS file picker allowing multiple file selection.

    Returns list[Path] on success, None if the user cancels,
    or dict{"error": str} when no picker is available or an exception occurs.
    """
    system = sys.platform
    try:
        if system == "darwin":
            script = (
                "set ps to {}\n"
                "try\n"
                "    set selectedFiles to (choose file with multiple selections allowed"
                ' with prompt "Select files to import:")\n'
                "    repeat with f in selectedFiles\n"
                "        set end of ps to POSIX path of f\n"
                "    end repeat\n"
                "on error number -128\n"
                '    return ""\n'
                "end try\n"
                'set AppleScript\'s text item delimiters to "|"\n'
                "return ps as text\n"
            )
            proc = subprocess.run(
                ["osascript", "-"], input=script, capture_output=True, text=True
            )
            raw = proc.stdout.strip()
            if not raw:
                return None
            paths = [Path(p) for p in raw.split("|") if p]
            return paths or None

        elif system == "win32":
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms\n"
                "$f = New-Object System.Windows.Forms.OpenFileDialog\n"
                "$f.Multiselect = $true\n"
                "$f.Title = 'Select files to import'\n"
                "if ($f.ShowDialog() -eq 'OK') { $f.FileNames -join '|' }\n"
            )
            proc = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
            )
            raw = proc.stdout.strip()
            if not raw:
                return None
            paths = [Path(p) for p in raw.split("|") if p]
            return paths or None

        elif system == "linux":
            if shutil.which("zenity"):
                proc = subprocess.run(
                    [
                        "zenity",
                        "--file-selection",
                        "--multiple",
                        "--separator=|",
                        "--title=Select files to import",
                    ],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    return None
                paths = [Path(p) for p in proc.stdout.strip().split("|") if p]
                return paths or None

            elif shutil.which("kdialog"):
                proc = subprocess.run(
                    ["kdialog", "--getopenfilename", ".", "--multiple"],
                    capture_output=True,
                    text=True,
                )
                if proc.returncode != 0:
                    return None
                paths = [Path(p) for p in proc.stdout.strip().splitlines() if p]
                return paths or None

            return {"error": "No file picker available (install zenity or kdialog)"}

        return {"error": f"Unsupported platform: {system}"}

    except Exception as e:
        return {"error": str(e)}


def ask_overwrite_confirmation(filenames: List[str]) -> bool:
    """\
    Show a native OS dialog listing files that already exist and ask whether to
    overwrite all of them.

    Lists up to 10 filenames; when more exist, shows "... and N more".
    Returns True to overwrite all, False to cancel (also the safe default on error).
    """
    _MAX_LISTED = 10
    listed = filenames[:_MAX_LISTED]
    remainder = len(filenames) - _MAX_LISTED

    bullet_lines = [f"  - {f}" for f in listed]
    if remainder > 0:
        bullet_lines.append(f"  ... and {remainder} more")

    msg = (
        "These files already exist in the sandbox:\n"
        + "\n".join(bullet_lines)
        + "\n\nOverwrite all?"
    )

    system = sys.platform
    try:
        if system == "darwin":
            as_lines = ['set msg to "These files already exist in the sandbox:"']
            for f in listed:
                safe_f = f.replace("\\", "\\\\").replace('"', '\\"')
                as_lines.append(f'set msg to msg & return & "  - {safe_f}"')
            if remainder > 0:
                as_lines.append(
                    f'set msg to msg & return & "  ... and {remainder} more"'
                )
            as_lines.append('set msg to msg & return & return & "Overwrite all?"')
            as_lines.append(
                "button returned of (display dialog msg"
                ' buttons {"Cancel", "Overwrite All"} default button "Cancel")'
            )
            script = "\n".join(as_lines)
            proc = subprocess.run(
                ["osascript", "-"], input=script, capture_output=True, text=True
            )
            return proc.stdout.strip() == "Overwrite All"

        elif system == "win32":
            safe_msg = msg.replace('"', '`"')
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms\n"
                f'[System.Windows.Forms.MessageBox]::Show("{safe_msg}",'
                ' "Overwrite?", "YesNo", "Question") -eq "Yes"\n'
            )
            proc = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
            )
            return proc.stdout.strip().lower() == "true"

        elif system == "linux":
            if shutil.which("zenity"):
                proc = subprocess.run(
                    [
                        "zenity",
                        "--question",
                        f"--text={msg}",
                        "--title=Overwrite?",
                        "--ok-label=Overwrite All",
                        "--cancel-label=Cancel",
                    ],
                    capture_output=True,
                )
                return proc.returncode == 0

            elif shutil.which("kdialog"):
                proc = subprocess.run(
                    ["kdialog", "--yesno", msg],
                    capture_output=True,
                )
                return proc.returncode == 0

    except Exception:
        pass
    return False


async def _request_files_to_copy_to_sandbox_or_return_error() -> (
    Tuple[Union[List[Path], None, dict], str]
):
    selected = await asyncio.to_thread(select_multiple_files)

    error = ""
    if selected is None:
        error = "User cancelled file selection"
    elif isinstance(selected, dict):
        error = selected.get("error", "Unknown picker error")
    elif not selected:
        error = "No files selected"

    return selected, error


def _validate_selected_files_for_sandbox(
    selected: list[Path],
) -> Optional[ImportFilesResult]:
    """Type and sandbox checks on each selected path.

    Returns None if all clear, ImportFilesResult to abort if any file fails.
    """
    failures: List[ImportFailure] = []
    result = None
    for source in selected:
        if source.is_symlink():
            failures.append(
                ImportFailure(
                    name=source.name,
                    reason="symbolic link — symbolic links are not allowed",
                )
            )
        elif source.is_dir():
            failures.append(
                ImportFailure(
                    name=source.name,
                    reason="directory — only regular files may be imported",
                )
            )
        else:
            ok, path_error = _validate_path_in_sandbox(source.name)
            if not ok:
                failures.append(ImportFailure(name=source.name, reason=path_error))

    if failures:
        result = ImportFilesResult(
            imported=[],
            failures=failures,
            error=f"{len(failures)} file(s) failed validation",
        )
    return result


async def _confirm_sandbox_overwrites(
    selected: list[Path],
) -> Optional[ImportFilesResult]:
    """Check for sandbox conflicts and ask the user if any exist.

    Returns None if clear to proceed, ImportFilesResult to abort if declined.
    """
    result = None
    conflicts = [s.name for s in selected if Path(s.name).exists()]
    if conflicts:
        confirmed = await asyncio.to_thread(ask_overwrite_confirmation, conflicts)
        if not confirmed:
            result = ImportFilesResult(
                error="User declined to overwrite existing files"
            )
    return result


async def _copy_files_to_sandbox(selected: list[Path], ctx: Any) -> ImportFilesResult:
    error = ""
    imported: List[str] = []
    failures: List[ImportFailure] = []

    total = len(selected)
    for i, source in enumerate(selected, 1):
        dest = Path(source.name)
        try:
            await asyncio.to_thread(shutil.copy2, source, dest)
            imported.append(source.name)
            logger.info("_copy_files: %s -> %s", source, dest)
        except OSError as e:
            failures.append(ImportFailure(name=source.name, reason=str(e)))
            error = f"copy failed — '{source.name}' could not be written"
            break
        if ctx is not None:
            await ctx.report_progress(i, total, message=f"{i}/{total} copied")

    return ImportFilesResult(imported=imported, failures=failures, error=error)
