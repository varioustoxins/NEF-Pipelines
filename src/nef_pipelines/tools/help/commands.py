# TODO: Tests for this module are planned
# See plans/help_commands_testing_plan.md for implementation details
# Tests will be located in src/nef_pipelines/tests/tools/help/test_commands.py

import os
import sys
from contextlib import redirect_stdout
from enum import Enum, auto
from fnmatch import fnmatch
from io import StringIO
from itertools import groupby
from typing import Annotated, List, Optional

import click
import typer
from ordered_set import OrderedSet
from rich.console import Console
from rich.table import Table
from rich.tree import Tree as RichTree
from strenum import LowercaseStrEnum
from tabulate import tabulate
from treelib import Tree
from typer import Context

from nef_pipelines.lib.typer_lib import is_rich_in_use
from nef_pipelines.lib.util import parse_comma_separated_options
from nef_pipelines.tools.help import help_app

VERBOSE_HELP = """\
    display more verbose information about NEF-Pipelines and its environment,
    [ignored with the --version option]"
"""


class TreeNodeType(Enum):
    """Type of node in the command tree."""

    ROOT = auto()
    GROUP = auto()
    COMMAND = auto()


class DisplayMode(LowercaseStrEnum):
    """Display mode for command help output."""

    Auto = auto()  # Smart: table for multiple commands, full help for single command
    Tree = auto()  # Hierarchical tree view
    Table = auto()  # Always show table listing
    Help = auto()  # Always show full help for each command


class OutputFormat(LowercaseStrEnum):
    """Output format - works consistently across all display modes."""

    Simple = auto()  # Rich terminal with colours/boxes (default)
    Markdown = auto()  # Pure Markdown (AI-friendly, no ANSI codes)
    Html = auto()  # HTML output with inline CSS


# noinspection PyUnusedLocal
@help_app.command()
def commands(
    context: Context,
    display: Annotated[
        DisplayMode,
        typer.Option(
            "--display",
            help="""\
                display mode: auto (smart: table for multiple, help for single), tree (hierarchical),
                table (always table), help (always full help for each command)
            """,
        ),
    ] = DisplayMode.Auto,
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            show_choices=False,
            help="""\
                output format: simple (Rich terminal), markdown (pure Markdown for AI), html (HTML with CSS)
            """,
        ),
    ] = OutputFormat.Simple,
    group_by_category: Annotated[
        bool,
        typer.Option(
            "--group-by-category",
            help="display separate tables/help for each category with headings",
        ),
    ] = False,
    matchers: Annotated[
        List[str],
        typer.Argument(
            help="select commands to display multiple items, wildcards and comma separated lists are allowed"
        ),
    ] = None,
    python: Annotated[
        Optional[bool],
        typer.Option(
            help="""\
                filter commands: --python shows only commands with Python interfaces, --no-python shows only commands
                without Python interfaces, default shows all
            """
        ),
    ] = None,
    no_rich: Annotated[
        bool,
        typer.Option(
            "--no-rich",
            help="disable Rich terminal formatting (useful for testing or plain text output)",
        ),
    ] = False,
):
    r"""\- display and filter the help for commands

    Commands are shown in a hierarchical tree view by default.
    Use --display to control what is shown and --format to control how it's formatted.
    \b
    **Display Modes:**
    - auto (default): Smart mode - table for multiple commands, full help for one command, rich formatting if available
    - tree: Hierarchical tree view
    - table: Always show table listing
    - help: Always show full help for each command

    **Format Options (work across all display modes):**
    - simple (default): Rich terminal with colours and boxes
    - markdown: Pure Markdown (ideal for AI/LLM consumption)
    - html: HTML output with inline CSS styling

    **Grouping:**
    - use `--group-by-category` to separate by category (recommended for AIs)

    Examples:

    ```bash
        nef help commands                                                      # Tree view (default)
        nef help commands --display=auto                                       # Smart: table or help
        nef help commands --display=table                                      # Always table
        nef help commands --display=help                                       # Always full help
        nef help commands --display=table --format=markdown                    # Markdown table
        nef help commands --display=help --format=markdown                     # Pure Markdown help
        nef help commands --display=help --format=markdown --group-by-category # Grouped Markdown
        nef help commands --display=tree --format=html                         # HTML tree
        nef help commands save --display=auto                                  # Auto shows full help (1 match)
        nef help commands "*sparky*" --display=auto                            # Auto shows table (multiple)
        nef help commands plot                                                 # Filter to plot commands
    ```
    """
    # Temporarily disable Rich if requested
    old_rich_setting = os.environ.get("TYPER_USE_RICH")

    if no_rich:
        os.environ["TYPER_USE_RICH"] = "0"

    try:
        output = pipe(matchers, output_format, group_by_category, display, python)
        print(output, file=sys.stderr)
    finally:
        # Restore original Rich setting
        if no_rich:
            if old_rich_setting is None:
                os.environ.pop("TYPER_USE_RICH", None)
            else:
                os.environ["TYPER_USE_RICH"] = old_rich_setting


