import pytest
import typer
from pynmrstar import Entry

from nef_pipelines.lib.structures import SaveframeNameParts
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.rename import pipe as rename_pipe
from nef_pipelines.tools.frames.rename import rename

EXIT_ERROR = 1

app = typer.Typer()
app.command()(rename)

ORIGINAL_FRAME_NAMES = [
    "nef_nmr_meta_data",
    "nef_molecular_system",
    "nef_chemical_shift_list_default",
    "nef_nmr_spectrum_k_ubi_n_hsqc`1`",
    "nef_nmr_spectrum_k_ubi_hnca`1`",
    "nef_nmr_spectrum_k_ubi_hncoca`1`",
    "nef_nmr_spectrum_k_ubi_hncaco`1`",
    "nef_nmr_spectrum_k_ubi_hnco`1`",
    "nef_nmr_spectrum_k_ubi_hncacb`1`",
    "nef_nmr_spectrum_k_ubi_cbcaconh`1`",
    "nef_nmr_spectrum_mars_ubi_n_hsqc`1`",
    "ccpn_substance_1D3Z_1|Chain.None",
    "ccpn_substance_mySubstance.None",
    "ccpn_assignment",
]

# Frame table that appears in "not found" errors for ubiquitin_short.nef
_UBIQUITIN_FRAME_TABLE = """\
    nef_nmr_meta_data nef_molecular_system
    nef_chemical_shift_list_default nef_nmr_spectrum_k_ubi_n_hsqc`1`
    nef_nmr_spectrum_k_ubi_hnca`1` nef_nmr_spectrum_k_ubi_hncoca`1`
    nef_nmr_spectrum_k_ubi_hncaco`1` nef_nmr_spectrum_k_ubi_hnco`1`
    nef_nmr_spectrum_k_ubi_hncacb`1` nef_nmr_spectrum_k_ubi_cbcaconh`1`
    nef_nmr_spectrum_mars_ubi_n_hsqc`1` ccpn_substance_1D3Z_1|Chain.None
    ccpn_substance_mySubstance.None ccpn_assignment"""


# --- pipe-level tests (unchanged) ---


def test_rename_basic_pipe():
    OLD_FRAME_ID = "nef_chemical_shift_list_default"
    NEW_FRAME_ID = "nef_chemical_shift_list_renamed"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    entry = Entry.from_file(str(path))

    frame = entry.get_saveframe_by_name(OLD_FRAME_ID)
    target = SaveframeNameParts(identity="renamed")
    result = rename_pipe(entry, [(frame, target)])

    frame_names = list(result.frame_dict.keys())
    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_pipe_inherits_index():
    OLD_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_FRAME_ID = "nef_nmr_spectrum_new_id`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    entry = Entry.from_file(str(path))

    frame = entry.get_saveframe_by_name(OLD_FRAME_ID)
    target = SaveframeNameParts(identity="new_id")  # index=None → inherit
    result = rename_pipe(entry, [(frame, target)])

    frame_names = list(result.frame_dict.keys())
    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


# --- default mode: substring replace OLD→NEW in identity ---


def test_rename_basic():
    # replace 'k_ubi_hnco' in identity of frames matching _hnco`1`; index preserved
    OLD_STR = "k_ubi_hnco"
    NEW_STR = "k_ubi_hnco_new"
    OLD_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco_new`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, OLD_STR, NEW_STR, "_hnco`1`"])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_replace():
    # OLD NEW SELECTOR → substring replace; selector _hnco matches hnco and hncoca; index preserved
    OLD_HNCO = "nef_nmr_spectrum_k_ubi_hnco`1`"
    OLD_HNCOCA = "nef_nmr_spectrum_k_ubi_hncoca`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, "k_ubi", "k_ubiquitin", "_hnco"])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name not in (OLD_HNCO, OLD_HNCOCA)
    ]
    EXPECTED_FRAME_NAMES += [
        "nef_nmr_spectrum_k_ubiquitin_hnco`1`",
        "nef_nmr_spectrum_k_ubiquitin_hncoca`1`",
    ]
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_replace_default_selector():
    # no selectors → * (all frames); k_ubi appears in seven spectra identities
    K_UBI_FRAMES = [
        "nef_nmr_spectrum_k_ubi_n_hsqc`1`",
        "nef_nmr_spectrum_k_ubi_hnca`1`",
        "nef_nmr_spectrum_k_ubi_hncoca`1`",
        "nef_nmr_spectrum_k_ubi_hncaco`1`",
        "nef_nmr_spectrum_k_ubi_hnco`1`",
        "nef_nmr_spectrum_k_ubi_hncacb`1`",
        "nef_nmr_spectrum_k_ubi_cbcaconh`1`",
    ]

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, "k_ubi", "k_ubiquitin"])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name not in K_UBI_FRAMES
    ]
    EXPECTED_FRAME_NAMES += [
        name.replace("k_ubi", "k_ubiquitin") for name in K_UBI_FRAMES
    ]
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_replace_target_namespace():
    # substring replace in namespace: nef → ccpn for the hnco frame
    OLD_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_FRAME_ID = "ccpn_nmr_spectrum_k_ubi_hnco`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, "--target", "namespace", "nef", "ccpn", "_hnco`"]
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


# --- --replace mode: set whole component ---


@pytest.mark.parametrize(
    "searched_name",
    [
        pytest.param("_hnco`", id="short"),
        pytest.param("*hnco`", id="wildcard"),
        pytest.param("nef_nmr_spectrum_k_ubi_hnco`1`", id="full_name"),
    ],
)
def test_rename_pattern_match(searched_name):
    # --replace sets whole identity; index is cleared
    NEW_NAME = "k_ubi_hnco_1"
    OLD_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_FRAME_ID = f"nef_nmr_spectrum_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, "--replace", NEW_NAME, searched_name])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_multiple_matched():
    # *n_hsqc* matches two frames; --replace --target namespace sets same namespace, unique identities
    OLD_FRAMES = [
        "nef_nmr_spectrum_k_ubi_n_hsqc`1`",
        "nef_nmr_spectrum_mars_ubi_n_hsqc`1`",
    ]

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, "--target", "namespace", "--replace", "test_ns", "*n_hsqc*"]
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name not in OLD_FRAMES
    ]
    EXPECTED_FRAME_NAMES += [name.replace("nef_", "test_ns_") for name in OLD_FRAMES]
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_category_match():
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hnco_1"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--category", CATEGORY, "--in", path, "--replace", NEW_NAME, SEARCHED_NAME],
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


