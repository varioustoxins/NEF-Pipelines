# Plan: Require `"nef"` prefix in `nef_execute_pipeline` steps

## Context

`nef_execute_pipeline` currently accepts steps like `["frames", "list"]` and invokes them
via `runner.invoke(_nef_app.app, args)`. The upcoming `--sandbox-path` global option on
the root `nef` command needs every invocation to go through the root app so the option
can be injected. Making `"nef"` mandatory as the first element of every step:

1. Makes the AI's intent explicit (these are `nef` CLI commands, not arbitrary shell)
2. Gives the execution layer a clean hook to inject `["--sandbox-path", path]` before
   the subcommand args when that feature arrives
3. Matches real shell usage (`nef frames list` not `frames list`)

---

## Files to Modify

All paths relative to `/Users/garythompson/Dropbox/nef_pipelines/nef_pipelines/`.

| File | Change |
|------|--------|
| `src/nef_pipelines/tools/ai/mcp_commands.py` | Validate `"nef"` prefix; strip before invoke |
| `src/nef_pipelines/tests/ai/test_nef_mcp_server.py` | Prepend `"nef"` to all step lists; add error-case test |
| `src/nef_pipelines/tests/ai/test_nef_mcp_server_integration.py` | Prepend `"nef"` to all step lists |
| `src/nef_pipelines/resources/mcp_server/cli-idioms - NEF-Pipelines CLI common idioms and patterns.md` | Update all pipeline examples |

---

## Step 1 — `mcp_commands.py`: validate and strip the `"nef"` prefix

In `nef_execute_pipeline`, after the `if not args: continue` guard, add:

```python
if args[0] != "nef":
    result.stderr.append(
        f"each step must start with 'nef' — got {args!r}. "
        'Example: ["nef", "frames", "list"]'
    )
    result.exit_code = 1
    break

step_result = _safe_execute_step(args[1:], result.stdout)   # strip leading "nef"
```

Remove the existing unconditional `step_result = _safe_execute_step(args, result.stdout)` line.

`_execute_command_in_process` and `_safe_execute_step` in `mcp_lib.py` are **unchanged** —
they already receive only the subcommand args and pass them straight to `runner.invoke`.

---

## Step 2 — `test_nef_mcp_server.py`: update all steps + add error test

Prepend `"nef"` to every inner step list throughout the file, e.g.:

```python
# before
nef_execute_pipeline(steps=[["frames", "list"]], nef_input=simple_nef_data)
# after
nef_execute_pipeline(steps=[["nef", "frames", "list"]], nef_input=simple_nef_data)
```

Add one new test in the `# --- nef_execute_pipeline ---` section:

```python
def test_nef_execute_pipeline_step_missing_nef_prefix():
    """\
    Test nef_execute_pipeline returns an error if a step does not start with 'nef'.
    """
    result = nef_execute_pipeline(steps=[["frames", "list"]])
    EXPECTED = PipelineResult(
        steps=[["frames", "list"]],
        stdout="",
        stderr=["each step must start with 'nef' — got ['frames', 'list']. "
                'Example: ["nef", "frames", "list"]'],
        exit_code=1,
        steps_completed=0,
    )
    assert result == EXPECTED
```

---

## Step 3 — `test_nef_mcp_server_integration.py`: update all steps

Same mechanical change — prepend `"nef"` to every step list in the integration tests.

---

## Step 4 — cli-idioms resource: update all pipeline examples

In `cli-idioms - NEF-Pipelines CLI common idioms and patterns.md`, update the mapping
table and all code examples to show `"nef"` as the first element:

```markdown
| Shell pipeline              | MCP equivalent                            |
|-----------------------------|-------------------------------------------|
| `nef stream my.nef`         | `['nef', 'stream', 'my.nef']`             |
| `nef frames delete ccpn_*`  | `['nef', 'frames', 'delete', 'ccpn_*']`  |
| `nef save result.nef`       | `['nef', 'save', 'result.nef']`           |
```

And the multi-step example:

```python
nef_execute_pipeline([
    ['nef', 'stream', 'my.nef'],
    ['nef', 'frames', 'delete', 'ccpn_*'],
    ['nef', 'save', 'result.nef'],
])
```

---

## Verification

```
.venv/bin/python -m pytest src/nef_pipelines/tests/ai/test_nef_mcp_server.py -k pipeline -v
.venv/bin/python -m pytest src/nef_pipelines/tests/ai/ -v
```

All existing pipeline tests should pass with the `"nef"` prefix added.
The new `test_nef_execute_pipeline_step_missing_nef_prefix` test verifies the error path.