def pipe(
    matchers: Optional[List[str]] = None,
    output_format: OutputFormat = OutputFormat.Simple,
    group_by_category: bool = False,
    display: DisplayMode = DisplayMode.Auto,
    python: Optional[bool] = None,
    plain: bool = False,
) -> str:
    """Generate formatted help text for commands.

    This is the worker function that generates help output as a string.
    Used by the commands() CLI function and can be called from Python code.

    Context Access:
        When called from CLI, Context is available via click.get_current_context().
        When called from Python, you must create a Context and use with ctx.scope():.

    Args:
        matchers: List of patterns to match commands (None means all commands)
        output_format: Output format (simple, markdown, html)
        group_by_category: Whether to group by category
        display: Display mode (auto, tree, table, help)
        python: None (show all), True (only Python), False (only non-Python)
        plain: If True, use plain text without colours or boxes (internal option, not CLI)

    Returns:
        Formatted help text as string (with ANSI colour codes for Rich output unless plain=True)

    Raises:
        RuntimeError: If called outside of Click context and no context is available
    """
    context = _get_click_context()

    matchers = parse_comma_separated_options(matchers)
    if not matchers:
        matchers = ["*"]

    filtered_tree = _build_command_tree(context, matchers, python)
    num_commands = _count_commands_in_tree(filtered_tree)

    # Determine actual display mode based on DisplayMode and command count
    if display == DisplayMode.Auto:
        if num_commands == 1:
            actual_display = DisplayMode.Help
        else:
            actual_display = DisplayMode.Table
    else:
        actual_display = display

    # Execute the appropriate display mode
    if actual_display == DisplayMode.Tree:
        return _display_tree(filtered_tree, output_format, plain)
    elif actual_display == DisplayMode.Table:
        return _display_table(filtered_tree, output_format, group_by_category, plain)
    elif actual_display == DisplayMode.Help:
        return _display_full_command(
            filtered_tree, output_format, group_by_category, plain
        )
    else:
        return _display_tree(filtered_tree, output_format, plain)


def _get_click_context() -> Context:
    """Get or create a Click context for command introspection.

    Returns:
        Click Context object
    """
    try:
        context = click.get_current_context()
    except RuntimeError:
        import typer

        from nef_pipelines import nef_app

        command = typer.main.get_command(nef_app.app)
        context = click.Context(command)
    return context


def _count_commands_in_tree(tree: Tree) -> int:
    """Count the number of command nodes (leaf nodes) in a tree.

    Args:
        tree: Tree object to count commands in

    Returns:
        Number of command nodes (leaves) in the tree
    """
    return sum(1 for node in tree.all_nodes_itr() if node.is_leaf())


def _extract_commands_data(tree: Tree) -> List[tuple]:
    """Extract command data from filtered tree for table/list display.

    Args:
        tree: Filtered command tree

    Returns:
        List of (cmd_path_str, category, first_line_help, cmd_obj) tuples
    """
    commands_data = []
    group_panels = {}

    for node in tree.all_nodes_itr():
        if node.identifier == tree.root:
            continue

        cmd_obj = node.data
        path = tuple(node.identifier.split("."))
        node_type = _get_tree_node_type(path, cmd_obj)

        if node_type == TreeNodeType.GROUP:
            if hasattr(cmd_obj, "rich_help_panel") and cmd_obj.rich_help_panel:
                group_panels[path] = cmd_obj.rich_help_panel
            continue

        if node_type != TreeNodeType.COMMAND:
            continue

        cmd_path_str = " ".join(path)
        cmd_type = _get_rich_help_panel(path, group_panels, cmd_obj)

        help_text = ""
        if hasattr(cmd_obj, "callback") and cmd_obj.callback:
            help_text = cmd_obj.callback.__doc__ or ""
        elif hasattr(cmd_obj, "help"):
            help_text = cmd_obj.help or ""

        first_line = help_text.split("\n")[0].strip() if help_text else ""
        first_line = first_line.lstrip("-").strip()
        first_line = first_line.replace("\\-", "").strip()
        first_line = " ".join(first_line.split())

        commands_data.append((cmd_path_str, cmd_type, first_line, cmd_obj))

    commands_data = sorted(commands_data, key=lambda x: (x[1], x[0]))
    return commands_data


def _display_markdown_tree(tree: Tree) -> str:
    """Display commands in hierarchical tree view using plain text markdown.

    Args:
        tree: Filtered command tree to display

    Returns:
        Markdown formatted tree as string
    """
    if len(tree) == 0:
        return ""

    with StringIO() as output_buffer:
        output_buffer.write("# Command Tree\n\n```\n")

        # Get the root node
        root = tree.get_node(tree.root)
        output_buffer.write(f"{root.tag}\n")

        # Build the tree recursively using box-drawing characters
        def add_children(node_id, prefix=""):
            children = tree.children(node_id)
            for i, child in enumerate(children):
                is_last = i == len(children) - 1
                connector = "└── " if is_last else "├── "
                output_buffer.write(f"{prefix}{connector}{child.tag}\n")

                # Recursively add children with updated prefix
                if not child.is_leaf():
                    extension = "    " if is_last else "│   "
                    add_children(child.identifier, prefix + extension)

        add_children(tree.root)
        output_buffer.write("```\n\n")
        output_buffer.write(
            "**Key:** [X] has a python function [P]ipe / [C]md, [α] alpha feature\n"
        )

        return output_buffer.getvalue()


