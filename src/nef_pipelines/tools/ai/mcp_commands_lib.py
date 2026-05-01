from typing import Any, Dict, List

from nef_pipelines.tools.ai.mcp_lib import (
    _RESOURCES,
    _find_resource_file,
    execute_command_in_process,
    resource_name,
)


def nef_list_commands(command_pattern: str = "*") -> Dict[str, Any]:
    """
    Get a table listing of NEF pipeline commands.

    command_pattern - pattern to filter commands (e.g., "*sparky*", "frames*")
                      supports wildcards and comma-separated lists
                      default: "*" (all commands)

    Returns {"commands_table": str, "success": bool, "exit_code": int, "stderr": str}.
    """
    args = ["help", "commands", "--display=table", "--format=markdown", command_pattern]
    result = execute_command_in_process(args)
    return {
        "commands_table": result["stdout"],
        "success": result["success"],
        "exit_code": result["exit_code"],
        "stderr": result.get("stderr", ""),
    }


def nef_get_command_help(
    command_pattern: str = "*",
    group_by_category: bool = False,
) -> Dict[str, Any]:
    """
    Get detailed full help documentation for NEF commands.

    command_pattern   - pattern to match commands (e.g., "*sparky*", "frames*", "save")
    group_by_category - if True, organise output by category with headings

    Returns {"help_text": str, "success": bool, "exit_code": int, "stderr": str}.
    """
    args = ["help", "commands", "--display=help", "--format=markdown"]
    if group_by_category:
        args.append("--group-by-category")
    args.append(command_pattern)
    result = execute_command_in_process(args)
    return {
        "help_text": result["stdout"],
        "success": result["success"],
        "exit_code": result["exit_code"],
        "stderr": result.get("stderr", ""),
    }


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


def nef_read_resource(name: str) -> Dict[str, Any]:
    """
    Read a NEF-Pipelines documentation resource by name.
    Equivalent to reading nef://<name> via the resources interface; use this when
    the resources interface is unavailable.

    name - resource to fetch: readme, skill, cli-idioms, nef, nmr-data, star, preamble

    Returns {"content": str, "success": bool, "available_resources": list}.
    """
    available = sorted(
        resource_name(f.name) for f in _RESOURCES.iterdir() if f.name.endswith(".md")
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


def nef_execute_command(args: List[str], nef_input: str = "") -> Dict[str, Any]:
    """
    Execute a single NEF command in-process and return its output.

    args      - command tokens following 'nef', e.g. ["frames", "list"]
    nef_input - optional NEF content to supply as input

    Returns {"stdout": str, "stderr": str, "exit_code": int, "success": bool}.
    """
    return execute_command_in_process(args, nef_input)


def nef_execute_pipeline(
    steps: List[Dict[str, Any]],
    nef_input: str = "",
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Execute a fully composed NEF pipeline in-process with stdout→input chaining.

    steps     - list of {"args": [...]} dicts, executed in order
    nef_input - optional NEF content to seed the first step
    verbose   - include per-step stdout/input_length/output_length in step_results

    Returns {"stdout", "stderr", "exit_code", "success", "step_results", "failed_step"}.
    """
    if not steps:
        return {
            "stdout": "",
            "stderr": "No steps provided",
            "exit_code": -1,
            "success": False,
            "step_results": [],
            "failed_step": None,
        }

    current_output = nef_input
    step_results = []
    all_stderr_parts = []

    for i, step in enumerate(steps, start=1):
        args = step.get("args", [])
        if not args:
            return {
                "stdout": "",
                "stderr": f"Step {i} has no args. Step data: {step}",
                "exit_code": -1,
                "success": False,
                "step_results": step_results,
                "failed_step": i,
            }

        try:
            result = execute_command_in_process(args, current_output)
        except Exception as e:
            error_msg = f"Exception executing step {i}: {type(e).__name__}: {e}"
            step_results.append(
                {
                    "step": i,
                    "args": args,
                    "exit_code": -1,
                    "success": False,
                    "stderr": error_msg,
                }
            )
            return {
                "stdout": "",
                "stderr": error_msg,
                "exit_code": -1,
                "success": False,
                "step_results": step_results,
                "failed_step": i,
            }

        step_result = {
            "step": i,
            "args": args,
            "exit_code": result["exit_code"],
            "success": result["success"],
            "stderr": result["stderr"],
        }
        if verbose:
            step_result["stdout"] = result["stdout"][:1000]
            step_result["input_length"] = len(current_output)
            step_result["output_length"] = len(result["stdout"])

        step_results.append(step_result)

        if result["stderr"]:
            all_stderr_parts.append(f"[step {i}] {result['stderr']}")

        if not result["success"]:
            return {
                "stdout": result["stdout"],
                "stderr": "\n".join(all_stderr_parts)
                or f"Command failed with exit code {result['exit_code']}",
                "exit_code": result["exit_code"],
                "success": False,
                "step_results": step_results,
                "failed_step": i,
            }

        current_output = result["stdout"]

    return {
        "stdout": current_output,
        "stderr": "\n".join(all_stderr_parts),
        "exit_code": 0,
        "success": True,
        "step_results": step_results,
        "failed_step": None,
    }
