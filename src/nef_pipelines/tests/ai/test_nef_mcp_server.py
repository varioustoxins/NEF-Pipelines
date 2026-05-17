"""
Tests for AI server tool functions in server_lib.py.
"""

import re
import sys
from importlib.resources import files as _pkg_files
from pathlib import Path
from textwrap import dedent

import pytest

import nef_pipelines.tools.ai.mcp_commands as mcp_commands
import nef_pipelines.tools.ai.mcp_lib as mcp_lib
from nef_pipelines.lib.test_lib import assert_lines_match, isolate_frame, read_test_data
from nef_pipelines.tools.ai.mcp_commands import (
    _ERROR_ALREADY_UNLOCKED,
    _ERROR_INVALID_TOKEN,
    _ERROR_READ_ME_FIRST_NOT_CALLED,
    _ORIENTATION_ERROR,
    nef_change_sandbox,
    nef_download_file,
    nef_execute_pipeline,
    nef_get_command_help,
    nef_import_files,
    nef_list_commands,
    nef_list_files,
    nef_read_me_first,
    nef_upload_file,
    nef_warnings_shown,
)
from nef_pipelines.tools.ai.mcp_lib import (
    ChangeSandboxResult,
    CommandHelpResult,
    CommandTableResult,
    DownloadResult,
    ImportFailure,
    ImportFilesResult,
    ListFilesResult,
    NefStartupResult,
    PipelineResult,
    UploadResult,
    WarningsShownResult,
)
from nef_pipelines.tools.ai.sandbox_audit import audit_sandbox_writes
from nef_pipelines.tools.ai.server import (
    NEF_MCP_SANDBOX_ENV_VAR_NAME,
    NEF_MCP_SANDBOX_PATH_OPTION,
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
EXPECTED_PATH_ARG_NOT_EXIST = (
    f"Specified {NEF_MCP_SANDBOX_PATH_OPTION} does not exist: {{path}}"
)
EXPECTED_PATH_ARG_NOT_DIRECTORY = (
    f"Specified {NEF_MCP_SANDBOX_PATH_OPTION} is not a directory: {{path}}"
)
EXPECTED_FALLBACK_TO_ENV_VAR = " — falling back to {env_var}: {path}"

# Exact error templates matching sandbox_audit.py audit hook
EXPECTED_SANDBOX_VIOLATION_PREFIX = (
    "Sandbox violation: attempted write outside sandbox:"
)
EXPECTED_PATH_RESOLVES_OUTSIDE = "'{path}' resolves outside the sandbox"


@pytest.fixture(autouse=True)
def _orientation_ready(monkeypatch):
    """Set _WARNINGS_SHOWN=True for all unit tests by default."""
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", True)


def _setup_sandbox_context(monkeypatch, sandbox_path):
    """Helper to set up startup context for a sandbox path."""
    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox_path),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)


