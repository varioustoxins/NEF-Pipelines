# Plan B: `--no-sandbox` flag — let the AI change its working directory

## Context

By default the sandbox (working directory) can only be changed by the user via the
native OS dialog (`nef_change_sandbox` opens a GUI picker). The AI calling it gets
an error. With `--no-sandbox` at server startup the AI can call `nef_change_sandbox`
with an explicit `path` argument and change cwd directly, with no GUI involved.
Useful for headless/scripted/automated use.

## Design Decisions

- Add `path: str = None` parameter to `nef_change_sandbox`. Empty → GUI picker
  (current behaviour). Non-empty → applied directly (only works in unlocked mode).
- Module-level `_SANDBOX_LOCKED: bool = True` in `mcp_commands.py` controls AI
  access. If True and AI supplies a path → error. If False → path accepted directly.
- `--no-sandbox` at server startup sets `_SANDBOX_LOCKED = False`.
- `server.py` sets the flag before the server starts.
- When `_SANDBOX_LOCKED = False`, **all path restrictions are lifted**: `nef_upload_file`,
  `nef_download_file`, and `nef_import_files` skip `_validate_path_in_sandbox` and
  accept absolute paths and paths outside cwd. The AI can read/write anywhere on the
  filesystem — effectively the sandbox is just the current working directory with no
  enforced boundary. The user opted into this explicitly via `--no-sandbox`.

## Files to Modify

- `src/nef_pipelines/tools/ai/server.py` — add `--no-sandbox` CLI flag
- `src/nef_pipelines/tools/ai/mcp_commands.py` — `_SANDBOX_LOCKED` flag +
  updated `nef_change_sandbox` signature and logic
- `src/nef_pipelines/tests/ai/test_nef_mcp_server.py` — new tests for locked/unlocked

All paths relative to `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/`.

---

## Step 1 — `mcp_commands.py`: add `_SANDBOX_LOCKED` flag

After `_READ_ME_FIRST_CALLED` (which Plan A adds), add:

```python
_SANDBOX_LOCKED: bool = True  # set False via --no-sandbox at server startup
```

---

## Step 2 — `mcp_commands.py`: update `nef_change_sandbox`

Add `path: str = ""` parameter. Replace the body with:

```python
@mcp_tool
def nef_change_sandbox(path: str = "") -> ChangeSandboxResult:
    """\
    Change the server's working directory (sandbox).

    Default (sandbox locked): opens a native OS directory picker for the user.
    The AI must NOT supply a path — only the user picks the directory.
    If the AI supplies a path in locked mode, an error is returned.

    With --no-sandbox: the AI supplies path directly; no dialog is shown.

    path - target directory (AI-supplied). Only valid with --no-sandbox.
           Leave empty in normal (locked) mode — the native picker is used.

    Returns ChangeSandboxResult with new_path on success.
    On failure or user cancel, error is non-empty.
    """
    old_path = Path.cwd()

    if path and _SANDBOX_LOCKED:
        return ChangeSandboxResult(
            error=(
                """The Sandbox path can currently only be changed by the user via the native dialog.
                   As they started with the sanbox enabled, do not supply a path — call nef_change_sandbox()
                   with no arguments to open the directory picker for the user."""
            )
        )

    if path:
        picked = path          # --no-sandbox: AI supplies path directly
    else:
        picked = _get_native_directory(str(old_path))   # GUI picker

    if picked is None:
        return ChangeSandboxResult(error="User cancelled directory selection")

    if isinstance(picked, dict) and "error" in picked:
        return ChangeSandboxResult(error=picked["error"])

    try:
        new_path = Path(picked).resolve()
    except Exception as e:
        return ChangeSandboxResult(error=f"Invalid path: {e}")

    if not new_path.exists():
        return ChangeSandboxResult(error=f"Path does not exist: {new_path}")

    if not new_path.is_dir():
        return ChangeSandboxResult(error=f"Path is not a directory: {new_path}")

    try:
        os.chdir(new_path)
    except Exception as e:
        return ChangeSandboxResult(error=f"Failed to change directory: {e}")

    logger.info("nef_change_sandbox: %s -> %s", old_path, new_path)
    return ChangeSandboxResult(new_path=str(new_path))
```

---

## Step 3 — `mcp_commands.py`: bypass sandbox validation in file tools

In `nef_upload_file` and `nef_download_file`, skip `_validate_path_in_sandbox` when
unlocked. The `name` parameter can then be any path (absolute, relative, outside cwd).

```python
@mcp_tool
def nef_upload_file(name: str, content: str) -> UploadResult:
    if _SANDBOX_LOCKED:
        ok, error = _validate_path_in_sandbox(name)
        if not ok:
            return UploadResult(name=name, error=error)
    # ... rest unchanged (path write proceeds with name as-is)


@mcp_tool
def nef_download_file(name: str) -> DownloadResult:
    if _SANDBOX_LOCKED:
        ok, error = _validate_path_in_sandbox(name)
        if not ok:
            return DownloadResult(name=name, error=error)
    # ... rest unchanged (path read proceeds with name as-is)
```

