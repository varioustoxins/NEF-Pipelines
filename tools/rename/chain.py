import sys
from typing import List

from ordered_set import OrderedSet
from typer import Option, Argument

from lib.util import get_pipe_file, chunks
from tools.rename import rename_app
import typer

from pynmrstar import Entry

app = typer.Typer()

#TODO: it would be nice to put the chains with the first molecular system frame

# noinspection PyUnusedLocal
@rename_app.command()
def chain(
    old: str = Argument(...,  help='old chain code'),
    new: str = Argument(..., help='new chain code'),
    comment: bool = Option(False, '-c', '--comment', help='prepend comment to chains'),
    verbose: bool = Option(False, '-v', '--verbose', help='print verbose info'),
    frames: List[str] = Option([], '-f', '--frame', help='limit changes toa a particular frame'),

):
    """- change the name of a chain"""

    lines = ''.join(get_pipe_file([]).readlines())
    entry = Entry.from_string(lines)

    changes = 0
    changed_frames = OrderedSet()
    for save_frame in entry:
        if len(frames) >= 1 and save_frame.name not in frames:
            continue
        for loop in save_frame.loop_iterator():
            for tag in loop.get_tag_names():
                tag_parts = tag.split('.')
                if tag_parts[-1].startswith('chain_code'):
                    tag_values = loop[tag]
                    for i, row in enumerate(tag_values):
                        if row == old:
                            tag_values[i] = new
                            changes += 1
                            changed_frames.add(save_frame.name)

                    loop[tag] = tag_values

    if verbose:
        comment = '# ' if comment else ''
        out = sys.stderr if not comment else sys.stdout
        if changes >= 1:
            print(f'{comment}rename chain: {changes} changes made in the following frames', file=out)
            for chunk in chunks(changed_frames, 5):
                print(f'{comment}  {", ".join(chunk)}', file=out)

        else:
            print(f'{comment}rename chain: no changes made', file=out)
        print(file=out)

    print(entry)


    # sequence_frames = entry.get_saveframes_by_category('nef_molecular_system')
    #
    # chains = set()
    # for sequence_frame in sequence_frames:
    #     for loop in sequence_frame.loop_dict.values():
    #         chains.update(loop.get_tag('chain_code'))
    #
    # chains = sorted(chains)
    #
    # result = ' '.join(chains)
    # chains = 'chain' if len(chains) == 1 else 'chains'
    #
    # verbose = f'{len(result)} {chains}: ' if verbose else ''
    #
    # comment = '# ' if comment else ''
    #
    # print(f'{comment}{verbose}{result}')
    #
    # if stream:
    #     print(lines)

