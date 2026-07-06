# Plan: Wire skills subdirectory into MCP server + fix broken URIs

## Context

The resource layout was refactored: skills moved from top-level `.md` files in
`resources/mcp_server/` into `resources/mcp_server/skill/`. Three resource files
were also renamed. The server code only iterates top-level `.md` files, so skills
are currently invisible to MCP clients. Several URI references in the docs now
point to names that no longer exist.

---

## URI rename map (old → new)

| Old URI | New URI | Cause |
|---------|---------|-------|
| `nef://nef` | `nef://nef-file-format` | file renamed |
| `nef://nmr-data` | `nef://nef-nmr-data-model` | file renamed |
| `nef://star` | `nef://star-file-format` | file renamed |
| `nef://skills` (plural) | `nef://skill` (singular, index) or `nef://skill/<name>` | skills moved to subdirectory; `nef://skill` is now index |

---

## Changes

### 1. `src/nef_pipelines/tools/ai/mcp_lib.py`

Add a `_SKILLS` path constant after `_RESOURCES`:

```python
_SKILLS = _RESOURCES / "skill"
```

Export it so `server_lib.py` can import it.

### 2. `src/nef_pipelines/tools/ai/server_lib.py`

Import `_SKILLS` alongside `_RESOURCES`.

In `_build_server()`, after the existing resource registration loop, add a second
loop for skills. Use `nef://skill/{name}` as the URI:

```python
for md_file in sorted(_SKILLS.iterdir(), key=lambda f: f.name):
    if not md_file.name.endswith(".md"):
        continue
    name = _get_resource_name_from_filename(md_file.name)
    description = _get_resource_description_from_filename(md_file.name)
    uri = f"nef://skill/{name}"

    def _make_reader(f):
        def _reader() -> str:
            return f.read_text()
        return _reader

    mcp_server.resource(uri, mime_type="text/markdown", description=description)(
        _make_reader(md_file)
    )
```

This registers skills as native MCP resources (for clients that support the
resources protocol) and they automatically appear in `nef_resources_list` /
`nef_resources_read` via the existing `_NefResourcesAsTools` fallback (for
clients that don't).

### 3. `src/nef_pipelines/resources/mcp_server/skill - index of available expert workflow skills.md`

Create a new top-level resource file that serves as the skills index, registered
as `nef://skill`:

```markdown
# Expert Workflow Skills

NEF-Pipelines includes expert workflow guides ("skills") that provide detailed
guidance on complex tasks. **Always read the relevant skill before attempting
non-trivial workflows.**

## Available Skills

- **`nef://skill/nef-pipelines-howto`** — How to use NEF-Pipelines commands in a pipeline

  The canonical guide to pipeline construction: command chaining, stdin/stdout
  flow, frame/loop creation, the `@file:col` reference syntax, value specs, and
  the NEF data model. Read this before building any multi-step pipeline.

- **`nef://skill/adhoc-data`** — Ad-hoc frame/loop/column building from columnar files

  When no transcoder exists for your input format, this guide shows how to
  construct NEF frames and loops manually from CSV/TSV files using `frames create`,
  `loops create`, and `columns insert`.

## How to Access

**If your client supports native MCP resources:**
- Read skills directly via `nef://skill/<name>` URIs

**Fallback (tool-based access):**
- `nef_resources_list()` — list all resources and skills
- `nef_resources_read('nef://skill/<name>')` — fetch a specific skill by URI
```

This file will be registered as `nef://skill` by the top-level resource loop in
`server_lib.py`, providing a navigable index before users dive into specific skills.

### 4. `src/nef_pipelines/resources/preamble.md`

Rewrite to reflect the new structure. Split into **Resources** and **Skills**
sections. Cover both access paths (native `nef://` and tool fallback):

```markdown
Tools for composing and running NEF-Pipelines NMR data manipulation pipelines.

**Start here - every session:**
Read `nef://readme` before anything else.

**Resources** — read via `nef://<name>` or `nef_resources_read('<name>')`:
- `nef://readme`             - overview, data model, command/transcoder catalogue
- `nef://cli-idioms`         - option names, selectors, escape syntax
- `nef://nef-file-format`    - NEF STAR dialect (namespaces, saveframe categories, loop tags)
- `nef://nef-nmr-data-model` - NMR domain model (4-string identifier, atom names)
- `nef://star-file-format`   - foundational STAR syntax (rare; only when nef-file-format references it)

**Skills** — expert workflow guides; read before any non-trivial task:
- `nef://skill` - index of available skills; start here to find the right guide
  - `nef://skill/nef-pipelines-howto` - how to use NEF-Pipelines commands in a pipeline
  - `nef://skill/adhoc-data`          - ad-hoc frame/loop/column building from columnar files

If `nef://` URIs are not supported, use:
  `nef_resources_list()` to list all resources and skills
  `nef_resources_read('<uri>')` to fetch any resource or skill by URI

**MCP Tools:**
1. `nef_list_commands()`         - enumerate available commands
2. `nef_get_command_help(...)`   - full `--help` for one command
3. `nef_execute_pipeline(...)`   - run one or more steps as a pipeline
4. `nef_upload_file(...)`        - write a text file into the working directory
5. `nef_download_file(...)`      - read a text file from the working directory
6. `nef_list_files()`            - list files in the working directory
```

### 5. Fix broken URI references in doc files

Apply the URI rename map to all files that contain stale references:

**`resources/mcp_server/readme -  README for the NEF-PIpelines MCP server.md`:**
- `nef://nef` → `nef://nef-file-format` (lines 9, 22)
- `nef://nmr-data` → `nef://nef-nmr-data-model` (lines 10, 103)
- `nef://star` → `nef://star-file-format` (line 11)
- `nef://skills` → `nef://skill/adhoc-data` (line 139)
- `nef://skill` (line 12) → keep as `nef://skill` (now refers to the skills index)

**`resources/mcp_server/nef-nmr-data-model - NEF Molecular Structure and NMR Data Model.md`:**
- `nef://nef` → `nef://nef-file-format` (line 306)
- `nef://star` → `nef://star-file-format` (line 308)

**`resources/mcp_server/nef-file-format - NEF STAR dialect reference - read before working with NEF files.md`:**
- `nef://nmr-data` → `nef://nef-nmr-data-model` (line 517)

**`resources/mcp_server/skill/nef-pipelines-howto - how to use the NEF-Pipelines commands in a pipeline.md`:**
- `nef://skills` → `nef://skill/adhoc-data` (lines 186, 265, 336)

---

## Verification

```bash
# Skills appear as registered resources
python -c "
from nef_pipelines.tools.ai.server_lib import _build_server
s = _build_server()
print([r for r in s._resource_manager._resources])
"

# All tests pass
python -m pytest src/nef_pipelines/tests/ -q -k "mcp or ai"
```
