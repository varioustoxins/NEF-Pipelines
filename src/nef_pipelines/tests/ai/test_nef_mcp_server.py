"""
Tests for AI server tool functions in server_lib.py.
"""

import sys
from pathlib import Path

import pytest

from nef_pipelines.lib.test_lib import assert_lines_match, isolate_frame, read_test_data
from nef_pipelines.tools.ai.mcp_commands_lib import (
    nef_change_sandbox,
    nef_download_file,
    nef_execute_pipeline,
    nef_get_command_help,
    nef_list_commands,
    nef_list_files,
    nef_read_me_first,
    nef_resources_list,
    nef_resources_read,
    nef_upload_file,
)
from nef_pipelines.tools.ai.mcp_lib import (
    ChangeSandboxResult,
    CommandHelpResult,
    CommandTableResult,
    DownloadResult,
    ListFilesResult,
    NefStartupResult,
    PipelineResult,
    UploadResult,
)
from nef_pipelines.tools.ai.server import (
    NEF_MCP_SANDBOX_ENV_VAR_NAME,
    SandboxPathResult,
    _get_sandbox_path,
)

if sys.version_info < (3, 10):
    pytest.skip("MCP server requires Python 3.10 or later", allow_module_level=True)

pytest.importorskip("fastmcp")

EXPECTED_COMMON_COMMANDS = ["frames", "save", "help"]
EXPECTED_README_SECTIONS = [
    "NEF-Pipelines",
]
EXPECTED_HELP_SECTIONS = ["Usage:", "Options", "General"]
EXPECTED_FRAMES_LIST = """\
nef_nmr_meta_data                    nef_molecular_system
nef_chemical_shift_list_default      nef_nmr_spectrum_k_ubi_n_hsqc`1`
nef_nmr_spectrum_k_ubi_hnca`1`       nef_nmr_spectrum_k_ubi_hncoca`1`
nef_nmr_spectrum_k_ubi_hncaco`1`     nef_nmr_spectrum_k_ubi_hnco`1`
nef_nmr_spectrum_k_ubi_hncacb`1`     nef_nmr_spectrum_k_ubi_cbcaconh`1`
nef_nmr_spectrum_mars_ubi_n_hsqc`1`  ccpn_substance_1D3Z_1|Chain.None
ccpn_substance_mySubstance.None      ccpn_assignment
"""
EXPECTED_README_DESCRIPTION = "README for the NEF-PIpelines MCP server"

# Exact error templates matching mcp_commands_lib.py nef_change_sandbox
EXPECTED_ERROR_CANCELLED = "User cancelled directory selection"
EXPECTED_ERROR_UNSUPPORTED_OS = "Unsupported OS"
EXPECTED_ERROR_PATH_DOES_NOT_EXIST = "Path does not exist: {path}"
EXPECTED_ERROR_PATH_NOT_DIRECTORY = "Path is not a directory: {path}"

# Exact warning templates matching server.py _get_sandbox_path
EXPECTED_PATH_ARG_NOT_EXIST = "Specified --path does not exist: {path}"
EXPECTED_PATH_ARG_NOT_DIRECTORY = "Specified --path is not a directory: {path}"
EXPECTED_FALLBACK_TO_ENV_VAR = " — falling back to {env_var}: {path}"


@pytest.fixture
def simple_nef_data():
    """\
    Simple NEF data for testing.
    """
    return read_test_data("ubiquitin_short.nef", __file__)


# --- nef_list_commands ---


@pytest.mark.parametrize(
    "command_pattern,expected_keywords",
    [
        pytest.param("*", EXPECTED_COMMON_COMMANDS, id="all"),
        pytest.param("*frames*", ["frames"], id="frames_filter"),
        pytest.param("*sparky*", ["sparky"], id="sparky_filter"),
    ],
)
def test_nef_list_commands(command_pattern, expected_keywords):
    """\
    Test nef_list_commands returns a markdown table containing expected commands.
    """
    result = nef_list_commands(command_pattern=command_pattern)
    EXPECTED = CommandTableResult(
        commands_table=result.commands_table, exit_code=0, stderr=""
    )
    assert result == EXPECTED
    table = result.commands_table
    assert "|" in table
    assert "command" in table.lower()
    assert "category" in table.lower()
    for keyword in expected_keywords:
        assert keyword in table.lower(), f"Missing keyword: {keyword}"


