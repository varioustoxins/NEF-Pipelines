from difflib import SequenceMatcher
from enum import Enum
from fnmatch import fnmatchcase
from pathlib import Path
from textwrap import dedent, indent
from typing import List, Optional, Tuple

import typer
from pynmrstar import Entry, Saveframe
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    parse_frame_name,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames_by_name,
)
from nef_pipelines.lib.structures import NEFPipelinesInternalError, SaveframeNameParts
from nef_pipelines.lib.util import (
    FOUR_SPACES,
    STDIN,
    exit_error,
    find_index_of_first_unescaped,
    oxford_join,
    parse_comma_separated_options,
    strings_to_table_terminal_sensitive,
    unescape_backslashes,
)
from nef_pipelines.tools.frames import frames_app
from nef_pipelines.tools.frames.frames_lib import NEFFrameAlreadyExistsException

# TODO: Update rename to match frames create behavior and design-overview.md:
#       - Stream operations should succeed and warn by default (not error)
#       - Use --quiet to suppress warnings (not --force to allow overwriting)
#       - Reserve --force for file operations only
#       Currently: errors by default, --force allows overwriting (inconsistent with create)
#       Should be: succeeds + warns by default, --quiet suppresses warning
# TODO: add mmv like semantics as an option [https://manpages.ubuntu.com/manpages/bionic/man1/mmv.1.html]
# TODO: --singleton should also be added to frames create
# TODO: --index N|+N|-N flag for counter arithmetic (see plans/frames-rename-none-inherit-refactor.md)


class RenameTarget(str, Enum):
    identity = "identity"
    category = "category"
    namespace = "namespace"
    type = "type"


TARGET_NAMES = oxford_join([e.value for e in RenameTarget])


class Mode(str, Enum):
    find_and_replace = "find_and_replace"
    singleton = "singleton"
    replace = "replace"
    delete = "delete"
    bulk = "bulk"


