"""
Tests for nmrstar project import functionality, focusing on error handling for failed reads
"""

import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import typer

from nef_pipelines.lib.test_lib import NOQA_E501, assert_lines_match, run_and_report
from nef_pipelines.transcoders.nmrstar.importers.project_cli import project


def extract_error_lines(output):
    """Extract ERROR lines and continuation lines until exiting, ignoring tracebacks and debug hints"""
    lines = output.split("\n")
    error_lines = []
    capturing = False
    for line in lines:
        if line.strip().startswith("ERROR [in:"):
            capturing = True
            error_lines.append(line.strip())
        elif capturing:
            if line.strip() == "exiting...":
                error_lines.append(line.strip())
                capturing = False
            elif line.strip() and not line.strip().startswith(
                ("Traceback", "... for full debug")
            ):
                # Continuation line of the error message (skip tracebacks and debug hints)
                error_lines.append(line.strip())
    return "\n".join(error_lines)


EXPECTED_BMRB_CODE_ERROR = """\
ERROR [in: project]:
the file name bmr9999 looks like a bmrb code but I couldn't read it
from the bmrb website, is it correct, is you network up, is the bmrb up?
exiting...
"""

EXPECTED_PERMISSION_ERROR_PATTERN = """\
ERROR [in: project]: couldn't read from {file_path} because you don't have read permission.
Try: chmod +r {file_path}
exiting...
"""

EXPECTED_OWNER_NO_READ_ERROR_PATTERN = """\
ERROR [in: project]: couldn't read from {file_path} because the owner doesn't have read permission.
Try: chmod u+r {file_path}
exiting...
"""

EXPECTED_PERMISSION_RESTRICTION_ERROR_PATTERN = """\
ERROR [in: project]: couldn't read from {file_path} due to permission restrictions.
Check file ownership and permissions.
exiting...
"""

EXPECTED_GENERIC_PERMISSION_ERROR_PATTERN = """\
ERROR [in: project]: couldn't read from {file_path} due to permission error. Check file permissions and ownership.
exiting...
"""

EXPECTED_DIRECTORY_ERROR_PATTERN = """\
ERROR [in: project]: couldn't read from {file_path}, it exists but isn't a file
exiting...
"""

EXPECTED_PARSING_ERROR_PATTERN = """\
ERROR [in: project]: couldn't read from {file_path} even though it exists, do you have permission to read it?
exiting...
"""

EXPECTED_UBIQUITIN_BMRB_ERROR = """\
ERROR [in: project]:
the file name bmr5387 looks like a bmrb code but I couldn't read it
from the bmrb website, is it correct, is you network up, is the bmrb up?
exiting...
"""

EXPECTED_NUMERIC_BMRB_ERROR = """\
ERROR [in: project]:
the file name 5387 looks like a bmrb code but I couldn't read it
from the bmrb website, is it correct, is you network up, is the bmrb up?
exiting...
"""

EXPECTED_NONEXISTENT_FILE_ERROR = (
    "doesn't look like an entry on the bmrb website and doesn't exist on disk"
)

EXPECTED_DIRECT_READ_ERROR_PATTERN = """\
ERROR [in: unknown]: couldn't read an entry from the file {file_path} because [Errno 13] Permission denied: '{file_path}' # noqa: E501
exiting...
""".replace(
    NOQA_E501, ""
)


def test_failed_bmrb_web_fetch_fallback_to_nonexistent_file():
    """Test that when BMRB web fetch fails, the error message is informative for bmrb codes"""
    app = typer.Typer()
    app.command()(project)

    nef_argv = ["nef", "nmrstar", "import", "project", "bmr9999", "--source", "auto"]

    with patch("sys.argv", nef_argv):
        # Mock the web fetch to fail
        with patch(
            "nef_pipelines.transcoders.nmrstar.importers.project._get_bmrb_entry_from_web_or_none"
        ) as mock_web:
            mock_web.return_value = None

            # This should try to fetch from web, fail, then try file "bmr9999" which doesn't exist
            result = run_and_report(
                app, ["bmr9999", "--source", "auto"], expected_exit_code=1
            )

            assert result.exit_code != 0
            assert_lines_match(EXPECTED_BMRB_CODE_ERROR, result.stdout)


