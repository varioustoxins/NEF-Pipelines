# Plan: MCP server temporary file access

## Motivation

AI clients (e.g. Claude Desktop) need to supply format-specific files to NEF
commands (e.g. `xeasy import shifts foo.shifts`, `nmrview import peaks peaks.out`).
These commands read foreign-format files from disk, not from stdin, so they
cannot be driven purely by the `nef_input` pipeline mechanism.

The simplest safe solution: start the server in a private temporary directory
and expose three tools that let the AI upload files into it, list what is there,
and download results back. Filenames are validated with a small set of
structural rules (no path separators, no NUL, no leading dot, must resolve
inside the temp dir) plus Unicode NFC normalisation, so the realistic
confused-AI failure modes are contained without much machinery.

This is a development release and a deliberate intermediate step. It unblocks
real workflows immediately. A full IoBackend / annotation-based sandbox
described in `mcp_sandbox.md` adds defence-in-depth later — see "Threat model"
below for what this layer does and doesn't cover.

## Threat model

What this layer guards against:

- **Confused-AI failure modes.** Realistic case: an AI decides to start over
  and tries to wipe everything, or generates a filename like `../foo` because
  it got muddled. Rejecting path traversal contains the blast radius to the
  temp dir.
- **Cross-platform filename pitfalls.** NUL truncation, Unicode normalisation
  surprises, accidental dotfile shadowing.
- **Cwd drift between the file-access tools and command execution.**

What this layer does **not** guard against:

- **A deliberately adversarial AI.** That's the IoBackend / annotation
  sandbox's job. This isn't pen-testing-grade defence; it's "stupid rather
  than malicious".
- **Validation of file paths passed as NEF command arguments.** Only the
  `nef_upload_file` / `nef_download_file` `name` arguments are validated.
  Command-argument paths will be validated later by a cooperation between
  command-level annotations (declaring which arguments are input files,
  output files, templates, etc.) and the server (checking those declared
  paths against the sandbox). That work is deliberately deferred — this
  plan is an intermediate step.
- **Symlink attacks.** Temp dir is fresh per server start, NEF tools are
  author-controlled and don't create symlinks, no other process has a
  reason to write there. A compromised user filesystem is outside this
  layer's scope.
- **Disk-fill / DoS via large uploads.** Desktop deployment; restart
  resolves it; low likelihood.
- **Binary files.** Text only (UTF-8). Binary formats and archives (zip,
  tar, gzipped NEF) are deferred to the sandbox phase, where they need
  proper handling for zip-slip, decompression bombs, and similar.
- **Cross-session persistence.** Temp dir is fresh each time the server
  starts, by design. A `--preserve-tmp` flag exists for debugging.
