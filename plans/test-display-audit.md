# test_display.py — Test Audit

**STATUS: PARTIALLY ADDRESSED** ⚠️

**Cleanup done:**
- ✅ `test_tags_only_with_loop_selector` removed (deprecated test)
- ❌ `test_basic_selector` still exists (should be removed per audit)
- ❌ `test_loops_only` not merged into parametrized test

**Missing tests:**
- ❌ Not added: proper `test_all_columns_via_wildcard`
- ❌ Not added: multi-loop frame test data and hidden loop hints test
- ❌ Not added: `--force` overwrite test
- ❌ Not added: `--out @out` / `--out -` routing tests

**Current state**: This is an **audit document** identifying test quality issues. One deprecated test was removed, but most recommendations (deduplication, missing coverage) remain unaddressed.

---

## Duplicates / Overlapping Objectives

| Test | Issue | comment                                                                         |
|---|---|---------------------------------------------------------------------------------|
| `test_basic_selector` + `test_exact_indentation` | Same command, same selector. `test_exact_indentation` is strictly stronger (`squash_spaces=False`). `test_basic_selector` is fully subsumed and could be removed. | use test_exact_indentation but merge the test test names                        |
| `test_loops_only` + `test_entire_frame_vs_frame_tags[loops_with_context]` | Both test `molecular_system.` selector with nearly identical expected output. True overlap — one is redundant. | just keep test_entire_frame_vs_frame_tags[loops_with_context]                   |
| `test_tags_only_with_loop_selector` | Marked `DEPRECATED` with `TODO: Remove or rewrite`. Only asserts `"sequence" in result.stderr.lower()` — near-zero coverage value. Should be deleted. | can goo tested by parameterised test as a Check list the equivalent test first. |
| `test_pipe_mode_output_routing` + `test_out_err_no_entry` | Both assert the same stderr content and entry-to-stdout routing. Different mechanism under test (default vs explicit `@err`) but the stderr assertion is shared boilerplate. Minor, not worth fixing. | keep the routing matters |

## Missing Tests

1. **`loop:*` → no `# more columns...`** — `test_tags_only_with_loop_selector` was meant to cover this but is too weak. There is no solid test that `molecular_system.sequence:*` (explicit wildcard, all columns) produces a complete loop with no column hint.

2. **Frame with multiple loops** — all test data has one loop per frame. The `_append_hidden_loop_hints` logic (hidden loop hints for non-selected loops within a frame) has zero coverage. Needs new test data with a frame containing two or more loops.
**COMMENT** and we shoudl have loops before and after the displayed loop, same with saveframes
3. **`--force` overwrite** — `test_explicit_display_file_streams_entry` creates a fresh file. No test for overwriting an existing file (with `--force`) or the refusal without it.

4. **`--out @out` / `--out -`** — `@err` and `<file>` routing are tested; explicit stdout routing (`@out` / `-`) is not.

5. **`--no-initial-selection` alone** — only tested combined with `--namespace -nef`. Alone (no `--namespace`) it should produce empty output with no comments — not covered.

6. **`--no-comments` suppresses hidden frame hints** — `test_no_comments` implicitly confirms hints are suppressed (they are absent from the expected output) but this is never asserted directly.

## Recommendation

**Immediate cleanup (low effort):**
- Delete `test_tags_only_with_loop_selector` (deprecated, trivially weak)
- Delete `test_basic_selector` (subsumed by `test_exact_indentation`)
- Merge `test_loops_only` into `test_entire_frame_vs_frame_tags` parametrize list

**Worth adding:**
- Replace weak `test_tags_only_with_loop_selector` with a proper `test_all_columns_via_wildcard` checking no `# more columns...` appears
- Add test data with a multi-loop frame and a test for hidden loop hints

**COMMENT**
1. not all expectations are nicely indented [indent doesn't amtter for test except when identation is tested because of squash_spaces but is important for humans!]
2. not all expectations are at the global level of before first use
