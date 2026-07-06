# Plan: MCP Server Startup Context

Relay sandbox status and warnings to the AI at session start via two independent channels.
In BOTH channels, the AI is explicitly instructed to show the information to the user immediately:

1. MCP `instructions` field (protocol handshake) - for clients that honour it
2. `nef_read_me_first()` `information` field - reliable fallback for Claude and clients that ignore `instructions`

---

## 1. `mcp_lib.py` — Add `StartupContext` dataclass and global

```python
@dataclass
class StartupContext:
    sandbox_path: str = ""
    is_temporary: bool = False
    will_be_cleaned: bool = False
    warning: str = ""

_STARTUP_CONTEXT = StartupContext()
```

andAdd `information: str = ""` to `ResourceResult`, with a docstring that instructs the AI:

```python
@dataclass
class ResourceResult(OperationResult):
    """Result of nef_read_me_first and nef_read_resource.

    information — if non-empty, the AI MUST show this to the user verbatim before anything else.
    It carries startup warnings and sandbox status that must be relayed immediately.
    """
    content: str = ""
    information: str = ""  # ← Sandbox status message with "Show this to user" instruction
    available_resources: List[str] = field(default_factory=list)
```

Add a helper `_build_startup_notice(ctx: StartupContext) -> str` that formats the context into a
message with an explicit instruction to show it to the user, e.g.:

```
**IMPORTANT: Show this to the user immediately:**

## Sandbox Status

- **Directory**: `/tmp/nef_mcp_abc123`
- **Type**: Temporary — will be **deleted** on exit
- **⚠ Warning**: Specified --path does not exist: /bad/path — falling back to temporary directory
```

or for a user-provided persistent sandbox:

```
**Show this to the user:**

## Sandbox Status

- **Directory**: `/Users/gary/nmr_work`
- **Type**: Persistent — files will NOT be deleted on exit
```

---

## 2. `server.py` — Populate `_STARTUP_CONTEXT` and suppress FastMCP banner

After resolving the sandbox, before `_build().run(...)`:

```python
import nef_pipelines.tools.ai.mcp_lib as mcp_lib
mcp_lib._STARTUP_CONTEXT = mcp_lib.StartupContext(
    sandbox_path=str(sandbox_path),
    is_temporary=is_temp,
    will_be_cleaned=is_temp and not preserve,
    warning=warning or "",
)
_build().run(show_banner=False, **server_transport_args)
```

**Key points:**
- `_STARTUP_CONTEXT` is set AFTER sandbox resolution but BEFORE the server starts
- This allows `_build_server()` (which runs during `.run()`) to read the context
- `show_banner=False` suppresses the FastMCP banner since we display our own experimental warning

---

## 3. `server_lib.py` — Append startup notice to `instructions`

`_build_server()` reads `_STARTUP_CONTEXT` and appends the startup notice to the preamble:

```python
startup_notice = _build_startup_notice(_STARTUP_CONTEXT) if _STARTUP_CONTEXT.sandbox_path else ""
instructions = preamble + ("\n\n" + startup_notice if startup_notice else "")
mcp_server = FastMCP("nef-pipelines", version=get_version(), instructions=instructions)
```

The `instructions` field is sent during the MCP protocol handshake. For clients that honour it,
the AI sees the sandbox status immediately at connection time with explicit instructions to show
it to the user.

---

## 4. `mcp_commands.py` — Populate `information` in `nef_read_me_first()`

`nef_read_me_first()` reads `_STARTUP_CONTEXT` and sets the `information` field with the same
startup notice text (including the explicit "Show this to the user" instruction).

The `information` field is part of the `ResourceResult` dataclass. Its docstring states:

> **information** — if non-empty, the AI must show this to the user verbatim before anything else.

This is the reliable fallback channel for Claude and other clients that ignore the MCP `instructions`
field. Since `nef_read_me_first()` is called first in every session, it ensures the user sees the
sandbox status even when `instructions` is ignored.

---

## Summary of channels

Both channels contain the same message with explicit instructions for the AI to show it to the user:

| Channel | Where set | When seen by AI | Reliability |
|---|---|---|---|
| `instructions` field | `server_lib._build_server()` | MCP handshake (connection time) | Only if client honours MCP `instructions` |
| `information` field in `NefStartupResult` | `mcp_commands.nef_read_me_first()` | When AI calls `nef_read_me_first()` (first tool call) | Reliable — Claude and others always call this |

The redundancy ensures the user sees critical sandbox information regardless of which MCP features
the client supports.