def _display_html_tree(tree: Tree) -> str:
    """Display commands in hierarchical tree view using HTML with CSS.

    Args:
        tree: Filtered command tree to display

    Returns:
        HTML formatted tree as string
    """
    if len(tree) == 0:
        return ""

    with StringIO() as output_buffer:
        # Add CSS styling
        output_buffer.write(
            """<style>
.command-tree {
    font-family: system-ui, -apple-system, sans-serif;
    line-height: 1.6;
    margin: 20px 0;
    padding: 15px;
    background: #fafafa;
    border-radius: 8px;
    border: 1px solid #eee;
}
.command-tree ul {
    list-style-type: none;
    padding-left: 24px;
    margin: 0;
}
.command-tree > ul {
    padding-left: 0;
}
.command-tree li {
    margin: 4px 0;
    position: relative;
}
.tree-root {
    font-weight: 800;
    color: #007acc;
    font-size: 1.2em;
    margin-bottom: 8px;
}
.tree-group {
    color: #d48806;
    font-weight: 600;
}
.tree-command {
    color: #389e0d;
}
.tree-decorator {
    color: #8c8c8c;
    font-size: 0.85em;
    margin-left: 6px;
    font-family: ui-monospace, SFMono-Regular, monospace;
}
.tree-decorator-python {
    color: #096dd9;
    font-weight: bold;
}
.tree-decorator-alpha {
    color: #eb2f96;
    font-weight: bold;
}
.tree-key {
    margin-top: 16px;
    padding: 12px;
    background-color: #f0f5ff;
    border-left: 4px solid #1890ff;
    border-radius: 0 4px 4px 0;
    font-size: 0.9em;
    color: #595959;
}
</style>
<div class="command-tree">
"""
        )

        # Get the root node
        root = tree.get_node(tree.root)
        output_buffer.write(f'<div class="tree-root">{root.tag}</div>\n')

        # Build the tree recursively using nested lists
        def add_children(node_id):
            children = tree.children(node_id)
            if not children:
                return

            output_buffer.write("<ul>\n")
            for child in children:
                # Parse the tag to extract name and decorators
                tag_parts = child.tag.split()
                name = tag_parts[0]
                decorators = tag_parts[1:] if len(tag_parts) > 1 else []

                # Determine node class
                if child.is_leaf():
                    node_class = "tree-command"
                else:
                    node_class = "tree-group"

                output_buffer.write(f'<li><span class="{node_class}">{name}</span>')

                # Add decorators
                for decorator in decorators:
                    if "[P]" in decorator or "[C]" in decorator:
                        output_buffer.write(
                            f'<span class="tree-decorator tree-decorator-python">{decorator}</span>'
                        )
                    elif "[α]" in decorator:
                        output_buffer.write(
                            f'<span class="tree-decorator tree-decorator-alpha">{decorator}</span>'
                        )
                    else:
                        output_buffer.write(
                            f'<span class="tree-decorator">{decorator}</span>'
                        )

                # Recursively add children
                if not child.is_leaf():
                    add_children(child.identifier)

                output_buffer.write("</li>\n")

            output_buffer.write("</ul>\n")

        add_children(tree.root)

        output_buffer.write("</div>\n")
        text = " [X] has a python function [P]ipe / [C]md, [α] alpha feature"
        text = f'<div class="tree-key"><strong>Key:</strong>{text}</div>\n'

        output_buffer.write(text)

        return output_buffer.getvalue()


def _display_tree(
    tree: Tree, output_format: OutputFormat = OutputFormat.Simple, plain: bool = False
) -> str:
    """Display commands in hierarchical tree view.

    Args:
        tree: Filtered command tree to display
        output_format: Output format (simple, markdown, html)
        plain: If True, use plain text without colours or boxes

    Returns:
        Formatted tree as string
    """
    if len(tree) == 0:
        return ""

    if output_format == OutputFormat.Markdown:
        return _display_markdown_tree(tree)
    elif output_format == OutputFormat.Html:
        return _display_html_tree(tree)
    elif output_format == OutputFormat.Simple:
        if is_rich_in_use() and not plain:
            return _display_rich_tree(tree, plain)
        else:
            output = tree.show(stdout=False)
            output += "\n\nkey: [X] has a python function [P]ipe / [C]md"
            output += "\n     [α] alpha feature"
            return output
    else:
        # Fallback to simple
        return _display_tree(tree, OutputFormat.Simple, plain)


def _display_full_command(
    tree: Tree,
    output_format: OutputFormat,
    group_by_category: bool,
    plain: bool = False,
) -> str:
    """Display full detailed help for commands.

    Args:
        tree: Filtered command tree
        output_format: Output format (simple, markdown, html)
        group_by_category: Whether to group by category
        plain: If True, use plain text without colours or boxes

    Returns:
        Formatted help text as string
    """
    if output_format == OutputFormat.Simple:
        result = _display_full_format(tree, group_by_category, plain)
    elif output_format == OutputFormat.Markdown:
        result = _display_markdown_full_format(tree, group_by_category)
    elif output_format == OutputFormat.Html:
        result = _display_html_full_format(tree, group_by_category)
    else:
        result = ""

    return result


