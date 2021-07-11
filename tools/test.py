
from nef_app import app
from pytest import main

# noinspection PyUnusedLocal
@app.command()
def test():
    """-  run the test suite"""

    main(['.'])