@pytest.fixture(autouse=True)
def _default_sandbox(monkeypatch, tmp_path):
    """Provide a default sandbox for all tests (can be overridden by individual tests)."""
    _setup_sandbox_context(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
    yield tmp_path


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

_FIXED_TOKEN = "fixed-test-token-00000000"

_ORIENTATION_SKIP_HEADER = """\
> **Already oriented this session?** \
Skip reading this text and proceed directly with what you need to do next.

---

"""

_RESOURCE_FOOTER = (
    "\n\n---\n\n"
    "**Resources unavailable via `nef://`?**\n"
    "Use nef_resources_list to list resource names and what they do\n"
    "Use `nef_resources_read(name)` to fetch any resource document\n"
)

_DEFAULT_STARTUP_NOTICE = """\
**⚠️ AI: You MUST show the following to the user as the last thing in your current response. ⚠️**

---

⚠️  **EXPERIMENTAL - USE WITH CAUTION**  ⚠️

The NEF-Pipelines MCP server is EXPERIMENTAL software. It is still under development!

In **sandbox mode** (default) the AI is restricted to a single directory.
With **--no-sandbox** it has direct, unsupervised access to your filesystem and can
**READ, WRITE and OVERWRITE** files anywhere without further confirmation.

**THE AUTHORS ACCEPT NO LIABILITY FOR BUGS, DATA LOSS OR UNINTENDED FILE ACCESS.**"""

_TOKEN_SUFFIX = (
    f"\n\nORIENTATION-TOKEN: {_FIXED_TOKEN}\n"
    f"AI: You MUST show all of the above to the user verbatim before using this token. "
    f'Then call nef_warnings_shown(token="{_FIXED_TOKEN}") to unlock the NEF tools.'
)


def _orientation_content(startup_notice: str) -> str:
    preamble = (_pkg_files("nef_pipelines") / "resources" / "preamble.md").read_text()
    return (
        _ORIENTATION_SKIP_HEADER + preamble + _RESOURCE_FOOTER + "\n\n" + startup_notice
    )


def test_nef_read_me_first(monkeypatch):
    """\
    Test nef_read_me_first returns orientation content with a token in information.
    """
    # Reset to empty startup context for this test
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mcp_lib.StartupContext())
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", False)
    monkeypatch.setattr(mcp_commands, "_ORIENTATION_TOKEN", _FIXED_TOKEN)

    result = nef_read_me_first()

    EXPECTED = NefStartupResult(
        content=_orientation_content(_DEFAULT_STARTUP_NOTICE),
        information=_DEFAULT_STARTUP_NOTICE + _TOKEN_SUFFIX,
    )
    assert result == EXPECTED


def test_nef_read_me_first_with_startup_context(monkeypatch):
    """\
    Test nef_read_me_first includes startup context when _STARTUP_CONTEXT is set.
    """
    SANDBOX_PATH = "/tmp/test_sandbox"
    WARNING_TEXT = "Test warning message"

    mock_context = mcp_lib.StartupContext(
        sandbox_path=SANDBOX_PATH,
        is_temporary=True,
        will_be_cleaned=True,
        warning=WARNING_TEXT,
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", False)
    monkeypatch.setattr(mcp_commands, "_ORIENTATION_TOKEN", _FIXED_TOKEN)

    result = nef_read_me_first()

    SANDBOX_STARTUP_NOTICE = """\
**⚠️ AI: You MUST show the following to the user as the last thing in your current response. ⚠️**

---

⚠️  **EXPERIMENTAL - USE WITH CAUTION**  ⚠️

The NEF-Pipelines MCP server is EXPERIMENTAL software. It is still under development!

The server is in **sandbox mode**. The AI is restricted to a single directory:

**`/tmp/test_sandbox`**

It can **READ, WRITE and OVERWRITE** files within this directory without further confirmation.

**⚠️ THE SANDBOX IS A TEMPORARY DIRECTORY AND WILL BE DELETED AT SERVER / AI SHUTDOWN.**

Ask the AI to change the sandbox to another directory if you want more permanent storage.

**THE AUTHORS ACCEPT NO LIABILITY FOR BUGS, DATA LOSS OR UNINTENDED FILE ACCESS.**

⚠️ **Warning**: Test warning message"""

    EXPECTED = NefStartupResult(
        content=_orientation_content(SANDBOX_STARTUP_NOTICE),
        information=SANDBOX_STARTUP_NOTICE + _TOKEN_SUFFIX,
    )
    assert result == EXPECTED


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
    result = nef_execute_pipeline(
        steps=[["nef", "frames", "list"]], nef_input=simple_nef_data
    )
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["nef", "frames", "list"]],
        steps_completed=1,
    )
    assert result == EXPECTED
    assert len(result.stderr) == 1


def test_nef_execute_pipeline_multiple_steps(simple_nef_data):
    """\
    Test nef_execute_pipeline chains stdout→stdin across steps.
    """
    result = nef_execute_pipeline(
        steps=[["nef", "save", "-"], ["nef", "frames", "list"]],
        nef_input=simple_nef_data,
    )
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["nef", "save", "-"], ["nef", "frames", "list"]],
        steps_completed=2,
    )
    assert result == EXPECTED
    assert_lines_match(EXPECTED_FRAMES_LIST, result.stdout)