- **Windows.** Not a target platform — NEF Pipelines doesn't currently
  support Windows pipelines well. The plan assumes POSIX semantics
  (Linux/macOS). If Windows ever becomes a target, revisit reserved
  filenames (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`),
  trailing-dot/space stripping, and the 255-byte name length.

## How files reach the server

The MCP server has no filesystem access of its own beyond the temp dir it
creates. File content reaches it as a string argument to
`nef_upload_file(name, content)`, carried over the MCP JSON-RPC transport.
The AI client is responsible for getting content into that argument,
typically by:

- **User attachment.** The user attaches the file in their chat client
  (e.g. drag-and-drop into Claude Desktop). The AI sees the content in
  its context and copies it into the tool call. This is the expected
  common case.
- **Filesystem MCP server.** Power-user setups where the AI client has a
  separate filesystem MCP configured can read files from the host and
  pass the content through. Out of scope here, but the data path is the
  same once the content is in the AI's hands.

What this server explicitly does **not** do:

- Read files from the user's host filesystem directly.
- Fetch URLs.
- Accept file paths or path-like arguments to "upload" (only inline
  `content`).

Practical consequence: the maximum upload size is whatever the MCP
transport will carry in a single tool call. Tens of megabytes are fine;
hundreds may not be. There is no server-side size cap because the
transport is already the binding constraint.

Round-trip fidelity: the AI client decodes file content into a Python
string before it reaches us. For UTF-8 / ASCII NMR text files this is
safe. Files that depend on exact bytes (line endings, non-UTF-8 codepages,
binary) are out of scope — see "Threat model".

## Design decisions

- **CWD-only, no `TMP_DIR` constant.** The server creates a temp dir and
  `chdir`s into it; the file-access tools resolve `Path(name)` against the
  current working directory. NEF tools are author-controlled, run in
  process, and don't `chdir`, so this is safe. Avoids module-level state,
  import-ordering traps, and an unnecessary accessor layer.

- **CWD invariant assertion.** `nef_execute_command` and
  `nef_execute_pipeline` assert that cwd hasn't drifted before running.
  This should never fire — it's enforcement of the assumption above and
  catches future regressions early.

- **Structural filename validation, not character allowlist.** Rejects
  empty, oversize (>max file name length for os), path separators (`/`, `\`), NUL, leading
  dot, and names that resolve outside the temp dir via
  `Path.is_relative_to`. Spaces, parentheses, Unicode, `+`, `&`, etc. are
  all permitted — real NMR filenames in the wild contain these and a
  character allowlist would reject them for no good reason.

- **Unicode NFC normalisation up front.** First step in validation. Makes
  filename behaviour deterministic across platforms with different
  default normalisations (HFS+ historically NFD, most Linux filesystems
  pass-through), and means downstream checks operate on a canonical form.
  Validation returns the normalised name so callers can use the canonical
  form for the actual write/read — otherwise an AI uploading NFD and
  downloading NFC would get a confusing "not found".

- **Leading dot rejected.** NMR formats don't use hidden files. Rejecting
  avoids accidental dotfile shadowing and shell glob surprises.

- **`tempfile.TemporaryDirectory`** rather than `mkdtemp` + `atexit`. The
  context manager's finalizer is at least as reliable as `atexit` and
  reads more clearly. Handle bound to a module-level name for the
  server's lifetime; cleanup happens on normal exit.

- **`--preserve-tmp` debug flag.** When set, uses `mkdtemp` directly and
  skips cleanup. Logs a warning at startup with the path so it's
  discoverable. Useful when something goes wrong and you want to inspect
  what the AI actually wrote.

- **UTF-8 explicit, end-to-end.** `write_text(..., encoding="utf-8")` and
  `read_text(encoding="utf-8")`. Non-ASCII content is supported and
  expected to round-trip cleanly.

- **`nef_list_files` treats non-file entries as an error state.** Any
  subdirectory, symlink, or other entry in the temp dir is unexpected —
  author-controlled NEF tools don't create them. The tool returns
  `success: False` with details, but still lists the regular files so
  the AI has something to work with for diagnosis. Server stays alive so
  the user can intervene.

- **Audit logging.** One `logger.info` per upload/download/list, with name
  and byte count. Cheap, valuable for debugging.

- **Concurrent server processes are safe.** Each
  `tempfile.TemporaryDirectory(prefix="nef_mcp_")` gets a unique suffix,
  and `chdir` is per-process. Two MCP server instances don't collide on
  the directory or interfere with each other's cwd. Worth confirming in
  case the deployment story ever moves beyond desktop.


## Files to change

| File | Change |
| --- | --- |
| `src/nef_pipelines/tools/ai/mcp_commands_lib.py` | `_validate_flat_name()`; `_assert_cwd_is_tmp_dir()`; `nef_upload_file()`; `nef_download_file()`; `nef_list_files()` |
| `src/nef_pipelines/tools/ai/server.py` | Create temp dir via `TemporaryDirectory`, `chdir` into it, `--preserve-tmp` CLI flag |
| `src/nef_pipelines/tools/ai/mcp_lib.py` | Register `nef_upload_file`, `nef_download_file`, `nef_list_files` tools |
| `src/nef_pipelines/resources/mcp_server/preamble.md` | Document the three new tools and the filename rules |
| `src/nef_pipelines/tests/ai/test_nef_mcp_server.py` | New tests for upload / download / list / name validation / round-trip |
| `src/nef_pipelines/tests/ai/test_nef_mcp_server_integration.py` | Add three tool names to `EXPECTED_TOOL_NAMES` |

## Implementation

### A. `mcp_commands_lib.py` — validation and three new tools

```python
import logging
import os
import unicodedata
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_NAME_LEN = 255  # POSIX NAME_MAX; revisit if Windows ever supported


def _validate_flat_name(name: str) -> Tuple[Optional[str], str]:
    """\
    Validate a flat filename and return (error_or_None, normalised_name).

    Normalises the input to Unicode NFC up front so downstream checks
    operate on a canonical form. Callers should use the returned
    normalised name for the actual write/read so that NFC/NFD round
    trips don't bite.

    Rejects:
      - empty
      - over 255 chars
      - path separators (/, \\)
      - NUL byte
      - leading '.'
      - names that resolve outside the current working directory
    All other characters are permitted (spaces, parentheses, Unicode, etc.).
    """
    name = unicodedata.normalize("NFC", name)
    result = None

    if not name:
        result = "filename must not be empty"
    elif len(name) > _MAX_NAME_LEN:
        result = f"filename exceeds {_MAX_NAME_LEN} characters (got {len(name)})"
    elif "/" in name or "\\" in name:
        result = f"'{name}' must not contain path separators"
    elif "\x00" in name:
        result = f"'{name}' contains a NUL byte"
    elif name.startswith("."):
        result = f"'{name}' must not start with '.'"
    else:
        cwd = Path(os.getcwd()).resolve()
        resolved = (cwd / name).resolve()
        if not resolved.is_relative_to(cwd):
            result = f"'{name}' resolves outside the working directory"

    return result, name


def _assert_cwd_is_tmp_dir() -> None:
    """\
    Sanity-check that the working directory is still the server's temp dir.

    NEF tools are author-controlled and do not chdir, so this should never
    fire. It exists to enforce the assumption that lets the file-access
    tools use cwd directly, and to catch future regressions early.

    The expected directory is read from the NEF_MCP_TMP_DIR environment
    variable, set by server.py at startup.
    """
    expected = os.environ.get("NEF_MCP_TMP_DIR")
    assert expected is not None, "NEF_MCP_TMP_DIR not set; server not initialised"
    current = str(Path(os.getcwd()).resolve())
    expected_resolved = str(Path(expected).resolve())
    assert current == expected_resolved, (
        f"cwd drifted: {current!r} != {expected_resolved!r}"
    )


def nef_upload_file(name: str, content: str) -> dict:
    """\
    Write a flat UTF-8 text file into the server's working directory.

    name    - plain filename, no path components (e.g. 'pxo.shifts').
              Normalised to Unicode NFC.
    content - UTF-8 text content to write. Non-ASCII is supported.

    Returns {"success": bool, "name": str, "bytes_written": int}.
    `bytes_written` is the number of encoded UTF-8 bytes, not characters.
    On failure, includes "error".
    """
    error, normalised = _validate_flat_name(name)
    result = {"success": False, "name": normalised, "bytes_written": 0}

    if error is not None:
        result["error"] = error
    else:
        path = Path(normalised)
        path.write_text(content, encoding="utf-8")
        bytes_written = len(content.encode("utf-8"))
        logger.info("nef_upload_file: %s (%d bytes)", normalised, bytes_written)
        result = {
            "success": True,
            "name": normalised,
            "bytes_written": bytes_written,
        }

    return result


def nef_download_file(name: str) -> dict:
    """\
    Read a flat UTF-8 text file from the server's working directory.

    name - plain filename, no path components (e.g. 'result.nef').
           Normalised to Unicode NFC.

    Returns {"success": bool, "name": str, "content": str}.
    On failure, includes "error" and (when the file is missing)
    "available_files".
    """
    error, normalised = _validate_flat_name(name)
    result = {"success": False, "name": normalised, "content": ""}

    if error is not None:
        result["error"] = error
    else:
        path = Path(normalised)
        if not path.exists():
            cwd = Path(os.getcwd())
            files = sorted(f.name for f in cwd.iterdir() if f.is_file())
            result["error"] = f"'{normalised}' not found"
            result["available_files"] = files
        else:
            content = path.read_text(encoding="utf-8")
            logger.info(
                "nef_download_file: %s (%d bytes)", normalised, len(content)
            )
            result = {
                "success": True,
                "name": normalised,
                "content": content,
            }

    return result


def nef_list_files() -> dict:
    """\
    List entries in the server's working directory.

    Returns {"success": bool, "files": [str], "cwd": str}.

    Any non-file entry (subdirectory, symlink, FIFO, socket, ...) is an
    unexpected error state — author-controlled NEF tools don't create
    them. When such entries are present, returns success=False with an
    "error" message and an "unexpected_entries" list giving each entry's
    name and type. Regular files are still listed so the AI has something
    to work with for diagnosis.
    """
    cwd = Path(os.getcwd())
    files = []
    unexpected = []

    for entry in sorted(cwd.iterdir()):
        if entry.is_symlink():
            unexpected.append({"name": entry.name, "type": "symlink"})
        elif entry.is_file():
            files.append(entry.name)
        elif entry.is_dir():
            unexpected.append({"name": entry.name, "type": "directory"})
        else:
            unexpected.append({"name": entry.name, "type": "other"})

    logger.info(
        "nef_list_files: %d file(s), %d unexpected entry/entries",
        len(files), len(unexpected),
    )

    if unexpected:
        result = {
            "success": False,
            "error": (
                "unexpected non-file entries in working directory "
                "(NEF tools should not create these)"
            ),
            "files": files,
            "unexpected_entries": unexpected,
            "cwd": str(cwd),
        }
    else:
        result = {
            "success": True,
            "files": files,
            "cwd": str(cwd),
        }

    return result
```

The existing `nef_execute_command` and `nef_execute_pipeline` should call
`_assert_cwd_is_tmp_dir()` as their first line.

### B. `server.py` — temp dir setup

Add imports:

```python
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)
```

Add module-level state and a setup helper:

```python
_TMP_DIR_HANDLE: tempfile.TemporaryDirectory | None = None


