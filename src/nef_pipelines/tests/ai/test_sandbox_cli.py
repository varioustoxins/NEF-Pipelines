"""Tests for the nef ai sandbox CLI command."""

import sys
from textwrap import dedent

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "AI sandbox features require Python 3.10 or later", allow_module_level=True
    )

from nef_pipelines.lib import preferences_storage_lib
from nef_pipelines.lib.test_lib import run_and_report
from nef_pipelines.tools.ai import ai_app

EXPECTED_REQUIRED_ERROR = "required"
EXPECTED_MISSING_ARGUMENT_ERROR = "missing argument"


@pytest.fixture
def temp_config_dir(monkeypatch, tmp_path):
    """Fixture to use a temporary directory for config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(preferences_storage_lib, "_get_config_path", lambda: config_dir)
    return config_dir


def test_sandbox_cli_set(temp_config_dir, tmp_path):
    """Test setting sandbox via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    result = run_and_report(
        ai_app, ["sandbox", "set", str(sandbox)], merge_stderr=False
    )

    assert result.stdout == f"Sandbox preference set to: {sandbox}\n"
    assert (
        result.stderr
        == "WARNING: this will not take effect until you restart your AI / MCP server\n"
    )


def test_sandbox_cli_show(temp_config_dir, tmp_path):
    """Test showing sandbox info via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    run_and_report(ai_app, ["sandbox", "set", str(sandbox)], merge_stderr=False)
    result = run_and_report(ai_app, ["sandbox", "show"], merge_stderr=False)

    config_file = temp_config_dir / "config.toml"
    EXPECTED = f"""\
        Path: {sandbox}
        Config File: {config_file}
        Field: mcp_sandbox_path
    """
    EXPECTED = dedent(EXPECTED)
    assert result.stdout == EXPECTED
    assert result.stderr == ""


def test_sandbox_cli_set_nonexistent_path_allowed(temp_config_dir, tmp_path):
    """Test setting a nonexistent path is allowed."""
    nonexistent = tmp_path / "does_not_exist"

    result = run_and_report(
        ai_app, ["sandbox", "set", str(nonexistent)], merge_stderr=False
    )

    assert result.stdout == f"Sandbox preference set to: {nonexistent}\n"
    assert (
        result.stderr
        == "WARNING: this will not take effect until you restart your AI / MCP server\n"
    )


def test_sandbox_cli_set_no_path(temp_config_dir):
    """Test set without path fails."""
    result = run_and_report(
        ai_app, ["sandbox", "set"], expected_exit_code=1, merge_stderr=False
    )

    stderr_lower = result.stderr.lower()
    assert (
        EXPECTED_REQUIRED_ERROR in stderr_lower
        or EXPECTED_MISSING_ARGUMENT_ERROR in stderr_lower
    )


def test_sandbox_cli_get_when_set(temp_config_dir, tmp_path):
    """Test getting preference via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    run_and_report(ai_app, ["sandbox", "set", str(sandbox)], merge_stderr=False)
    result = run_and_report(ai_app, ["sandbox", "get"], merge_stderr=False)

    assert result.stdout == f"{sandbox}\n"
    assert result.stderr == ""


def test_sandbox_cli_get_when_not_set(temp_config_dir):
    """Test getting preference when not set."""
    result = run_and_report(ai_app, ["sandbox", "get"], merge_stderr=False)

    assert result.stdout == ""
    assert result.stderr == ""


def test_sandbox_cli_clear(temp_config_dir, tmp_path):
    """Test clearing preference via CLI."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    run_and_report(ai_app, ["sandbox", "set", str(sandbox)], merge_stderr=False)
    result = run_and_report(ai_app, ["sandbox", "clear"], merge_stderr=False)

    assert result.stdout == "Sandbox preference cleared\n"
    assert (
        result.stderr
        == "WARNING: this will not take effect until you restart your AI / MCP server\n"
    )

    get_result = run_and_report(ai_app, ["sandbox", "get"], merge_stderr=False)
    assert get_result.stdout == ""
    assert get_result.stderr == ""


@pytest.mark.parametrize(
    "validate_flag,path_exists",
    [
        (True, True),  # existing path with --validate: no validation warning
        (True, False),  # nonexistent path with --validate: validation warning shown
        (False, False),  # nonexistent path without --validate: no validation warning
    ],
)
def test_sandbox_cli_validate(temp_config_dir, tmp_path, validate_flag, path_exists):
    """Test --validate validates path only when passed, and warns if nonexistent."""
    if path_exists:
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
    else:
        sandbox = tmp_path / "does_not_exist"

    args = ["sandbox", "set", str(sandbox)]
    if validate_flag:
        args.append("--validate")

    result = run_and_report(ai_app, args, merge_stderr=False)

    assert result.stdout == f"Sandbox preference set to: {sandbox}\n"

    if validate_flag and not path_exists:
        EXPECTED = f"""\
            WARNING: this will not take effect until you restart your AI / MCP server
            WARNING: Sandbox validation failed: does not exist: {sandbox}
        """
        EXPECTED = dedent(EXPECTED)
        assert result.stderr == EXPECTED
    else:
        assert (
            result.stderr
            == "WARNING: this will not take effect until you restart your AI / MCP server\n"
        )


def test_sandbox_cli_invalid_action(temp_config_dir):
    """Test invalid action fails."""
    run_and_report(ai_app, ["sandbox", "invalid"], expected_exit_code=2)
