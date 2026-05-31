"""
    Small Typer/Click helpers (introspect caller frame to capture the active command's arguments).

    TODO - this should be retired it is no longer the way commands are handled
"""

from argparse import Namespace
from inspect import currentframe, getargvalues, getouterframes


def get_args():
    frame = currentframe()
    outer_frames = getouterframes(frame)
    caller_frame = outer_frames[1][0]
    args = getargvalues(caller_frame).locals
    return Namespace(**args)
