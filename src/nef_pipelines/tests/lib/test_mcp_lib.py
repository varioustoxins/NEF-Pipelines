"""
Tests for utility functions in mcp_lib.
"""

import sys

import pytest

from nef_pipelines.tools.ai.mcp_lib import _validate_path_in_sandbox

if sys.version_info < (3, 10):
    pytest.skip("MCP server requires Python 3.10 or later", allow_module_level=True)

pytest.importorskip("fastmcp")

_POSIX = sys.platform != "win32"

TEST_CASES = [
    # (path_str, should_pass, expected_error, description, platforms)
    # platforms: "all", "posix", "windows"
    ("foo.txt", True, "", "normal filename", "all"),
    ("my peaks (copy).out", True, "", "spaces and parens", "all"),
    ("naïve_peaks.txt", True, "", "unicode", "all"),
    ("subdir/foo.txt", True, "", "relative subdir", "all"),
    ("", False, "'' resolves to the sandbox root itself", "empty", "all"),
    (".", False, "'.' resolves to the sandbox root itself", "resolves to root", "all"),
    (
        "../etc/passwd",
        False,
        "'../etc/passwd' resolves outside the sandbox",
        "escapes sandbox",
        "all",
    ),
    (
        "/etc/passwd",
        False,
        "'/etc/passwd' must be a relative path, not absolute",
        "absolute",
        "posix",
    ),
    (
        "foo\x00bar",
        False,
        [
            "could not resolve 'foo\x00bar': embedded null byte",  # Python 3.10 (ValueError)
            "could not resolve 'foo\x00bar': lstat: embedded null character in path",  # newer Python (OSError)
        ],
        "NUL byte",
        "all",
    ),
    (
        "a" * 300,
        False,
        f"path component '{'a' * 40}...' exceeds 255 characters (got 300)",
        "oversize component",
        "all",
    ),
    (123, False, "path must be a string, got int", "wrong type", "all"),
    # backslash is a valid filename character on POSIX; on Windows it is a path
    # separator so these are caught by the existing absolute/traversal checks.
    ("..\\Windows\\System32", True, "", "windows traversal", "posix"),
    (
        "..\\Windows\\System32",
        False,
        "'..\\Windows\\System32' resolves outside the sandbox",
        "windows traversal",
        "windows",
    ),
    ("C:\\Windows\\System32", True, "", "windows absolute", "posix"),
    (
        "C:\\Windows\\System32",
        False,
        "'C:\\Windows\\System32' must be a relative path, not absolute",
        "windows absolute",
        "windows",
    ),
    # drive-relative paths: "C:foo" has no separator so is_absolute() returns False
    # on Windows — caught by Step 3a.
    ("C:foo", True, "", "windows drive-relative", "posix"),
    (
        "C:foo",
        False,
        "'C:foo' contains a Windows drive letter",
        "windows drive-relative",
        "windows",
    ),
    # UNC/network paths
    ("\\\\server\\share", True, "", "windows UNC", "posix"),
    (
        "\\\\server\\share",
        False,
        "'\\\\server\\share' must be a relative path, not absolute",
        "windows UNC",
        "windows",
    ),
    ("foo//bar.txt", True, "", "double slash", "all"),
    ("foo/./bar.txt", True, "", "current directory reference", "all"),
    (
        "foo/../../etc/passwd",
        False,
        "'foo/../../etc/passwd' resolves outside the sandbox",
        "sneaky traversal",
        "all",
    ),
]

_ACTIVE_CASES = [
    (path_str, should_pass, expected_error, description)
    for path_str, should_pass, expected_error, description, platforms in TEST_CASES
    if platforms == "all"
    or (platforms == "posix" and _POSIX)
    or (platforms == "windows" and not _POSIX)
]


@pytest.mark.parametrize(
    "path_str,should_pass,expected_error,description",
    _ACTIVE_CASES,
    ids=[d for _, _, _, d in _ACTIVE_CASES],
)
def test_validate_path_in_sandbox(
    tmp_path, monkeypatch, path_str, should_pass, expected_error, description
):
    """\
    Test _validate_path_in_sandbox with valid and invalid path inputs.
    """
    monkeypatch.chdir(tmp_path)
    ok, error = _validate_path_in_sandbox(path_str)

    if should_pass:
        assert ok, f"{description!r}: expected valid but got error: {error!r}"
        assert (
            error == ""
        ), f"{description!r}: expected no error message but got: {error!r}"
    else:
        assert not ok, f"{description!r}: expected invalid but got ok=True"
        if isinstance(expected_error, list):
            assert (
                error in expected_error
            ), f"{description!r}: error not in expected list:\n  {expected_error!r}\nbut got:\n  {error!r}"
        else:
            assert (
                error == expected_error
            ), f"{description!r}: expected error:\n  {expected_error!r}\nbut got:\n  {error!r}"
