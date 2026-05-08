import asyncio
import functools
import inspect
import logging
import os
import shlex
import uuid
from pathlib import Path
from typing import Callable, List, Optional

try:
    from fastmcp import Context
except ImportError:
    Context = object  # type: ignore[assignment,misc]

from nef_pipelines.tools.ai.mcp_lib import (
    ChangeSandboxResult,
    CommandHelpResult,
    CommandTableResult,
    DownloadResult,
    ImportFilesResult,
    ListFilesResult,
    NefStartupResult,
    PipelineResult,
    UploadResult,
    WarningsShownResult,
    _build_full_orientation,
    _build_startup_notice,
    _confirm_sandbox_overwrites,
    _copy_files_to_sandbox,
    _execute_command_in_process,
    _get_native_directory,
    _request_files_to_copy_to_sandbox_or_return_error,
    _safe_execute_step,
    _validate_path_in_sandbox,
    _validate_selected_files_for_sandbox,
)

logger = logging.getLogger(__name__)

_MCP_TOOLS: List[Callable] = []
_GENERATED_MCP_TOOLS: List[Callable] = []

_ORIENTATION_TOKEN: str = ""
_WARNINGS_SHOWN: bool = False

_ORIENTATION_ERROR = """\
ERROR: nef_warnings_shown has not been called yet. \
You MUST call nef_read_me_first, show the warnings to the user verbatim \
including information about the sandbox, \
then call nef_warnings_shown with the token from the warnings text.\
"""

_UNGUARDED_TOOLS = {"nef_read_me_first", "nef_warnings_shown"}

_ERROR_READ_ME_FIRST_NOT_CALLED = "nef_read_me_first has not been called — call it first and show warnings to the user"
_ERROR_ALREADY_UNLOCKED = "Invalid token — tools are already unlocked, you don't need to call this command again!"
_ERROR_INVALID_TOKEN = """\
Invalid token. Extract the ORIENTATION-TOKEN from the information field \
of nef_read_me_first and pass it here.\
"""


def _orientation_guard(fn: Callable) -> Callable:
    """Wrap a tool so it errors until nef_warnings_shown has been called."""
    return_type = fn.__annotations__.get("return")

    if asyncio.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if not _WARNINGS_SHOWN:
                return return_type(error=_ORIENTATION_ERROR)
            return await fn(*args, **kwargs)

    else:

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not _WARNINGS_SHOWN:
                return return_type(error=_ORIENTATION_ERROR)
            return fn(*args, **kwargs)

    wrapper.__signature__ = inspect.signature(fn)
    return wrapper


def mcp_tool(fn: Callable) -> Callable:
    """\
    Decorator that marks a function as an MCP tool for auto-registration.
    All tools except nef_read_me_first and nef_warnings_shown are wrapped
    with _orientation_guard.
    """
    if fn.__name__ not in _UNGUARDED_TOOLS:
        fn = _orientation_guard(fn)
    _MCP_TOOLS.append(fn)
    return fn


@mcp_tool
def nef_upload_file(name: str, content: str) -> UploadResult:
    """\
    Write a flat UTF-8 text file into the server's working directory.

    name    - plain filename, no path components (e.g. 'pxo.shifts').
    content - UTF-8 text content to write.

    Returns UploadResult with name and bytes_written.
    bytes_written is the number of encoded UTF-8 bytes, not characters.
    On failure, error is non-empty.
    """
    ok, error = _validate_path_in_sandbox(name)
    if not ok:
        return UploadResult(name=name, error=error)

    path = Path(name)
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return UploadResult(name=name, error=str(e))
    bytes_written = len(content.encode("utf-8"))
    logger.info("nef_upload_file: %s (%d bytes)", name, bytes_written)
    return UploadResult(name=name, bytes_written=bytes_written)


@mcp_tool
def nef_download_file(name: str) -> DownloadResult:
    """\
    Read a flat UTF-8 text file from the server's working directory.

    name - plain filename, no path components (e.g. 'result.nef').

    Returns DownloadResult with name and content.
    On failure, error is non-empty; when the file is missing, available_files is populated.
    """
    ok, error = _validate_path_in_sandbox(name)
    if not ok:
        return DownloadResult(name=name, error=error)

    path = Path(name)
    if not path.exists():
        available = sorted(f.name for f in Path.cwd().iterdir() if f.is_file())
        return DownloadResult(
            name=name,
            error=f"'{name}' not found",
            available_files=available,
        )

    content = path.read_text(encoding="utf-8")
    logger.info("nef_download_file: %s (%d bytes)", name, len(content))
    return DownloadResult(name=name, content=content)


