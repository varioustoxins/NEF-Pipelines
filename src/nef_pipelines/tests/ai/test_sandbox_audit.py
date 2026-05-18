"""Unit tests for sandbox write auditing functionality."""

import mmap
import os
import shutil
import sys
import threading
from pathlib import Path

import pytest

if sys.version_info < (3, 10):
    pytest.skip(
        "AI sandbox features require Python 3.10 or later", allow_module_level=True
    )

from nef_pipelines.tools.ai.sandbox_audit import (
    SandboxViolation,
    _AuditState,
    audit_sandbox_writes,
)

EXPECTED_SANDBOX_VIOLATION = "Sandbox violation"
EXPECTED_NESTING_ERROR = "audit_sandbox_writes does not support nesting - a sandbox context is already active"


def test_audit_hook_allows_writes_inside_sandbox(tmp_path):
    """Verify audit hook allows file writes inside the sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    test_file = sandbox / "allowed.txt"

    with audit_sandbox_writes(sandbox) as audit_state:
        test_file.write_text("This write should succeed")

    assert test_file.exists()
    assert test_file.read_text() == "This write should succeed"
    assert audit_state == _AuditState()


def test_audit_hook_blocks_writes_outside_sandbox(tmp_path):
    """Verify audit hook blocks file writes outside the sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    outside_file = tmp_path / "outside.txt"

    with pytest.raises(SandboxViolation, match=EXPECTED_SANDBOX_VIOLATION):
        with audit_sandbox_writes(sandbox):
            outside_file.write_text("This write should be blocked")

    assert not outside_file.exists()


def test_audit_hook_inactive_outside_context(tmp_path):
    """Verify audit hook is dormant when not in context."""
    outside_file = tmp_path / "outside.txt"

    outside_file.write_text("This write should succeed")

    assert outside_file.exists()
    assert outside_file.read_text() == "This write should succeed"


@pytest.mark.parametrize(
    "write_op",
    [
        pytest.param(
            lambda outside: (outside / "file.txt").write_text("test"), id="write_text"
        ),
        pytest.param(
            lambda outside: (outside / "file.bin").write_bytes(b"test"),
            id="write_bytes",
        ),
        pytest.param(
            lambda outside: open(outside / "file2.txt", "w").close(), id="open_write"
        ),
        pytest.param(
            lambda outside: open(outside / "file3.txt", "a").close(), id="open_append"
        ),
        pytest.param(lambda outside: (outside / "dir").mkdir(), id="mkdir"),
    ],
)
def test_audit_hook_blocks_write_operation(tmp_path, write_op):
    """Verify audit hook catches different types of write operations outside sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside"

    with pytest.raises(SandboxViolation, match=EXPECTED_SANDBOX_VIOLATION):
        with audit_sandbox_writes(sandbox):
            write_op(outside)


def test_audit_hook_allows_reads_anywhere(tmp_path):
    """Verify audit hook allows read operations outside sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    outside_file = tmp_path / "readable.txt"
    outside_file.write_text("Content to read")

    with audit_sandbox_writes(sandbox) as audit_state:
        content = outside_file.read_text()

    assert content == "Content to read"
    assert audit_state == _AuditState()


def test_audit_hook_thread_safety(tmp_path):
    """Verify audit hook state is thread-local and doesn't interfere across threads."""
    sandbox1 = tmp_path / "sandbox1"
    sandbox2 = tmp_path / "sandbox2"
    sandbox1.mkdir()
    sandbox2.mkdir()

    results = {"thread1": None, "thread2": None}

    def thread1_work():
        try:
            with audit_sandbox_writes(sandbox1):
                (sandbox2 / "file.txt").write_text("test")
            results["thread1"] = "no_error"
        except SandboxViolation:
            results["thread1"] = "blocked"

    def thread2_work():
        try:
            with audit_sandbox_writes(sandbox2):
                (sandbox1 / "file.txt").write_text("test")
            results["thread2"] = "no_error"
        except SandboxViolation:
            results["thread2"] = "blocked"

    thread1 = threading.Thread(target=thread1_work)
    thread2 = threading.Thread(target=thread2_work)

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    assert (
        results["thread1"] == "blocked"
    ), "Thread 1 should be blocked from writing to sandbox2"
    assert (
        results["thread2"] == "blocked"
    ), "Thread 2 should be blocked from writing to sandbox1"