For `nef_import_files`, when unlocked:
- Skip the `_validate_path_in_sandbox(source.name)` path check.
- **Allow symlinks** — they resolve to real files and can be copied normally.
- **Still reject directories** — no recursive copy machinery exists yet.

---

## Step 5 — `server.py`: add `--no-sandbox` CLI flag

Locate the Typer `serve` command. Add the option:

```python
no_sandbox: bool = typer.Option(
    False, "--no-sandbox",
    help="Allow the AI to set the sandbox path directly without a GUI dialog."
),
```

In the command body, before `_build_server()` / `mcp_server.run()`:

```python
if no_sandbox:
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    _cmd._SANDBOX_LOCKED = False
```

Optionally update `StartupContext` to carry a `no_sandbox` flag so
`_build_startup_notice` can tell the AI and user the server is running unlocked.

---

## Step 6 — Tests (`test_nef_mcp_server.py`)

Add a constant and three new tests in the existing `# --- nef_change_sandbox ---`
section. All use monkeypatch to control `_SANDBOX_LOCKED`.

```python
EXPECTED_ERROR_AI_PATH_LOCKED = (
    "Sandbox path can only be changed by the user via the native dialog. "
    "Do not supply a path — call nef_change_sandbox() with no arguments "
    "to open the directory picker for the user."
)


def test_change_sandbox_ai_path_rejected_when_locked(tmp_path, monkeypatch):
    """\
    Test that supplying a path while sandbox is locked returns an error.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_SANDBOX_LOCKED", True)

    result = nef_change_sandbox(path=str(tmp_path))

    EXPECTED = ChangeSandboxResult(error=EXPECTED_ERROR_AI_PATH_LOCKED)
    assert result == EXPECTED
    assert Path.cwd() == tmp_path.resolve()


def test_change_sandbox_ai_path_accepted_when_unlocked(tmp_path, monkeypatch):
    """\
    Test that supplying a path while sandbox is unlocked changes the cwd.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    target = tmp_path / "target"
    target.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_SANDBOX_LOCKED", False)

    result = nef_change_sandbox(path=str(target))

    EXPECTED = ChangeSandboxResult(new_path=str(target.resolve()))
    assert result == EXPECTED
    assert Path.cwd() == target.resolve()


def test_change_sandbox_gui_still_works_when_unlocked(tmp_path, monkeypatch):
    """\
    Test that an empty path still opens the GUI picker even when unlocked.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    target = tmp_path / "target"
    target.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_SANDBOX_LOCKED", False)
    monkeypatch.setattr(
        "nef_pipelines.tools.ai.mcp_commands._get_native_directory",
        lambda initial_dir: str(target),
    )

    result = nef_change_sandbox()   # no path → GUI picker

    EXPECTED = ChangeSandboxResult(new_path=str(target.resolve()))
    assert result == EXPECTED
```

Also add tests for file tool bypass in a `# --- no-sandbox file access ---` section:

```python
def test_upload_file_absolute_path_allowed_when_unlocked(tmp_path, monkeypatch):
    """\
    Test nef_upload_file accepts an absolute path when sandbox is unlocked.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_SANDBOX_LOCKED", False)
    target = tmp_path / "sub" / "out.nef"
    target.parent.mkdir()

    result = nef_upload_file(str(target), "data\n")
    EXPECTED = UploadResult(name=str(target), bytes_written=len("data\n".encode()))
    assert result == EXPECTED
    assert target.read_text() == "data\n"


def test_download_file_absolute_path_allowed_when_unlocked(tmp_path, monkeypatch):
    """\
    Test nef_download_file accepts an absolute path when sandbox is unlocked.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    target = tmp_path / "remote.nef"
    target.write_text("content\n")
    monkeypatch.chdir(tmp_path / "other_dir" if False else tmp_path)
    monkeypatch.setattr(_cmd, "_SANDBOX_LOCKED", False)

    result = nef_download_file(str(target))
    EXPECTED = DownloadResult(name=str(target), content="content\n")
    assert result == EXPECTED


def test_upload_file_absolute_path_still_rejected_when_locked(tmp_path, monkeypatch):
    """\
    Test nef_upload_file still rejects absolute paths when sandbox is locked.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_SANDBOX_LOCKED", True)

    result = nef_upload_file("/etc/passwd", "x")
    EXPECTED = UploadResult(name="/etc/passwd", error=result.error)
    assert result == EXPECTED
    assert bool(result.error)
```

---

## Verification

```
nefl test src/nef_pipelines/tests/ai/test_nef_mcp_server.py -k sandbox
nefl test src/nef_pipelines/tests/ai/
```

Manual: start server with `--no-sandbox`, connect AI, call
`nef_change_sandbox(path="/tmp/test")`, confirm cwd changed. Without the flag,
confirm the same call returns an error.
