# Plan: Drop CommandResult and nef_execute_command

## Context

`nef_execute_command` is a thin MCP tool wrapping a single pipeline step. Since
`nef_execute_pipeline(steps=[["version"]])` does the same thing, the extra tool
adds surface area without meaningful benefit. Similarly `CommandResult` is only
used internally by private helpers; it can be replaced by returning `PipelineResult`
directly, leaving `PipelineResult` as the single exported result type.

## Changes

### `src/nef_pipelines/tools/ai/mcp_lib.py`
- Remove `CommandResult` dataclass entirely
- `_execute_command_in_process` returns a `PipelineResult` with:
  - `stdout` = command stdout
  - `stderr` = `[the_stderr]` (single-element list)
  - `exit_code` = exit code
  - `steps` = `[args]`
  - `steps_completed` = 1 if exit_code == 0, else 0
- Keep `PipelineResult` unchanged

### `src/nef_pipelines/tools/ai/mcp_commands_lib.py`
- Remove `CommandResult` from imports
- `_safe_execute_step` returns `PipelineResult`; error case also returns a `PipelineResult`
  with `exit_code=-1` and `stderr=["Exception: ..."]`
- In `nef_execute_pipeline` loop: `result.stderr.append(step_result.stderr[0] if step_result.stderr else "")`
- `nef_list_commands` and `nef_get_command_help`: access `result.stdout`, `result.exit_code`,
  `result.stderr[0]` instead of dict keys
- Remove `nef_execute_command` function and its `@mcp_tool` decorator entirely

### `src/nef_pipelines/tests/ai/test_nef_mcp_server.py`
- Remove `nef_execute_command` from imports
- Remove tests already covered by pipeline tests:
  - `test_nef_execute_command_version` → covered by `test_nef_execute_pipeline_step_failure` (uses version)
  - `test_nef_execute_command_with_nef_input` → covered by `test_nef_execute_pipeline_single_step`
  - `test_nef_execute_command_frames_list` → duplicate of above
  - `test_nef_execute_command_invalid` → covered by `test_nef_execute_pipeline_step_failure`
  - `test_nef_execute_command_returns_dict_structure` → covered by `test_nef_execute_pipeline_returns_dataclass_structure`
- Port test not yet covered: `test_nef_execute_command_help` (checks `["--help"]` returns
  help sections "Usage:", "Options", "General") → becomes `test_nef_execute_pipeline_help`
  using `nef_execute_pipeline(steps=[["--help"]])`

### `src/nef_pipelines/tests/lib/test_mcp_execution.py`
- `_execute_command_in_process` now returns `PipelineResult` — keep attribute access
  but update `test_execute_command_returns_command_result` to check `isinstance(result, PipelineResult)`
  and verify `result.stderr` is a list

## Verification

```
python -m pytest src/nef_pipelines/tests/ai/test_nef_mcp_server.py \
                 src/nef_pipelines/tests/lib/test_mcp_execution.py -x -q
```