def test_audit_hook_handles_relative_paths(tmp_path):
    """Verify audit hook blocks writes using relative paths to escape sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    original_cwd = Path.cwd()
    try:
        os.chdir(sandbox)

        with pytest.raises(SandboxViolation, match=EXPECTED_SANDBOX_VIOLATION):
            with audit_sandbox_writes(sandbox):
                Path("../outside.txt").write_text("escape attempt")

    finally:
        os.chdir(original_cwd)


def test_audit_hook_allows_write_to_sandbox_subdirectory(tmp_path):
    """Verify audit hook allows writes to subdirectories within sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    subdir = sandbox / "subdir"

    with audit_sandbox_writes(sandbox):
        subdir.mkdir()
        (subdir / "file.txt").write_text("allowed")

    assert (subdir / "file.txt").exists()
    assert (subdir / "file.txt").read_text() == "allowed"


def test_audit_hook_nested_contexts(tmp_path):
    """Verify that nested audit_sandbox_writes raises RuntimeError."""
    sandbox1 = tmp_path / "sandbox1"
    sandbox2 = tmp_path / "sandbox2"
    sandbox1.mkdir()
    sandbox2.mkdir()

    with pytest.raises(RuntimeError, match=EXPECTED_NESTING_ERROR):
        with audit_sandbox_writes(sandbox1):
            with audit_sandbox_writes(sandbox2):
                pass


def test_audit_hook_blocks_shutil_operations(tmp_path):
    """Verify audit hook catches shutil.copy and shutil.move operations."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    (sandbox / "source.txt").write_text("content")
    (outside / "outside_source.txt").write_text("content")

    with audit_sandbox_writes(sandbox):
        shutil.copy(sandbox / "source.txt", sandbox / "dest.txt")
    assert (sandbox / "dest.txt").exists()

    with pytest.raises(SandboxViolation, match=EXPECTED_SANDBOX_VIOLATION):
        with audit_sandbox_writes(sandbox):
            shutil.copy(sandbox / "source.txt", outside / "evil.txt")
    assert not (outside / "evil.txt").exists()

    with pytest.raises(SandboxViolation, match=EXPECTED_SANDBOX_VIOLATION):
        with audit_sandbox_writes(sandbox):
            shutil.move(sandbox / "dest.txt", outside / "moved.txt")
    assert not (outside / "moved.txt").exists()


def test_audit_hook_allows_shutil_inside_sandbox(tmp_path):
    """Verify shutil operations work normally inside sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    (sandbox / "source.txt").write_text("content")

    with audit_sandbox_writes(sandbox) as audit_state:
        shutil.copy(sandbox / "source.txt", sandbox / "copy1.txt")
        shutil.copy2(sandbox / "source.txt", sandbox / "copy2.txt")
        shutil.move(sandbox / "copy1.txt", sandbox / "moved.txt")

    assert (sandbox / "copy2.txt").exists()
    assert (sandbox / "moved.txt").exists()
    assert not (sandbox / "copy1.txt").exists()
    assert audit_state == _AuditState()


def test_audit_hook_blocks_mmap_writes_outside_sandbox(tmp_path):
    """Verify audit hook catches mmap write attempts outside sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    outside_file = outside / "mmap_target.bin"
    outside_file.write_bytes(b"x" * 1024)

    f = open(outside_file, "r+b")
    try:
        with pytest.raises(SandboxViolation, match=EXPECTED_SANDBOX_VIOLATION):
            with audit_sandbox_writes(sandbox):
                mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
    finally:
        f.close()


def test_audit_hook_allows_mmap_inside_sandbox(tmp_path):
    """Verify mmap works normally inside sandbox."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    test_file = sandbox / "mmap_file.bin"
    test_file.write_bytes(b"test data" * 100)

    with audit_sandbox_writes(sandbox) as audit_state:
        with open(test_file, "r+b") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
            mm[0:4] = b"PASS"
            mm.close()

    assert test_file.read_bytes().startswith(b"PASS")
    assert audit_state == _AuditState()


def test_audit_hook_allows_readonly_mmap_anywhere(tmp_path):
    """Verify read-only mmap is allowed anywhere."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    outside_file = outside / "readonly.bin"
    outside_file.write_bytes(b"read only data")

    with audit_sandbox_writes(sandbox) as audit_state:
        with open(outside_file, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            data = mm[:]
            mm.close()

        assert data == b"read only data"
    assert audit_state == _AuditState()
