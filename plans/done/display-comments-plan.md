# Display Command Comment Strategy Plan

Using `multi_frame_test.nef` which contains:
- Frame: `nef_molecular_system` with frame tags (sf_category, sf_framecode) and loop `nef_sequence` (5 columns, 3 rows)
- Frame: `ccpn_additional_data_1` with frame tags and loop `ccpn_data` (2 columns, 2 rows)
- Frame: `ccpn_additional_data_2` with frame tags and loop `ccpn_data` (2 columns, 2 rows)

## Case 1: No selector (all complete frames)

**Selector:** `--in multi_frame_test.nef` (no selector)

**Expected output:**
```
save_nef_molecular_system

   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system

loop_
   _nef_sequence.index
   _nef_sequence.chain_code
   _nef_sequence.sequence_code
   _nef_sequence.residue_name
   _nef_sequence.linking

  1   A   1   ALA   start
  2   A   2   GLY   middle
  3   A   3   VAL   end

stop_

save_

save_ccpn_additional_data_1

   _ccpn_additional_data.sf_category   ccpn_additional_data
   _ccpn_additional_data.sf_framecode  ccpn_additional_data_1

loop_
   _ccpn_data.key
   _ccpn_data.value

  frame1_key1   frame1_value1
  frame1_key2   frame1_value2

stop_

save_

save_ccpn_additional_data_2

   _ccpn_additional_data.sf_category   ccpn_additional_data
   _ccpn_additional_data.sf_framecode  ccpn_additional_data_2

loop_
   _ccpn_data.key
   _ccpn_data.value

  frame2_key1   frame2_value1
  frame2_key2   frame2_value2

stop_

save_
```

**Comments:** None - showing complete frames, valid NEF output

**COOMENT** correct
---

## Case 2: One complete frame

**Selector:** `molecular_system`

**Expected output:**
```
save_nef_molecular_system

   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system

loop_
   _nef_sequence.index
   _nef_sequence.chain_code
   _nef_sequence.sequence_code
   _nef_sequence.residue_name
   _nef_sequence.linking

  1   A   1   ALA   start
  2   A   2   GLY   middle
  3   A   3   VAL   end

stop_

save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...
```

**Comments:** None - showing complete frame

**COMMENT** changed

---

## Case 3: One complete loop from a frame

**Selector:** `molecular_system.sequence`

**Expected output:**
```
# save_nef_molecular_system

# frame tags ...

loop_
   _nef_sequence.index
   _nef_sequence.chain_code
   _nef_sequence.sequence_code
   _nef_sequence.residue_name
   _nef_sequence.linking

  1   A   1   ALA   start
  2   A   2   GLY   middle
  3   A   3   VAL   end

stop_

# save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...
```

**Comments:**
- `# save_nef_molecular_system` - frame start (commented because showing partial frame)
- `# frame tags ...` - frame tags hidden
- `# save_` - frame end (commented)

**COMMENTS** changed

---

## Case 4: Specific columns from a loop

**Selector:** `molecular_system.sequence:chain_code,residue_name`

**Expected output:**
```
# save_nef_molecular_system

# frame tags ...

loop_
   _nef_sequence.chain_code
   _nef_sequence.residue_name
   # more columns...

  A   ALA
  A   GLY
  A   VAL

stop_

# save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...
```

**Comments:**
- `# save_nef_molecular_system` - frame start (commented, partial frame)
- `# frame tags ...` - frame tags hidden
- Loop structure NOT commented (showing complete rows, just subset of columns)
- `# save_` - frame end (commented)

**COMMENT changed, question about column headers answered

**Question:** Should we show commented loop header with ALL columns to show structure?


---

## Case 5: Frame tags only (all tags)

**Selector:** `molecular_system:sf_category,sf_framecode`

**Expected output:**
```
# save_nef_molecular_system

   _nef_molecular_system.sf_category   nef_molecular_system
   _nef_molecular_system.sf_framecode  nef_molecular_system

# loop nef_sequence ...

# save_

# frame ccpn_additional_data_1 ...
# frame ccpn_additional_data_2 ...
```

**Comments:**
- `# save_nef_molecular_system` - frame start (commented, partial frame)
- `# loop nef_sequence ...` - entire loop hidden (no underscore prefix)
- `# save_` - frame end (commented)
- No `# more frame tags...` because showing ALL frame tags


**COMMENT** changed
---

## Case 6: Partial frame tags across multiple frames

**Selector:** `:sf_category`

**Expected output:**
```
# save_nef_molecular_system

   _nef_molecular_system.sf_category   nef_molecular_system
   # more frame tags...

# loop nef_sequence ...

# save_

# save_ccpn_additional_data_1

   _ccpn_additional_data.sf_category   ccpn_additional_data
   # more frame tags...

# loop ccpn_data ...

# save_

# save_ccpn_additional_data_2

   _ccpn_additional_data.sf_category   ccpn_additional_data
   # more frame tags...

# loop ccpn_data ...

# save_
```

**Comments:**
- All `# save_` markers commented (showing partial frames)
- `# loop <category> ...` - loops hidden (no underscore prefix)
- `# more frame tags...` - indicating there are more tags not shown (consistent with `# more columns...`)

**COMMENT** updated with consistent notation

---

## Summary of Comment Rules

1. **Complete frames selected** → `save_framename` / `save_` (uncommented), no structural comments
2. **Partial frame content** → `# save_framename` / `# save_` (commented)
3. **Hidden frame tags** → `# frame tags ...`
4. **Hidden complete loops** → `# loop <loop_category> ...` (no underscore prefix)
5. **Hidden complete frames** → `# frame <frame_name> ...` (no save_ prefix)
6. **Partial loop columns** → `# more columns...` in loop header
7. **Partial frame tags** → `# more frame tags...` after shown tags
8. **Multiple consecutive hidden items** → no blank lines between them (group together)

## Questions to Clarify

1. When showing partial columns, should we show the complete loop structure commented above the actual selection?
**COMMENT** no just # more columns...
2. When showing some but not all frame tags, do we need `# other frame tags ...` or just show what's selected?
**COMMENT** yes well done!
3. Format for elided loops/frames - exactly `# loop _nef_sequence ...` or something else?
**COMMENT** exactly but without _ or save_
