"""
In-process command execution for MCP server using temporary files.

Executes Typer commands directly in the current process with output capture,
avoiding subprocess overhead. Uses temporary files on disk for NEF content.
"""

import tempfile
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List

from typer.testing import CliRunner

from nef_pipelines.nef_app_runner import create_nef_app

# Initialize the nef app once at module load
_nef_app = create_nef_app()

# Import all plugin modules to register commands (same as main.py)
_modules = [
    "nef_pipelines.tools.help",
    "nef_pipelines.tools.chains",
    "nef_pipelines.tools.entry",
    "nef_pipelines.tools.fit",
    "nef_pipelines.tools.frames",
    "nef_pipelines.tools.globals",
    "nef_pipelines.tools.header",
    "nef_pipelines.tools.loops",
    "nef_pipelines.tools.namespace",
    "nef_pipelines.tools.peaks",
    "nef_pipelines.tools.plot",
    "nef_pipelines.tools.save",
    "nef_pipelines.tools.series",
    "nef_pipelines.tools.shifts",
    "nef_pipelines.tools.simulate",
    "nef_pipelines.tools.sink",
    "nef_pipelines.tools.stream",
    "nef_pipelines.tools.test",
    "nef_pipelines.tools.version",
    "nef_pipelines.transcoders.csv",
    "nef_pipelines.transcoders.deep",
    "nef_pipelines.transcoders.echidna",
    "nef_pipelines.transcoders.fasta",
    "nef_pipelines.transcoders.mars",
    "nef_pipelines.transcoders.modelfree",
    "nef_pipelines.transcoders.nmrpipe",
    "nef_pipelines.transcoders.nmrview",
    "nef_pipelines.transcoders.pales",
    "nef_pipelines.transcoders.rcsb",
    "nef_pipelines.transcoders.rpf",
    "nef_pipelines.transcoders.shifty",
    "nef_pipelines.transcoders.shiftx2",
    "nef_pipelines.transcoders.sparky",
    "nef_pipelines.transcoders.nmrstar",
    "nef_pipelines.transcoders.talos",
    "nef_pipelines.transcoders.ucbshift",
    "nef_pipelines.transcoders.xcamshift",
    "nef_pipelines.transcoders.xeasy",
    "nef_pipelines.transcoders.xplor",
]
for module_name in _modules:
    try:
        import_module(module_name)
    except Exception:
        pass  # Silently ignore failed imports


def execute_command_in_process(
    args: List[str],
    nef_input: str = "",
) -> Dict[str, Any]:
    """
    Execute a NEF command in-process with captured output using temporary files.

    Args:
        args: Command arguments (e.g., ["frames", "tabulate", "--show-all"])
        nef_input: NEF content to use as input (will be written to temp file)

    Returns:
        {
            "stdout": str,       # Captured stdout
            "stderr": str,       # Captured stderr (may be mixed into stdout)
            "exit_code": int,    # 0 for success
            "success": bool,
        }
    """
    temp_file = None

    # Debug: log what we're receiving
    import sys

    print("[DEBUG] execute_command_in_process called with:", file=sys.stderr)
    print(f"[DEBUG]   args: {args}", file=sys.stderr)
    input_type = type(nef_input)
    length = len(nef_input) if nef_input else "N/A"
    representation = repr(nef_input[:50] if nef_input else nef_input)
    msg = (
        f"[DEBUG]   nef_input type: {input_type}, len: {length}, repr: {representation}"
    )
    print(
        msg,
        file=sys.stderr,
    )
    print(f"[DEBUG]   bool(nef_input): {bool(nef_input)}", file=sys.stderr)

    try:
        # Write NEF content to temporary file ONLY if there's actual content
        # Empty string, None, or whitespace-only should NOT create temp file or add --in
        if nef_input:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".nef", delete=False
            ) as f:
                f.write(nef_input)
                temp_file = Path(f.name)

            # Add temp file as input argument if not already specified
            # Only add if we actually created a temp file
            if "--in" not in args and "-i" not in args and "--input" not in args:
                args = list(args) + ["--in", str(temp_file)]

        # Use CliRunner to execute command in-process
        # CliRunner automatically captures stdout/stderr
        runner = CliRunner()

        # Invoke the Typer app with the arguments
        result = runner.invoke(_nef_app.app, args)

        # Handle stderr - newer click versions may separate it
        # Many nef commands write output to stderr, so we combine both
        stderr = ""
        if hasattr(result, "stderr") and result.stderr:
            stderr = result.stderr

        # Combine stdout and stderr to ensure we capture all output
        # Many commands write their primary output to stderr
        combined_output = result.stdout
        if stderr:
            combined_output = (combined_output + stderr) if combined_output else stderr

        return {
            "stdout": combined_output,
            "stderr": stderr,
            "exit_code": result.exit_code,
            "success": result.exit_code == 0,
        }

    finally:
        # Cleanup temporary file
        if temp_file and temp_file.exists():
            temp_file.unlink(missing_ok=True)
