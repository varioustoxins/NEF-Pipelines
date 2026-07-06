# Plan: Replace custom interleaved-arg parser — registered flags + track_order + gnu_getopt

## Context

`_parse_interleaved_column_specification_from_args_or_exit_error` in `columns_cli_lib.py` is a
hand-rolled token scanner with known defects (silently ignores unknown `-x` options, buggy
combined-flag detection, accepts `--before/--after/--at` with no anchor). Replace it with a
Typer/Click-native approach, scope `insert.py` only.

**The design:**

1. Register `--before/-b`, `--after/-a`, `--at/-@` as real Typer options with
   `callback=track_order`. Click then validates unknown options / missing anchors natively.
2. In `track_order`:
   - **(a)** on the *first* call, build the `gnu_getopt` parser strings from the live context
     (`ctx.command.params`) — the context is the single source of truth.
   - **(b)** run `getopt.gnu_getopt` on the command's argv. getopt returns options-with-values
     and positional arguments *separately*.
   - **(c)** unify options and arguments back with their positions by **searching argv** for
     each item getopt returned (getopt drops the interleaving; argv search restores it).
   - **(d)** save that single ordered structure (a `List[OrderedArg]` of flags *and* col
     specs, in argv order) in `ctx`. This is built once, on the first callback call.
3. In `insert`, walk that one ordered structure to emit per-group instructions.

> Note: the design originally had a separate per-param offset structure (step "e"), but it is
> redundant — the ordered `sequence` already interleaves flags with col specs, which is all
> `insert` needs. Dropped to keep a single source and the simplest consumer.

**Critical mechanical facts (traced against all 10 parametrized tests + error cases):**
- Must use `getopt.gnu_getopt` (intermixes options after positionals), **never** `getopt.getopt`
  (stops at first positional → would swallow `col --before anchor`).
- `_get_argv()` wraps `sys.argv[1:]`, mocked in `run_and_report` so getopt parses exactly what
  Click parses. This is parsing-by-getopt then position-by-search — NOT a manual token walk.
- The sequence is built on the first callback call **regardless of value**, so no-flag
  invocations build it too and `insert` has a single path (no `ctx.args` fallback).

---

## Design

### Step 1 — flags on `insert` signature

```python
before: Optional[str] = typer.Option(None, "--before", "-b", callback=track_order, metavar="ANCHOR")
after:  Optional[str] = typer.Option(None, "--after",  "-a", callback=track_order, metavar="ANCHOR")
at:     Optional[str] = typer.Option(None, "--at",     "-@", callback=track_order, metavar="ANCHOR")
```

`context_settings` → `{"allow_extra_args": True}` (drop `ignore_unknown_options`).
`-@` as the short form of `--at` is confirmed valid (already tested) — no fallback needed.

### Step 2 — infrastructure

```python
@dataclass
class OrderedArg:
    """One item from the command line, in argv order. The ordered sequence is a
    List[OrderedArg] holding both placement flags and col specs."""
    offset: int
    kind: str               # "flag" or "col"
    name: Optional[str]     # param variable name for flags ("before"/"after"/"at"); None for cols
    value: str              # anchor for flags; raw col-spec token for cols

def _get_argv() -> List[str]:
    return sys.argv[1:]

def _trim_command_prefix(argv, ctx):
    """Drop leading subcommand-name tokens (e.g. 'columns', 'insert') so getopt sees only
    the insert-level args. In CliRunner tests the mocked argv has no command names → no-op."""
    cmd_path = []
    c = ctx
    while c is not None:
        if c.info_name:
            cmd_path.insert(0, c.info_name)
        c = c.parent
    idx = 0
    for name in cmd_path:
        for i in range(idx, len(argv)):
            if argv[i] == name:
                idx = i + 1
                break
    return argv[idx:]

def _build_getopt_strings(ctx):
    """(a) Build gnu_getopt short/long strings from the live context params."""
    short_opts, long_opts = "", []
    for param in ctx.command.params:
        if not isinstance(param, click.Option):
            continue
        requires_arg = not param.is_flag
        for opt in param.opts:
            if opt.startswith("--"):
                long_opts.append(opt[2:] + ("=" if requires_arg else ""))
            elif opt.startswith("-"):
                short_opts += opt[1:] + (":" if requires_arg else "")
    return short_opts, long_opts

def _placement_token_map(ctx):
    """Map every spelling of the placement flags to the param's variable name, derived
    from the live context. Placement params are identified by name membership in
    _FLAG_NAME_TO_PLACEMENT (the one semantic table); their spellings (--before, -b, ...)
    come from param.opts so they are never hardcoded. Replaces _POSITION_OPTS + _CANONICAL.

    (Identifying by `param.callback is track_order` is avoided: Typer may wrap the callback,
    so callback identity is not reliable; param.name is stable.)
    """
    return {
        opt: param.name
        for param in ctx.command.params
        if isinstance(param, click.Option) and param.name in _FLAG_NAME_TO_PLACEMENT
        for opt in param.opts
    }
```

### Step 3 — `track_order` callback

