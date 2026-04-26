from typing import Annotated, List, Tuple

import typer
from tabulate import tabulate

from nef_pipelines.lib.namespace_lib import get_registered_namespaces
from nef_pipelines.lib.table_format_lib import TableOutputFormat
from nef_pipelines.tools.namespace import namespace_app

_FORMAT_HELP = "output format:\n" + "\n".join(
    f"- {fmt.value:<10} – {fmt.description}" for fmt in TableOutputFormat
)


@namespace_app.command(name="defined")
def defined_namespaces(
    output_format: Annotated[
        TableOutputFormat,
        typer.Option(
            "--format",
            "-f",
            help=_FORMAT_HELP,
            show_default=True,
        ),
    ] = TableOutputFormat.SIMPLE,
) -> None:
    """- list the internally defined NEF namespaces, their programmes and intended use"""

    result = pipe(output_format)
    print(result)


def pipe(output_format: TableOutputFormat) -> str:
    """
    Build a table of internally defined NEF namespaces.

    Args:
        output_format: Output format for the table.

    Returns:
        Formatted string containing the namespace table.
    """

    rows = _namespace_rows()
    headers = ["Namespace", "Programme", "Use"]

    return tabulate(rows, headers=headers, tablefmt=output_format.tablefmt)


def _namespace_rows() -> List[Tuple[str, str, str]]:
    """Return table rows built from the registered namespaces."""

    return [
        (namespace, programme, use)
        for namespace, (programme, use) in get_registered_namespaces().items()
    ]