def test_failed_file_read_permission_error_no_read():
    """Test error message when file exists but has no read permissions (000)"""
    app = typer.Typer()
    app.command()(project)

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        temp_file.write("test content")
        temp_path = Path(temp_file.name)

    try:
        # Make file completely unreadable (no permissions)
        temp_path.chmod(0o000)

        result = run_and_report(
            app, [str(temp_path), "--source", "file"], expected_exit_code=1
        )

        assert result.exit_code != 0
        expected_permission_error = EXPECTED_PERMISSION_ERROR_PATTERN.format(
            file_path=temp_path
        )
        actual_error = extract_error_lines(result.stdout)
        assert_lines_match(expected_permission_error, actual_error)

    finally:
        # Clean up - restore permissions then delete
        temp_path.chmod(0o644)
        temp_path.unlink()


def test_failed_file_read_permission_error_write_only():
    """Test error message when file is write-only (200) - no read permissions"""
    app = typer.Typer()
    app.command()(project)

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        temp_file.write("test content")
        temp_path = Path(temp_file.name)

    try:
        # Make file write-only for owner (no read permissions anywhere)
        temp_path.chmod(0o200)

        result = run_and_report(
            app, [str(temp_path), "--source", "file"], expected_exit_code=1
        )

        assert result.exit_code != 0
        expected_permission_error = EXPECTED_PERMISSION_ERROR_PATTERN.format(
            file_path=temp_path
        )
        actual_error = extract_error_lines(result.stdout)
        assert_lines_match(expected_permission_error, actual_error)

    finally:
        # Clean up - restore permissions then delete
        temp_path.chmod(0o644)
        temp_path.unlink()


def test_failed_file_read_permission_error_execute_only():
    """Test error message when file is execute-only (100) - no read permissions"""
    app = typer.Typer()
    app.command()(project)

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        temp_file.write("test content")
        temp_path = Path(temp_file.name)

    try:
        # Make file execute-only for owner (no read permissions anywhere)
        temp_path.chmod(0o100)

        result = run_and_report(
            app, [str(temp_path), "--source", "file"], expected_exit_code=1
        )

        assert result.exit_code != 0
        expected_permission_error = EXPECTED_PERMISSION_ERROR_PATTERN.format(
            file_path=temp_path
        )
        actual_error = extract_error_lines(result.stdout)
        assert_lines_match(expected_permission_error, actual_error)

    finally:
        # Clean up - restore permissions then delete
        temp_path.chmod(0o644)
        temp_path.unlink()


def test_failed_file_read_permission_error_owner_no_read():
    """Test error message when file has read permissions for group/others but not owner (044)"""
    app = typer.Typer()
    app.command()(project)

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        temp_file.write("test content")
        temp_path = Path(temp_file.name)

    try:
        # Give read permissions to group and others but not owner
        temp_path.chmod(0o044)

        result = run_and_report(
            app, [str(temp_path), "--source", "file"], expected_exit_code=1
        )

        assert result.exit_code != 0
        expected_permission_error = EXPECTED_OWNER_NO_READ_ERROR_PATTERN.format(
            file_path=temp_path
        )
        actual_error = extract_error_lines(result.stdout)
        assert_lines_match(expected_permission_error, actual_error)

    finally:
        # Clean up - restore permissions then delete
        temp_path.chmod(0o644)
        temp_path.unlink()


def test_failed_file_read_directory_instead_of_file():
    """Test error message when path exists but is a directory not a file"""
    app = typer.Typer()
    app.command()(project)

    with tempfile.TemporaryDirectory() as temp_dir:
        result = run_and_report(
            app, [temp_dir, "--source", "file"], expected_exit_code=1
        )

        assert result.exit_code != 0
        expected_directory_error = EXPECTED_DIRECTORY_ERROR_PATTERN.format(
            file_path=temp_dir
        )
        actual_error = extract_error_lines(result.stdout)
        assert_lines_match(expected_directory_error, actual_error)


def test_failed_file_read_nonexistent_file():
    """Test error message for completely nonexistent file"""
    app = typer.Typer()
    app.command()(project)

    nonexistent_file = "/path/that/does/not/exist/file.txt"
    result = run_and_report(
        app, [nonexistent_file, "--source", "file"], expected_exit_code=1
    )

    assert result.exit_code != 0
    assert EXPECTED_NONEXISTENT_FILE_ERROR in result.stdout


