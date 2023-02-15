import sys
from datetime import date
from textwrap import dedent, indent

import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.util import get_version

if nef_app:
    # noinspection PyUnusedLocal
    @nef_app.app.command()
    def about(
        version: bool = typer.Option(
            False, "--version", help="only display the current version"
        )
    ):
        "- info about NEF-Pipelines"

        print(cmd(version), file=sys.stderr)

    def cmd(version):
        version_data = get_version()

        if version:
            result = str(version_data)
        else:
            NEF_PIPLINES_URL = "https://github.com/varioustoxins/NEF-Pipelines"
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

            result = "\n".join([header, indent(msg, "  "), header])

        return result