@mcp_tool
def nef_list_files() -> ListFilesResult:
    """\
    List entries in the server's working directory.

    Returns ListFilesResult with files and cwd.
    Any non-file entry (subdirectory, symlink, etc.) is unexpected — NEF tools
    don't create them. When present, error is non-empty and unexpected_entries
    lists them as 'name (type)' strings. Regular files are always listed.
    """
    cwd = Path.cwd()
    regular_files = []
    unexpected = []

    for entry in sorted(cwd.iterdir()):
        if entry.is_symlink():
            unexpected.append(f"{entry.name} (symlink)")
        elif entry.is_file():
            regular_files.append(entry.name)
        elif entry.is_dir():
            unexpected.append(f"{entry.name} (directory)")
        else:
            unexpected.append(f"{entry.name} (other)")

    logger.info(
        "nef_list_files: %d file(s), %d unexpected entry/entries",
        len(regular_files),
        len(unexpected),
    )

    if unexpected:
        return ListFilesResult(
            error="unexpected non-file entries in working directory (NEF tools should not create these)",
            files=regular_files,
            cwd=str(cwd),
            unexpected_entries=unexpected,
        )
    return ListFilesResult(files=regular_files, cwd=str(cwd))


@mcp_tool
async def nef_import_files(ctx: Optional[Context] = None) -> ImportFilesResult:
    """\
    Open a native OS file picker to select files from the local filesystem and copy
    them into the server's sandbox (working directory).

    All file_paths files are validated before any are copied (all-or-none):
    directories and symbolic links are rejected. All validation failures are
    collected and returned together — if any file fails, nothing is copied.
    When file_paths files already exist in the sandbox, a single native dialog
    lists the conflicts (up to 10, then "... and N more") and asks whether to
    overwrite all of them. Declining or cancelling aborts the operation.

    Reports progress after each file is copied (e.g. "1/5 copied").

   Returns ImportFilesResult with:
        imported  - filenames successfully copied into the sandbox
        failures  - one ImportFailure(name, reason) per file that failed validation
                    or could not be copied; empty for operation-level failures
                    (cancelled, no files selected, overwrite declined)
    On failure, error is non-empty, failures may contain filenames and the causes of
    failure and imported is empty.
    """

    file_paths, error = await _request_files_to_copy_to_sandbox_or_return_error()

    result = (
        (ImportFilesResult(error=error) if error else None)
        or _validate_selected_files_for_sandbox(file_paths)
        or await _confirm_sandbox_overwrites(file_paths)
        or await _copy_files_to_sandbox(file_paths, ctx)
    )

    return result


@mcp_tool
def nef_list_commands(command_pattern: str = "*") -> CommandTableResult:
    """
    Get a table listing of NEF pipeline commands.

    command_pattern - pattern to filter commands (e.g., "*sparky*", "frames*")
                      supports wildcards, bash-style parsing of space-separated
                      patterns (e.g. "sparky import")  and comma-separated lists.
                      default: "*" (all commands)

    Returns CommandTableResult with commands_table. On failure, exit_code is non-zero.
    """
    args = ["help", "commands", "--display=table", "--format=markdown"]
    args.extend(shlex.split(command_pattern))
    result = _execute_command_in_process(args)
    return CommandTableResult(
        commands_table=result.stdout,
        exit_code=result.exit_code,
        stderr=result.stderr[0] if result.stderr else "",
    )


@mcp_tool
def nef_get_command_help(
    command_pattern: str = "*",
    group_by_category: bool = False,
) -> CommandHelpResult:
    """
    Get detailed full help documentation for NEF commands.

    command_pattern   - pattern to match commands (e.g., "*sparky*", "frames*", "save")
                        supports wildcards and bash-style parsing of space-separated
                        patterns (e.g. "sparky import").
    group_by_category - if True, organise output by category with headings

    Returns CommandHelpResult with help_text. On failure, exit_code is non-zero.
    """
    args = ["help", "commands", "--display=help", "--format=markdown"]
    if group_by_category:
        args.append("--group-by-category")
    args.extend(shlex.split(command_pattern))
    result = _execute_command_in_process(args)
    return CommandHelpResult(
        help_text=result.stdout,
        exit_code=result.exit_code,
        stderr=result.stderr[0] if result.stderr else "",
    )