def _display_table(
    tree: Tree,
    output_format: OutputFormat,
    group_by_category: bool,
    plain: bool = False,
) -> str:
    """Display commands in table format.

    Args:
        tree: Filtered command tree
        output_format: Output format (simple, markdown, html)
        group_by_category: Whether to group by category
        plain: If True, use plain text without colours or boxes

    Returns:
        Formatted table as string
    """
    if output_format == OutputFormat.Simple:
        result = _display_list_format(tree, "simple", group_by_category, plain)
    elif output_format == OutputFormat.Markdown:
        # Use 'pipe' format for proper markdown tables with | separators
        result = _display_list_format(tree, "pipe", group_by_category, plain)
    elif output_format == OutputFormat.Html:
        result = _display_html_table_format(tree, group_by_category)
    else:
        result = _display_list_format(tree, "simple", group_by_category, plain)

    return result


def _display_rich_tree(tree: Tree, plain: bool = False) -> str:
    """Display a tree using Rich's Tree component with colours.

    TODO: Refactor to use tree_lib.render_tree_with_rich() with custom color_callback
    instead of duplicating the tree rendering logic. The color callback should handle
    parsing decorators ([P], [C], [α]) and applying appropriate styling.

    Args:
        tree: treelib.Tree object to display
        plain: If True, use plain text without colours or boxes

    Returns:
        Formatted tree as string with ANSI colour codes (or plain text if plain=True)
    """
    with StringIO() as output_buffer:
        if plain:
            console = Console(
                file=output_buffer, force_terminal=False, color_system=None
            )
        else:
            console = Console(file=output_buffer, force_terminal=True)

        # Get the root node
        root = tree.get_node(tree.root)
        rich_tree = RichTree(f"[bold cyan]{root.tag}[/bold cyan]")

        # Build the Rich tree recursively
        def add_children(treelib_node_id, rich_parent):
            children = tree.children(treelib_node_id)
            for child in children:
                # Parse the tag to extract name and decorators
                tag_parts = child.tag.split()
                name = tag_parts[0]
                decorators = tag_parts[1:] if len(tag_parts) > 1 else []

                # Style based on whether it's a leaf or branch
                if child.is_leaf():
                    # Leaf nodes (actual commands) in green
                    styled_name = f"[green]{name}[/green]"
                else:
                    # Branch nodes (groups) in yellow
                    styled_name = f"[yellow]{name}[/yellow]"

                # Add decorators with specific colours
                decorator_parts = []
                for decorator in decorators:
                    if "[P]" in decorator:
                        decorator_parts.append("[blue][P][/blue]")
                    elif "[α]" in decorator:
                        decorator_parts.append("[magenta][α][/magenta]")
                    else:
                        decorator_parts.append(f"[dim]{decorator}[/dim]")

                label = styled_name
                if decorator_parts:
                    label += " " + " ".join(decorator_parts)

                # Add this node to the Rich tree
                new_branch = rich_parent.add(label)

                # Recursively add children
                add_children(child.identifier, new_branch)

        # Build the tree starting from root
        add_children(tree.root, rich_tree)

        # Display the tree
        console.print(rich_tree)

        # Display the key
        console.print(
            "\n[dim]key: [X] has a python function [/dim][blue][P][/blue][dim]ipe / [/dim][blue][C][/blue][dim]md[/dim]"
        )
        console.print("     [magenta][α][/magenta] [dim]alpha feature[/dim]")

        return output_buffer.getvalue()


def _get_function_help(data):
    return data.callback.__doc__ if data.callback and data.callback.__doc__ else ""


def _build_command_tree(
    context: Context, matchers: List[str], python_filter: Optional[bool] = None
) -> Tree:
    """Build a filtered command tree from the Typer application structure.

    Args:
        context: Typer context
        matchers: List of patterns to match commands
        python_filter: None (show all), True (only Python), False (only non-Python)

    Returns:
        Tree object with filtered commands, decorated with Python interface markers and alpha feature tags
    """
    app = context.find_root()
    root_command = app.command

    tree_elems = {
        path: found_object for path, found_object in _walk_tree(root_command, "nef")
    }

    raw_filtered_tree = []
    for path in tree_elems:
        matches = [fnmatch(".".join(path), f"*{matcher}*") for matcher in matchers]
        if all(matches):
            cmd_obj = tree_elems[path]
            # Filter by Python interface if this is a command (not root or group)
            node_type = _get_tree_node_type(path, cmd_obj)
            if node_type == TreeNodeType.COMMAND:
                if not _should_include_command(cmd_obj, python_filter):
                    continue
            raw_filtered_tree.append(path)

    filtered_tree = OrderedSet()
    for path in raw_filtered_tree:
        for elem in _path_components(path):
            if elem not in filtered_tree:
                filtered_tree.add(elem)

    tree = Tree()
    for path in filtered_tree:
        node_name = path[-1]
        node_path = ".".join(path)
        parent_path = ".".join(path[:-1])
        parent_path = None if not parent_path else parent_path
        data = tree_elems[path]

        programming_commands = _get_python_commands(data)
        programming_decorators = [
            f"[{command.__name__[0].upper()}]" for command in programming_commands
        ]
        help_text = _get_function_help(data)
        if "[alpha]" in help_text:
            programming_decorators.append("[α]")

        programming_decorators = " ".join(programming_decorators)

        node_title = f"{node_name} {programming_decorators}"

        tree.create_node(node_title, node_path, parent=parent_path, data=data)

    return tree


