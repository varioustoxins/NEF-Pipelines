import inspect
import logging
import os
import sys
from dataclasses import dataclass
from importlib import import_module
from textwrap import dedent
from traceback import format_exc, print_exc
from types import ModuleType
from typing import Iterator, List, NoReturn, Optional

import typer
from click import ClickException, Group

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup, patch_rich_code_theme
from nef_pipelines.lib.util import exit_error
from nef_pipelines.module_registry import get_registerd_modules


@dataclass
class CommandFailure:
    location: str
    function: str
    file: str
    line: int
    error: Exception


debug_mode = False
typer_debug_mode = "--debug-typer" in sys.argv
if typer_debug_mode:
    logging.basicConfig(level=logging.DEBUG)

try:
    import future  # noqa: F401
except ImportError:
    pass

# for pynmrstar to avoid WARNING:root:Loop with no data on line: xx
logging.getLogger("pynmrstar").setLevel(logging.ERROR)

EXIT_ERROR = 1

patch_rich_code_theme()


def do_exit_error(
    msg: str, trace_back: bool = True, exit_code: int = EXIT_ERROR
) -> NoReturn:
    msg = dedent(msg)
    if trace_back:
        print_exc()
    print(msg, file=sys.stderr)
    print("exiting...", file=sys.stderr)
    sys.exit(exit_code)


def main_callback(
    ctx: typer.Context,
    debug: bool = typer.Option(
        False, "--debug", help="Enable debug output including stack traces"
    ),
    # NOTE: this is defined here so that it appears in the list of options shown by typer
    #      however, it is set at the top of the file because it needs to be set before
    #      typer interprets commands...
    _debug_typer: bool = typer.Option(
        False,
        "--debug-typer",
        help="Developer tool enable debugging of typer CLI interface construction",
    ),
    server_mode: Optional[bool] = typer.Option(
        False,
        "--server",
        help="""
            indicates to the runtime that its running inside an mcp server
        """,
    ),
):
    if debug:
        global debug_mode
        debug_mode = True
        logging.basicConfig(level=logging.DEBUG)

    if server_mode:
        # remove the ai command if we are running inside an AI server
        # ctx.command is actually a Group at runtime (typed as Command in stubs)
        group = ctx.command
        if isinstance(group, Group) and "ai" in group.commands:
            del group.commands["ai"]

        if ctx.invoked_subcommand == "ai":
            msg = """
                The 'ai' commands are not available when running inside an AI server.
                This is for security and to avoid recursion.
            """
            exit_error(msg)

    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


def create_nef_app():

    if nef_app.app is None:
        nef_app.app = typer.Typer(
            no_args_is_help=True,
            invoke_without_command=True,
            callback=main_callback,
            rich_markup_mode="markdown",
            cls=FilteredHelpGroup,
        )
    return nef_app


def load_nef_modules_and_build_failure() -> Optional[str]:
    """Load all registered plugin modules.

    Caller must ensure create_nef_app() was called first.
    Returns a formatted error message or None when all modules loaded successfully.
    Does not call exit_error — callers decide how to handle failures.
    """
    load_failure_messages = []
    for module_name in get_registerd_modules():
        try:
            import_module(module_name)
        except Exception as e:
            msg = f"plugin {module_name}: {e}\n{format_exc()}"
            load_failure_messages.append((module_name, msg))

    if load_failure_messages:

        bad_modules = []
        for module_name, warning in load_failure_messages:
            bad_modules.append(module_name)

            lines = warning.split("\n")
            max_line_length = max([len(line) for line in lines])
            msg = f"error in {module_name}"
            line_length_m_module_name = max_line_length - len(msg)
            stars_2_m1 = (line_length_m_module_name // 2) - 2

            header = f"{'*' * stars_2_m1} {msg} {'*' * stars_2_m1}"
            discrepancy = max_line_length - len(header)
            header = f'{header}{"*" * discrepancy}'

            print(file=sys.stderr)
            print(header)
            print(file=sys.stderr)
            print(warning, file=sys.stderr)
            print("*" * max_line_length)

        NEW_LINE = "\n    "
        msg = f"""
                WARNING: the following plugins failed to load:

                    {NEW_LINE.join(bad_modules)}

                the remaining plugins will work but NEF-Pipelines is working  with reduced capabilities. The modules
                that failed to load and the causes of the problem are listed above please report this to the authors
                at github: https://github.com/varioustoxins/NEF-Pipelines/issues
            """
        result = dedent(msg)
    else:
        result = None
    return result


def _report_typer_load_problems(messages: List[Optional[str]]):
    for message in messages:
        if message:
            print(message, file=sys.stderr)


def _shutdown_stdout_for_broken_pipe():
    # to get rid of messages about broken pipes when SIGPIPE is received
    # Exception ignored in: <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>
    # BrokenPipeError: [Errno 32] Broken pipe
    # https://stackoverflow.com/questions/26692284/how-to-prevent-brokenpipeerror-when-doing-a-flush-in-python
    # note: https://docs.python.org/3/library/signal.html#note-on-sigpipe
    #      doesn't appear to work for us, not quite sure why
    try:
        sys.stdout.flush()
    except (BrokenPipeError, OSError):
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except Exception:
            pass

    try:
        sys.stdout.close()
    except (BrokenPipeError, OSError):
        pass

    try:
        sys.stderr.flush()
    except (BrokenPipeError, OSError):
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stderr.fileno())
        except Exception:
            pass


