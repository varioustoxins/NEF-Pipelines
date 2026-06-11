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
2. `nef_get_command_help(...)`   - full help for one command
3. `nef_execute_pipeline(...)`   - run one or more steps as a pipeline
4. `nef_upload_file(...)`        - write a text file into the working directory
5. `nef_download_file(...)`      - read a text file from the working directory
6. `nef_list_files()`            - list files in the working directory
7. `nef_import_files()`          - open file picker for the user to choose files to copy into the working directory
8. `nef_change_sandbox()`        - open directory picker for the user to change the sndabox / working directory