# --- nef_get_command_help ---


@pytest.mark.parametrize(
    "command_pattern,group_by_category,expected_keyword,min_len",
    [
        pytest.param("save", False, "save", 200, id="single_command"),
        pytest.param("*frames*", False, "frames", 100, id="wildcard"),
        pytest.param("*", True, None, 500, id="grouped"),
    ],
)
def test_nef_get_command_help(
    command_pattern, group_by_category, expected_keyword, min_len
):
    """\
    Test nef_get_command_help returns full help text for the given pattern.
    """
    result = nef_get_command_help(
        command_pattern=command_pattern, group_by_category=group_by_category
    )
    EXPECTED = CommandHelpResult(help_text=result.help_text, exit_code=0, stderr="")
    assert result == EXPECTED
    assert len(result.help_text) > min_len
    if expected_keyword:
        assert expected_keyword in result.help_text.lower()


# --- nef_read_me_first ---

EXPECTED_ORIENTATION_CONTENT_SUBSTRINGS = [
    "Already oriented",
    "NEF",
    "`readme``",
]


def test_nef_read_me_first():
    """\
    Test nef_read_me_first returns orientation content.
    """
    result = nef_read_me_first()
    EXPECTED = NefStartupResult(
        content=result.content,
        information=result.information,
    )
    assert result == EXPECTED

    for substring in EXPECTED_ORIENTATION_CONTENT_SUBSTRINGS:
        assert substring.replace("`", "") in result.content
    assert len(result.content) > 200


# --- nef_execute_pipeline ---


def test_nef_execute_pipeline_empty_steps():
    """\
    Test nef_execute_pipeline with no steps is a no-op.
    """
    result = nef_execute_pipeline(steps=[])
    EXPECTED = PipelineResult(
        steps=[], stdout="", stderr=[], exit_code=0, steps_completed=0
    )
    assert result == EXPECTED


def test_nef_execute_pipeline_single_step(simple_nef_data):
    """\
    Test nef_execute_pipeline with single step executes successfully.
    """
    result = nef_execute_pipeline(steps=[["frames", "list"]], nef_input=simple_nef_data)
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["frames", "list"]],
        steps_completed=1,
    )
    assert result == EXPECTED
    assert len(result.stderr) == 1


def test_nef_execute_pipeline_multiple_steps(simple_nef_data):
    """\
    Test nef_execute_pipeline chains stdout→stdin across steps.
    """
    result = nef_execute_pipeline(
        steps=[["save", "-"], ["frames", "list"]], nef_input=simple_nef_data
    )
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["save", "-"], ["frames", "list"]],
        steps_completed=2,
    )
    assert result == EXPECTED
    assert_lines_match(EXPECTED_FRAMES_LIST, result.stdout)


def test_nef_execute_pipeline_step_failure():
    """\
    Test nef_execute_pipeline stops on step failure.
    """
    result = nef_execute_pipeline(steps=[["version"], ["nonexistent", "command"]])
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        steps=[["version"], ["nonexistent", "command"]],
        steps_completed=1,
    )
    assert result == EXPECTED
    assert result.exit_code != 0
    assert len(result.stderr) == 2


def test_nef_execute_pipeline_with_nef_data_passthrough(simple_nef_data):
    """\
    Test that pipeline can process NEF data through save command.
    """
    result = nef_execute_pipeline(steps=[["save", "-"]], nef_input=simple_nef_data)
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["save", "-"]],
        steps_completed=1,
    )
    assert result == EXPECTED
    assert_lines_match(
        isolate_frame(simple_nef_data, "nef_molecular_system"),
        isolate_frame(result.stdout, "nef_molecular_system"),
    )