def test_web_source_only_with_invalid_bmrb_code():
    """Test web-only source with invalid BMRB code"""
    app = typer.Typer()
    app.command()(project)

    with patch(
        "nef_pipelines.transcoders.nmrstar.importers.project._get_bmrb_entry_from_web_or_none"
    ) as mock_web:
        mock_web.return_value = None

        result = run_and_report(
            app, ["bmr99999", "--source", "web"], expected_exit_code=1
        )

        assert result.exit_code != 0
        # Should exit immediately for web-only source when web fetch fails


def test_shortcut_ubiquitin_web_failure_fallback():
    """Test that ubiquitin shortcut fails gracefully when web is down and file doesn't exist"""
    app = typer.Typer()
    app.command()(project)

    nef_argv = ["nef", "nmrstar", "import", "project", "ubiquitin", "--source", "auto"]

    with patch("sys.argv", nef_argv):
        # Mock web fetch to fail
        with patch(
            "nef_pipelines.transcoders.nmrstar.importers.project._get_bmrb_entry_from_web_or_none"
        ) as mock_web:
            mock_web.return_value = None

            result = run_and_report(
                app, ["ubiquitin", "--source", "auto"], expected_exit_code=1
            )

            assert result.exit_code != 0
            assert_lines_match(EXPECTED_UBIQUITIN_BMRB_ERROR, result.stdout)


def test_numeric_file_path_error_message():
    """Test specific error message for purely numeric file paths (BMRB IDs)"""
    app = typer.Typer()
    app.command()(project)

    nef_argv = ["nef", "nmrstar", "import", "project", "5387", "--source", "auto"]

    with patch("sys.argv", nef_argv):
        with patch(
            "nef_pipelines.transcoders.nmrstar.importers.project._get_bmrb_entry_from_web_or_none"
        ) as mock_web:
            mock_web.return_value = None

            result = run_and_report(
                app, ["5387", "--source", "auto"], expected_exit_code=1
            )

            assert result.exit_code != 0
            assert_lines_match(EXPECTED_NUMERIC_BMRB_ERROR, result.stdout)


def test_failed_file_read_parsing_error():
    """Test error message when file exists but contains invalid NMRSTAR content"""
    app = typer.Typer()
    app.command()(project)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".str", delete=False
    ) as temp_file:
        temp_file.write("invalid content")
        temp_path = Path(temp_file.name)

    try:
        result = run_and_report(
            app, [str(temp_path), "--source", "file"], expected_exit_code=1
        )

        assert result.exit_code != 0
        expected_parsing_error = EXPECTED_PARSING_ERROR_PATTERN.format(
            file_path=temp_path
        )
        actual_error = extract_error_lines(result.stdout)
        assert_lines_match(expected_parsing_error, actual_error)

    finally:
        temp_path.unlink()


def test_direct_read_entry_from_file_or_exit_error():
    """Test the updated error message format from read_entry_from_file_or_exit_error function"""

    from nef_pipelines.lib.nef_lib import read_entry_from_file_or_exit_error

    fake_path = "/fake/test/file.txt"

    # Mock open to raise PermissionError
    with patch("builtins.open", mock_open()) as mock_file:
        mock_file.side_effect = PermissionError(
            f"[Errno 13] Permission denied: '{fake_path}'"
        )

        # Mock exit_error to capture the error message instead of actually exiting
        with patch("nef_pipelines.lib.nef_lib.exit_error") as mock_exit_error:
            mock_exit_error.side_effect = SystemExit("mocked exit")

            try:
                read_entry_from_file_or_exit_error(fake_path)
            except SystemExit:
                pass

            # Verify exit_error was called with the expected message
            mock_exit_error.assert_called_once()
            error_message = mock_exit_error.call_args[0][0]
            expected_message = f"couldn't read an entry from the file {fake_path} because [Errno 13] Permission denied: '{fake_path}'"  # noqa: E501
            assert expected_message in error_message


def test_valid_local_file_import():
    """Test importing from a valid local NEF file"""
    app = typer.Typer()
    app.command()(project)

    # Use one of the test data files
    test_file = Path(__file__).parent / "test_data" / "bmr5387_3.str.txt"

    if test_file.exists():
        result = run_and_report(app, [str(test_file), "--source", "file"])

        # Should succeed and produce NEF output
        assert result.exit_code == 0
        # NEF files start with data_ block
        expected_nef_output = "data_"
        assert expected_nef_output in result.stdout