@frames_app.command()
def rename(
    input: Path = typer.Option(
        STDIN, "-i", "--in", help="file to read input from [- is stdin]"
    ),
    exact: bool = typer.Option(
        False, "--exact", help="when matching frames and categories do it exactly"
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="""
            replace the whole target component of the framename with `NEW`,
            arguments are `NEW` [`FRAME-SELECTOR`...]""",
    ),
    delete: bool = typer.Option(
        False,
        "--delete",
        help="delete `STRING` from the target component, arguments are `STRING` [`FRAME-SELECTOR`...]",
    ),
    category: Optional[str] = typer.Option(None, help="select saveframes by category"),
    target: RenameTarget = typer.Option(
        RenameTarget.identity,
        "--target",
        help=f"""
            the component of the saveframe name to target: the default is the identity
            [available options: {TARGET_NAMES}]
            """,
    ),
    singleton: bool = typer.Option(
        False, "--singleton", help="rename to a category-only singleton saveframe name"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="overwrite a pre-existing fram of the same name",
    ),
    bulk: bool = typer.Option(
        False,
        "--bulk",
        help="apply multiple independent SELECTOR=/OLD/NEW/ triples; positional args are the triples",
    ),
    old_new_names: Optional[List[str]] = typer.Argument(
        None,
        help="""
            the arguments required depend on the mode:
            default: `OLD` `NEW` [`FRAME-SELECTOR`...] `NEW` text replaces `OLD`
            `--replace`: `NEW` [`FRAME-SELECTOR`...] the complete text of the part of the frame name with `NEW`
            `--delete`: `STRING` [`FRAME-SELECTOR`...] delete the `STRING` from the part of the frame name targeted
            `--singleton`: [`FRAME-SELECTOR`...] make the selected frames singletons remove their identities
            `--bulk`: `SELECTOR=/OLD/NEW/` ... apply independent rename triples (comma or space separated)
        """,
    ),
):
    """
         rename saveframes with substring replacements [default], complete replacements or deletions
         targeting namespaces, categories, types, and identities [see below for defintions]; singletons may also be
         created.

    the default operation is substring replacement in the identity of matched frames using the strings OLD and NEW:

    `frames rename OLD NEW [FRAME-SELECTOR...]`

    The options `--replace`, `--delete` and `--singleton` require different arguments:

    `--replace` directly replaces a whole target component with a NEW value and
    `--delete` deletes a substring TARGET from a component; both use a single argument and no OLD string value

    `frames rename --replace NEW [FRAME-SELECTOR...]`
    `frames rename --delete TARGET [FRAME-SELECTOR...]`

    >notes: `--replace`, `--delete`, and `--singleton` are mutually exclusive operation modes;
    >       `--target` selects the component to operate on and composes freely with all three
    >       except `--singleton`, which always operates on the identity.

    ```
         parts of a frame name:

         nef_nmr_spectrum_k_ubi_hncoca`1`
         ||| |||||||||||| |||||||||||| |
         nnn tttttttttttt iiiiiiiiiiii I
         cccccccccccccccc

         n - namespace
         t - type
         i - identity
         c - category
         I - index
    ```

    examples using:


    ```bash

        # nef_nmr_spectrum_k_ubi_hncoca`1`
        # nef_nmr_spectrum_k_ubi_hncaco`1`
        # nef_nmr_spectrum_k_ubi_hnco`1`


        # default: substring replace in identity, all frames (selector defaults to *)
        frames rename k_ubi k_ubiquitin
        #    nef_nmr_spectrum_k_ubiquitin_hncoca`1`
        #    nef_nmr_spectrum_k_ubiquitin_hncaco`1`
        #    nef_nmr_spectrum_k_ubiquitin_hnco`1`

        # default: substring replace with explicit selector
        frames rename k_ubi k_ubiquitin nef_nmr_spectrum_k_ubi_hnco`1`
        #    nef_nmr_spectrum_k_ubi_hncoca`1`          (unchanged)
        #    nef_nmr_spectrum_k_ubi_hncaco`1`          (unchanged)
        #    nef_nmr_spectrum_k_ubiquitin_hnco`1`

        # default: substring replace in namespace (--target is orthogonal to operation)
        frames rename --target namespace nef ccpn
        #    ccpn_nmr_spectrum_k_ubi_hncoca`1`
        #    ccpn_nmr_spectrum_k_ubi_hncaco`1`
        #    ccpn_nmr_spectrum_k_ubi_hnco`1`

        # --replace: set whole identity, explicit selector
        frames rename --replace new_hnco nef_nmr_spectrum_k_ubi_hnco`1`
        #    nef_nmr_spectrum_k_ubi_hncoca`1`          (unchanged)
        #    nef_nmr_spectrum_k_ubi_hncaco`1`          (unchanged)
        #    nef_nmr_spectrum_new_hnco

        # --replace: set whole namespace, all frames
        frames rename --target namespace --replace ccpn
        #    ccpn_nmr_spectrum_k_ubi_hncoca`1`
        #    ccpn_nmr_spectrum_k_ubi_hncaco`1`
        #    ccpn_nmr_spectrum_k_ubi_hnco`1`

        # --replace: set whole type
        frames rename --target type --replace relaxation
        #    nef_relaxation_k_ubi_hncoca`1`
        #    nef_relaxation_k_ubi_hncaco`1`
        #    nef_relaxation_k_ubi_hnco`1`

        # --replace: set whole category (namespace + type together)
        frames rename --target category --replace ccpn_nmr_spectrum
        #    ccpn_nmr_spectrum_k_ubi_hncoca`1`
        #    ccpn_nmr_spectrum_k_ubi_hncaco`1`
        #    ccpn_nmr_spectrum_k_ubi_hnco`1`

        # --delete: remove substring from identity, explicit selector
        frames rename --delete k_ubi nef_nmr_spectrum_k_ubi_hnco`1`
        #    nef_nmr_spectrum_k_ubi_hncoca`1`          (unchanged)
        #    nef_nmr_spectrum_k_ubi_hncaco`1`          (unchanged)
        #    nef_nmr_spectrum__hnco`1`   (note: leading underscore in identity)

        # --singleton: strip identity and index, leaving only the category framecode
        frames rename --singleton nef_nmr_spectrum_k_ubi_hnco`1`
        #    nef_nmr_spectrum_k_ubi_hncoca`1`          (unchanged)
        #    nef_nmr_spectrum_k_ubi_hncaco`1`          (unchanged)
        #    nef_nmr_spectrum

        # --bulk: apply independent SELECTOR=/OLD/NEW/ triples (single quotes avoid shell escaping)
        frames rename --bulk '*hnco*=/k_ubi/k_ubiquitin/' '*hncaco*=/k_ubi/k_ubiquitin/'
        #    nef_nmr_spectrum_k_ubiquitin_hncoca`1`
        #    nef_nmr_spectrum_k_ubiquitin_hncaco`1`
        #    nef_nmr_spectrum_k_ubiquitin_hnco`1`

        # --bulk: comma-separated in one arg
        frames rename --bulk '*hnco*=/k_ubi/k_ubiquitin/,*hncaco*=/k_ubi/k_ubiquitin/'

        # --bulk: composes with --target
        frames rename --target namespace --bulk '*=/nef/ccpn/'

    ```
    """

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    category_filter = category or ""

    mode = _mode_from_flags_or_exit_error(replace, delete, singleton, bulk, target)

    if mode == Mode.bulk:
        renames = []
        for arg in old_new_names or []:
            for chunk in _split_on_unescaped_comma(arg):
                for (
                    selector,
                    old_val,
                    new_val,
                ) in _parse_bulk_replace_triple_specs_or_exit_error(chunk):
                    selected = _select_frames_or_exit_error(
                        entry, [selector], category_filter, exact
                    )
                    pairs = _build_rename_pairs_or_exit_error(
                        selected, [old_val, new_val], target, Mode.find_and_replace
                    )
                    renames.extend(pairs)
    else:
        args = parse_comma_separated_options(old_new_names or [])
        operation_args, selectors = _extract_args_and_selectors_or_exit_error(
            args, mode
        )
        frames = _select_frames_or_exit_error(entry, selectors, category_filter, exact)
        renames = _build_rename_pairs_or_exit_error(
            frames, operation_args, target, mode
        )

    try:
        entry = pipe(entry, renames, force=force)
    except NEFFrameAlreadyExistsException as e:
        exit_error(
            dedent(
                f"""
                renaming '{e.source_name}' would overwrite the existing frame '{e.existing_name}'
                in entry '{e.entry_id}',  use --force to allow overwriting
                """
            ).strip()
        )
    print(entry)


