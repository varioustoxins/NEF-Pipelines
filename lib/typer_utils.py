
from argparse import Namespace
from inspect import currentframe, getouterframes, getargvalues

def get_args():
    frame = currentframe()
    outer_frames = getouterframes(frame)
    caller_frame = outer_frames[1][0]
    args = getargvalues(caller_frame).locals
    return Namespace(**args)
