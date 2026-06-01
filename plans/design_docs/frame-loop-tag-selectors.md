# Frame.Loop:Tag Selectors — Design Notes

Internal design notes for the composite selector grammar used by `frames tabulate`,
`frames display`, `entry tree` and any future command that needs to select frame tags
or loop columns.

User-facing documentation lives in `cli-idioms` under *Frame.Loop:Tag Selectors*.
This document is for the parser implementation, the data model it produces, and the
reasoning behind the choices.

---

## 1. Internal Data Model

A parsed selector is a 4-tuple:

```
Selector = (Frame, Loop, FrameTags, LoopTags)
```

| Field       | Type                                        | Meaning                                              |
|-------------|---------------------------------------------|------------------------------------------------------|
| `Frame`     | `str` (name or `*`)                         | Which frame(s) to address. Always present.           |
| `Loop`      | `str` (name or `*`) or `None`               | Which loop(s) to address. `None` = loop scope not addressed at all. |
| `FrameTags` | `list[str]` — `[]`, `['*']`, or `[n, ...]`  | Frame-tag selection.                                 |
| `LoopTags`  | `list[str]` — `[]`, `['*']`, or `[n, ...]`  | Loop-column selection.                               |

### Three-state convention for tag selection lists

This is the load-bearing convention:

| List value     | Meaning                                                                                  |
|----------------|------------------------------------------------------------------------------------------|
| `[]`           | No selection. The container (frame or loop) is addressed; the command decides what to render. |
| `['*']`        | Explicit wildcard. The user asked for every member to be expanded.                       |
| `[n1, n2, …]`  | Specific named tags (may include fnmatch wildcards).                                     |

The distinction between `[]` and `['*']` is **semantic** and intentional:

- A user typing `frame` is addressing the frame and trusting the command to do the
  sensible thing (e.g. `frames tabulate frame` shows the whole frame).
- A user typing `frame:*` is *explicitly* asking that every tag be expanded and returned.

Most commands treat the two identically. Some don't — and those that don't are the
reason this distinction exists. Don't collapse `[]` and `['*']` into one state.

---

## 2. Selectors Address, Commands Interpret

The selector identifies *what to look at*. The command decides *what to do with what
it sees*.

Concretely: when `FrameTags=[]` and `Loop=None`, the selector has addressed a saveframe
and projected nothing. A frame implicitly contains its tags and loops, so a command
receiving this has the whole frame available. What it renders is its business:

- `frames tabulate frame` — dump the whole thing.
- `frames list frame` — show just the frame's name and category.
- `tags list frame` — list available tag names without values.

None of these need a different selector. The selector is the same; the command's
interpretation differs. This is why the tag selection lists can be empty without being
ambiguous — emptiness means "no tags selected", not "no data".

---

## 3. Complete Truth Table (Canonical Forms)

These are the canonical forms — what the parser produces after normalisation. Shorthand
forms (§5) reduce to these.

| Selector              | Frame  | Loop  | FrameTags  | LoopTags  |
|-----------------------|--------|-------|------------|-----------|
| **Frame scope (no dot)** |     |       |            |           |
| `frame`               | name   | None  | `[]`       | `[]`      |
| `frame:tag`           | name   | None  | `[tag]`    | `[]`      |
| `frame:tag1,tag2`     | name   | None  | `[t1, t2]` | `[]`      |
| `frame:*`             | name   | None  | `['*']`    | `[]`      |
| `*:tag`               | `*`    | None  | `[tag]`    | `[]`      |
| `*`                   | `*`    | None  | `[]`       | `[]`      |
| `*:*`                 | `*`    | None  | `['*']`    | `[]`      |
| **Loop scope (has dot)** |     |       |            |           |
| `frame.loop`          | name   | loop  | `[]`       | `[]`      |
| `frame.loop:col`      | name   | loop  | `[]`       | `[col]`   |
| `frame.loop:col1,col2`| name   | loop  | `[]`       | `[c1, c2]`|
| `frame.loop:*`        | name   | loop  | `[]`       | `['*']`   |
| `frame.*`             | name   | `*`   | `[]`       | `[]`      |
| `frame.*:col`         | name   | `*`   | `[]`       | `[col]`   |
| `*.loop`              | `*`    | loop  | `[]`       | `[]`      |
| `*.loop:col`          | `*`    | loop  | `[]`       | `[col]`   |
| `*.*`                 | `*`    | `*`   | `[]`       | `[]`      |
| `*.*:col`             | `*`    | `*`   | `[]`       | `[col]`   |
| `*.*:*`               | `*`    | `*`   | `[]`       | `['*']`   |