```python
def track_order(ctx, param, value):
    # Build the ordered structure once, on the first callback call (regardless of value,
    # so no-flag invocations build it too). Subsequent calls are no-ops that just return
    # value — the ordering is fully captured in ctx.obj["sequence"].
    if ctx.obj is None:
        ctx.obj = {}

    if "sequence" not in ctx.obj:
        argv = _trim_command_prefix(_get_argv(), ctx)
        short_opts, long_opts = _build_getopt_strings(ctx)
        placement_tokens = _placement_token_map(ctx)   # token -> param.name (e.g. "before")
        try:
            opts, positionals = getopt.gnu_getopt(argv, short_opts, long_opts)  # (b)
        except getopt.GetoptError:
            opts, positionals = [], []   # Click is the real validator; don't hard-exit

        # (c) unify by searching argv for each item's position
        items, used = [], set()
        for flag, val in opts:
            if flag in placement_tokens:
                for i, tok in enumerate(argv):
                    if i not in used and tok == flag and i + 1 < len(argv) and argv[i + 1] == val:
                        items.append(OrderedArg(i, "flag", placement_tokens[flag], val))
                        used.add(i)
                        break
        for col in positionals:
            for i, tok in enumerate(argv):
                if i not in used and tok == col:
                    items.append(OrderedArg(i, "col", None, col))
                    used.add(i)
                    break

        # (d) the one ordered structure: flags + col specs interleaved, in argv order
        ctx.obj["sequence"] = sorted(items, key=lambda e: e.offset)

    return value
```

### Step 4 — `_parse_ordered_col_instructions(ctx, ctx_args)` (single path, walks the sequence)

```python
_FLAG_NAME_TO_PLACEMENT = {
    "before": InsertPlacement.BEFORE,
    "after":  InsertPlacement.AFTER,
    "at":     InsertPlacement.AT,
}

def _parse_ordered_col_instructions(ctx, ctx_args):
    sequence = (ctx.obj or {}).get("sequence", [])   # List[OrderedArg], argv order
    pending, instructions = [], []
    for arg in sequence:
        if arg.kind == "col":
            prefix, specs = _peel_selector_prefix(arg.value)
            for spec in _split_on_column_specification_on_assignment_boundaries(specs):
                pending.append(prefix + spec)
        else:  # flag
            for col in pending:
                instructions.append((col, _FLAG_NAME_TO_PLACEMENT[arg.name], arg.value))
            pending = []
    for col in pending:
        instructions.append((col, InsertPlacement.APPEND, None))
    return instructions
```

`ctx_args` is retained in the signature (and used for error messages in `insert`) but the
ordering comes entirely from `ctx.obj["sequence"]`.

---

## Worked traces (CliRunner, `_get_argv` mocked to `args`)

- `["--in","-","--selector","myshifts.chemical_shift","new_col","--before","atom_name"]`
  → getopt: opts incl `("--before","atom_name")`, positionals `["new_col"]`
  → sequence `[OrderedArg(4,"col",None,"new_col"), OrderedArg(5,"flag","before","atom_name")]`
  → `[("new_col", BEFORE, "atom_name")]` ✓ (EXPECTED_BEFORE_ATOM)
- `["--in","-","--selector","myshifts.chemical_shift","new_col"]` (no flag)
  → sequence `[OrderedArg(4,"col",None,"new_col")]` → `[("new_col", APPEND, None)]` ✓
- `["...","flag=ok,ok","uncertainty=0.1,0.05"]` → both cols, both APPEND, in order ✓
- `["...","--at","3"]` with col `new_col` → `[("new_col", AT, "3")]` ✓

---

## Files changed

### `columns_cli_lib.py`
- Add `import sys`, `import getopt`, `import click`, `from dataclasses import dataclass`
- Add `OrderedArg` dataclass; `_get_argv`, `_trim_command_prefix`,
  `_build_getopt_strings`, `_placement_token_map`, `track_order`, `_FLAG_NAME_TO_PLACEMENT`,
  `_parse_ordered_col_instructions`
  (`_FLAG_NAME_TO_PLACEMENT` is module-level; `_placement_token_map` and `track_order`
  reference it at call time, so file order does not matter)
- No hardcoded flag-spelling tables (`_POSITION_OPTS` / `_CANONICAL` are *not* introduced —
  spellings derive from `param.opts`)
- Remove `_parse_interleaved_column_specification_from_args_or_exit_error`, `POSITION_FLAGS`,
  `_POSITION_SHORT_CHARS`
- All other functions unchanged

### `insert.py`
- Add `before`/`after`/`at` params with `callback=track_order`; import `track_order` and
  `_parse_ordered_col_instructions` (replacing the old import)
- `context_settings` → `{"allow_extra_args": True}`
- Call site → `_parse_ordered_col_instructions(ctx, ctx.args)`
- General structure of `insert()` unchanged

### `test_lib.py` (`src/nef_pipelines/lib/test_lib.py`)
Wrap the `runner.invoke` call in **both** branches of `run_and_report` with a patch of
`columns_cli_lib._get_argv` → `args`, so CliRunner tests exercise the real getopt+search path:

```python
from unittest import mock as _mock

def _columns_argv_patch(args):
    try:
        import nef_pipelines.tools.columns.columns_cli_lib as _ccl
        if hasattr(_ccl, "_get_argv"):
            return _mock.patch.object(_ccl, "_get_argv", return_value=list(args))
    except ImportError:
        pass
    return contextlib.nullcontext()

# both branches:
with _columns_argv_patch(args):
    result = runner.invoke(typer_app, args, input=input)
```

### `test_insert.py`
One line: the local `app` registration drops `ignore_unknown_options` (the flags are now
registered, so they must be consumed by Click, not passed through):
```python
app.command(context_settings={"allow_extra_args": True})(insert)
```
No test cases change.

---

## Verification

```bash
nefl pytest nef_pipelines/src/nef_pipelines/tests/columns/test_insert.py -v
```

Empirical checks that only running confirms:
- `track_order` fires (incl. with `value=None` for absent flags) and `ctx.command.params` is
  populated mid-callback;
- `typer.Option(None, "--at", "-@")` registers at import (else drop `-@`);
- `--befroe col` → Click "No such option"; `--before` with no anchor → Click "Missing argument".