def _get_python_commands(data):
    python_commands = []
    if data.callback:
        module_name = data.callback.__module__
        module = sys.modules[module_name]
        for name in "pipe", "cmd":
            if hasattr(module, name):
                python_commands.append(getattr(module, name))
    return python_commands


def _has_python_interface(cmd_obj) -> bool:
    """Check if a command has a Python interface (pipe or cmd functions).

    Args:
        cmd_obj: Click command object

    Returns:
        True if the command has pipe or cmd functions, False otherwise
    """
    return len(_get_python_commands(cmd_obj)) > 0


def _should_include_command(cmd_obj, python_filter: Optional[bool]) -> bool:
    """Determine if a command should be included based on Python interface filter.

    Args:
        cmd_obj: Click command object
        python_filter: None (show all), True (only Python), False (only non-Python)

    Returns:
        True if the command should be included, False otherwise
    """
    if python_filter is None:
        result = True
    else:
        has_python = _has_python_interface(cmd_obj)
        result = has_python if python_filter else not has_python

    return result


def _path_components(path):
    result = []
    for elem in path:
        result.append(elem)
        yield tuple(result)


def _walk_tree(root, root_name):

    def object_walker(obj, node_path=()):
        node_path = [*node_path]

        yield node_path, obj
        if hasattr(obj, "commands"):
            for child_cmd in obj.commands.values():
                for child_path, child in object_walker(
                    child_cmd, [*node_path, child_cmd.name]
                ):
                    yield child_path, child

    for path, elem in object_walker(root, [root_name]):
        yield tuple(path), elem


def _get_tree_node_type(path: tuple, cmd_obj) -> TreeNodeType:
    """Determine the type of a command tree node.

    Args:
        path: Tuple of command path components (e.g., ("nef") or ("nef", "save"))
        cmd_obj: Click command object

    Returns:
        TreeNodeType enum indicating whether this is ROOT, GROUP, or COMMAND
    """
    if len(path) < 2:
        result = TreeNodeType.ROOT

    elif hasattr(cmd_obj, "commands") and len(cmd_obj.commands) > 0:
        result = TreeNodeType.GROUP
    else:
        result = TreeNodeType.COMMAND

    return result


def _display_list_format(
    tree: Tree, table_format: str, group_by_category: bool = False, plain: bool = False
) -> str:
    """Display commands in a tabulated list format.

    Args:
        tree: Filtered command tree
        table_format: Format for tabulate (simple, grid, pipe, Markdown, etc.)
        group_by_category: If True, display separate tables for each category with headings
        plain: If True, use plain text without colours or boxes

    Returns:
        Formatted table as string (with ANSI codes if Rich is used)
    """
    commands_data = _extract_commands_data(tree)

    if not commands_data:
        result = "No commands found matching the specified patterns."
    else:
        with StringIO() as output_buffer:
            use_rich_table = table_format == "simple" and is_rich_in_use() and not plain

            if group_by_category:
                for category, the_commands in groupby(
                    commands_data, key=lambda x: x[1]
                ):
                    commands_list = list(the_commands)

                    output_buffer.write(f"\n## {category}\n\n")

                    table_data = [
                        [cmd_path, desc] for cmd_path, _, desc, _ in commands_list
                    ]
                    headers = ["Command", "Description"]

                    if use_rich_table:
                        output_buffer.write(_format_rich_table(table_data, headers))
                    else:
                        output_buffer.write(
                            tabulate(table_data, headers=headers, tablefmt=table_format)
                        )
            else:
                table_data = [
                    [cmd_path, cmd_type, desc]
                    for cmd_path, cmd_type, desc, _ in commands_data
                ]
                headers = ["Command", "Category", "Description"]

                if use_rich_table:
                    output_buffer.write(_format_rich_table(table_data, headers))
                else:
                    output_buffer.write(
                        tabulate(table_data, headers=headers, tablefmt=table_format)
                    )

            result = output_buffer.getvalue()

    return result


def _format_rich_table(table_data: List[List[str]], headers: List[str]) -> str:
    """Format a table using Rich's Table class, return as string with ANSI codes.

    Args:
        table_data: List of rows, where each row is a list of cell values
        headers: List of column headers

    Returns:
        Formatted table as string with ANSI colour codes
    """
    with StringIO() as output_buffer:
        console = Console(file=output_buffer, force_terminal=True)

        table = Table(show_header=True, header_style="bold cyan")

        for header in headers:
            table.add_column(header)

        for row in table_data:
            table.add_row(*row)

        console.print(table)
        return output_buffer.getvalue()


