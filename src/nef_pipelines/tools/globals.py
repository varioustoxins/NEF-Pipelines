from textwrap import dedent

import typer
from pynmrstar import Entry

from nef_pipelines import nef_app
from nef_pipelines.lib.globals_lib import get_global, set_global
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    _parse_globals,
    create_entry_from_stdin,
    create_nef_save_frame,
)

VERBOSE_HELP = """\
    display more verbose information about NEF-Pipelines as it runs
"""

FORCE_HELP = """\
    globally force overwrite of output files even if it they exist and aren't empty
"""

INFO = """
    this is a frame for storing global options inside NEF-Pipelines, it can be safely deleted,
    [you can delete it automatically if you use 'nef save -' as the last command in your pipeline]
"""

INFO = dedent(INFO)


INFO = INFO.strip()
INFO = dedent(INFO)
INFO = INFO.replace(r"\s+", " ")

if nef_app:
    # noinspection PyUnusedLocal
    @nef_app.app.command("globals")
    def globals_(
        verbose: bool = typer.Option(None, "-v", "--verbose", help=VERBOSE_HELP),
        force: bool = typer.Option(None, "-f", "--force", help=FORCE_HELP),
    ):
        "- add global options to the pipeline [use save as your last command to clean up the globals]"

        entry = create_entry_from_stdin()
        if entry:
            _parse_globals(entry)

        if not entry and verbose or force:
            entry = Entry.from_scratch("nefpls_globals")

        if verbose is None:
            verbose = False
        if force is None:
            force = False

        set_global("force", force)
        set_global("verbose", verbose)
        set_global("info", INFO)

        entry = _create_or_update_globals_frame(entry)

        if entry:
            print(entry)
        else:
            print()


def _create_or_update_globals_frame(entry):

    if entry:
        global_frames = entry.get_saveframes_by_category("nefpls_globals")
        for global_frame in global_frames:
            entry.remove_saveframe(global_frame)

        global_frame = create_nef_save_frame("nefpls_globals")
        entry.add_saveframe(global_frame)

        tags = "force verbose info".split()

        for name in tags:
            global_frame.add_tags([(name, get_global(name, UNUSED))])

    return entry