def test_nef_execute_pipeline_step_failure():
    """\
    Test nef_execute_pipeline stops on step failure.
    """
    result = nef_execute_pipeline(
        steps=[["nef", "version"], ["nef", "nonexistent", "command"]]
    )
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        steps=[["nef", "version"], ["nef", "nonexistent", "command"]],
        steps_completed=1,
    )
    assert result == EXPECTED
    assert result.exit_code != 0
    assert len(result.stderr) == 2


def test_nef_execute_pipeline_with_nef_data_passthrough(simple_nef_data):
    """\
    Test that pipeline can process NEF data through save command.
    """
    result = nef_execute_pipeline(
        steps=[["nef", "save", "-"]], nef_input=simple_nef_data
    )
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["nef", "save", "-"]],
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
        steps=[["nef", "frames", "list"], ["nef", "save", "-"]],
        nef_input=simple_nef_data,
    )
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        steps=[["nef", "frames", "list"], ["nef", "save", "-"]],
        steps_completed=result.steps_completed,
    )
    assert result == EXPECTED
    assert len(result.stderr) == 2


def test_nef_execute_pipeline_help():
    """\
    Test nef_execute_pipeline with --help returns complete help structure.
    """
    result = nef_execute_pipeline(steps=[["nef", "--help"]])
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["nef", "--help"]],
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
    result = nef_execute_pipeline(steps=[["nef", "version"]])
    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["nef", "version"]],
        steps_completed=1,
    )
    assert result == EXPECTED


def test_nef_execute_pipeline_step_missing_nef_prefix():
    """\
    Test nef_execute_pipeline returns an error if a step does not start with 'nef'.
    """
    result = nef_execute_pipeline(steps=[["frames", "list"]])
    EXPECTED = PipelineResult(
        steps=[["frames", "list"]],
        stdout="",
        stderr=[
            dedent(
                """
                each step must start with 'nef' — got ['frames', 'list'].
                Example: ["nef", "frames", "list"]
            """
            )
        ],
        exit_code=1,
        steps_completed=0,
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
    result = nef_upload_file(path, "x")
    EXPECTED = UploadResult(name=path, error=result.error)
    assert result == EXPECTED
    assert bool(result.error)


def test_nef_upload_file_unicode_content(tmp_path, monkeypatch):
    """\
    Test nef_upload_file handles unicode content correctly.
    """
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
    (tmp_path / "result.nef").write_text("data_result\n")
    result = nef_download_file("result.nef")
    EXPECTED = DownloadResult(name="result.nef", content="data_result\n")
    assert result == EXPECTED


def test_nef_download_file_not_found(tmp_path, monkeypatch):
    """\
    Test nef_download_file returns available files when file is missing.
    """
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
    result = nef_download_file("/etc/passwd")
    EXPECTED = DownloadResult(name="/etc/passwd", error=result.error)
    assert result == EXPECTED
    assert bool(result.error)


def test_nef_list_files_empty(tmp_path, monkeypatch):
    """\
    Test nef_list_files returns empty list for empty directory.
    """
    result = nef_list_files()
    EXPECTED = ListFilesResult(files=[], cwd=result.cwd)
    assert result == EXPECTED
    assert bool(result.cwd)


def test_nef_list_files_after_upload(tmp_path, monkeypatch):
    """\
    Test nef_list_files lists files written by nef_upload_file.
    """
    nef_upload_file("a.nef", "x")
    nef_upload_file("b.nef", "y")
    result = nef_list_files()
    EXPECTED = ListFilesResult(files=["a.nef", "b.nef"], cwd=result.cwd)
    assert result == EXPECTED


def test_nef_upload_download_roundtrip(tmp_path, monkeypatch):
    """\
    Test upload followed by download returns identical content.
    """
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

    assert _get_sandbox_path(str(cli_dir)) == SandboxPathResult(
        path=cli_dir, path_source=f"{NEF_MCP_SANDBOX_PATH_OPTION} option"
    )
    assert _get_sandbox_path(None) == SandboxPathResult(
        path=env_dir, path_source=f"{NEF_MCP_SANDBOX_ENV_VAR_NAME} environment variable"
    )


def test_sandbox_temp_fallback(monkeypatch):
    """\
    Test that a temp directory is signalled when no path is specified.
    """
    # Mock get_sandbox_preference to return None
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.sandbox_lib.get_sandbox_preference", lambda: None
    )
    monkeypatch.delenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, raising=False)

    assert _get_sandbox_path(None) == SandboxPathResult(is_temp=True)


