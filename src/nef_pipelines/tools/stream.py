from pathlib import Path

import typer

from nef_pipelines import nef_app

if nef_app:
    # noinspection PyUnusedLocal
    @nef_app.app.command()
    def stream(
        file_name: Path = typer.Argument(
            ..., help="nef file to stream [- indicates stdin]", metavar="<nef file>"
        )
    ):
        "- stream a nef file"
        with open(file_name) as file_h:
            for line in file_h:
                print(line, end="")