def test_nef_execute_pipeline_step_with_no_args():
    """\
    Test nef_execute_pipeline with empty inner list is a silent no-op.
    """
    result = nef_execute_pipeline(steps=[[]])
    EXPECTED = PipelineResult(
        steps=[[]], stdout="", stderr=[""], exit_code=0, steps_completed=0
    )
    assert result == EXPECTED


def test_nef_execute_pipeline_stderr_is_list(simple_nef_data):
    """\
    Test nef_execute_pipeline stderr is a list with one entry per step.
    """
    result = nef_execute_pipeline(
        steps=[["frames", "list"], ["save", "-"]], nef_input=simple_nef_data
    )
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        steps=[["frames", "list"], ["save", "-"]],
        steps_completed=result.steps_completed,
    )
    assert result == EXPECTED
    assert len(result.stderr) == 2


def test_nef_execute_pipeline_help():
    """\
    Test nef_execute_pipeline with --help returns complete help structure.
    """
    result = nef_execute_pipeline(steps=[["--help"]])
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["--help"]],
        steps_completed=1,
    )
    assert result == EXPECTED
    for section in EXPECTED_HELP_SECTIONS:
        assert section in result.stdout, f"Missing section: {section}"
    assert len(result.stdout) > 200


def test_nef_execute_pipeline_returns_dataclass_structure():
    """\
    Test that nef_execute_pipeline returns a PipelineResult dataclass.
    """
    result = nef_execute_pipeline(steps=[["version"]])
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["version"]],
        steps_completed=1,
    )
    assert result == EXPECTED


def test_nef_list_commands_returns_dataclass_structure():
    """\
    Test that nef_list_commands returns a CommandTableResult dataclass.
    """
    result = nef_list_commands()
    EXPECTED = CommandTableResult(
        commands_table=result.commands_table, exit_code=0, stderr=""
    )
    assert result == EXPECTED


def test_nef_get_command_help_returns_dataclass_structure():
    """\
    Test that nef_get_command_help returns a CommandHelpResult dataclass.
    """
    result = nef_get_command_help()
    EXPECTED = CommandHelpResult(help_text=result.help_text, exit_code=0, stderr="")
    assert result == EXPECTED


# --- nef_upload_file / nef_download_file / nef_list_files --------------------


def test_nef_upload_file(tmp_path, monkeypatch):
    """\
    Test nef_upload_file writes file content to the working directory.
    """
    monkeypatch.chdir(tmp_path)
    result = nef_upload_file("peaks.nef", "data_test\n")
    EXPECTED = UploadResult(
        name="peaks.nef", bytes_written=len("data_test\n".encode("utf-8"))
    )
    assert result == EXPECTED
    assert (tmp_path / "peaks.nef").read_text() == "data_test\n"


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("/etc/passwd", id="absolute"),
        pytest.param("../../etc/passwd", id="traversal"),
    ],
)
def test_nef_upload_file_path_rejected(tmp_path, monkeypatch, path):
    """\
    Test nef_upload_file rejects absolute paths and path traversal attempts.
    """
    monkeypatch.chdir(tmp_path)
    result = nef_upload_file(path, "x")
    EXPECTED = UploadResult(name=path, error=result.error)
    assert result == EXPECTED
    assert bool(result.error)


def test_nef_upload_file_unicode_content(tmp_path, monkeypatch):
    """\
    Test nef_upload_file handles unicode content correctly.
    """
    monkeypatch.chdir(tmp_path)
    content = "naïve shifts: δ = 7.3 ppm\n"
    result = nef_upload_file("shifts.txt", content)
    EXPECTED = UploadResult(
        name="shifts.txt", bytes_written=len(content.encode("utf-8"))
    )
    assert result == EXPECTED
    assert (tmp_path / "shifts.txt").read_text(encoding="utf-8") == content


