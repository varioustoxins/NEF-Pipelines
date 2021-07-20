import os
from pathlib import Path

from nef_app import app

# noinspection PyUnusedLocal
@app.command()
def test():
    """-  run the test suite"""

    from pytest import main

    dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent / 'tests'

    # file_path = f'{str(dir_path.parent / "tests/nmrview/test_sequence.py")}::test_3aa10'
    file_path = f'{str(dir_path.parent /"tests")}'
    main(['-vvv',  file_path])