def test_sandbox_invalid_path_fallback_to_env(tmp_path, monkeypatch):
    """\
    Test that an invalid --path is used anyway with a warning (does NOT fall back).
    """
    # Mock get_sandbox_preference to return None so we test CLI arg behavior
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.sandbox_lib.get_sandbox_preference", lambda: None
    )

    env_dir = tmp_path / "env_sandbox"
    env_dir.mkdir()
    invalid_path = tmp_path / "does_not_exist"

    monkeypatch.setenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, str(env_dir))

    # With new behavior: invalid CLI arg is used with warning, no fallback
    EXPECTED_WARNING = EXPECTED_PATH_ARG_NOT_EXIST.format(path=invalid_path.resolve())
    assert _get_sandbox_path(str(invalid_path)) == SandboxPathResult(
        path=invalid_path.resolve(),
        warning=EXPECTED_WARNING,
        path_source=f"{NEF_MCP_SANDBOX_PATH_OPTION} option",
    )


def test_sandbox_invalid_path_fallback_to_temp(tmp_path, monkeypatch):
    """\
    Test that an invalid --path is used anyway with a warning (does NOT fall back to temp).
    """
    # Mock get_sandbox_preference to return None
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.sandbox_lib.get_sandbox_preference", lambda: None
    )
    monkeypatch.delenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, raising=False)
    invalid_path = tmp_path / "does_not_exist"

    # With new behavior: invalid CLI arg is used with warning, no fallback
    EXPECTED_WARNING = EXPECTED_PATH_ARG_NOT_EXIST.format(path=invalid_path.resolve())
    assert _get_sandbox_path(str(invalid_path)) == SandboxPathResult(
        path=invalid_path.resolve(),
        warning=EXPECTED_WARNING,
        path_source=f"{NEF_MCP_SANDBOX_PATH_OPTION} option",
    )


def test_sandbox_file_not_directory_fallback(tmp_path, monkeypatch):
    """\
    Test that --path pointing to a file is used anyway with a warning (does NOT fall back).
    """
    # Mock get_sandbox_preference to return None
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.sandbox_lib.get_sandbox_preference", lambda: None
    )
    monkeypatch.delenv(NEF_MCP_SANDBOX_ENV_VAR_NAME, raising=False)
    test_file = tmp_path / "test.txt"
    test_file.write_text("not a directory")

    # With new behavior: invalid CLI arg (file) is used with warning, no fallback
    EXPECTED_WARNING = EXPECTED_PATH_ARG_NOT_DIRECTORY.format(path=test_file.resolve())
    assert _get_sandbox_path(str(test_file)) == SandboxPathResult(
        path=test_file.resolve(),
        warning=EXPECTED_WARNING,
        path_source=f"{NEF_MCP_SANDBOX_PATH_OPTION} option",
    )


# --- nef_import_files ---------------------------------------------------------

EXPECTED_ERROR_IMPORT_CANCELLED = "User cancelled file selection"
EXPECTED_ERROR_OVERWRITE_DECLINED = "User declined to overwrite existing files"
EXPECTED_IMPORT_VALIDATION_ERROR = "{count} file(s) failed validation"
EXPECTED_IMPORT_FAILURE_DIRECTORY_REASON = (
    "directory — only regular files may be imported"
)
EXPECTED_IMPORT_FAILURE_SYMLINK_REASON = (
    "symbolic link — symbolic links are not allowed"
)


async def test_nef_import_files_success(tmp_path, monkeypatch):
    """\
    Test nef_import_files copies selected files into the sandbox.
    """
    src_dir = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    src_dir.mkdir()
    sandbox.mkdir()
    (src_dir / "a.nef").write_text("data_a")
    (src_dir / "b.nef").write_text("data_b")

    # Set up startup context for the sandbox
    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: [src_dir / "a.nef", src_dir / "b.nef"],
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(imported=["a.nef", "b.nef"])
    assert result == EXPECTED
    assert (sandbox / "a.nef").read_text() == "data_a"
    assert (sandbox / "b.nef").read_text() == "data_b"


