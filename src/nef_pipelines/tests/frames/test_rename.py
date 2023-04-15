import typer
from pynmrstar import Entry

from nef_pipelines.lib.test_lib import path_in_test_data, run_and_report
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


# noinspection PyUnusedLocal
def test_rename_basic():

    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hnco_1"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, SEARCHED_NAME, NEW_NAME])

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert OLD_FRAME_ID not in frame_names

    assert sorted(ORIGINAL_FRAME_NAMES) != sorted(frame_names)

    NEW_FRAME_NAMES = [name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID]
    NEW_FRAME_NAMES.append(NEW_FRAME_ID)

    assert sorted(NEW_FRAME_NAMES) == sorted(frame_names)


def test_multiple_selection_fail():

    SEARCHED_NAME = "ubi"
    NEW_NAME = "k_ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, SEARCHED_NAME, NEW_NAME], expected_exit_code=EXIT_ERROR
    )

    assert "ERROR" in result.stdout
    assert "one save frame at the same time" in result.stdout


def test_rename_short_match():

    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "_hnco`"
    NEW_NAME = "k_ubi_hnco_1"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, SEARCHED_NAME, NEW_NAME])

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert OLD_FRAME_ID not in frame_names

    assert sorted(ORIGINAL_FRAME_NAMES) != sorted(frame_names)


def test_rename_wildcard_match():

    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "*hnco`"
    NEW_NAME = "k_ubi_hnco_1"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, SEARCHED_NAME, NEW_NAME])

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert OLD_FRAME_ID not in frame_names

    assert sorted(ORIGINAL_FRAME_NAMES) != sorted(frame_names)


def test_rename_full_name_match():

    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hnco_1"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, SEARCHED_NAME, NEW_NAME])

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert OLD_FRAME_ID not in frame_names

    assert sorted(ORIGINAL_FRAME_NAMES) != sorted(frame_names)


def test_category_match():

    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hnco_1"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--category", CATEGORY, "--in", path, SEARCHED_NAME, NEW_NAME]
    )

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert OLD_FRAME_ID not in frame_names

    assert sorted(ORIGINAL_FRAME_NAMES) != sorted(frame_names)


def test_bad_category_match():

    CATEGORY = "nef_nmr_peaklist"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--category", CATEGORY, "--in", path, SEARCHED_NAME, NEW_NAME],
        expected_exit_code=1,
    )

    assert "wasn't found in the entry" in result.stdout


def test_exact_match():

    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "ubi_hnco_1"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--exact", "--in", path, SEARCHED_NAME, NEW_NAME])

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert OLD_FRAME_ID not in frame_names


def test_exact_match_category():

    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "ubi_hnco_1"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--exact", "--category", CATEGORY, "--in", path, SEARCHED_NAME, NEW_NAME]
    )

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert OLD_FRAME_ID not in frame_names


def test_exact_match_category_failure():

    CATEGORY = "ef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--exact", "--category", CATEGORY, "--in", path, SEARCHED_NAME, NEW_NAME],
        expected_exit_code=EXIT_ERROR,
    )

    assert "wasn't found in the entry" in result.stdout


def test_bad_new_name():

    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "hn co"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, SEARCHED_NAME, NEW_NAME], expected_exit_code=EXIT_ERROR
    )

    assert "frame names can't contain spaces" in result.stdout


def test_bad_exact_match():
    SEARCHED_NAME = "ef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app,
        ["--exact", "--in", path, SEARCHED_NAME, NEW_NAME],
        expected_exit_code=EXIT_ERROR,
    )

    assert "wasn't found in the entry" in result.stdout


def test_error_multiple_frames_matched():
    SEARCHED_NAME = "*"
    NEW_NAME = "ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, SEARCHED_NAME, NEW_NAME], expected_exit_code=EXIT_ERROR
    )

    assert "multiple save frames were selected" in result.stdout


def test_error_empty_entry():
    SEARCHED_NAME = "*"
    NEW_NAME = "ubi_hnco_1"

    path = path_in_test_data(__file__, "empty.nef")
    result = run_and_report(
        app, ["--in", path, SEARCHED_NAME, NEW_NAME], expected_exit_code=EXIT_ERROR
    )

    assert "there were no frames in the entry" in result.stdout


def test_error_no_frames_selected():
    SEARCHED_NAME = "wibble"
    NEW_NAME = "k_ubi_hnco_1"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, SEARCHED_NAME, NEW_NAME], expected_exit_code=EXIT_ERROR
    )

    assert "wasn't found in the entry" in result.stdout


def test_rename_to_existing_fail():
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hncaco`1`"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, SEARCHED_NAME, NEW_NAME], expected_exit_code=EXIT_ERROR
    )

    assert "a frame with the name" in result.stdout
    assert NEW_NAME in result.stdout
    assert "already exists in entry" in result.stdout


def test_rename_to_existing_force():
    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "nef_nmr_spectrum_k_ubi_hnco`1`"
    NEW_NAME = "k_ubi_hncaco`1`"
    NEW_FRAME_ID = f"{CATEGORY}_{NEW_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(app, ["--in", path, "--force", SEARCHED_NAME, NEW_NAME])

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert SEARCHED_NAME not in frame_names


def test_rename_category():

    CATEGORY = "nef_nmr_spectrum"
    SEARCHED_NAME = "k_ubi_hnco`1`"
    NEW_NAME = "nef_test"
    OLD_FRAME_ID = f"{CATEGORY}_{SEARCHED_NAME}"
    NEW_FRAME_ID = f"{NEW_NAME}_{SEARCHED_NAME}"

    path = path_in_test_data(__file__, "ubiquitin_short.nef")
    result = run_and_report(
        app, ["--in", path, "--rename-category", SEARCHED_NAME, NEW_NAME]
    )

    entry = Entry.from_string(result.stdout)

    frame_names = list(entry.frame_dict.keys())
    assert NEW_FRAME_ID in frame_names
    assert OLD_FRAME_ID not in frame_names

    assert sorted(ORIGINAL_FRAME_NAMES) != sorted(frame_names)

    NEW_FRAME_NAMES = [name for name in ORIGINAL_FRAME_NAMES if name != OLD_FRAME_ID]
    NEW_FRAME_NAMES.append(NEW_FRAME_ID)

    assert sorted(NEW_FRAME_NAMES) == sorted(frame_names)

    assert ["sf_category", NEW_NAME] in entry.frame_dict[NEW_FRAME_ID].tags
