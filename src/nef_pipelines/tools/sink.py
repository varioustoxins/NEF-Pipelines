import sys

from nef_pipelines import nef_app

if nef_app:
    # noinspection PyUnusedLocal
    @nef_app.app.command()
    def sink():
        """- read the current stream and don't write anything"""
        if not sys.stdin.isatty():
            for line in sys.stdin:
                pass