@mcp_tool
def nef_read_me_first() -> NefStartupResult:
    """
    Call this FIRST before using any other nef tools — once per session.
    Returns orientation: what NEF-Pipelines is, what resources to read, and what tools are available.
    If you have already received this content in the current session, skip this call.

    IMPORTANT: if information is non-empty, show it to the user verbatim before anything else,
    then call nef_warnings_shown with the token found at the end of the information text.
    """
    global _ORIENTATION_TOKEN

    skip_header = """\
> **Already oriented this session?** \
Skip reading this text and proceed directly with what you need to do next.

---

"""

    content = _build_full_orientation(skip_header=skip_header)

    if _WARNINGS_SHOWN:
        return NefStartupResult(content=content, information="")

    if not _ORIENTATION_TOKEN:
        _ORIENTATION_TOKEN = str(uuid.uuid4())

    information = _build_startup_notice()
    information += f"""\


ORIENTATION-TOKEN: {_ORIENTATION_TOKEN}
AI: You MUST show all of the above to the user verbatim before using this token. \
Then call nef_warnings_shown(token="{_ORIENTATION_TOKEN}") to unlock the NEF tools.\
"""

    return NefStartupResult(
        content=content,
        information=information,
    )


@mcp_tool
def nef_warnings_shown(token: str) -> WarningsShownResult:
    """\
    Call this after nef_read_me_first, once you have shown the warnings to the user verbatim.

    token - the ORIENTATION-TOKEN value from the information field of nef_read_me_first.
            You MUST show all warnings to the user before calling this.

    Returns WarningsShownResult with success=True on success.
    On failure, error is non-empty and the tools remain locked.
    """
    global _WARNINGS_SHOWN

    if not _ORIENTATION_TOKEN:
        return WarningsShownResult(error=_ERROR_READ_ME_FIRST_NOT_CALLED)

    if token != _ORIENTATION_TOKEN:
        if _WARNINGS_SHOWN:
            return WarningsShownResult(error=_ERROR_ALREADY_UNLOCKED)
        return WarningsShownResult(error=_ERROR_INVALID_TOKEN)

    _WARNINGS_SHOWN = True
    return WarningsShownResult(success=True)


@mcp_tool
def nef_execute_pipeline(
    steps: List[List[str]],
    nef_input: str = "",
) -> PipelineResult:
    """
    Execute a sequence of NEF commands in-process, chaining stdout → stdin.

    steps     - list of argument lists, e.g. [["frames","list"], ["save","-"]]
                empty list or empty inner list are both silent no-ops
    nef_input - optional NEF content to seed the first step

    Returns PipelineResult with stdout, stderr (one entry per step),
    exit_code, steps, steps_completed, and success (exit_code == 0).
    """
    result = PipelineResult(steps=steps, stdout=nef_input)

    for args in steps:
        if not args:
            result.stderr.append("")
            continue

        step_result = _safe_execute_step(args, result.stdout)
        result.stderr.append(step_result.stderr[0] if step_result.stderr else "")
        result.exit_code = step_result.exit_code

        if step_result.exit_code == 0:
            result.steps_completed += 1
            result.stdout = step_result.stdout
        else:
            break

    return result


@mcp_tool
def nef_change_sandbox() -> ChangeSandboxResult:
    """\
    Change the server's working directory (sandbox) to a new location using native OS dialog.

    Opens a native directory picker dialog starting at the current sandbox location.
    User selects the new sandbox directory via the OS dialog.

    Returns ChangeSandboxResult with new_path on success.
    On failure or if user cancels, error is non-empty and path remains unchanged.

    Note: This changes the working directory for all subsequent operations.
    Files in the old sandbox are not moved or copied.
    """
    old_path = Path.cwd()

    picked = _get_native_directory(str(old_path))

    if picked is None:
        return ChangeSandboxResult(error="User cancelled directory selection")

    if isinstance(picked, dict) and "error" in picked:
        return ChangeSandboxResult(error=picked["error"])

    try:
        new_path = Path(picked).resolve()
    except Exception as e:
        return ChangeSandboxResult(error=f"Invalid path: {e}")

    if not new_path.exists():
        return ChangeSandboxResult(error=f"Path does not exist: {new_path}")

    if not new_path.is_dir():
        return ChangeSandboxResult(error=f"Path is not a directory: {new_path}")

    try:
        os.chdir(new_path)
    except Exception as e:
        return ChangeSandboxResult(error=f"Failed to change directory: {e}")

    logger.info("nef_change_sandbox: %s -> %s", old_path, new_path)

    return ChangeSandboxResult(new_path=str(new_path))