def _setup_working_directory(preserve: bool = False) -> Path:
    """\
    Create a fresh temp dir, chdir into it, and record its path in
    NEF_MCP_TMP_DIR for the cwd-invariant assertion to read.

    When preserve=False (default), uses tempfile.TemporaryDirectory so
    the directory is cleaned up on normal exit. The handle is bound to
    a module-level name to keep its finalizer alive for the server's
    lifetime.

    When preserve=True, uses tempfile.mkdtemp directly — the directory
    is NOT cleaned up. A warning is logged with the path so it's
    discoverable. Intended for debugging.
    """
    global _TMP_DIR_HANDLE

    if preserve:
        tmp_path = Path(tempfile.mkdtemp(prefix="nef_mcp_")).resolve()
        logger.warning(
            "--preserve-tmp set; working directory will NOT be cleaned up: %s",
            tmp_path,
        )
    else:
        _TMP_DIR_HANDLE = tempfile.TemporaryDirectory(prefix="nef_mcp_")
        tmp_path = Path(_TMP_DIR_HANDLE.name).resolve()

    os.environ["NEF_MCP_TMP_DIR"] = str(tmp_path)
    os.chdir(tmp_path)
    return tmp_path
```

Call it in `server()` before `_build().run(**kwargs)`, threading a CLI
flag through:

```python
def server(..., preserve_tmp: bool = False, ...):
    _setup_working_directory(preserve=preserve_tmp)
    # ... existing _build().run(**kwargs)