async def test_nef_import_files_user_cancels(tmp_path, monkeypatch):
    """\
    Test nef_import_files returns error when user cancels the picker.
    """

    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: None,
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(error=EXPECTED_ERROR_IMPORT_CANCELLED)
    assert result == EXPECTED


async def test_nef_import_files_picker_error(tmp_path, monkeypatch):
    """\
    Test nef_import_files surfaces picker errors in the error field.
    """

    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: {"error": "No file picker available"},
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(error="No file picker available")
    assert result == EXPECTED


async def test_nef_import_files_rejects_directory(tmp_path, monkeypatch):
    """\
    Test nef_import_files reports a directory selection in failures.
    """
    src_dir = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    subdir = src_dir / "mydir"
    src_dir.mkdir()
    sandbox.mkdir()
    subdir.mkdir()

    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: [subdir],
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(
        failures=[
            ImportFailure(name="mydir", reason=EXPECTED_IMPORT_FAILURE_DIRECTORY_REASON)
        ],
        error=EXPECTED_IMPORT_VALIDATION_ERROR.format(count=1),
    )
    assert result == EXPECTED
    assert not (sandbox / "mydir").exists()


async def test_nef_import_files_rejects_symlink(tmp_path, monkeypatch):
    """\
    Test nef_import_files reports symbolic links in failures; nothing is copied.
    """
    src_dir = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    src_dir.mkdir()
    sandbox.mkdir()
    real_file = src_dir / "real.nef"
    real_file.write_text("data")
    link = src_dir / "link.nef"
    link.symlink_to(real_file)

    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: [link],
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(
        failures=[
            ImportFailure(
                name="link.nef", reason=EXPECTED_IMPORT_FAILURE_SYMLINK_REASON
            )
        ],
        error=EXPECTED_IMPORT_VALIDATION_ERROR.format(count=1),
    )
    assert result == EXPECTED
    assert not (sandbox / "link.nef").exists()


async def test_nef_import_files_collects_all_validation_failures(tmp_path, monkeypatch):
    """\
    Test nef_import_files collects failures for all invalid files, not just the first.
    """
    src_dir = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    src_dir.mkdir()
    sandbox.mkdir()
    subdir = src_dir / "adir"
    subdir.mkdir()
    link_target = src_dir / "real.nef"
    link_target.write_text("data")
    link = src_dir / "link.nef"
    link.symlink_to(link_target)

    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: [subdir, link],
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(
        failures=[
            ImportFailure(name="adir", reason=EXPECTED_IMPORT_FAILURE_DIRECTORY_REASON),
            ImportFailure(
                name="link.nef", reason=EXPECTED_IMPORT_FAILURE_SYMLINK_REASON
            ),
        ],
        error=EXPECTED_IMPORT_VALIDATION_ERROR.format(count=2),
    )
    assert result == EXPECTED


async def test_nef_import_files_copy_error_reports_partial_success(
    tmp_path, monkeypatch
):
    """\
    Test nef_import_files keeps already-copied files in imported and puts the
    failing file in failures when an OS copy error occurs mid-operation.
    """
    src_dir = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    src_dir.mkdir()
    sandbox.mkdir()
    (src_dir / "good.nef").write_text("data_good")
    bad_src = src_dir / "bad.nef"
    bad_src.write_text("data_bad")

    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    import shutil as _shutil

    real_copy2 = _shutil.copy2

    def mock_copy(src, dst):
        if src == bad_src:
            raise OSError("disk full")
        real_copy2(src, dst)

    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: [src_dir / "good.nef", bad_src],
    )
    monkeypatch.setattr("nef_pipelines.tools.ai.mcp_lib.shutil.copy2", mock_copy)

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(
        imported=["good.nef"],
        failures=[ImportFailure(name="bad.nef", reason="disk full")],
        error="copy failed — 'bad.nef' could not be written",
    )
    assert result == EXPECTED
    assert (sandbox / "good.nef").read_text() == "data_good"
    assert not (sandbox / "bad.nef").exists()