The two governing rules underneath the table:

- **Dot governs loop scope.** No dot → `Loop = None`, `LoopTags = []`.
  Dot present → `Loop` is set (to a name or `*`) and `LoopTags` may be set.
- **Colon governs tag selection.** No colon → tag selection list is `[]`. Colon present →
  tag selection list is `[name, ...]` (one or more), or `['*']` if the operand is `*`.

Which side of the dot the colon falls on determines whether it populates `FrameTags`
(before the dot, or no dot at all) or `LoopTags` (after the dot).

---

## 4. BNF Grammar

```
selector      ::= frame-form | loop-form

frame-form    ::= frame-part [ ":" tag-list ]
loop-form     ::= frame-part "." loop-part [ ":" tag-list ]

frame-part    ::= name | "*"          ; empty in source promoted to "*"
loop-part     ::= name | "*"          ; empty in source promoted to "*"

tag-list      ::= name { "," name } | "*"

name          ::= /* literal name, may contain fnmatch wildcards * ? [ ] */
                  /* backslash-escaped separators (\:, \., \,) allowed when
                     --use-escapes is active; doubled forms (::, .., ,,) are
                     a transitional alternative — see §8 */
```

**Promotion rule.** An empty `frame-part` or `loop-part` in the source text is
promoted to `*` at parse time. This is how the shorthand forms (§5) reduce to the
canonical forms. The promotion happens once, in the parser, so command implementations
only ever see canonical selectors.

---

## 5. Shorthand Expansion

| Source text     | Canonical form  |
|-----------------|-----------------|
| `.`             | `*.*`           |
| `:`             | `*:*`           |
| `.:col`         | `*.*:col`       |
| `frame.`        | `frame.*`       |
| `frame:`        | `frame:*`       |
| `frame.loop:`   | `frame.loop:*`  |
| `:tag`          | `*:tag`         |
| `.loop`         | `*.loop`        |

The rule is uniform: any delimiter (`.` or `:`) without a name on the missing side
defaults that position to `*`. There are no special cases — the parser promotes empty
parts to `*` and re-runs the canonical-form logic.

---

## 6. Disallowed Combinations

### 6.1 Frame tag + loop column in one selector

`frame:tag.loop:col` is rejected at parse time.

**Why:** a frame tag is owned by the frame; a loop column is owned by a loop. Asking
for both in one selector mixes scopes that don't share an addressing model — the data
they refer to lives in different parts of the NEF tree and a single rendering call has
no sensible way to combine them. Use two selectors instead.

**Error message:**
```
invalid selector: a single selector cannot address both a frame tag and a loop
column (a frame tag belongs to the frame, a loop column belongs to a loop —
they are different scopes). Use two selectors:
  frame:tag
  frame.loop:col
```

### 6.2 Multiple dots or multiple colons in one scope

`frame.sub.loop` — rejected. Selectors have at most one `.`.

`frame:tag1:tag2` — rejected. Use the comma: `frame:tag1,tag2`. Same for columns.

(`\:` and `\.` are not multiple separators — they are backslash escapes for literal
`:` and `.` in names, active under `--use-escapes`. Doubled forms `::` / `..` are an
older transitional alternative still accepted by some commands; see §8.)

---

## 7. `:tag` vs `.:col` — Known Visual Collision

`:tag` selects a frame tag across every frame; `.:tag` selects a loop column across
every loop. One dot flips the meaning entirely, and both parse cleanly — so a user
who misreads or mistypes gets different data with no error.

