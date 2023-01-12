from random import seed

import pytest


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


def pytest_configure(config):
    from nef_pipelines.main import create_nef_app

    create_nef_app()
