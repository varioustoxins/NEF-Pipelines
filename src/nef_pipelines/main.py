#!/usr/bin/env python3
# for pynmrstar to avoid WARNING:root:Loop with no data on line: xx
import logging
import sys
import traceback
from textwrap import dedent

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


logging.getLogger().setLevel(logging.ERROR)

EXIT_ERROR = 1


def do_exit_error(msg, trace_back=True, exit_code=EXIT_ERROR):
    msg = dedent(msg)
    if trace_back:
        traceback.print_exc()
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

    try:
        # import components which will self register, this could and will be automated
        import nef_pipelines.tools.chains  # noqa: F401
        import nef_pipelines.tools.entry  # noqa: F401
        import nef_pipelines.tools.frames  # noqa: F401
        import nef_pipelines.tools.header  # noqa: F401
        import nef_pipelines.tools.stream  # noqa: F401
        import nef_pipelines.tools.test  # noqa: F401
        import nef_pipelines.transcoders.csv  # noqa: F401
        import nef_pipelines.transcoders.fasta  # noqa: F401
        import nef_pipelines.transcoders.mars  # noqa: F401
        import nef_pipelines.transcoders.nmrpipe  # noqa: F401
        import nef_pipelines.transcoders.nmrview  # noqa: F401
        import nef_pipelines.transcoders.pales  # noqa: F401
        import nef_pipelines.transcoders.pdbx  # noqa: F401
        import nef_pipelines.transcoders.sparky  # noqa: F401
        import nef_pipelines.transcoders.xplor  # noqa: F401

    except Exception as e:
        msg = """\

             Initialisation error: failed to load a plugin, remove the plugin or contact the developer
             """

        do_exit_error(msg, e)

    try:

        nef_app.app

        command = typer.main.get_command(nef_app.app)

        command(standalone_mode=False)

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


if __name__ == "__main__":
    main()
