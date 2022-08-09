from typer import Option

from lib.util import get_pipe_file
from lib.sequence_lib import frame_to_chains
from tools.list import list_app
import typer

from pynmrstar import Entry

app = typer.Typer()

#TODO: it would be nice to put the chains with the first molecular system frame

# noinspection PyUnusedLocal
@list_app.command()
def chains(
    comment: bool = Option(False, '-c', '--comment', help='prepend comment to chains'),
    verbose: bool = Option(False, '-v', '--verbose', help='print verbose info'),
    stream: bool = Option(False, '-s', '--stream', help='stream file after comment')
):
    """- list the chains in the molecular systems"""
    lines = ''.join(get_pipe_file([]).readlines())
    entry = Entry.from_string(lines)
    sequence_frames = entry.get_saveframes_by_category('nef_molecular_system')

    chains = frame_to_chains(sequence_frames)

    result = ' '.join(chains)
    chains = 'chain' if len(chains) == 1 else 'chains'

    verbose = f'{len(result)} {chains}: ' if verbose else ''

    comment = '# ' if comment else ''

    print(f'{comment}{verbose}{result}')

    if stream:
        print(lines)