def pipe(
    entry: Entry,
    renames: List[Tuple[Saveframe, SaveframeNameParts]],
    force: bool = False,
) -> Entry:
    for frame, target_parts in renames:
        resolved = _resolve_frame_name_parts(target_parts, parse_frame_name(frame))

        new_category = (
            f"{resolved.namespace}_{resolved.type}"
            if resolved.namespace
            else resolved.type
        )

        if resolved.full_name in entry.frame_dict:
            existing = entry.get_saveframe_by_name(resolved.full_name)

            is_rename_to_same_name = existing is frame
            if is_rename_to_same_name:
                continue

            if not force:
                raise NEFFrameAlreadyExistsException(
                    existing_name=resolved.full_name,
                    entry_id=entry.entry_id,
                    source_name=frame.name,
                )
            entry.remove_saveframe(existing)

        frame.name = resolved.full_name
        if frame.category != new_category:
            frame.category = new_category

    return entry


def _exit_no_frames_selected(target_name, target_category, entry, exact):
    all_names_and_categories = [(frame.name, frame.category) for frame in entry]

    if len(all_names_and_categories) == 0:
        msg = """
            there were no frames in the entry to rename
        """
    else:
        category_msg = (
            "" if not target_category else f" with category {target_category}"
        )
        matcher = SequenceMatcher()
        distances = []
        for name, cat in all_names_and_categories:
            matcher.set_seq1(name)
            matcher.set_seq2(target_name)
            distance_name = 1.0 - matcher.ratio()

            if target_category:
                matcher.set_seq1(target_category)
                matcher.set_seq2(cat)
                distance_category = 1.0 - matcher.ratio()
            else:
                distance_category = 0.0
            distance = (distance_name + distance_category) / 2.0
            distances.append((distance, (name, cat)))

        distances.sort()

        all_names = [name for name, _ in all_names_and_categories]
        table = strings_to_table_terminal_sensitive(all_names)
        table = tabulate(table, tablefmt="plain")
        table = indent(dedent(table), FOUR_SPACES)

        template = """
            the frame {target_name}{category_msg} wasn't found in the entry {entry_id},
            did you mean {closest_name} [category: {closest_category}]?

            all the frame names in the entry {entry_id} were:

            {table}
        """
        template = dedent(template)

        msg = template.format(
            target_name=target_name,
            category_msg=category_msg,
            entry_id=entry.entry_id,
            closest_name=distances[0][-1][0],
            closest_category=distances[0][-1][1],
            table=table,
        )

    exit_error(msg)