EXPECTED_BAD_CATEGORY_MATCH_ERROR = f"""
    ERROR [in: rename]:
    the frame nef_nmr_spectrum_k_ubi_hnco`1` with category nef_nmr_peaklist wasn't found in the entry ubiquitin,
    did you mean nef_nmr_spectrum_k_ubi_hnco`1` [category: nef_nmr_spectrum]?
    all the frame names in the entry ubiquitin were:

    {_UBIQUITIN_FRAME_TABLE}

    exiting...
"""  # noqa: E501


def test_bad_category_match():
    CATEGORY = "nef_nmr_peaklist"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--category", CATEGORY, "--in", path, "--replace", NEW_NAME, SEARCHED_NAME],
        expected_exit_code=1,
    )

    assert_lines_match(EXPECTED_BAD_CATEGORY_MATCH_ERROR, result.stdout)


def test_exact_match():
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "ubi_hnco_new"
    OLD_FRAME_ID = SEARCHED_NAME
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--exact", "--in", path, "--replace", NEW_NAME, SEARCHED_NAME]
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_exact_match_category():
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "ubi_hnco_1"
    OLD_FRAME_ID = SEARCHED_NAME
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        [
            "--exact",
            "--category",
            CATEGORY,
            "--in",
            path,
            "--replace",
            NEW_NAME,
            SEARCHED_NAME,
        ],
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


EXPECTED_EXACT_CATEGORY_FAILURE_ERROR = f"""
    ERROR [in: rename]:
    the frame nef_nmr_spectrum_k_ubi_hnco`1` with category ef_nmr_spectrum wasn't found in the entry ubiquitin,
    did you mean nef_nmr_spectrum_k_ubi_hnco`1` [category: nef_nmr_spectrum]?
    all the frame names in the entry ubiquitin were:
    {_UBIQUITIN_FRAME_TABLE}
    exiting...
"""  # noqa: E501


def test_exact_match_category_failure():
    CATEGORY = "ef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        [
            "--exact",
            "--category",
            CATEGORY,
            "--in",
            path,
            "--replace",
            NEW_NAME,
            SEARCHED_NAME,
        ],
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(EXPECTED_EXACT_CATEGORY_FAILURE_ERROR, result.stdout)


EXPECTED_BAD_NEW_NAME_ERROR = """
    ERROR [in: rename]:
    frame names can't contain spaces your new name was hn co and contains spaces
    exiting...
"""


def test_bad_new_name():
    # spaces in NEW (default substring mode)
    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, "k_ubi_hnco", "hn co"], expected_exit_code=EXIT_ERROR
    )

    assert_lines_match(EXPECTED_BAD_NEW_NAME_ERROR, result.stdout)


EXPECTED_BAD_EXACT_MATCH_ERROR = f"""
    ERROR [in: rename]:
    the frame ef_nmr_spectrum_k_ubi_hnco`1` wasn't found in the entry ubiquitin,
    did you mean nef_nmr_spectrum_k_ubi_hnco`1` [category: nef_nmr_spectrum]?
    all the frame names in the entry ubiquitin were:
    {_UBIQUITIN_FRAME_TABLE}
    exiting...
"""


def test_bad_exact_match():
    SEARCHED_NAME = "ef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--exact", "--in", path, "--replace", NEW_NAME, SEARCHED_NAME],
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(EXPECTED_BAD_EXACT_MATCH_ERROR, result.stdout)


EXPECTED_CLASHING_MULTIPLE_RENAME_ERROR = """
    ERROR [in: rename]: renaming 'nef_nmr_spectrum_mars_ubi_n_hsqc`1`' would overwrite the existing frame 'nef_nmr_spectrum_N15_hsqc'  # noqa: E501
    in entry 'ubiquitin', use --force to allow overwriting
    exiting...
"""