def _get_rich_help_panel(path: tuple, group_panels: dict, cmd_obj=None) -> str:
    """Get the rich_help_panel for a command.

    First checks if the command itself has rich_help_panel,
    then looks up parent group panels.

    Args:
        path: Tuple of command path components
        group_panels: Dictionary mapping group paths to their rich_help_panel values
        cmd_obj: The command object (optional)

    Returns:
        rich_help_panel string or "Unknown" if not found
    """
    result = "Unknown"

    if cmd_obj and hasattr(cmd_obj, "rich_help_panel") and cmd_obj.rich_help_panel:
        result = cmd_obj.rich_help_panel
    else:
        for i in range(len(path), 0, -1):
            parent_path = path[:i]
            if parent_path in group_panels:
                result = group_panels[parent_path]
                break

    return result


def _display_html_table_format(tree: Tree, group_by_category: bool = False) -> str:
    """Display commands in HTML table format with CSS styling.

    Args:
        tree: Filtered command tree
        group_by_category: If True, display separate tables for each category

    Returns:
        HTML table as string
    """
    commands_data = _extract_commands_data(tree)

    if not commands_data:
        return "<p>No commands found matching the specified patterns.</p>"

    with StringIO() as output_buffer:
        # Add CSS styling
        output_buffer.write(
            """<style>
.commands-table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-family: system-ui, -apple-system, sans-serif;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    border-radius: 8px;
    overflow: hidden;
}
.commands-table th {
    background-color: #007acc;
    color: white;
    padding: 14px 16px;
    text-align: left;
    font-weight: 600;
}
.commands-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #f0f0f0;
    color: #262626;
}
.commands-table tr:hover {
    background-color: #fafafa;
}
.category-heading {
    color: #007acc;
    font-size: 1.5em;
    font-weight: 700;
    margin-top: 32px;
    margin-bottom: 12px;
    border-bottom: 2px solid #007acc;
    padding-bottom: 6px;
}
.command-name {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-weight: 700;
    color: #096dd9;
}
.category-name {
    color: #8c8c8c;
    font-size: 0.9em;
}
</style>
"""
        )

        if group_by_category:
            for category, the_commands in groupby(commands_data, key=lambda x: x[1]):
                commands_list = list(the_commands)

                output_buffer.write(f'<h2 class="category-heading">{category}</h2>\n')
                output_buffer.write('<table class="commands-table">\n')
                output_buffer.write(
                    '<thead><tr><th scope="col">Command</th><th scope="col">Description</th></tr></thead>\n'
                )
                output_buffer.write("<tbody>\n")

                for cmd_path, _, desc, _ in commands_list:
                    output_buffer.write("<tr>")
                    output_buffer.write(f'<td class="command-name">{cmd_path}</td>')
                    output_buffer.write(f"<td>{desc}</td>")
                    output_buffer.write("</tr>\n")

                output_buffer.write("</tbody>\n")
                output_buffer.write("</table>\n")
        else:
            output_buffer.write('<table class="commands-table">\n')

            headings = ["Command", "Category", "Description"]
            headings = [f'<th scope="col">{heading}</th>' for heading in headings]
            text = f"<thead><tr>{headings}</tr></thead>\n"

            output_buffer.write(text)
            output_buffer.write("<tbody>\n")

            for cmd_path, cmd_type, desc, _ in commands_data:
                output_buffer.write("<tr>")
                output_buffer.write(f'<td class="command-name">{cmd_path}</td>')
                output_buffer.write(f'<td class="category-name">{cmd_type}</td>')
                output_buffer.write(f"<td>{desc}</td>")
                output_buffer.write("</tr>\n")

            output_buffer.write("</tbody>\n")
            output_buffer.write("</table>\n")

        return output_buffer.getvalue()


def _display_full_format(
    tree: Tree, group_by_category: bool = False, plain: bool = False
) -> str:
    """Display commands with full Markdown documentation.

    Uses Click's help infrastructure and adds structured Markdown formatting.

    Args:
        tree: Filtered command tree
        group_by_category: If True, group commands by category with headings
        plain: If True, use plain text without colours or boxes

    Returns:
        Formatted help text as string with ANSI colour codes (or plain text if plain=True)
    """
    commands_data = _extract_commands_data(tree)

    if not commands_data:
        return ""

    commands_data_for_display = [
        (cmd_path, cmd_type, cmd_obj)
        for cmd_path, cmd_type, _, cmd_obj in commands_data
    ]

    if group_by_category:
        result = _display_full_grouped(commands_data_for_display, plain)
    else:
        result = _display_full_flat(commands_data_for_display, plain)

    return result


def _display_markdown_full_format(tree: Tree, group_by_category: bool = False) -> str:
    """Display commands with full Markdown documentation.

    Uses custom Markdown generation instead of Click's terminal formatting.

    Args:
        tree: Filtered command tree
        group_by_category: If True, group commands by category with headings

    Returns:
        Pure Markdown as string
    """
    commands_data = _extract_commands_data(tree)

    if not commands_data:
        result = "No commands found matching the specified patterns."
    else:
        commands_data_for_display = [
            (cmd_path, cmd_type, cmd_obj)
            for cmd_path, cmd_type, _, cmd_obj in commands_data
        ]

        if group_by_category:
            result = _display_markdown_full_grouped(commands_data_for_display)
        else:
            result = _display_markdown_full_flat(commands_data_for_display)

    return result