def _mode_from_flags_or_exit_error(
    replace: bool, delete: bool, singleton: bool, bulk: bool, target: RenameTarget
) -> Mode:
    if bulk and (replace or delete or singleton):
        exit_error("--bulk cannot be used with --replace, --delete, or --singleton")
    if replace and delete:
        exit_error("--replace and --delete are mutually exclusive")
    if singleton and (replace or delete):
        exit_error("--singleton cannot be used with --replace or --delete")
    if singleton and target != RenameTarget.identity:
        exit_error(
            "--singleton cannot be used with --target set to category, namespace, or type"
        )
    if bulk:
        mode = Mode.bulk
    elif replace:
        mode = Mode.replace
    elif delete:
        mode = Mode.delete
    elif singleton:
        mode = Mode.singleton
    else:
        mode = Mode.find_and_replace
    return mode


def _extract_args_and_selectors_or_exit_error(
    args: List[str], mode: Mode
) -> Tuple[List[str], List[str]]:
    if mode == Mode.replace:
        if not args:
            exit_error("--replace requires a NEW value argument")
        operation_args, selectors = args[:1], args[1:] or ["*"]
    elif mode == Mode.delete:
        if not args:
            exit_error("--delete requires a STRING argument")
        operation_args, selectors = args[:1], args[1:] or ["*"]
    elif mode == Mode.singleton:
        operation_args, selectors = [], args or ["*"]
    elif mode == Mode.find_and_replace:  # find_and_replace
        if len(args) < 2:
            exit_error("rename requires OLD and NEW arguments")
        operation_args, selectors = args[:2], args[2:] or ["*"]
    else:
        exit_error(f"internal error unknown mode: {mode}; please report this as a bug")

    return operation_args, selectors


_BULK_SELECTOR_ESCAPES = (".", "*", "?", "=", "\\")
_BULK_VALUE_ESCAPES = (".", "*", "?", "/", "\\")


def _split_on_unescaped_comma(s: str) -> List[str]:
    chunks = []
    start = 0
    while True:
        idx = find_index_of_first_unescaped(s[start:], ",")
        if idx is None:
            chunks.append(s[start:])
            break
        chunks.append(s[start : start + idx])
        start += idx + 1
    return [c for c in chunks if c]


def _parse_bulk_replace_triple_specs_or_exit_error(
    chunk: str,
) -> List[Tuple[str, str, str]]:
    results = []
    remainder = chunk
    while remainder:
        eq_idx = find_index_of_first_unescaped(remainder, "=")
        if eq_idx is None:
            exit_error(
                f"bulk expression {chunk!r}: missing '=' separator (SELECTOR=/OLD/NEW/)"
            )
        selector = unescape_backslashes(
            remainder[:eq_idx], escapes=_BULK_SELECTOR_ESCAPES
        )
        remainder = remainder[eq_idx + 1 :]

        if not remainder.startswith("/"):
            exit_error(
                f"bulk expression {chunk!r}: replacement must start with '/' after '=' (SELECTOR=/OLD/NEW/)"
            )
        remainder = remainder[1:]

        slash_idx = find_index_of_first_unescaped(remainder, "/")
        if slash_idx is None:
            exit_error(
                f"bulk expression {chunk!r}: missing '/' between OLD and NEW (SELECTOR=/OLD/NEW/)"
            )
        old_val = unescape_backslashes(
            remainder[:slash_idx], escapes=_BULK_VALUE_ESCAPES
        )
        remainder = remainder[slash_idx + 1 :]

        slash_idx2 = find_index_of_first_unescaped(remainder, "/")
        if slash_idx2 is None:
            exit_error(
                f"bulk expression {chunk!r}: missing trailing '/' after NEW (SELECTOR=/OLD/NEW/)"
            )
        new_val = unescape_backslashes(
            remainder[:slash_idx2], escapes=_BULK_VALUE_ESCAPES
        )
        remainder = remainder[slash_idx2 + 1 :]

        # After trailing slash, remainder should be empty
        # (comma separation is handled by _split_on_unescaped_comma before parsing)
        if remainder:
            exit_error(
                f"bulk expression {chunk!r}: unexpected text after trailing '/'. "
                + "Multiple triples should be comma-separated or passed as separate arguments."
            )

        results.append((selector, old_val, new_val))
    return results


