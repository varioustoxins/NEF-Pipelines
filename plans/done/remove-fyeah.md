# Plan: Remove `fyeah` — replace with explicit `str.format()`

## Context

`fyeah` provides `f()`, which evaluates a string as a Python f-string at runtime
using the caller's local variables (via `inspect.currentframe().f_back.f_locals`).
This is essentially `eval()` on a string. The security risk: several commands accept
user-supplied filename/frame-name templates via CLI options (e.g. `--out`, `--frame`,
`--frame-name`). A user could inject `{__import__('os').system('...')}` in a template
and it would execute. Python's built-in `str.format()` only does variable substitution
— it cannot evaluate arbitrary Python expressions — making it a safe drop-in.

## Approach

Replace every `f(template)` with `template.format(var=var, ...)` passing **only the
variables that appear as `{name}` placeholders in the documented template**. This is
safer than `**locals()` (which would expose every variable in scope) and makes the
API contract explicit.

Remove `from fyeah import f` from each file.
Remove `f-yeah` from `requirements.txt`.

## Replacements (by call site)

### tools/simulate/peaks.py:150
```python
# before
frame_name = f(name_template_string)
# after  (default template: "synthetic_{spectrum}")
frame_name = name_template_string.format(spectrum=spectrum)
```

### tools/frames/tabulate.py:354
```python
# before
expanded_file_name = f(args.out)
# after  (template supports {entry}, {frame}, {loop})
expanded_file_name = args.out.format(entry=entry, frame=frame, loop=loop)
```

### tools/frames/rename.py:172
```python
# before
exit_error(f(msg))
# after  (msg uses {target_name}, {category_msg}, {entry}, {frames})
exit_error(msg.format(target_name=target_name, category_msg=category_msg, entry=entry, frames=frames))
```

### tools/frames/rename.py:240
```python
# before
msg = f(template)
# after  (template uses {target_name}, {distances}, {entry}, {table})
msg = template.format(target_name=target_name, distances=distances, entry=entry, table=table)
```

### tools/save.py:136
```python
# before
file_name = f(template)
# after  (default template: "{entry_id}.nef")
file_name = template.format(entry_id=entry_id)
```

### tools/save.py:171
```python
# before
header_text = f(HEADER)
# after  (HEADER = "{DELIMITER} {entry_id} {DELIMITER}")
header_text = HEADER.format(DELIMITER=DELIMITER, entry_id=entry_id)
```

### tools/fit/fit_lib.py:541
```python
# before
series_category = f(SERIES_DATA_CATEGORY)
# after  (SERIES_DATA_CATEGORY = "_{NAMESPACE}_series_data")
series_category = SERIES_DATA_CATEGORY.format(NAMESPACE=NAMESPACE)
```

### tools/shifts/average.py:88
```python
# before
frame_name = f(frame_name)
# after  (default template: "{entry_id}")
frame_name = frame_name.format(entry_id=entry_id)
```

### tools/shifts/average.py:193
```python
# before
msg = f(msg)
# after  — read surrounding code at implementation time to confirm template variables
msg = msg.format(...)   # TBD
```

### tools/simulate/unlabelling.py:759
```python
# before
frame_name = f(name_template_string)
# after  (default: "synthetic_{spectrum}_unlabelled_{residues}")
frame_name = name_template_string.format(spectrum=spectrum, residues=residues)
```

### transcoders/talos/importers/restraints.py:289
```python
# before
frame_name = f(frame_name)
# after  (default: "talos_restraints_{chain_code}_{angle}")
frame_name = frame_name.format(chain_code=chain_code, angle=angle)
```

### transcoders/talos/importers/secondary_structure.py:95
```python
# before
frame_name = f(frame_name)
# after  (default: "{chain_code}_talos")
frame_name = frame_name.format(chain_code=chain_code)
```

