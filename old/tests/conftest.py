from random import seed

import pytest


@pytest.fixture
def typer_app():
    import nef_app
    import typer

    if not nef_app.app:
        nef_app.app = typer.Typer()

        # if only one command is registered it is ignored on the command line...
        dummy_app = typer.Typer()
        nef_app.app.add_typer(dummy_app, name="dummy")

    return nef_app.app


@pytest.fixture
def fixed_seed():
    seed(42)


@pytest.fixture
def clear_cache():
    """
    clear the lru cache used by lib.util cached_stdin
    see https://stackoverflow.com/questions/40273767/clear-all-lru-cache-in-python
    """
    import functools
    import gc

    gc.collect()
    wrappers = []
    for elem in gc.get_objects():
        try:
            if isinstance(elem, functools._lru_cache_wrapper):
                wrappers.append(elem)
        except ReferenceError:
            pass

    for wrapper in wrappers:
        wrapper.cache_clear()