def _exit_spaces_in_new_name(new_name):
    msg = f"""
        frame names can't contain spaces your new name was  {new_name} and contains spaces
    """
    exit_error(msg)


def _exit_empty_after_edit(frame, old_val, new_val, component):
    msg = f"""
        replacing '{old_val}' with '{new_val}' in the {component} of '{frame.name}' would produce an empty value
    """
    exit_error(msg)


def _exit_empty_after_delete(frame, substr, component):
    msg = f"""
        deleting '{substr}' from the {component} of '{frame.name}' would produce an empty value
    """
    exit_error(msg)


def _resolve_frame_name_parts(
    target: SaveframeNameParts, source: SaveframeNameParts
) -> SaveframeNameParts:
    return SaveframeNameParts(
        namespace=(
            target.namespace if target.namespace is not None else source.namespace
        ),
        type=target.type if target.type is not None else source.type,
        identity=target.identity if target.identity is not None else source.identity,
        index=target.index if target.index is not None else source.index,
    )


def _select_frames_or_exit_error(
    entry, selectors: List[str], category: str, exact: bool
) -> List[Saveframe]:
    frames = []
    for selector in selectors:
        selected = select_frames_by_name(entry, [selector], exact)
        if category:
            if exact:
                selected = [f for f in selected if f.category == category]
            else:
                selected = [
                    f for f in selected if fnmatchcase(f.category, f"*{category}*")
                ]
        if not selected:
            _exit_no_frames_selected(selector, category, entry, exact)
        frames.extend(selected)
    return frames


def _get_component(source: SaveframeNameParts, target: RenameTarget) -> str:
    if target == RenameTarget.identity:
        return source.identity or ""
    elif target == RenameTarget.namespace:
        return source.namespace or ""
    elif target == RenameTarget.type:
        return source.type or ""
    else:  # category
        ns = source.namespace or ""
        t = source.type or ""
        return f"{ns}_{t}" if ns else t


def _parts_from_component(
    target: RenameTarget, new_value: str, clear_index: bool = False
) -> SaveframeNameParts:

    if target == RenameTarget.identity:
        result = SaveframeNameParts(
            identity=new_value or "", index="" if clear_index else None
        )
    elif target == RenameTarget.namespace:
        result = SaveframeNameParts(namespace=new_value or "")
    elif target == RenameTarget.type:
        result = SaveframeNameParts(type=new_value or "")
    elif target == RenameTarget.category:
        cat_parts = parse_frame_name((new_value, new_value))
        ns = cat_parts.namespace if cat_parts.namespace is not None else ""
        result = SaveframeNameParts(namespace=ns, type=cat_parts.type)
    else:
        raise NEFPipelinesInternalError(f"unknown target {target}")
    return result


def _build_rename_pairs_or_exit_error(
    frames: List[Saveframe],
    operation_args: List[str],
    target: RenameTarget,
    mode: Mode,
) -> List[Tuple[Saveframe, SaveframeNameParts]]:
    renames = []

    if mode in (Mode.replace, Mode.singleton):
        new_value = "" if mode == Mode.singleton else operation_args[0]
        if new_value and len(new_value.split()) > 1:
            _exit_spaces_in_new_name(new_value)
        for frame in frames:
            renames.append(
                (frame, _parts_from_component(target, new_value, clear_index=True))
            )

    elif mode == Mode.delete:
        substr = operation_args[0]
        for frame in frames:
            source = parse_frame_name(frame)
            field_val = _get_component(source, target)
            new_val = field_val.replace(substr, "")
            if new_val == field_val:
                continue
            if not new_val:
                _exit_empty_after_delete(frame, substr, target.value)
            renames.append(
                (frame, _parts_from_component(target, new_val, clear_index=False))
            )

    else:  # Mode.find_and_replace
        old_str, new_str = operation_args[0], operation_args[1]
        if len(new_str.split()) > 1:
            _exit_spaces_in_new_name(new_str)
        for frame in frames:
            source = parse_frame_name(frame)
            field_val = _get_component(source, target)
            new_val = field_val.replace(old_str, new_str)
            if new_val == field_val:
                continue
            if not new_val:
                _exit_empty_after_edit(frame, old_str, new_str, target.value)
            renames.append(
                (frame, _parts_from_component(target, new_val, clear_index=False))
            )

    return renames
