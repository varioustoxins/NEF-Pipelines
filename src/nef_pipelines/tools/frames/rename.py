import sys
from difflib import SequenceMatcher
from fnmatch import fnmatch
from pathlib import Path
from textwrap import dedent, indent
from typing import List

import typer
from fyeah import f
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.util import (
    FOUR_SPACES,
    STDIN,
    chunks,
    exit_error,
    parse_comma_separated_options,
    strings_to_table_terminal_sensitive,
)
from nef_pipelines.tools.frames import frames_app

# TODO: add mmv like semantics as an option [https://manpages.ubuntu.com/manpages/bionic/man1/mmv.1.html]

REPLACE_HELP = """replace part of the frame name selected with the replacement string, rather than the whole name"""


@frames_app.command()
def rename(
    input: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read input from [- is stdin]"
    ),
    exact: bool = typer.Option(False),
    replace: bool = typer.Option(False, help=REPLACE_HELP),
    delete: bool = typer.Option(
        False, help="delete the text rather than replacing it if replace is specified"
    ),
    category: str = typer.Option(
        "*", help="category to match as well as the frame name"
    ),
    rename_category: bool = typer.Option(False, help="change the category"),
    force: bool = typer.Option(
        False,
        help="force a replacement so a rename can delete a frame with a name clash",
    ),
    old_new_names: List[str] = typer.Argument(
        ...,
        help="a list of pairs of old and new names for frames, arguments can be repeated or comma separated",
    ),
):
    """- rename frames in the current input"""

    if delete and not replace:
        exit_error("you can't use --delete without --replace")

    old_new_names = parse_comma_separated_options(old_new_names)

    if delete:
        new_new_old_names = []
        for name in old_new_names:
            new_new_old_names.append(name)
            new_new_old_names.append("")
        old_new_names = new_new_old_names

    _exit_renames_not_pairs(old_new_names)

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    for old_name, new_name in chunks(old_new_names, 2):

        target_frames = select_frames_by_name(
            entry,
            [
                old_name,
            ],
            exact,
        )

        if category != "*":
            if exact:
                target_frames = [
                    frame for frame in target_frames if frame.category == category
                ]
            else:
                target_frames = [
                    frame
                    for frame in target_frames
                    if fnmatch(frame.category, f"*{category}*")
                ]

        if len(target_frames) == 0:
            _exit_no_frames_selected(old_name, category, entry, exact)

        if len(target_frames) > 1 and not replace:
            _exit_error_mutiple_frames_selected(
                old_name, category, exact, entry, target_frames
            )

        target_frame = target_frames[0]

        # TODO: check for accceptable characters [33-126] though maybe we allow unicode
        # TODO: tests
        for target_frame in target_frames:
            if len(new_name.split()) > 1:
                _exit_spaces_in_new_name(new_name)

            if not rename_category:
                category = target_frame.category
                new_name_part = new_name
                if replace:
                    frame_name = target_frame.name[len(category) :].lstrip("_")
                    new_name_part = frame_name.replace(old_name, new_name)
                    if new_name_part.startswith("_"):
                        new_name_part = new_name_part[1:]

                new_full_name = f"{category}_{new_name_part}"

                if new_full_name in entry.frame_dict.keys() and not force:
                    _exit_clashing_frame_name(new_full_name, entry)

                if new_full_name in entry.frame_dict.keys() and force:
                    frame_to_remove = entry.get_saveframe_by_name(new_full_name)
                    entry.remove_saveframe(frame_to_remove)

                target_frame.name = new_full_name

            else:

                name_part = target_frame.name[len(target_frame.category) :].lstrip("_")
                new_full_name = f"{new_name}_{name_part}"

                target_frame.category = new_name
                target_frame.name = new_full_name

    print(entry)


def _exit_error_mutiple_frames_selected(
    target_name, target_category, exact, entry, target_frames
):
    if not exact:
        target_name = f"*{target_name}*"
        target_category = f"*{target_category}*"

    category_msg = (  # noqa: F841
        "" if target_category == "*" else f" and the category {target_category}"
    )

    target_frame_names = [frame.name for frame in target_frames]
    frames_table = strings_to_table_terminal_sensitive(target_frame_names)
    frames_table = tabulate(frames_table, tablefmt="plain")
    frames = indent(dedent(frames_table), FOUR_SPACES)  # noqa: F841

    msg = """
        multiple save frames were selected using the name {target_name}{category_msg} in entry {entry.entry_id}
        and I can only rename one save frame at the same time...

        the save frames were

        {frames}
    """

    msg = dedent(msg)
    exit_error(f(msg))


def _exit_renames_not_pairs(old_new_names):
    if len(old_new_names) % 2 != 0:
        pairs = ", ".join(old_new_names[:-1])
        pairs = indent(pairs, "   ")
        msg = f"""\
            old and new names must be pairs, i got an extra term {old_new_names[-1]}'

            pairs were:

            {pairs}
        """

        exit(msg)

        print(msg, file=sys.stderr)
        print(file=sys.stderr)


def _exit_no_frames_selected(target_name, target_category, entry, exact):
    if not exact:
        target_name = f"*{target_name}*"
        target_category = f"*{target_category}*"

    all_names_and_categories = [(frame.name, frame.category) for frame in entry]

    if len(all_names_and_categories) == 0:
        msg = """
            there were no frames in the entry to rename
        """
    else:
        # TODO whahats happening here????
        category_msg = (
            "" if target_category == "*" else f" with category {target_category}"
        )
        category_msg = category_msg
        matcher = SequenceMatcher()
        distances = []
        for name, category in all_names_and_categories:
            matcher.set_seq1(name)
            matcher.set_seq2(target_name)
            distance_name = 1.0 - matcher.ratio()

            matcher.set_seq1(target_category)
            matcher.set_seq2(category)
            distance_category = 1.0 - matcher.ratio()
            distance = (distance_name + distance_category) / 2.0
        distances.append((distance, (name, category)))

        distances.sort()

        all_names = [name for name, _ in all_names_and_categories]
        table = strings_to_table_terminal_sensitive(all_names)
        table = tabulate(table, tablefmt="plain")
        table = indent(dedent(table), FOUR_SPACES)

        template = """
            the frame {target_name}{category_msg} wasn't found in the entry {entry.entry_id},
            did you mean {distances[0][-1][0]} [category: {distances[0][-1][1]}]?

            all the frame names in the entry {entry.entry_id} were:

            {table}
        """
        template = dedent(template)

        msg = f(template)

    exit_error(msg)


def _exit_spaces_in_new_name(new_name):
    msg = f"""
        frame names can't contain spaces your new name was  {new_name} and contains spaces
    """

    exit_error(msg)


def _exit_clashing_frame_name(new_full_name, entry):
    msg = f"""
        a frame with the name {new_full_name} already exists in entry {entry.entry_id}  you will need to use the --force
        option to force the rename to replace it (if that's what you want to do!)
    """

    exit_error(msg)