async def test_nef_import_files_overwrite_confirmed(tmp_path, monkeypatch):
    """\
    Test nef_import_files overwrites an existing sandbox file when confirmed.
    """
    src_dir = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    src_dir.mkdir()
    sandbox.mkdir()
    (src_dir / "data.nef").write_text("new content")
    (sandbox / "data.nef").write_text("old content")

    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: [src_dir / "data.nef"],
    )
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.ask_overwrite_confirmation",
        lambda filenames: True,
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(imported=["data.nef"])
    assert result == EXPECTED
    assert (sandbox / "data.nef").read_text() == "new content"


async def test_nef_import_files_overwrite_declined(tmp_path, monkeypatch):
    """\
    Test nef_import_files aborts and copies nothing when user declines overwrite.
    """
    src_dir = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    src_dir.mkdir()
    sandbox.mkdir()
    (src_dir / "data.nef").write_text("new content")
    (sandbox / "data.nef").write_text("old content")

    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: [src_dir / "data.nef"],
    )
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.ask_overwrite_confirmation",
        lambda filenames: False,
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(error=EXPECTED_ERROR_OVERWRITE_DECLINED)
    assert result == EXPECTED
    assert (sandbox / "data.nef").read_text() == "old content"


async def test_nef_import_files_overwrite_lists_conflicts(tmp_path, monkeypatch):
    """\
    Test nef_import_files passes all conflicting filenames to ask_overwrite_confirmation.
    """
    src_dir = tmp_path / "source"
    sandbox = tmp_path / "sandbox"
    src_dir.mkdir()
    sandbox.mkdir()

    for name in ("x.nef", "y.nef", "z.nef"):
        (src_dir / name).write_text("new")
        (sandbox / name).write_text("old")

    mock_context = mcp_lib.StartupContext(
        sandbox_path=str(sandbox),
        is_temporary=True,
        will_be_cleaned=False,
        path_source="test fixture",
    )
    monkeypatch.setattr(mcp_lib, "_STARTUP_CONTEXT", mock_context)

    captured = []

    def mock_confirm(filenames):
        captured.extend(filenames)
        return True

    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.select_multiple_files",
        lambda: [src_dir / "x.nef", src_dir / "y.nef", src_dir / "z.nef"],
    )
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_lib.ask_overwrite_confirmation",
        mock_confirm,
    )

    result = await nef_import_files()

    EXPECTED = ImportFilesResult(imported=["x.nef", "y.nef", "z.nef"])
    assert result == EXPECTED
    assert set(captured) == {"x.nef", "y.nef", "z.nef"}


# --- orientation guard ---


def test_orientation_guard_blocks_tool_before_warnings_shown(tmp_path, monkeypatch):
    """\
    Test that tools return an error if nef_warnings_shown has not been called.
    """
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", False)

    result = nef_list_files()
    EXPECTED = ListFilesResult(error=_ORIENTATION_ERROR)
    assert result == EXPECTED


def test_orientation_guard_unblocked_after_warnings_shown(tmp_path, monkeypatch):
    """\
    Test that calling nef_read_me_first then nef_warnings_shown unblocks subsequent tools.
    """
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", False)
    monkeypatch.setattr(mcp_commands, "_ORIENTATION_TOKEN", "")

    startup = nef_read_me_first()
    token = re.search(r"ORIENTATION-TOKEN: (\S+)", startup.information).group(1)
    nef_warnings_shown(token=token)

    result = nef_list_files()
    EXPECTED = ListFilesResult(files=[], cwd=result.cwd)
    assert result == EXPECTED


# --- nef_warnings_shown ---


def test_warnings_shown_rejects_wrong_token(monkeypatch):
    """\
    Test that nef_warnings_shown rejects a wrong token.
    """
    monkeypatch.setattr(mcp_commands, "_ORIENTATION_TOKEN", "correct-token")
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", False)

    result = nef_warnings_shown(token="wrong-token")
    EXPECTED = WarningsShownResult(error=_ERROR_INVALID_TOKEN)
    assert result == EXPECTED
    assert not mcp_commands._WARNINGS_SHOWN


