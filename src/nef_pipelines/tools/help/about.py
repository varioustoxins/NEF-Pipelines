import platform
import sys
from datetime import date
from textwrap import dedent, indent

import typer

from nef_pipelines.lib.util import get_version
from nef_pipelines.tools.help import help_app

VERBOSE_HELP = """\
    display more verbose information about NEF-Pipelines and its environment,
    [ignored with the --version option]"
"""


# noinspection PyUnusedLocal
@help_app.command()
def about(
    version: bool = typer.Option(
        False, "--version", help="only display the current version"
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help=VERBOSE_HELP),
):
    "- info about this NEF-Pipelines installation"

    print(cmd(version, verbose), file=sys.stderr)


def cmd(version, verbose=False):
    version_data = get_version()

    if version:
        result = str(version_data)
    else:
        NEF_PIPLINES_URL = "https://github.com/varioustoxins/NEF-Pipelines"

        if verbose:
            # TODO add the modules in requirements.txt and their versions
            extra_msg = f"""\

                Environment
                -----------

                Python version:   {platform.python_version()}
                Python path:      {sys.executable}
                Operating system: {platform.platform(aliased=True, terse=True)}

            """
        else:
            extra_msg = ""
        extra_msg = dedent(extra_msg)

        msg = f"""\

            This is NEF-Pipelines version {version_data}

            For information about this program and the code please see: {NEF_PIPLINES_URL}
            For bug reporting please goto: {NEF_PIPLINES_URL}/issues

            If you like this project please star it on the projects github page (listed above)!
            If you want to cite the project please cite it as

            G. S. Thompson {NEF_PIPLINES_URL} ({date.today().year})

            regards Gary (aka varioustoxins)
        """

        msg = dedent(msg)

        max_width = max([len(line) for line in msg.split("\n")])

        header = "=" * (max_width + 4)

        result = "\n".join([header, indent(msg, "  "), indent(extra_msg, "  "), header])

    return result
