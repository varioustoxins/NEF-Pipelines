from typing import Any, Callable, Dict, List

from nef_pipelines.tools.ai.mcp_lib import (
    _RESOURCES,
    CommandResult,
    PipelineResult,
    _execute_command_in_process,
    _find_resource_file,
    _get_resource_name_from_filename,
)

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
def nef_list_commands(command_pattern: str = "*") -> Dict[str, Any]:
    """
    Get a table listing of NEF pipeline commands.

    command_pattern - pattern to filter commands (e.g., "*sparky*", "frames*")
                      supports wildcards and comma-separated lists
                      default: "*" (all commands)

    Returns {"commands_table": str, "exit_code": int, "stderr": str}.
    """
    args = ["help", "commands", "--display=table", "--format=markdown", command_pattern]
    result = _execute_command_in_process(args)
    return {
        "commands_table": result.stdout,
        "exit_code": result.exit_code,
        "stderr": result.stderr,
    }


@mcp_tool
def nef_get_command_help(
    command_pattern: str = "*",
    group_by_category: bool = False,
) -> Dict[str, Any]:
    """
    Get detailed full help documentation for NEF commands.

    command_pattern   - pattern to match commands (e.g., "*sparky*", "frames*", "save")
    group_by_category - if True, organise output by category with headings

    Returns {"help_text": str, "exit_code": int, "stderr": str}.
    """
    args = ["help", "commands", "--display=help", "--format=markdown"]
    if group_by_category:
        args.append("--group-by-category")
    args.append(command_pattern)
    result = _execute_command_in_process(args)
    return {
        "help_text": result.stdout,
        "exit_code": result.exit_code,
        "stderr": result.stderr,
    }


@mcp_tool
def nef_read_me_first() -> Dict[str, Any]:
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

    return {
        "content": skip_header + preamble + resource_footer,
        "success": True,
    }


@mcp_tool
def nef_read_resource(name: str) -> Dict[str, Any]:
    """
    Read a NEF-Pipelines documentation resource by name.
    Equivalent to reading nef://<name> via the resources interface; use this when
    the resources interface is unavailable.

    name - resource to fetch: readme, skill, cli-idioms, nef, nmr-data, star, preamble

    Returns {"content": str, "success": bool, "available_resources": list}.
    """
    available = sorted(
        _get_resource_name_from_filename(f.name)
        for f in _RESOURCES.iterdir()
        if f.name.endswith(".md")
    )

    f = _find_resource_file(name)
    if f is None:
        return {
            "content": "",
            "success": False,
            "error": f"Resource '{name}' not found. Available: {available}",
            "available_resources": available,
        }

    return {
        "content": f.read_text(),
        "success": True,
        "available_resources": available,
    }


@mcp_tool
def nef_execute_command(args: List[str], nef_input: str = "") -> Dict[str, Any]:
    """
    Execute a single NEF command in-process and return its output.

    args      - command tokens following 'nef', e.g. ["frames", "list"]
    nef_input - optional NEF content to supply as stdin

    Returns {"stdout": str, "stderr": str, "exit_code": int}.
    """
    result = _execute_command_in_process(args, nef_input)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
    }


def _safe_execute_step(args: List[str], nef_input: str) -> CommandResult:
    """Execute one pipeline step, returning a CommandResult even on exception."""
    try:
        return _execute_command_in_process(args, nef_input)
    except Exception as e:
        return CommandResult(
            stdout="", stderr=f"Exception: {type(e).__name__}: {e}", exit_code=-1
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
        result.stderr.append(step_result.stderr or "")
        result.exit_code = step_result.exit_code

        if step_result.exit_code == 0:
            result.steps_completed += 1
            result.stdout = step_result.stdout
        else:
            break

    return result