def test_warnings_shown_rejects_when_read_me_first_not_called(monkeypatch):
    """\
    Test that nef_warnings_shown errors if nef_read_me_first was never called.
    """
    monkeypatch.setattr(mcp_commands, "_ORIENTATION_TOKEN", "")
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", False)

    result = nef_warnings_shown(token="any-token")
    EXPECTED = WarningsShownResult(error=_ERROR_READ_ME_FIRST_NOT_CALLED)
    assert result == EXPECTED
    assert not mcp_commands._WARNINGS_SHOWN


def test_warnings_shown_rejects_wrong_token_when_already_unlocked(monkeypatch):
    """\
    Test that nef_warnings_shown returns a clear message if tools are already unlocked.
    """
    monkeypatch.setattr(mcp_commands, "_ORIENTATION_TOKEN", "correct-token")
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", True)

    result = nef_warnings_shown(token="wrong-token")
    EXPECTED = WarningsShownResult(error=_ERROR_ALREADY_UNLOCKED)
    assert result == EXPECTED


def test_warnings_shown_accepts_correct_token(monkeypatch):
    """\
    Test that nef_warnings_shown succeeds with the correct token.
    """
    monkeypatch.setattr(mcp_commands, "_ORIENTATION_TOKEN", "correct-token")
    monkeypatch.setattr(mcp_commands, "_WARNINGS_SHOWN", False)

    result = nef_warnings_shown(token="correct-token")
    EXPECTED = WarningsShownResult(success=True)
    assert result == EXPECTED
    assert mcp_commands._WARNINGS_SHOWN


def test_audit_sandbox_writes_raises_on_nesting(tmp_path):
    """
    Test that audit_sandbox_writes raises RuntimeError if nested.
    """

    EXPECTED_ERROR = "audit_sandbox_writes does not support nesting - a sandbox context is already active"

    with pytest.raises(RuntimeError, match=EXPECTED_ERROR):
        with audit_sandbox_writes(tmp_path):
            with audit_sandbox_writes(tmp_path):
                pass


def test_execute_command_invalid_namespace():
    """
    Test that the low-level runner rejects commands outside the 'nef' namespace.
    """
    from nef_pipelines.tools.ai.mcp_lib import _execute_command_in_process

    # We test the internal function directly to verify the safety net
    result = _execute_command_in_process(["not-nef", "version"])
    assert result.error == "only nef and it sub commands are currently supported"


def test_nef_upload_file_respects_sandbox_audit(tmp_path, monkeypatch):
    """
    Test that nef_upload_file is protected by audit hook during pipeline execution.
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    monkeypatch.setattr(
        mcp_lib, "_STARTUP_CONTEXT", mcp_lib.StartupContext(sandbox_path=str(sandbox))
    )
    monkeypatch.chdir(sandbox)

    # Upload inside sandbox - should work
    result = nef_upload_file("allowed.txt", "content")
    EXPECTED_SUCCESS = UploadResult(
        name="allowed.txt", bytes_written=len("content".encode("utf-8"))
    )
    assert result == EXPECTED_SUCCESS
    assert (sandbox / "allowed.txt").exists()
    assert (sandbox / "allowed.txt").read_text() == "content"

    # Path validation already prevents this, but audit hook is backup layer
    # Upload with relative path escape attempt - should be caught by path validation
    result = nef_upload_file("../outside.txt", "content")
    EXPECTED_FAILURE = UploadResult(
        name="../outside.txt",
        bytes_written=0,
        error=EXPECTED_PATH_RESOLVES_OUTSIDE.format(path="../outside.txt"),
    )
    assert result == EXPECTED_FAILURE


def test_real_nef_save_command_respects_sandbox(tmp_path, monkeypatch, simple_nef_data):
    """
    End-to-end test: real NEF save command writes file inside sandbox.
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    monkeypatch.setattr(
        mcp_lib, "_STARTUP_CONTEXT", mcp_lib.StartupContext(sandbox_path=str(sandbox))
    )
    monkeypatch.chdir(sandbox)

    result = nef_execute_pipeline(
        steps=[["nef", "save", "output.nef"]], nef_input=simple_nef_data
    )

    EXPECTED = PipelineResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=0,
        steps=[["nef", "save", "output.nef"]],
        steps_completed=1,
    )
    assert result == EXPECTED

    # Side effects: file written inside sandbox with complete content matching pipeline output
    assert (sandbox / "output.nef").exists()
    assert_lines_match(result.stdout, (sandbox / "output.nef").read_text())