def _display_markdown_full_grouped(commands_data: List[tuple]) -> str:
    """Display full help in pure Markdown grouped by category.

    Args:
        commands_data: List of (command_path, category, command_obj) tuples

    Returns:
        Pure Markdown as string
    """

    with StringIO() as output_buffer:
        for category, the_commands in groupby(commands_data, key=lambda x: x[1]):
            commands_list = list(the_commands)

            output_buffer.write(f"\n# {category}\n\n")

            for cmd_path, _, cmd_obj in commands_list:
                output_buffer.write(_format_command_markdown(cmd_path, cmd_obj))

        return output_buffer.getvalue()


def _display_markdown_full_flat(commands_data: List[tuple]) -> str:
    """Display full help in pure Markdown flat format.

    Args:
        commands_data: List of (command_path, category, command_obj) tuples

    Returns:
        Pure Markdown as string
    """

    with StringIO() as output_buffer:
        for cmd_path, cmd_type, cmd_obj in commands_data:
            output_buffer.write(f"\n## {cmd_path}\n\n")
            output_buffer.write(f"**Category:** {cmd_type}\n\n")
            output_buffer.write(
                _format_command_markdown(cmd_path, cmd_obj, skip_title=True)
            )
            output_buffer.write("\n" + "-" * 80 + "\n")

        return output_buffer.getvalue()


def _format_command_markdown(cmd_path: str, cmd_obj, skip_title: bool = False) -> str:
    """Format pure Markdown documentation for a command.

    Generates clean Markdown without box-drawing characters.

    Args:
        cmd_path: Full command path (e.g., "nef plot correlations")
        cmd_obj: Click command object
        skip_title: If True, don't print the title (already printed by caller)

    Returns:
        Markdown documentation as string
    """

    with StringIO() as output_buffer:
        if not skip_title:
            output_buffer.write(f"\n## `{cmd_path}`\n\n")

        help_text = ""
        if hasattr(cmd_obj, "callback") and cmd_obj.callback:
            help_text = cmd_obj.callback.__doc__ or ""
        elif hasattr(cmd_obj, "help"):
            help_text = cmd_obj.help or ""

        if help_text:
            clean_help = help_text.strip().lstrip("-").strip()
            clean_help = clean_help.replace("\\-", "").strip()
            paragraphs = clean_help.split("\n\n")
            clean_paragraphs = [" ".join(p.split()) for p in paragraphs]
            formatted_help = "\n\n".join(clean_paragraphs)
            output_buffer.write(f"{formatted_help}\n\n")

        arguments = [p for p in cmd_obj.params if isinstance(p, click.Argument)]
        if arguments:
            output_buffer.write("### Arguments\n\n")
            for arg in arguments:
                output_buffer.write(_format_param_markdown(arg, is_argument=True))

        options = [p for p in cmd_obj.params if isinstance(p, click.Option)]
        if options:
            output_buffer.write("### Options\n\n")
            for opt in options:
                output_buffer.write(_format_param_markdown(opt, is_argument=False))

        return output_buffer.getvalue()


def _format_param_markdown(param, is_argument: bool = False) -> str:
    """Format Markdown for a single parameter (argument or option).

    Args:
        param: Click Parameter object (Argument or Option)
        is_argument: True if this is an argument, False if option

    Returns:
        Markdown formatted parameter as string
    """
    param_name = param.name
    param_type = param.type.name if hasattr(param.type, "name") else str(param.type)

    if is_argument:
        name_display = f"`{param_name.upper()}`"
    else:
        opts = param.opts if hasattr(param, "opts") else [f"--{param_name}"]
        name_display = ", ".join(f"`{opt}`" for opt in opts)

    type_display = f"`{param_type}`"

    is_required = param.required if hasattr(param, "required") else False
    required_badge = " **[required]**" if is_required else ""

    default_val = param.default if hasattr(param, "default") else None
    default_display = ""
    if default_val is not None and default_val != ():
        if isinstance(default_val, (str, bool, int, float)) and not callable(
            default_val
        ):
            default_display = f" (default: `{default_val}`)"

    lines = [f"- {name_display} — {type_display}{required_badge}{default_display}"]

    param_help = getattr(param, "help", "")
    if param_help:
        clean_help = param_help.strip().replace("\\-", "").strip()
        clean_help = " ".join(clean_help.split())
        lines.append(f"  - {clean_help}")

    lines.append("")

    return "\n".join(lines)


def _display_html_full_format(tree: Tree, group_by_category: bool = False) -> str:
    """Display commands with full help exported as HTML.

    Uses Rich Console's export_html() to generate HTML from terminal formatting.

    Args:
        tree: Filtered command tree
        group_by_category: If True, group commands by category with headings

    Returns:
        HTML as string
    """
    commands_data = _extract_commands_data(tree)

    if not commands_data:
        result = "<p>No commands found matching the specified patterns.</p>"
    else:
        commands_data_for_display = [
            (cmd_path, cmd_type, cmd_obj)
            for cmd_path, cmd_type, _, cmd_obj in commands_data
        ]

        if group_by_category:
            result = _display_html_full_grouped(commands_data_for_display)
        else:
            result = _display_html_full_flat(commands_data_for_display)

    return result


