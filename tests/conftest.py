from random import seed

import pytest


@pytest.fixture
def typer_app():
    import typer

    import nef_app

    if not nef_app.app:
        nef_app.app = typer.Typer()

        # if only one command is registered it is ignored on the command line...
        dummy_app = typer.Typer()
        nef_app.app.add_typer(dummy_app, name="dummy")

    return nef_app.app


@pytest.fixture
def fixed_seed():
    seed(42)