def test_nef_download_file(tmp_path, monkeypatch):
    """\
    Test nef_download_file reads file content from the working directory.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "result.nef").write_text("data_result\n")
    result = nef_download_file("result.nef")
    EXPECTED = DownloadResult(name="result.nef", content="data_result\n")
    assert result == EXPECTED


def test_nef_download_file_not_found(tmp_path, monkeypatch):
    """\
    Test nef_download_file returns available files when file is missing.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "other.nef").write_text("x")
    result = nef_download_file("missing.nef")
    EXPECTED = DownloadResult(
        name="missing.nef", error=result.error, available_files=result.available_files
    )
    assert result == EXPECTED
    assert bool(result.error)
    assert "other.nef" in result.available_files


def test_nef_download_file_absolute_path_rejected(tmp_path, monkeypatch):
    """\
    Test nef_download_file rejects absolute paths.
    """
    monkeypatch.chdir(tmp_path)
    result = nef_download_file("/etc/passwd")
    EXPECTED = DownloadResult(name="/etc/passwd", error=result.error)
    assert result == EXPECTED
    assert bool(result.error)


def test_nef_list_files_empty(tmp_path, monkeypatch):
    """\
    Test nef_list_files returns empty list for empty directory.
    """
    monkeypatch.chdir(tmp_path)
    result = nef_list_files()
    EXPECTED = ListFilesResult(files=[], cwd=result.cwd)
    assert result == EXPECTED
    assert bool(result.cwd)


def test_nef_list_files_after_upload(tmp_path, monkeypatch):
    """\
    Test nef_list_files lists files written by nef_upload_file.
    """
    monkeypatch.chdir(tmp_path)
    nef_upload_file("a.nef", "x")
    nef_upload_file("b.nef", "y")
    result = nef_list_files()
    EXPECTED = ListFilesResult(files=["a.nef", "b.nef"], cwd=result.cwd)
    assert result == EXPECTED


def test_nef_upload_download_roundtrip(tmp_path, monkeypatch):
    """\
    Test upload followed by download returns identical content.
    """
    monkeypatch.chdir(tmp_path)
    content = "data_ubiquitin\n_nef_sequence.chain_code A\n"
    nef_upload_file("ubiquitin.nef", content)
    result = nef_download_file("ubiquitin.nef")
    EXPECTED = DownloadResult(name="ubiquitin.nef", content=content)
    assert result == EXPECTED


# --- nef_change_sandbox / _get_sandbox_path ----------------------------------


def test_change_sandbox(tmp_path, monkeypatch):
    """\
    Test changing sandbox to a new directory via native picker.
    """
    dir1 = tmp_path / "sandbox1"
    dir2 = tmp_path / "sandbox2"
    dir1.mkdir()
    dir2.mkdir()
    (dir2 / "test.txt").write_text("hello")

    monkeypatch.chdir(dir1)
    old_cwd = dir1.resolve()

    def mock_picker(initial_dir):
        assert initial_dir == str(old_cwd)
        return str(dir2)

    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_commands._get_native_directory", mock_picker
    )

    result = nef_change_sandbox()

    EXPECTED = ChangeSandboxResult(new_path=str(dir2.resolve()))
    assert result == EXPECTED
    assert Path.cwd() == dir2.resolve()


def test_change_sandbox_user_cancelled(tmp_path, monkeypatch):
    """\
    Test that user cancelling directory picker is handled gracefully.
    """
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_commands._get_native_directory",
        lambda initial_dir: None,
    )

    result = nef_change_sandbox()

    EXPECTED = ChangeSandboxResult(error=EXPECTED_ERROR_CANCELLED)
    assert result == EXPECTED
    assert Path.cwd() == tmp_path.resolve()


def test_change_sandbox_picker_error(tmp_path, monkeypatch):
    """\
    Test that errors reported by the native picker are surfaced.
    """
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_commands._get_native_directory",
        lambda initial_dir: {"error": EXPECTED_ERROR_UNSUPPORTED_OS},
    )

    result = nef_change_sandbox()

    EXPECTED = ChangeSandboxResult(error=EXPECTED_ERROR_UNSUPPORTED_OS)
    assert result == EXPECTED
    assert Path.cwd() == tmp_path.resolve()