def _display_html_full_grouped(commands_data: List[tuple]) -> str:
    """Display full help as HTML grouped by category.

    Args:
        commands_data: List of (command_path, category, command_obj) tuples

    Returns:
        HTML as string
    """

    with StringIO() as output_buffer:
        for category, the_commands in groupby(commands_data, key=lambda x: x[1]):
            commands_list = list(the_commands)

            output_buffer.write(f'<h1 style="color: #af00ff;">{category}</h1>\n\n')

            for cmd_path, _, cmd_obj in commands_list:
                output_buffer.write(f'<h2 style="color: #0087ff;">{cmd_path}</h2>\n\n')

                # Create console for recording with file= to suppress stdout
                console = Console(
                    record=True, force_terminal=True, width=100, file=StringIO()
                )

                # Capture stdout
                with StringIO() as captured_stdout:
                    with redirect_stdout(captured_stdout):
                        ctx = click.Context(cmd_obj, info_name=cmd_path, color=True)
                        ctx.get_help()

                    # Print captured output to recording console
                    console.print(captured_stdout.getvalue())

                # Export as HTML
                html_chunk = console.export_html(
                    inline_styles=True, code_format="<pre>{code}</pre>"
                )
                output_buffer.write(html_chunk)
                output_buffer.write("\n")

        return output_buffer.getvalue()


def _display_html_full_flat(commands_data: List[tuple]) -> str:
    """Display full help as HTML in flat format.

    Args:
        commands_data: List of (command_path, category, command_obj) tuples

    Returns:
        HTML as string
    """

    with StringIO() as output_buffer:
        show_headers = len(commands_data) > 1

        for cmd_path, cmd_type, cmd_obj in commands_data:
            if show_headers:
                output_buffer.write(f'<h2 style="color: #0087ff;">{cmd_path}</h2>\n')
                output_buffer.write(
                    f'<p style="color: #6c6c6c;">Category: {cmd_type}</p>\n\n'
                )

            # Create console for recording with file= to suppress stdout
            console = Console(
                record=True, force_terminal=True, width=100, file=StringIO()
            )

            # Capture stdout
            with StringIO() as captured_stdout:
                with redirect_stdout(captured_stdout):
                    ctx = click.Context(cmd_obj, info_name=cmd_path, color=True)
                    ctx.get_help()

                # Print captured output to recording console
                console.print(captured_stdout.getvalue())

            # Export as HTML
            html_chunk = console.export_html(
                inline_styles=True, code_format="<pre>{code}</pre>"
            )
            output_buffer.write(html_chunk)

            if show_headers:
                output_buffer.write("\n<hr>\n")

        return output_buffer.getvalue()


def _display_full_grouped(commands_data: List[tuple], plain: bool = False) -> str:
    """Display full help grouped by category with headings.

    Args:
        commands_data: List of (command_path, category, command_obj) tuples
        plain: If True, use plain text without colours

    Returns:
        Formatted help text as string with ANSI colour codes (or plain text if plain=True)
    """

    with StringIO() as output_buffer:
        for category, the_commands in groupby(commands_data, key=lambda x: x[1]):
            commands_list = list(the_commands)

            if plain:
                output_buffer.write(f"\n# {category}\n\n")
            else:
                output_buffer.write(f"\n\x1b[1;35m{category}\x1b[0m\n\n")

            for cmd_path, _, cmd_obj in commands_list:
                if plain:
                    output_buffer.write(f"\n## {cmd_path}\n\n")
                else:
                    output_buffer.write(f"\n\x1b[1;34m{cmd_path}\x1b[0m\n\n")

                ctx = click.Context(cmd_obj, info_name=cmd_path, color=not plain)
                help_text = ctx.get_help()
                output_buffer.write(help_text)

        return output_buffer.getvalue()


def _display_full_flat(commands_data: List[tuple], plain: bool = False) -> str:
    """Display full help in flat format.

    Args:
        commands_data: List of (command_path, category, command_obj) tuples
        plain: If True, use plain text without colours

    Returns:
        Formatted help text as string with ANSI colour codes (or plain text if plain=True)
    """

    with StringIO() as output_buffer:
        # Skip headers if only one command (help already shows command name)
        show_headers = len(commands_data) > 1

        for cmd_path, cmd_type, cmd_obj in commands_data:
            if show_headers:
                if plain:
                    output_buffer.write(f"\n## {cmd_path}\n")
                    output_buffer.write(f"Category: {cmd_type}\n\n")
                else:
                    # Write ANSI codes directly to buffer to avoid console buffering issues
                    output_buffer.write(f"\n\x1b[1;34m{cmd_path}\x1b[0m\n")
                    output_buffer.write(f"\x1b[2mCategory: {cmd_type}\x1b[0m\n\n")

            ctx = click.Context(cmd_obj, info_name=cmd_path, color=not plain)
            help_text = ctx.get_help()
            output_buffer.write(help_text)

            if show_headers:
                output_buffer.write("\n" + "-" * 80 + "\n")

        return output_buffer.getvalue()
