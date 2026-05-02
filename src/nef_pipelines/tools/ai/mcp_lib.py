import logging
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, List

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


def _execute_command_in_process(
    args: List[str],
    nef_input: str = "",
) -> Dict[str, Any]:
    """
    Execute a NEF command in-process with stdin/stdout streaming.

    Returns {"stdout": str, "stderr": str, "exit_code": int}.
    """
    runner = CliRunner()
    result = runner.invoke(
        _nef_app.app, list(args), input=nef_input if nef_input else None
    )

    stderr = ""
    if hasattr(result, "stderr") and result.stderr:
        stderr = result.stderr

    stdout = result.output or ""
    if stderr:
        stdout = (stdout + stderr) if stdout else stderr

    return {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": result.exit_code,
    }


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
