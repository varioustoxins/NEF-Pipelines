import copy

_globals = {}


def set_global(key, value):
    _globals[key] = value


def get_global(key, default):
    return _globals[key] if key in _globals else default


def debug_clear_globals():
    _globals.clear()


def debug_get_globals():
    return copy.deepcopy(_globals)
