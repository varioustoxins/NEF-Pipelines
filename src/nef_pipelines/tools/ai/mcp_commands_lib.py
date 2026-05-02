import logging
from pathlib import Path
from typing import Callable, List

from nef_pipelines.tools.ai.mcp_lib import (
    _RESOURCES,
    CommandHelpResult,
    CommandTableResult,
    DownloadResult,
    ListFilesResult,
    PipelineResult,
    ResourceResult,
    UploadResult,
    _execute_command_in_process,
    _find_resource_file,
    _get_resource_name_from_filename,
    _validate_path_in_sandbox,
)

logger = logging.getLogger(__name__)

_MCP_TOOLS: List[Callable] = []


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
                      supports wildcards and comma-separated lists
                      default: "*" (all commands)

    Returns CommandTableResult with commands_table. On failure, exit_code is non-zero.
    """
    args = ["help", "commands", "--display=table", "--format=markdown", command_pattern]
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
    group_by_category - if True, organise output by category with headings

    Returns CommandHelpResult with help_text. On failure, exit_code is non-zero.
    """
    args = ["help", "commands", "--display=help", "--format=markdown"]
    if group_by_category:
        args.append("--group-by-category")
    args.append(command_pattern)
    result = _execute_command_in_process(args)
    return CommandHelpResult(
        help_text=result.stdout,
        exit_code=result.exit_code,
        stderr=result.stderr[0] if result.stderr else "",
    )


@mcp_tool
def nef_read_me_first() -> ResourceResult:
    """
    Call this FIRST before using any other nef tools — once per session.
    Returns orientation: what NEF-Pipelines is, what resources to read, and what tools are available.
    If you have already received this content in the current session, skip this call.
    """
    preamble_file = _find_resource_file("preamble")
    preamble = (
        preamble_file.read_text() if preamble_file and preamble_file.is_file() else ""
    )

    skip_header = (
        "> **Already oriented this session?** "
        "Skip this call and proceed directly with the tools.\n\n"
        "---\n\n"
    )
    resource_footer = (
        "\n\n---\n\n"
        "**Resources unavailable via `nef://`?**  "
        "Use `nef_read_resource(name)` to fetch any resource document:\n"
        "`readme` · `skill` · `cli-idioms` · `nef` · `nmr-data` · `star`"
    )

    return ResourceResult(content=skip_header + preamble + resource_footer)


@mcp_tool
def nef_read_resource(name: str) -> ResourceResult:
    """
    Read a NEF-Pipelines documentation resource by name.
    Equivalent to reading nef://<name> via the resources interface; use this when
    the resources interface is unavailable.

    name - resource to fetch: readme, skill, cli-idioms, nef, nmr-data, star, preamble

    Returns ResourceResult with content and available_resources. On failure, error is non-empty.
    """
    available = sorted(
        _get_resource_name_from_filename(f.name)
        for f in _RESOURCES.iterdir()
        if f.name.endswith(".md")
    )

    f = _find_resource_file(name)
    if f is None:
        return ResourceResult(
            error=f"Resource '{name}' not found. Available: {available}",
            available_resources=available,
        )

    return ResourceResult(content=f.read_text(), available_resources=available)


def _safe_execute_step(args: List[str], nef_input: str) -> PipelineResult:
    """Execute one pipeline step, returning a PipelineResult even on exception."""
    try:
        return _execute_command_in_process(args, nef_input)
    except Exception as e:
        return PipelineResult(
            stdout="", stderr=[f"Exception: {type(e).__name__}: {e}"], exit_code=-1
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
