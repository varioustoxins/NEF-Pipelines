# Plan A: Orientation Guard — enforce `nef_read_me_first` before any other tool

## Context

An AI connecting to the MCP server can currently call any tool without ever calling
`nef_read_me_first`. We want to enforce this: if `nef_read_me_first` has not been
called in the current server session, every other tool must return an error telling
the AI to call it first. Part of the reason behind this is that `nef_read_me_first`
provides important context  information (e.g. about the working directory /sandbox )
and also is the source of important warning for the user, so it's not just a formality.

## Files to Modify

- `src/nef_pipelines/tools/ai/mcp_commands.py`
- `src/nef_pipelines/tests/ai/test_nef_mcp_server.py`
- `src/nef_pipelines/tests/ai/test_nef_mcp_server_integration.py`

All paths relative to `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/`.

---

## Step 1 — `mcp_commands.py`: add flag + guard infrastructure

Add `import functools` and `import inspect` to the top-level imports.

After `logger = logging.getLogger(__name__)`, add:

```python
_READ_ME_FIRST_CALLED: bool = False

_ORIENTATION_ERROR = (
    "⛔ nef_read_me_first has not been called yet. "
    "You MUST call nef_read_me_first before using any other NEF tool. "
    "Call nef_read_me_first now, tell the user about any warnings and then retry."
)


def _orientation_guard(fn: Callable) -> Callable:
    """Wrap a tool so it errors if nef_read_me_first has not been called."""
    return_type = fn.__annotations__.get("return")

    if asyncio.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if not _READ_ME_FIRST_CALLED:
                return return_type(error=_ORIENTATION_ERROR)
            return await fn(*args, **kwargs)
    else:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not _READ_ME_FIRST_CALLED:
                return return_type(error=_ORIENTATION_ERROR)
            return fn(*args, **kwargs)

    wrapper.__signature__ = inspect.signature(fn)  # FastMCP needs the real sig
    return wrapper
```

---

## Step 2 — `mcp_commands.py`: apply guard in `mcp_tool` decorator

Replace the existing `mcp_tool` body:

```python
def mcp_tool(fn: Callable) -> Callable:
    """\
    Decorator that marks a function as an MCP tool for auto-registration.
    All tools except nef_read_me_first are wrapped with _orientation_guard.
    """
    if fn.__name__ != "nef_read_me_first":
        fn = _orientation_guard(fn)
    _MCP_TOOLS.append(fn)
    return fn
```

---

## Step 3 — `mcp_commands.py`: set flag in `nef_read_me_first`

Add `global _READ_ME_FIRST_CALLED` at the very start of the function body:

```python
@mcp_tool
def nef_read_me_first() -> NefStartupResult:
    """..."""
    global _READ_ME_FIRST_CALLED
    _READ_ME_FIRST_CALLED = True
    # ... rest unchanged
```

---

## Step 4 — `test_nef_mcp_server.py`: autouse fixture + guard tests

Add an autouse fixture so every existing unit test starts with the flag True
(existing tests don't need to change):

```python
@pytest.fixture(autouse=True)
def _orientation_ready(monkeypatch):
    """Set _READ_ME_FIRST_CALLED=True for all unit tests by default."""
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    monkeypatch.setattr(_cmd, "_READ_ME_FIRST_CALLED", True)
```

Add two new tests in a `# --- orientation guard ---` section:

```python
# --- orientation guard ---

def test_orientation_guard_blocks_tool_before_read_me_first(tmp_path, monkeypatch):
    """\
    Test that tools return an error if nef_read_me_first has not been called.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_READ_ME_FIRST_CALLED", False)

    result = nef_list_files()
    EXPECTED = ListFilesResult(error=_cmd._ORIENTATION_ERROR)
    assert result == EXPECTED


def test_orientation_guard_unblocked_after_read_me_first(tmp_path, monkeypatch):
    """\
    Test that calling nef_read_me_first unblocks subsequent tool calls.
    """
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_READ_ME_FIRST_CALLED", False)

    nef_read_me_first()  # sets flag True

    result = nef_list_files()
    EXPECTED = ListFilesResult(files=[], cwd=result.cwd)
    assert result == EXPECTED
```

---

## Step 5 — `test_nef_mcp_server_integration.py`: call orientation tool in fixture

Modify the `mcp_client` fixture to call `nef_read_me_first` via the client
before yielding, so all integration tests start oriented:

```python
@pytest.fixture
async def mcp_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async with Client(_build_server()) as client:
        await client.call_tool("nef_read_me_first", arguments={})
        yield client
```

Add one integration guard test (uses a raw client without orientation):

```python
@pytest.mark.anyio
async def test_orientation_guard_blocks_tool_in_integration(tmp_path, monkeypatch):
    """\
    Test that the guard error is surfaced via MCP protocol before read_me_first.
    """
    import json
    import nef_pipelines.tools.ai.mcp_commands as _cmd
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_cmd, "_READ_ME_FIRST_CALLED", False)
    async with Client(_build_server()) as client:
        result = await client.call_tool("nef_list_files", arguments={})
        data = json.loads(result.content[0].text)
        assert "nef_read_me_first" in data["error"]
```

---

## Verification

```
nefl test src/nef_pipelines/tests/ai/test_nef_mcp_server.py -k orientation
nefl test src/nef_pipelines/tests/ai/test_nef_mcp_server_integration.py
nefl test src/nef_pipelines/tests/ai/
```

All 71 tests (69 existing + 2 new unit + 1 new integration) should pass.