### transcoders/talos/importers/order_parameters.py:106-107
```python
# before
frame_name = f(frame_name)
frame_id = f(frame_name)
# after  (default: "{chain_code}_{element_1}{isotope_number_1}_{element_2}{isotope_number_2}")
frame_name = frame_name.format(chain_code=chain_code, element_1=element_1,
    isotope_number_1=isotope_number_1, element_2=element_2, isotope_number_2=isotope_number_2)
frame_id = frame_name  # already expanded above
```

### transcoders/nmrview/importers/peaks.py:465
```python
# before
new_entry_names.append(f(entry_name_template))
# after
new_entry_names.append(entry_name_template.format(file_name=file_name))
```

### transcoders/nmrview/exporters/sequences.py:226
```python
# before
return {chain_code: f(file_name_template) for chain_code in chain_codes}
# after
return {chain_code: file_name_template.format(chain_code=chain_code) for chain_code in chain_codes}
```

### transcoders/sparky/importers/peaks.py:186
```python
# before
frame_code = f(frame_code_template)
# after  (default: "sparky_{file_name}")
frame_code = frame_code_template.format(file_name=file_name)
```

### transcoders/xeasy/importers/peaks.py:109
```python
# before
frame_name = f(frame_name)
# after  (default: "xeasy_{file_name}")
frame_name = frame_name.format(file_name=file_name)
```

### transcoders/mars/importers/peaks.py:164
```python
# before
frame_code = f(frame_code_template)
# after  (default: "mars_{file_name}")
frame_code = frame_code_template.format(file_name=file_name)
```

### transcoders/nmrpipe/importers/peaks.py:143
```python
# before
new_name = f(entry_name_template)
# after
new_name = entry_name_template.format(file_name=file_name)
```

### transcoders/nmrstar/importers/shifts.py:743
```python
# before
msg = f(msg)
# after  (msg uses {missing_residue_table})
msg = msg.format(missing_residue_table=missing_residue_table)
```

### transcoders/echidna/importers/peaks.py:405
```python
# before
frame_code = f"{SPECTRUM_FRAME_CATEGORY}_{f(frame_name_template)}"
# after
frame_code = f"{SPECTRUM_FRAME_CATEGORY}_{frame_name_template.format(file_name=file_name)}"
```

### transcoders/deep/importers/peaks.py:191
```python
# before
new_name = f(entry_name_template)
# after
new_name = entry_name_template.format(file_name=file_name)
```

### transcoders/shifty/exporters/shifts.py:99
```python
# before
output_file = f(file_name_template)
# after  (default: "{nef_entry_id}_{chain_code}.shifty")
output_file = file_name_template.format(nef_entry_id=nef_entry_id, chain_code=chain_code)
```

### Test files (hardcoded strings — just remove the dependency)
```python
# test_secondary_structure.py:65,116
PATCHED_EXPECTED = EXPECTED.format(pred_4_path=pred_4_path)
PATCHED_EXPECTED = EXPECTED_FIRST_RESID_2.format(pred_4_path=pred_4_path)

# test_import_order_parameters.py:71
PATCHED_EXPECTED = EXPECTED.format(pred_4_path=pred_4_path)

# test_import_restraints.py:84,152
PATCHED_EXPECTED = EXPECTED.format(pred_4_path=pred_4_path)
PATCHED_EXPECTED = EXPECTED_CHI1.format(pred_4_path=pred_4_path)
```

## requirements.txt

Remove:
```
f-yeah~=0.3.0; python_version < "3.12.0"
f-yeah~=0.4.0; python_version >= "3.12.0"
```

## Note

A few call sites (rename.py:240, average.py:193) need the surrounding code read
before editing to confirm exact variable names. Do this during implementation.

## Verification

```bash
# Confirm no remaining fyeah references
grep -r "fyeah\|f-yeah" src/ requirements.txt

# Run full test suite
.venv39/bin/pytest  src/nef_pipelines/tests -q
.venv310/bin/pytest src/nef_pipelines/tests -q
.venv313/bin/pytest src/nef_pipelines/tests -q
.venv314/bin/pytest src/nef_pipelines/tests -q
```