# TODO: this should actually say the error is that there are multiple matches...
def test_error_multiple_frames_matched():
    # --replace sets same identity on two frames → clash
    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--in", path, "--replace", "N15_hsqc", "*n_hsqc*"],
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(EXPECTED_CLASHING_MULTIPLE_RENAME_ERROR, result.stdout)


EXPECTED_EMPTY_ENTRY_ERROR = """
    ERROR [in: rename]:
    there were no frames in the entry to rename
    exiting...
"""


def test_error_empty_entry():
    path = path_in_test_data(__file__, "empty.nef")
    result = run_and_report(
        app, ["--in", path, "--replace", "new_name"], expected_exit_code=EXIT_ERROR
    )

    assert_lines_match(EXPECTED_EMPTY_ENTRY_ERROR, result.stdout)


EXPECTED_NO_FRAMES_SELECTED_ERROR = f"""
    ERROR [in: rename]:
    the frame nef_molecular_sytem wasn't found in the entry ubiquitin,
    did you mean nef_molecular_system [category: nef_molecular_system]?
    all the frame names in the entry ubiquitin were:
    {_UBIQUITIN_FRAME_TABLE}
    exiting...
"""


# TODO but there is a nef_molecular_system the problem is replacement names don't match it...
def test_error_no_frames_selected():
    # explicit selector with typo → no match → error
    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--in", path, "k_ubi", "k_ubiquitin", "nef_molecular_sytem"],
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(EXPECTED_NO_FRAMES_SELECTED_ERROR, result.stdout)


EXPECTED_CLASHING_NAME_ERROR = """
    ERROR [in: rename]: renaming 'nef_nmr_spectrum_k_ubi_hnco`1`' would overwrite the existing frame 'nef_nmr_spectrum_k_ubi_hncaco`1`'
    in entry 'ubiquitin', use --force to allow overwriting
    exiting...
"""  # noqa: E501


# TODO renaming a frame to the same name isn't an error at most its a warning!
def test_rename_to_existing_fail():
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hncaco`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--in", path, "--replace", NEW_NAME, SEARCHED_NAME],
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(EXPECTED_CLASHING_NAME_ERROR, result.stdout)


# TODO: not needed see above!
def test_rename_to_existing_force():
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hncaco`1`"
    OLD_FRAME_ID = SEARCHED_NAME

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, "--force", "--replace", NEW_NAME, SEARCHED_NAME]
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_category():
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_NAME = "nef_test"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{NEW_NAME}_{SEARCHED_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--in", path, "--target", "category", "--replace", NEW_NAME, SEARCHED_NAME],
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)

    assert ["sf_category", NEW_NAME] in entry.frame_dict[NEW_FRAME_ID].tags


# TODO: what does this test!? whats id flag?
def test_rename_id_flag():
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_NAME = "my_new_id"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, "--replace", NEW_NAME, SEARCHED_NAME])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_id_to_singleton():
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = CATEGORY

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, "--replace", "", SEARCHED_NAME])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_singleton():
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    OLD_FRAME = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME = CATEGORY

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, "--singleton", SEARCHED_NAME])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    assert NEW_FRAME in frame_names
    assert OLD_FRAME not in frame_names

    EXPECTED_FRAME_NAMES = [name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


EXPECTED_REPLACE_AND_DELETE_TOGETHER_ERROR = """
    ERROR [in: rename]: --replace and --delete are mutually exclusive
    exiting...
"""


def test_rename_replace_and_delete_error():
    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--in", path, "--replace", "new_id", "--delete", "k_ubi"],
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(EXPECTED_REPLACE_AND_DELETE_TOGETHER_ERROR, result.stdout)


EXPECTED_DELETE_AND_SINGLETON_TOGETHER_ERROR = """
    ERROR [in: rename]: --singleton cannot be used with --replace or --delete
    exiting...
"""


def test_rename_delete_and_singleton_error():
    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--in", path, "--delete", "k_ubi", "--singleton"],
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(EXPECTED_DELETE_AND_SINGLETON_TOGETHER_ERROR, result.stdout)


def test_rename_delete():
    OLD_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_FRAME_ID = "nef_nmr_spectrum__hnco`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, "--delete", "k_ubi", "_hnco`"])

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_target_namespace():
    OLD_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_FRAME_ID = "ccpn_nmr_spectrum_k_ubi_hnco`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, "--target", "namespace", "--replace", "ccpn", "_hnco`"]
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


def test_rename_target_type():
    OLD_FRAME_ID = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_FRAME_ID = "nef_relaxation_k_ubi_hnco`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, "--target", "type", "--replace", "relaxation", "_hnco`"]
    )

    entry = Entry.from_string(result.stdout)
    frame_names = list(entry.frame_dict.keys())

    EXPECTED_FRAME_NAMES = [
        name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID
    ]
    EXPECTED_FRAME_NAMES.append(NEW_FRAME_ID)
    assert sorted(EXPECTED_FRAME_NAMES) == sorted(frame_names)


# TODO what happens if you do a rename to singleton and it produces multiple frams of the same name this should be an error  # noqa: E501