```

### C. `mcp_lib.py` — register tools

Add to the import from `mcp_commands_lib`:

```python
from nef_pipelines.tools.ai.mcp_commands_lib import (
    ...,
    nef_upload_file,
    nef_download_file,
    nef_list_files,
)
```

Register after `nef_read_resource`, before `nef_list_commands`:

```python
mcp_server.tool()(nef_read_me_first)
mcp_server.tool()(nef_read_resource)
mcp_server.tool()(nef_upload_file)
mcp_server.tool()(nef_download_file)
mcp_server.tool()(nef_list_files)
mcp_server.tool()(nef_list_commands)
mcp_server.tool()(nef_get_command_help)
mcp_server.tool()(nef_execute_command)
mcp_server.tool()(nef_execute_pipeline)
```

### D. `preamble.md` — updated Tools section

```
0. nef_read_me_first()             — orientation (call first; skip if seen this session)
1. nef_read_resource(name)         — fetch any resource document by name
2. nef_upload_file(name, content)  — write a flat UTF-8 file into the server working directory
3. nef_download_file(name)         — read a flat UTF-8 file from the server working directory
4. nef_list_files()                — list files in the server working directory
5. nef_list_commands()             — enumerate available commands
6. nef_get_command_help(...)       — full --help for one command
7. nef_execute_command(...)        — single step (prototyping)
8. nef_execute_pipeline(...)       — production multi-step pipeline
```

Add a "File access" section explaining:

- Filenames are flat: no `/` or `\`, no leading `.`, no NUL, max 255
  characters. Spaces, parentheses, and Unicode are fine.
- Filenames are normalised to Unicode NFC; the normalised form is what
  gets returned and what should be used for subsequent operations.
- Content is UTF-8 text (ASCII is a subset). Binary files and archives
  are not supported in this version.
- The working directory is fresh per server start and discarded on exit
  (unless `--preserve-tmp` was given).
- If a NEF command writes a subdirectory or symlink into the working
  directory, `nef_list_files()` returns an error — that's an unexpected
  state.

#### Typical workflow

```
AI: nef_upload_file("pxo.shifts", "<xeasy shifts content>")
AI: nef_execute_command(["xeasy", "import", "shifts", "--frame-name", "pxo", "pxo.shifts"])
AI: nef_download_file("result.nef")
```

Or in a pipeline:

```
AI: nef_upload_file("pxo.shifts", "<content>")
AI: nef_execute_pipeline([
        {"args": ["xeasy", "import", "shifts", "pxo.shifts"]},
        {"args": ["save", "result.nef"]},
    ])
