Tools for composing and running NEF-Pipelines NMR data manipulation pipelines.

**Start here - every session:**
Read the resource `readme` next before anything else after reading the .

**Resources** - read via `nef://<name>` (using resource if supported)
  or `nef-resources_list()` & `nef_resources_read('<name>')` [fallback]:
- `readme`     - overview, data model, command/transcoder catalogue
- `skills`     - workflow guidance: discovery → build → verify
- `cli-idioms` - option names, selectors, escape syntax (the "how do I express X?" reference)
- `nef`        - NEF STAR dialect (namespaces, saveframe categories, loop tags)
- `nmr-data`   - NMR domain model (4-string identifier, atom names, pseudoatoms)
- `star`       - foundational STAR syntax (rare; only when `nef` references it)

**MCP Tools:**
1. `nef_list_commands()`         - enumerate available commands
2  `nef_get_command_help(...)`   - full `--help` for one command
3  `nef_execute_pipeline(...)`   - run one or more steps as a pipeline
4  `nef_upload_file(...)`         - write a text file into the working directory
5. `nef_download_file(...)`      - read a text file from the working directory
6. `nef_list_files()`            - list files in the working directory
