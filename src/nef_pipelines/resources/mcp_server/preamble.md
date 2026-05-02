Tools for composing and running NEF Pipelines NMR data pipelines.

**Start here — every session:**
Call `nef_read_me_first()` before anything else. It returns this orientation plus
instructions for what to read next. Skip it only if you have already seen it this session.

**Resources** — read via `nef://<name>` (if supported) or `nef_read_resource('<name>')`:
- `readme`     — overview, data model, command/transcoder catalogue
- `skill`      — workflow guidance: discovery → build → verify
- `cli-idioms` — option names, selectors, escape syntax (the "how do I express X?" reference)
- `nef`        — NEF STAR dialect (namespaces, saveframe categories, loop tags)
- `nmr-data`   — NMR domain model (4-string identifier, atom names, pseudoatoms)
- `star`       — foundational STAR syntax (rare; only when `nef` references it)

**Tools:**
0. `nef_read_me_first()`        — orientation (call first; skip if seen this session)
1. `nef_read_resource(name)`    — fetch any resource document by name
2. `nef_list_commands()`        — enumerate available commands
3. `nef_get_command_help(...)`  — full `--help` for one command
4. `nef_execute_pipeline(...)`  — run one or more steps as a pipeline