AI: nef_download_file("result.nef")
```

## Tests (`test_nef_mcp_server.py`)

Tests use a `working_dir` fixture that `monkeypatch.chdir`s into
`tmp_path` and sets `NEF_MCP_TMP_DIR`, isolating each test from the real
filesystem and from other tests:

```python
@pytest.fixture
def working_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEF_MCP_TMP_DIR", str(tmp_path))
    return tmp_path
```

| Test | Expectation |
| --- | --- |
| `test_upload_creates_file` | file appears in cwd after upload; `bytes_written` matches UTF-8 byte length |
| `test_upload_empty_content_creates_empty_file` | `nef_upload_file("foo", "")` succeeds, creates a zero-byte file |
| `test_upload_then_overwrite` | second upload with same name replaces content cleanly |
| `test_download_returns_content` | content round-trips through upload → download |
| `test_unicode_content_round_trip` | non-ASCII characters survive the round trip |
| `test_filename_nfc_normalisation` | upload as NFD, download as NFC (or vice versa); name returned is NFC; both operations refer to the same file |
| `test_filename_with_spaces_accepted` | `"my peaks (copy).out"` succeeds |
| `test_filename_with_unicode_accepted` | `"naïve_peaks.txt"` succeeds |
| `test_list_files_empty` | empty dir returns empty `files` list, `success=True` |
| `test_list_files_after_upload` | uploaded filename appears in `files` |
| `test_list_files_reports_subdir_as_error` | manually mkdir inside cwd; `success=False`, entry in `unexpected_entries` with `type="directory"` |
| `test_list_files_reports_symlink_as_error` | manually create symlink; `success=False`, entry has `type="symlink"` |
| `test_upload_rejects_path_separator` | `"sub/evil"` → `success=False` |
| `test_upload_rejects_backslash` | `"sub\\evil"` → `success=False` |
| `test_upload_rejects_leading_dot` | `".hidden"` → `success=False` |
| `test_upload_rejects_empty_name` | `""` → `success=False` |
| `test_upload_rejects_nul_byte` | `"foo\x00.txt"` → `success=False` |
| `test_upload_rejects_overlong_name` | 256-char name → `success=False` |
| `test_upload_rejects_resolved_escape` | a name that resolves outside cwd → `success=False` |
| `test_download_missing_file` | `success=False`, `available_files` list included |
| `test_download_rejects_bad_name` | path-traversal name → `success=False` |
| `test_assert_cwd_passes_when_correct` | `_assert_cwd_is_tmp_dir()` returns cleanly |
| `test_assert_cwd_raises_when_drifted` | manually chdir elsewhere; `_assert_cwd_is_tmp_dir()` raises `AssertionError` |

Integration test: add `"nef_upload_file"`, `"nef_download_file"`,
`"nef_list_files"` to `EXPECTED_TOOL_NAMES`.

## Verification

```bash
# Unit tests
.venv311/bin/python -m pytest src/nef_pipelines/tests/ai/test_nef_mcp_server.py -q -k upload

# Full AI test suite
.venv311/bin/python -m pytest src/nef_pipelines/tests/ai/ -q

# Manual smoke test — upload a file and list it
.venv311/bin/python -c "
import os, tempfile
from pathlib import Path
from nef_pipelines.tools.ai.mcp_commands_lib import (
    nef_upload_file, nef_list_files, nef_download_file,
)
tmp = Path(tempfile.mkdtemp(prefix='nef_mcp_smoke_')).resolve()
os.environ['NEF_MCP_TMP_DIR'] = str(tmp)
os.chdir(tmp)
print(nef_upload_file('test.shifts', 'hello'))
print(nef_list_files())
print(nef_download_file('test.shifts'))
"

# Smoke test with --preserve-tmp
.venv311/bin/python -m nef_pipelines.tools.ai.server --preserve-tmp
# ... should log a warning naming the temp dir at startup
```