def test_real_nef_command_blocked_from_writing_outside_sandbox(
    tmp_path, monkeypatch, simple_nef_data
):
    """
    End-to-end test: NEF command cannot write files outside sandbox (absolute path).
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    monkeypatch.setattr(
        mcp_lib, "_STARTUP_CONTEXT", mcp_lib.StartupContext(sandbox_path=str(sandbox))
    )
    monkeypatch.chdir(sandbox)

    # Try to save to absolute path outside sandbox
    outside_file = outside / "evil.nef"
    result = nef_execute_pipeline(
        steps=[["nef", "save", str(outside_file)]], nef_input=simple_nef_data
    )

    # stdout remains as nef_input on failure; exit_code is always 1 on SandboxViolation
    EXPECTED = PipelineResult(
        stdout=simple_nef_data,
        stderr=result.stderr,
        exit_code=1,
        steps=[["nef", "save", str(outside_file)]],
        steps_completed=0,
    )
    assert result == EXPECTED
    assert EXPECTED_SANDBOX_VIOLATION_PREFIX in result.stderr[0]

    # Side effect: file was NOT created
    assert not outside_file.exists()


def test_real_nef_command_blocked_from_path_traversal(
    tmp_path, monkeypatch, simple_nef_data
):
    """
    End-to-end test: NEF command cannot write files outside sandbox (relative path traversal).
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    monkeypatch.setattr(
        mcp_lib, "_STARTUP_CONTEXT", mcp_lib.StartupContext(sandbox_path=str(sandbox))
    )
    monkeypatch.chdir(sandbox)

    # Try to save using relative path traversal
    result = nef_execute_pipeline(
        steps=[["nef", "save", "../evil.nef"]], nef_input=simple_nef_data
    )

    # stdout remains as nef_input on failure; exit_code is always 1 on SandboxViolation
    EXPECTED = PipelineResult(
        stdout=simple_nef_data,
        stderr=result.stderr,
        exit_code=1,
        steps=[["nef", "save", "../evil.nef"]],
        steps_completed=0,
    )
    assert result == EXPECTED
    assert EXPECTED_SANDBOX_VIOLATION_PREFIX in result.stderr[0]

    # Side effect: file was NOT created
    assert not (tmp_path / "evil.nef").exists()


def test_real_nef_pipeline_multi_step_with_file_writes(
    tmp_path, monkeypatch, simple_nef_data
):
    """
    End-to-end test: multi-step pipeline with file writes stays in sandbox.
    """
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    monkeypatch.setattr(
        mcp_lib, "_STARTUP_CONTEXT", mcp_lib.StartupContext(sandbox_path=str(sandbox))
    )
    monkeypatch.chdir(sandbox)

    # Execute two separate save commands to verify multiple file writes work
    result1 = nef_execute_pipeline(
        steps=[["nef", "save", "step1.nef"]], nef_input=simple_nef_data
    )
    result2 = nef_execute_pipeline(
        steps=[["nef", "save", "step2.nef"]], nef_input=simple_nef_data
    )

    # Test complete structures with dynamic stdout/stderr captured
    EXPECTED1 = PipelineResult(
        stdout=result1.stdout,
        stderr=result1.stderr,
        exit_code=0,
        steps=[["nef", "save", "step1.nef"]],
        steps_completed=1,
    )
    EXPECTED2 = PipelineResult(
        stdout=result2.stdout,
        stderr=result2.stderr,
        exit_code=0,
        steps=[["nef", "save", "step2.nef"]],
        steps_completed=1,
    )
    assert result1 == EXPECTED1
    assert result2 == EXPECTED2

    # Side effects: files written inside sandbox with complete content matching pipeline output
    assert (sandbox / "step1.nef").exists()
    assert (sandbox / "step2.nef").exists()
    assert_lines_match(result1.stdout, (sandbox / "step1.nef").read_text())
    assert_lines_match(result2.stdout, (sandbox / "step2.nef").read_text())

    # No files written outside sandbox
    assert list(tmp_path.glob("*.nef")) == []
