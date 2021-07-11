import os
from pathlib import Path

from nef_app import app
from pytest import main

# noinspection PyUnusedLocal
@app.command()
def test():
    """-  run the test suite"""

    dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
    main([str(dir_path.parent)])