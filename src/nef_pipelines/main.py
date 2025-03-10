#!/usr/bin/env python3

import logging
import sys
from importlib import import_module
from textwrap import dedent
from traceback import format_exc, print_exc

verbose_mode = False

try:
    import future  # noqa: F401
except Exception:
    pass

MINIMUM_VERSION = (3, 7)
if not sys.version_info >= MINIMUM_VERSION:
    print(
        "Error; minimum version required id %i.%i [and python 2 is not supported]"
        % MINIMUM_VERSION,
        file=sys.stderr,
    )
    print("exiting...", file=sys.stderr)

# for pynmrstar to avoid WARNING:root:Loop with no data on line: xx
logging.getLogger().setLevel(logging.ERROR)

EXIT_ERROR = 1


def do_exit_error(msg, trace_back=True, exit_code=EXIT_ERROR):
    msg = dedent(msg)
    if trace_back:
        print_exc()
    print(msg, file=sys.stderr)
    print("exiting...", file=sys.stderr)
    sys.exit(exit_code)


def create_nef_app():
    import typer

    from nef_pipelines import nef_app

    nef_app.app = typer.Typer(no_args_is_help=True)
    app = nef_app.app  # noqa: F841
    return nef_app


def main():
    global verbose_mode
    try:
        import typer
        from click import ClickException

    except Exception as e:

        msg = """\

             Initializaion error: one of the core libraries [friendly_tracback/typer] if missing from you environment
             please make sure they are installed an try again
             exiting..."""
        do_exit_error(msg, e)

    try:
        nef_app = create_nef_app()

    except Exception as e:
        msg = """\

                 Initialisation error: failed to start the typer app, message the developer
                 exiting..."""
        do_exit_error(msg, e)

    warnings = []
    try:
        # import components which will self register, this could and will be automated
        modules = [
            "nef_pipelines.tools.help",
            "nef_pipelines.tools.chains",
            "nef_pipelines.tools.entry",
            "nef_pipelines.tools.fit",
            "nef_pipelines.tools.frames",
            "nef_pipelines.tools.globals",
            "nef_pipelines.tools.header",
            "nef_pipelines.tools.loops",
            "nef_pipelines.tools.peaks",
            "nef_pipelines.tools.save",
            "nef_pipelines.tools.series",
            "nef_pipelines.tools.shifts",
            "nef_pipelines.tools.simulate",
            "nef_pipelines.tools.sink",
            "nef_pipelines.tools.stream",
            "nef_pipelines.tools.test",
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
            "nef_pipelines.transcoders.xcamshift",
            "nef_pipelines.transcoders.xeasy",
            "nef_pipelines.transcoders.xplor",
        ]
        for module_name in modules:
            try:
                import_module(module_name)
            except Exception:
                msg = f"plugin {module_name}\n{format_exc()}"

                warnings.append((module_name, msg))

    except Exception as e:
        msg = """\

             Initialisation error: failed to load a plugin, remove the plugin or contact the developer
             """

        do_exit_error(msg, e)

    try:

        nef_app.app

        command = typer.main.get_command(nef_app.app)

        command(standalone_mode=False)

        _report_warnings(warnings)

    except ClickException as e:
        e.show()
        do_exit_error(
            f"inputs: {' '.join(sys.argv[1:])}", trace_back=False, exit_code=e.exit_code
        )

    except Exception as e:

        msg = f"""\

              Runtime error: failed to process the data using the plugin and commands, check you inputs or report a bug
              inputs: {' '.join(sys.argv[1:])}
              message: {e}
              """

        do_exit_error(msg)


def _report_warnings(warnings):
    if warnings:

        bad_modules = []
        for module_name, warning in warnings:
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
        msg = dedent(msg)
        print(msg, file=sys.stderr)

    # # to get rid of messages about broken pipes when SIGPIPE is recieved
    # Exception ignored in: <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>
    # BrokenPipeError: [Errno 32] Broken pipe
    # https://stackoverflow.com/questions/26692284/how-to-prevent-brokenpipeerror-when-doing-a-flush-in-python
    # note: https://docs.python.org/3/library/signal.html#note-on-sigpipe
    #      doesn't appear to work for us, not quite sure why
    # note: I added a flush of stderr to remove any dangling output
    sys.stderr.flush()
    sys.stderr.close()


if __name__ == "__main__":
    main()
