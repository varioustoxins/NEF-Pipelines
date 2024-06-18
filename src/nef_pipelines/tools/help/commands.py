import sys
from fnmatch import fnmatch
from typing import List

import typer
from ordered_set import OrderedSet
from treelib import Tree
from typer import Context

from nef_pipelines.lib.util import parse_comma_separated_options
from nef_pipelines.tools.help import help_app

VERBOSE_HELP = """\
    display more verbose information about NEF-Pipelines and its environment,
    [ignored with the --version option]"
"""


# noinspection PyUnusedLocal
@help_app.command()
def commands(
    context: Context,
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