def run():
    try:
        nef_app_module = _make_nef_app_or_exit_error()

        load_failure_message = load_nef_modules_and_build_failure()
        bad_command_message = _if_typer_debug_get_bad_command_messages(nef_app_module)

        _report_typer_load_problems([load_failure_message, bad_command_message])

        _exit_if_bad_typer_commands(bad_command_message)

        _run_command_or_exit_error(nef_app_module)
    finally:
        _shutdown_stdout_for_broken_pipe()


def _run_command_or_exit_error(nef_app_module: ModuleType) -> None:
    try:
        command = typer.main.get_command(nef_app_module.app)
        command(prog_name="nef", standalone_mode=False)
    except ClickException as e:
        e.show()
        msg = f"inputs: {' '.join(sys.argv[1:])}" if sys.argv[1:] else "no inputs!"
        do_exit_error(msg, trace_back=False, exit_code=e.exit_code)
    except Exception as e:

        msg = f"""\

              Runtime error: failed to process the data using the plugin and commands, check you inputs or report a bug
              inputs: {' '.join(sys.argv[1:])}
              message: {e}
              """

        do_exit_error(msg)


def _exit_if_bad_typer_commands(bad_command_message: Optional[str]):
    if bad_command_message:
        do_exit_error("bad typer commands detected", trace_back=False, exit_code=1)


def _make_nef_app_or_exit_error() -> ModuleType:
    # noinspection PyBroadException
    try:
        return create_nef_app()
    except Exception:
        msg = """\

                 Initialisation error: failed to start the typer app, message the developer
                 exiting..."""
        do_exit_error(msg)


def _if_typer_debug_get_bad_command_messages(nef_app_module):

    msg = None
    if typer_debug_mode:
        bad_commands = list(_walk_the_command_tree_and_find_bad(nef_app_module.app))
        if bad_commands:
            error_messages = ["some commands had bad typer command definitions"]

            for bad_command_info in bad_commands:
                msg = f"""
                    failed to load command: {bad_command_info.location}
                        function: {bad_command_info.function}
                        file:     {bad_command_info.file}:{bad_command_info.line}
                        error:    {bad_command_info.error}"
                """
                error_messages.append(dedent(msg))

            msg = "\n".join(error_messages)

    return msg


def _walk_the_command_tree_and_find_bad(app: typer.Typer) -> Iterator[CommandFailure]:
    """Walk every registered typer/click command/group and yield a CommandFailure
    for each command whose construction raises an exception."""

    def recursively_walk_child_commands_and_find_bad(
        typer_app: typer.Typer,
        path: tuple,
    ) -> Iterator[CommandFailure]:

        for command_info in typer_app.registered_commands:
            callback = command_info.callback
            if callback is None:
                continue
            name = command_info.name or callback.__name__
            try:
                typer.main.get_command_from_info(
                    command_info,
                    pretty_exceptions_short=False,
                    rich_markup_mode="markdown",
                )
            except Exception as e:
                location = " ".join((*path, name))
                yield CommandFailure(
                    location=location,
                    function=callback.__qualname__,
                    file=inspect.getsourcefile(callback) or "?",
                    line=inspect.getsourcelines(callback)[1],
                    error=e,
                )

        for group_info in app.registered_groups:
            sub_app = group_info.typer_instance
            if sub_app is None:
                continue
            sub_path = (*path, group_info.name or "?")
            yield from recursively_walk_child_commands_and_find_bad(sub_app, sub_path)

    yield from recursively_walk_child_commands_and_find_bad(app, path=("nef",))