We considered three responses:

1. **Accept both, document loudly.** Cheapest. Failure mode stays silent.
2. **Force the explicit form for one or both** (e.g. require `*.*:col` rather than
   accepting `.:col`). Heavier syntax; rules out a natural shorthand.
3. **Deprecate `.:col`** in favour of `*.*:col`.

Decision: **option 1**. Both forms are accepted; user-facing docs flag the collision
prominently and recommend the explicit `*:tag` / `*.*:col` forms when the dot count
is doing the work. We may revisit if we see real confusion in practice.

---

## 8. Parser Implementation

### Approach

The original selector parser was built with **PyParsing**. This was a deliberate choice
after trying alternatives:

- **Regex** was rejected up front. The grammar has nested escape rules (`\:`, `\.`,
  doubled separators under `--use-escapes`), context-sensitive empty-part promotion, and
  a small but non-trivial set of disallowed combinations. Regex either gets unreadable
  fast or pushes the work into post-regex Python anyway.
- **Hand-rolled / direct parsing** was tried and was painful in practice. Each new
  escape rule or shorthand form required threading state through the parsing functions,
  and error messages were hard to keep useful. The code got brittle as the grammar grew.

PyParsing gave us declarative production rules that map straightforwardly onto §4, with
escape handling that composes cleanly. Any extension to the grammar should follow the
same approach.

### Logical flow

The parser is small in semantic content — most of the value is in the grammar rules
and the canonical-form construction:

```
parse_selector(text: str) -> Selector:
    # 1. Reject empty input.
    # 2. Split on '.' at most once (escapes are pre-processed if --use-escapes).
    #    - no dot       → frame-form
    #    - one dot      → loop-form
    #    - more dots    → error
    # 3. For each half, split on ':' at most once.
    #    - more colons → error
    # 4. Promote empty parts to '*'.
    # 5. Detect the disallowed combination: frame-half has a colon AND loop-half
    #    has a colon → error (§6.1).
    # 6. Build the 4-tuple per the rules in §3.
    # 7. Return.
```

The promotion (step 4) and the canonical-form construction (step 6) are the entire
semantic content. Commands downstream see only canonical selectors and never have to
re-run the shorthand rules.

### Escape handling — existing tooling

Separator escapes are handled by tooling shared across NEF-Pipelines CLI parsing,
not by the selector parser itself. The selector parser consumes the post-escape
token stream and treats the remaining separators as structural.

**Direction of travel: backslash escapes only.** The target form for embedding a
separator in a name is `\:`, `\.`, `\,` (and by extension `\;` if Appendix A.2.2 lands).
The older doubled-form alternatives (`::`, `..`, `,,`) are transitional and will be
removed — they exist for backward compatibility with selectors written before backslash
escapes were universally supported. New code and new commands should target the
backslash form only.

When extending the grammar — adding a new separator, or extending the escape behaviour
to a new context — work with the existing shared escape machinery rather than adding
selector-parser-specific handling. Adding a separator (e.g. `;` — see Appendix) means
adding `\;` to that machinery in one place, not patching the selector parser directly.

---

## 9. Open Questions / Future Work

- **Column-wildcard parity across scopes.** The `fnmatch`-style wildcards in the column
  position are slated to extend to frame and loop names. When that lands, the grammar
  doesn't change — only the semantics of `name`.

- **Telemetry on shorthand vs explicit forms.** We accepted both `*.*:col` and `.:col`
  on the basis that we'd see which form users reach for. No instrumentation yet; revisit
  when the selector code touches usage logging.

---

## Appendix A — Deferred Extensions (Discussion, Not Decisions)

These came up while specifying the current grammar but are explicitly **not** part of
it. Recorded here so the reasoning isn't lost and we don't relitigate from scratch if
they come up again.

### A.1 Position-level orthogonality (comma lists in frame and loop positions)

Today, only the tag position accepts a comma-separated list:

