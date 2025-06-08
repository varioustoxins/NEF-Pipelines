import sys
from enum import auto
from fnmatch import fnmatch
from typing import List

import typer
from ordered_set import OrderedSet
from strenum import KebabCaseStrEnum
from treelib import Tree
from typer import Context

from nef_pipelines.lib.util import chunks, parse_comma_separated_options
from nef_pipelines.tools.help import help_app

VERBOSE_HELP = """\
    display more verbose information about NEF-Pipelines and its environment,
    [ignored with the --version option]"
"""


class CommandFormat(KebabCaseStrEnum):
    Tree = auto()
    HTML_Table = auto()


# noinspection PyUnusedLocal
@help_app.command()
def commands(
    context: Context,
    format: CommandFormat = typer.Option(
        CommandFormat.Tree, help="the format to output"
    ),
    matchers: List[str] = typer.Argument(
        None,
        help="select commands to display multiple items, wildcards and comma separated lists are allowed",
    ),
    # tree: bool = typer.Option(False, "--table", help="display the tree in a table format"),
    # python: bool = typer.Option(False, "-v", "--python", help='show commands with python interfaces'),
):
    "- display and filter the help for the NEF-Pipelines commands [alpha]"

    matchers = parse_comma_separated_options(matchers)
    if not matchers:
        matchers = [
            "*",
        ]

    tree = cmd(context, matchers)

    table_info = {}
    for elem in tree.all_nodes_itr():
        if elem.is_leaf():
            elem_name, *tags = elem.tag.split()
            tags = [tag.strip("[]") for tag in tags]

            parent = tree.parent(elem.identifier)
            parent_2 = tree.parent(parent.identifier)

            node_type = parent.tag.strip()

            node_owner = parent_2.tag.strip() if parent_2 else "global"

            translations = {"import": "R", "export": "W"}
            node_type = translations.get(node_type, "C")
            tags.insert(0, node_type)
            tags = [tag if tag != "P" else "🐍" for tag in tags]

            table_info.setdefault(node_owner, []).append((elem_name, tags))

    for node_owner, node_types in table_info.items():
        by_type = {}
        for node_type, node_info in node_types:
            by_type.setdefault(node_type, set()).update(set(node_info))

        for node_type, node_info in by_type.items():
            if "R" in node_info and "W" in node_info:
                node_info.remove("R")
                node_info.remove("W")
                node_info.add("RW")

        table_info[node_owner] = by_type

    SPACE_STRING = " "
    items = []
    for node_owner, node_info in table_info.items():
        item = [node_owner, ""]
        for node_type, node_tags in node_info.items():
            item.append(f"{node_type} {SPACE_STRING.join(sorted(node_tags))}")
        items.append(item)

    columns = 5
    column_width = 100 / columns

    # print(items)
    rows = chunks(items, columns)

    print('<table style="width:100%;table-layout=fixed">')
    print("<tbody>")
    for i, row in enumerate(rows):
        style = "" if i > 0 else f' style="width:{column_width:4.2f}%"'
        print(r" <tr>")

        max_num_lines = max([len(column) for column in row])
        for column in row:
            print(f"  <td{style}>")
            num_lines = len(column)

            for i, line in enumerate(column):
                bold_start = "<b>" if i == 0 else ""
                bold_end = "</b>" if i == 0 else ""

                print(f"    {bold_start}{line}{bold_end}<br>")
            for _ in range(max_num_lines - num_lines):
                print("    <br>")
            print("  </td>")
        print(" </tr>")
    print("</tbody>")
    print("</table>")
    sys.exit()

    if len(tree) != 0:
        print(tree.show(stdout=False), file=sys.stderr)
        print("key: [X] has a python function [P]ipe / [C]md", file=sys.stderr)
        print("     [α] alpha feature", file=sys.stderr)


def _get_function_help(data):
    return data.callback.__doc__ if data.callback and data.callback.__doc__ else ""


def cmd(context: Context, matchers: List[str]) -> Tree:
    app = context.find_root()
    root_command = app.command

    tree_elems = {path: object for path, object in _walk_tree(root_command, "nef")}

    raw_filtered_tree = []
    for path in tree_elems:
        matches = [fnmatch(".".join(path), f"*{matcher}*") for matcher in matchers]
        if all(matches):
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
        help = _get_function_help(data)
        if "[alpha]" in help:
            programming_decorators.append("[α]")

        programming_decorators = " ".join(programming_decorators)

        node_title = f"{node_name} {programming_decorators}"

        tree.create_node(node_title, node_path, parent=parent_path, data=data)

    return tree


def _get_python_commands(data):
    commands = []
    if data.callback:
        module_name = data.callback.__module__
        module = sys.modules[module_name]
        for name in "pipe", "cmd":
            if hasattr(module, name):
                commands.append(getattr(module, name))
    return commands


def _path_components(path):
    result = []
    for elem in path:
        result.append(elem)
        yield tuple(result)


def _walk_tree(root, root_name):

    def objwalk(obj, path=()):
        path = [*path]

        yield path, obj
        if hasattr(obj, "commands"):
            for child in obj.commands.values():
                for child_path, child in objwalk(child, [*path, child.name]):
                    yield child_path, child

    for path, elem in objwalk(root, [root_name]):
        yield tuple(path), elem
