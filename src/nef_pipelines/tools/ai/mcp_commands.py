import logging
import os
import shlex
from pathlib import Path
from typing import Callable, List

from nef_pipelines.tools.ai.mcp_lib import (
    _STARTUP_CONTEXT,
    ChangeSandboxResult,
    CommandHelpResult,
    CommandTableResult,
    DownloadResult,
    ListFilesResult,
    NefStartupResult,
    PipelineResult,
    UploadResult,
    _build_full_orientation,
    _build_startup_notice,
    _execute_command_in_process,
    _get_native_directory,
    _validate_path_in_sandbox,
)

logger = logging.getLogger(__name__)

_MCP_TOOLS: List[Callable] = []
_GENERATED_MCP_TOOLS: List[Callable] = []


def mcp_tool(fn: Callable) -> Callable:
    """\
    Decorator that marks a function as an MCP tool for auto-registration.

    Appends the function to _MCP_TOOLS in declaration order so server_lib
    can register them without a manual list.
    """
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
            error=(
                "unexpected non-file entries in working directory "
                "(NEF tools should not create these)"
            ),
            files=regular_files,
            cwd=str(cwd),
            unexpected_entries=unexpected,
        )
    return ListFilesResult(files=regular_files, cwd=str(cwd))


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

    IMPORTANT: if information is non-empty, show it to the user verbatim before anything else.
    """
    skip_header = (
        "> **Already oriented this session?** "
        "Skip reading this text and proceed directly with what you need to do next.\n\n"
        "---\n\n"
    )

    # Use the unified orientation builder for complete output
    content = _build_full_orientation(skip_header=skip_header)

    # Build startup notice for information field (unified helper)
    information = _build_startup_notice(_STARTUP_CONTEXT)

    return NefStartupResult(
        content=content,
        information=information,
    )


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
