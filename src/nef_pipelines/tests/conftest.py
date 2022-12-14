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
    wrappers = [
        a for a in gc.get_objects() if isinstance(a, functools._lru_cache_wrapper)
    ]

    for wrapper in wrappers:
        wrapper.cache_clear()