def test_change_sandbox_nonexistent_directory(tmp_path, monkeypatch):
    """\
    Test changing sandbox to a non-existent directory fails.
    """
    monkeypatch.chdir(tmp_path)
    nonexistent = tmp_path / "does_not_exist"

    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_commands._get_native_directory",
        lambda initial_dir: str(nonexistent),
    )

    result = nef_change_sandbox()

    EXPECTED = ChangeSandboxResult(
        error=EXPECTED_ERROR_PATH_DOES_NOT_EXIST.format(path=nonexistent.resolve()),
    )
    assert result == EXPECTED
    assert Path.cwd() == tmp_path.resolve()


def test_change_sandbox_file_not_directory(tmp_path, monkeypatch):
    """\
    Test changing sandbox to a file (not directory) fails.
    """
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "test.txt"
    test_file.write_text("not a directory")

    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_commands._get_native_directory",
        lambda initial_dir: str(test_file),
    )

    result = nef_change_sandbox()

    EXPECTED = ChangeSandboxResult(
        error=EXPECTED_ERROR_PATH_NOT_DIRECTORY.format(path=test_file.resolve()),
    )
    assert result == EXPECTED
    assert Path.cwd() == tmp_path.resolve()


def test_sandbox_env_var_priority(tmp_path, monkeypatch):
    """\
    Test that --path overrides the environment variable, and env var overrides temp.
    """
    env_dir = tmp_path / "env_sandbox"
    cli_dir = tmp_path / "cli_sandbox"
    env_dir.mkdir()
    cli_dir.mkdir()

    monkeypatch.setenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, str(env_dir))

    assert _get_sandbox_path(str(cli_dir)) == SandboxPathResult(path=cli_dir)
    assert _get_sandbox_path(None) == SandboxPathResult(path=env_dir)


def test_sandbox_temp_fallback(monkeypatch):
    """\
    Test that a temp directory is signalled when no path is specified.
    """
    monkeypatch.delenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, raising=False)

    assert _get_sandbox_path(None) == SandboxPathResult(is_temp=True)


def test_sandbox_invalid_path_fallback_to_env(tmp_path, monkeypatch):
    """\
    Test that an invalid --path falls back to the environment variable with a warning.
    """
    env_dir = tmp_path / "env_sandbox"
    env_dir.mkdir()
    invalid_path = tmp_path / "does_not_exist"

    monkeypatch.setenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, str(env_dir))

    EXPECTED_WARNING = EXPECTED_PATH_ARG_NOT_EXIST.format(
        path=invalid_path.resolve()
    ) + EXPECTED_FALLBACK_TO_ENV_VAR.format(
        env_var=NEF_MCP_SANDBOX_ENV_VAR_NAME, path=env_dir.resolve()
    )
    assert _get_sandbox_path(str(invalid_path)) == SandboxPathResult(
        path=env_dir, warning=EXPECTED_WARNING
    )


def test_sandbox_invalid_path_fallback_to_temp(tmp_path, monkeypatch):
    """\
    Test that an invalid --path signals temp needed with a warning.
    """
    monkeypatch.delenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, raising=False)
    invalid_path = tmp_path / "does_not_exist"

    EXPECTED_WARNING = EXPECTED_PATH_ARG_NOT_EXIST.format(path=invalid_path.resolve())
    assert _get_sandbox_path(str(invalid_path)) == SandboxPathResult(
        warning=EXPECTED_WARNING, is_temp=True
    )


def test_sandbox_file_not_directory_fallback(tmp_path, monkeypatch):
    """\
    Test that --path pointing to a file signals temp needed with a warning.
    """
    monkeypatch.delenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, raising=False)
    test_file = tmp_path / "test.txt"
    test_file.write_text("not a directory")

    EXPECTED_WARNING = EXPECTED_PATH_ARG_NOT_DIRECTORY.format(path=test_file.resolve())
    assert _get_sandbox_path(str(test_file)) == SandboxPathResult(
        warning=EXPECTED_WARNING, is_temp=True
    )
