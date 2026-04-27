# Testing the NEF-Pipelines MCP Server

This guide covers testing the NEF-Pipelines MCP server. The server runs in-process via the
`nef ai server` subcommand — there is no separate launcher script.

## Prerequisites

```bash
# Install with MCP support
uv pip install -e ".[mcp]"

# Or install fastmcp directly into the existing environment
uv pip install fastmcp
```

Confirm the entry point exists:

```bash
nef ai server --help
```

## What the server exposes

**4 tools:**

| Tool | Purpose |
|---|---|
| `nef_list_commands(command_pattern="*")` | Markdown table of available commands (filterable) |
| `nef_get_command_help(command_pattern="*", group_by_category=False)` | Full markdown help for one or more commands |
| `nef_execute_command(args, nef_input="")` | Run a single CLI step in-process |
| `nef_execute_pipeline(steps, nef_input="", verbose=False)` | Run a multi-step pipeline with stdout→stdin chaining |

**7 markdown resources** (live in `src/nef_pipelines/resources/mcp_server/`, exposed as `nef://<name>`):

| URI | Purpose |
|---|---|
| `nef://preamble` | Short orientation (also delivered as the server's `instructions`) |
| `nef://readme` | High-level overview, data model, command/transcoder catalogue |
| `nef://skill` | Workflow guidance — discovery → build → verify |
| `nef://cli-idioms` | Option / selector / escape syntax across commands |
| `nef://nef` | NEF STAR dialect reference |
| `nef://nmr-data` | NMR domain model (4-string identifier, atom names, pseudoatoms) |
| `nef://star` | Foundational STAR syntax |

## Method 1: MCP Inspector (recommended)

The MCP Inspector is a web UI for exercising MCP servers interactively.

```bash
# Install once
npm install -g @modelcontextprotocol/inspector

# Run the server through the inspector
cd /Users/garythompson/Dropbox/nef_pipelines/nef_pipelines
npx @modelcontextprotocol/inspector .venv311/bin/nef ai server
```

The inspector will:
1. Spawn `nef ai server` (stdio transport)
2. Open a browser UI
3. Let you list/call tools and read resources
4. Show the request/response JSON for each call

### Tool calls to try

**`nef_list_commands`** — markdown table of commands

```json
{ "command_pattern": "*" }
```
```json
{ "command_pattern": "*sparky*" }
```

Expected: a markdown table with `Command | Category | Description` columns.

**`nef_get_command_help`** — full help

```json
{ "command_pattern": "save", "group_by_category": false }
```
```json
{ "command_pattern": "*sparky*import*", "group_by_category": false }
```
```json
{ "command_pattern": "*sparky*", "group_by_category": true }
```

Expected: full markdown help; never a table (use `nef_list_commands` for that).

**`nef_execute_command`** — single command

```json
{ "args": ["help", "about"], "nef_input": "" }
```
```json
{ "args": ["frames", "list"], "nef_input": "<paste NEF text here>" }
```

Expected: `{ "stdout": "...", "stderr": "...", "exit_code": 0, "success": true }`.

**`nef_execute_pipeline`** — chained steps

```json
{
  "steps": [
    { "args": ["header"] },
    { "args": ["fasta", "import", "sequence", "test_data.fasta"] },
    { "args": ["save", "-"] }
  ],
  "nef_input": ""
}
```

Expected: chained stdout in `stdout`, plus `step_results` listing each step's outcome and
`failed_step` (`null` on success, step number on failure).

### Resource reads

In the inspector, switch to the *Resources* tab and read each `nef://<name>` URI listed above.
All 7 should resolve and return non-empty markdown.

## Method 2: Claude Code (CLI) — already configured

The repo ships a `.mcp.json` at the project root. Claude Code reads it automatically when you
start a session in this directory — no further setup is needed.

```json
{
  "mcpServers": {
    "nef-pipelines": {
      "command": "/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/.venv311/bin/nef",
      "args": ["ai", "server"]
    }
  }
}
```

To confirm the server is active in a Claude Code session, type `/mcp` — `nef-pipelines` should
appear in the list.

Sample prompts once connected:

- "What NEF pipeline commands are available?" → `nef_list_commands`
- "Show me detailed help for the save command." → `nef_get_command_help`
- "List all sparky commands." → `nef_get_command_help` with pattern
- "Run frames tabulate on this NEF file." → `nef_execute_command`

## Method 2b: Claude Desktop

Claude Desktop uses a separate JSON config file. If you have Claude Desktop installed, the config
lives at:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

This file does **not** exist by default — you must create it. Add (or merge) the server entry:

```json
{
  "mcpServers": {
    "nef-pipelines": {
      "command": "/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/.venv311/bin/nef",
      "args": ["ai", "server"]
    }
  }
}
```

Then quit and relaunch Claude Desktop (not just close the window). It will spawn the server and
discover the tools/resources automatically. If you don't have Claude Desktop installed, skip this
section — Claude Code via `.mcp.json` is sufficient.

## Method 3: Direct Python testing

The MCP-tool functions live in `nef_pipelines.tools.ai.mcp_commands_lib` and can be called
without a transport for quick smoke testing:

```python
from nef_pipelines.tools.ai.mcp_commands_lib import (
    nef_list_commands,
    nef_get_command_help,
    nef_execute_command,
    nef_execute_pipeline,
)

# Markdown command table
result = nef_list_commands("*save*")
print(result["success"], result["commands_table"][:300])

# Full help
result = nef_get_command_help("save")
print(result["success"], result["help_text"][:300])

# Single command
result = nef_execute_command(["help", "about"])
print(result["success"], result["exit_code"], result["stdout"][:200])

# Pipeline
result = nef_execute_pipeline([
    {"args": ["header"]},
    {"args": ["save", "-"]},
])
print(result["success"], len(result["step_results"]))
```

## Method 4: Tests

The test suite covers both library-level behaviour and FastMCP integration:

```bash
# Library functions (in-process execution, command parsing, pipeline chaining)
.venv311/bin/python -m pytest src/nef_pipelines/tests/ai/test_nef_mcp_server.py -q

# FastMCP integration (resource URIs, tool registration, end-to-end calls)
.venv311/bin/python -m pytest src/nef_pipelines/tests/ai/test_nef_mcp_server_integration.py -q
```

## Debugging tips

**Verify the server boots cleanly**

```bash
.venv311/bin/nef ai server </dev/null
# expect FastMCP banner + "Starting MCP server 'nef-pipelines' with transport 'stdio'"
# Ctrl-C to exit
```

**HTTP transport (useful for browser-based clients)**

```bash
nef ai server --transport streamable-http --host 127.0.0.1 --port 8000
```

**Verify the in-process executor works**

```bash
python -c "
from nef_pipelines.tools.ai.mcp_commands_lib import nef_execute_command
r = nef_execute_command(['help', 'about'])
print('success:', r['success'], 'exit:', r['exit_code'])
print(r['stdout'][:200])
"
```

**Verify all resource URIs resolve as expected**

```bash
python -c "
from nef_pipelines.tools.ai.mcp_commands_lib import _RESOURCES, resource_name
for f in sorted(_RESOURCES.iterdir()):
    if f.name.endswith('.md'):
        print('nef://' + resource_name(f.name))
"
```

You should see seven URIs: `nef://cli-idioms`, `nef://nef`, `nef://nmr-data`, `nef://preamble`,
`nef://readme`, `nef://skill`, `nef://star`.

## Tool behaviour reference

### `nef_list_commands`

- Returns a **markdown table** (`Command | Category | Description`)
- Parameters:
  - `command_pattern` (string, default `"*"`) — supports wildcards and comma-separated lists
- Wraps `nef help commands --display=table --format=markdown <pattern>`

### `nef_get_command_help`

- Returns **full markdown help** for the matched command(s)
- Parameters:
  - `command_pattern` (string, default `"*"`)
  - `group_by_category` (bool, default `false`) — adds category headings
- Wraps `nef help commands --display=help --format=markdown [--group-by-category] <pattern>`

### `nef_execute_command`

- Executes one CLI command in-process via Typer's `CliRunner`
- Parameters:
  - `args` (list of strings) — tokens following `nef`, e.g. `["frames", "list"]`
  - `nef_input` (string) — optional NEF content; written to a temp file and passed via `--in`
- Returns `{stdout, stderr, exit_code, success}`

### `nef_execute_pipeline`

- Chains multiple commands; each step's stdout becomes the next step's input
- Parameters:
  - `steps` — list of `{"args": [...]}` dicts
  - `nef_input` — optional seed for the first step
  - `verbose` — include per-step stdout/lengths in `step_results`
- Returns `{stdout, stderr, exit_code, success, step_results, failed_step}`
- Stops on first failing step; `failed_step` reports its index (1-based)

## Common issues

**`No module named 'mcp'` / `No module named 'fastmcp'`**
- Install: `uv pip install fastmcp` (or `uv pip install -e ".[mcp]"`)
- Verify: `python -c "from fastmcp import FastMCP; print('ok')"`

**`AttributeError: 'NoneType' object has no attribute 'add_typer'`**
- This happens if you import a `tools.*` submodule before `create_nef_app()` has run.
- Use the public entry points (`nef ai server`, `nef_pipelines.tools.ai.mcp_commands_lib.*`)
  rather than importing inner submodules directly.

**Resource URIs `nef://cli-idioms` or `nef://nmr-data` 404**
- The filename → URI parser splits on `" - "` (space-hyphen-space). Resources whose names
  contain hyphens (`cli-idioms`, `nmr-data`) require this — older logic that split on plain
  `-` truncates them to `cli` / `nmr`. If you see truncation, the parser in
  `mcp_commands_lib.py` has regressed.

**Claude Desktop doesn't show the tools**
- Validate `claude_desktop_config.json` parses as JSON
- Confirm the `command` path points to a working `nef` binary in a venv with `fastmcp` installed
- Quit and relaunch Claude Desktop (not just close the window)
- Inspect Claude Desktop logs for stderr from the spawned server
