import sys
from datetime import date
from pathlib import Path
from textwrap import dedent

from nef_pipelines import nef_app

if nef_app:
    # noinspection PyUnusedLocal
    @nef_app.app.command()
    def about():
        "- info about NEF-Pipelines"

        file_path = Path(__file__)
        root_path = file_path.parent.parent
        version_path = root_path / "VERSION"

        with open(version_path) as file_h:
            version = file_h.read().strip()

        NEF_PIPLINES_URL = "https://github.com/varioustoxins/NEF-Pipelines"
        msg = f"""\

            This is NEF-Pipelines version {version}

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

        print(header, file=sys.stderr)
        for line in msg.split("\n"):
            print(f"  {line}", file=sys.stderr)
        print(header, file=sys.stderr)