```
frame.loop:tag1,tag2     ✓ accepted
frame1,frame2.loop:tag   ✗ not accepted
frame.loop1,loop2:tag    ✗ not accepted
```

Conceptually all three positions answer the same question — "which named things in
this scope?" — so an orthogonal grammar would allow comma lists everywhere, with
union semantics:

```
name-list  ::= name { "," name } | "*"
frame-part ::= name-list
loop-part  ::= name-list
tag-list   ::= name-list
```

Combined with the planned extension of fnmatch wildcards to frame and loop positions,
this would give a clean "every position is a name-list, every name may be a pattern"
model. The expanded match set would be the Cartesian product across the three scopes.

**Why not now:** no concrete need yet, and changing the grammar later is cheaper than
unwinding misuse if the union semantics turn out to be confusing in some position.
The current asymmetry is a deliberate pause, not a final design.

### A.2 Multi-selector input

Two flavours are worth distinguishing:

**A.2.1 Argument-level (already supported in most commands).** Multiple whole
selectors as separate argv items, separated by shell whitespace:

```
nef frames tabulate  frame:experiment_type  frame.peak:height,volume
```

This is how to work around the §6.1 ban on mixing a frame tag and a loop column in
one selector. No grammar change required; this is a command-input convention, not a
selector-grammar feature. Commands that need it should already accept a list.

**A.2.2 Intra-string with a separator character.** For contexts where whitespace
isn't available — `--out` templates, config-file values, embedded selector strings —
a separator character would let one string carry several selectors. Example with
`/` (the leading candidate; see A.3 for the trade-offs):

```
frame:experiment_type/frame.peak:height,volume
```

At the shell this needs no quoting:

```
nef frames tabulate frame:experiment_type/frame.peak:height,volume
```

Adopting an intra-string separator would mean:

- Adding it to the escape machinery (`\/` or `\;` depending on choice) in the same
  place as the existing `\:` / `\.` / `\,` handling — see §8. No doubled-form
  alternative would be introduced, consistent with the direction of travel away from
  doubled escapes.
- A parser pass that splits on the separator *before* per-selector parsing, returning
  a list of canonical selectors.

**Why not now:** no command currently needs it. The argument-level form (A.2.1)
covers every case we have. If `--out` templates or config files start wanting
multiple selectors per value, revisit and pick the separator.

### A.3 Candidate separator characters

Briefly recorded so we don't relitigate. Two characters survive serious consideration:

- **`/`** — not a shell metacharacter at the argument level (bash, zsh, fish all treat
  it as ordinary), so no quoting needed. Conventional in URLs as a path/segment
  separator with a mild "and then this" feel. Composes cleanly with `\/` in the
  existing escape machinery. The one minor concern is visual confusion in contexts
  where file paths also appear (e.g. `--out` templates), but selector strings and
  path strings don't normally share a parameter, so the confusion is more theoretical
  than practical.

- **`;`** — shell command separator, so requires quoting at the interactive shell
  (`'a;b'`). Strong "and then this" convention from CSS, SQL, JS. The primary intra-string
  use case (templates, config files) isn't shell-parsed, so the quoting issue is
  contained — but for interactive use the quoting is a real cost.

Ruled out for the reasons noted:

- `,` — already the in-position name separator inside a selector; reusing it would
  make `frame.loop:tag1,tag2,frame2.loop2:tag3` context-sensitive (see earlier
  discussion). Hard rule-out.
- `|` — shell pipe; needs quoting; visually noisy.
- `+` — already used by include-selectors in NEF-Pipelines (`+name` / `-name` /
  `!name`). Also has meaning in zsh (autoload paths, named directories) which would
  surprise zsh users at the shell.
- `&` — shell background operator; needs quoting; ugly.
- whitespace — not available in the contexts where intra-string would matter
  (templates, config values).

**Current leaning: `/`**, on the strength of needing no shell quoting and having no
existing role in NEF-Pipelines or NEF-STAR. `;` remains a viable fallback if `/`
turns out to confuse users in path-adjacent contexts.
