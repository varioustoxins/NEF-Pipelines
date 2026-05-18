"""Tests for the nef ai sandbox CLI command."""

import sys

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "AI sandbox features require Python 3.10 or later", allow_module_level=True
    )

from typer.testing import CliRunner

from nef_pipelines.lib import preferences_storage_lib
from nef_pipelines.tools.ai import ai_app

# Expected output fragments
EXPECTED_SET_TO = "set to"
EXPECTED_CLEARED = "cleared"
EXPECTED_PATH = "Path:"
EXPECTED_CONFIG_FILE = "Config File:"
EXPECTED_FIELD = "Field:"
EXPECTED_FIELD_NAME = "mcp_sandbox_path"
EXPECTED_WARNING = "WARNING"
EXPECTED_DOES_NOT_EXIST = "does not exist"
EXPECTED_REQUIRED_ERROR = "required"
EXPECTED_MISSING_ARGUMENT_ERROR = "missing argument"


@pytest.fixture
def temp_config_dir(monkeypatch, tmp_path):
    """Fixture to use a temporary directory for config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(preferences_storage_lib, "_get_config_path", lambda: config_dir)
    return config_dir


@pytest.fixture
def runner():
    """Fixture providing CLI test runner."""
    return CliRunner()


def test_sandbox_cli_set(temp_config_dir, tmp_path, runner):
    """Test setting sandbox via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    result = runner.invoke(ai_app, ["sandbox", "set", str(sandbox)])

    assert result.exit_code == 0
    assert EXPECTED_SET_TO in result.output.lower()
    assert str(sandbox) in result.output


def test_sandbox_cli_show(temp_config_dir, tmp_path, runner):
    """Test showing sandbox info via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Set first
    runner.invoke(ai_app, ["sandbox", "set", str(sandbox)])

    # Show
    result = runner.invoke(ai_app, ["sandbox", "show"])

    assert result.exit_code == 0
    assert EXPECTED_PATH in result.output
    assert str(sandbox) in result.output
    assert EXPECTED_CONFIG_FILE in result.output
    assert EXPECTED_FIELD_NAME in result.output


def test_sandbox_cli_set_nonexistent_path_allowed(temp_config_dir, tmp_path, runner):
    """Test setting a nonexistent path is allowed."""
    nonexistent = tmp_path / "does_not_exist"

    result = runner.invoke(ai_app, ["sandbox", "set", str(nonexistent)])

    assert result.exit_code == 0
    assert EXPECTED_SET_TO in result.output.lower()
    assert str(nonexistent) in result.output


def test_sandbox_cli_set_no_path(temp_config_dir, runner):
    """Test set without path fails."""
    result = runner.invoke(ai_app, ["sandbox", "set"])

    assert result.exit_code != 0
    output_lower = result.output.lower()
    assert (
        EXPECTED_REQUIRED_ERROR in output_lower
        or EXPECTED_MISSING_ARGUMENT_ERROR in output_lower
    )


def test_sandbox_cli_get_when_set(temp_config_dir, tmp_path, runner):
    """Test getting preference via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Set first
    set_result = runner.invoke(ai_app, ["sandbox", "set", str(sandbox)])
    assert set_result.exit_code == 0

    # Get
    result = runner.invoke(ai_app, ["sandbox", "get"])

    assert result.exit_code == 0
    assert result.output.strip() == str(sandbox)


def test_sandbox_cli_get_when_not_set(temp_config_dir, runner):
    """Test getting preference when not set."""
    result = runner.invoke(ai_app, ["sandbox", "get"])

    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_sandbox_cli_clear(temp_config_dir, tmp_path, runner):
    """Test clearing preference via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Set first
    set_result = runner.invoke(ai_app, ["sandbox", "set", str(sandbox)])
    assert set_result.exit_code == 0

    # Clear
    result = runner.invoke(ai_app, ["sandbox", "clear"])

    assert result.exit_code == 0
    assert EXPECTED_CLEARED in result.output.lower()

    # Verify cleared
    get_result = runner.invoke(ai_app, ["sandbox", "get"])
    assert get_result.output.strip() == ""


@pytest.mark.parametrize(
    "validate_flag,should_warn,check_text",
    [
        (True, False, None),  # valid path with --validate
        (True, True, EXPECTED_DOES_NOT_EXIST),  # nonexistent path with --validate
    ],
)
def test_sandbox_cli_validate(
    temp_config_dir, tmp_path, runner, validate_flag, should_warn, check_text
):
    """Test --validate flag with valid and invalid paths."""
    if should_warn:
        sandbox = tmp_path / "does_not_exist"
    else:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()

    args = ["sandbox", "set", str(sandbox)]
    if validate_flag:
        args.append("--validate")

    result = runner.invoke(ai_app, args)

    assert result.exit_code == 0

    if should_warn:
        assert EXPECTED_WARNING in result.output
        if check_text:
            assert check_text in result.output
    else:
        assert EXPECTED_WARNING not in result.output


def test_sandbox_cli_invalid_action(temp_config_dir, runner):
    """Test invalid action fails."""
    result = runner.invoke(ai_app, ["sandbox", "invalid"])

    # Typer returns 2 for validation errors (invalid Enum value)
    assert result.exit_code == 2
