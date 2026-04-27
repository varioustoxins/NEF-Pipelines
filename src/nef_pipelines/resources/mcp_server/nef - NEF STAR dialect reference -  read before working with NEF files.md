# NEF STAR Dialect: Extensions and Ontology Reference




This document defines the **NEF Layer** that extends foundational STAR syntax. These rules are mandatory for
software-specific interoperability within the NEF-Pipelines ecosystem. It is assumed that the foundational STAR
specification has already been processed.

## TL;DR — Read This First

You read NEF as text (from user provided files or from command output) and act on it through NEF-Pipelines
MCP commands — you don't parse files yourself or generate STAR text. This document gives you the mental
model you need to choose the right commands, frame/loop/tag selectors, and to recognise what's safe to
modify versus what must be preserved.

*   **What NEF is:** a STAR text file holding NMR experimental data. Exactly one `data_<entry_name>` block
    containing **saveframes** (named tables), **loops** (tabular rows), and **tags** (key/value pairs).
*   **Namespace = software owner; Category = data schema.** A saveframe header
    `save_<NAMESPACE>_<CATEGORY>...` (e.g. `save_nef_nmr_spectrum_hsqc`1``) encodes both. Every saveframe
    declares a **registered** namespace (`nef`, `ccpn`, `aria`, ...). Loop and tag namespaces follow
    inheritance rules — see §6.
*   **The 4-string identifier** — `chain_code` + `sequence_code` + `residue_name` + `atom_name` — is the
    case-sensitive primary key linking every shift, peak, and restraint to the molecule.
*   **Pass-through rule:** anything in an unknown or non-target namespace must be preserved. Don't suggest
    deleting `ccpn_*`, `aria_*`, `xplor_*` etc. just because your task doesn't use them — that data belongs
    to other software in the user's pipeline.
*   **Live data, not memorised lists:** registered namespaces and frame contents change. Use
    `nef namespace list` to see namespaces in a file, `nef frames list` to discover frames, `nef namespace catalog` to
    list what namespaces have been registered by the community, and `nef frames tabulate` to inspect loop data.



## Worked Example (a real frame from `Sec5Part4.nef`)

What you'll typically see in a `frames list` / `frames tabulate` output for a CCPN-produced HSQC frame.
This frame mixes `nef`-namespace and `ccpn`-namespace tags — a very common pattern in real files:

```STAR
data_Sec5Part4

  # mandatory saveframes nef_nmr_meta_data, nef_molecular_system and nef_chemical_shift_list are not shown here for
  # brevity

  save_nef_nmr_spectrum_hsqc`1`
   _nef_nmr_spectrum.sf_category                  nef_nmr_spectrum
   _nef_nmr_spectrum.sf_framecode                 nef_nmr_spectrum_hsqc`1`
   _nef_nmr_spectrum.num_dimensions               2
   _nef_nmr_spectrum.experiment_type              '15N HSQC/HMQC'
   _nef_nmr_spectrum.ccpn_positive_contour_count  10
   _nef_nmr_spectrum.ccpn_spectrum_scale          1
   ... # more frame level tags

   # several more loops

   loop_
         _nef_peak.index
         _nef_peak.peak_id
         _nef_peak.volume
         _nef_peak.volume_uncertainty
         _nef_peak.height
         _nef_peak.height_uncertainty
         _nef_peak.position_1
         _nef_peak.position_uncertainty_1
         _nef_peak.position_2
         _nef_peak.position_uncertainty_2
         _nef_peak.chain_code_1
         _nef_peak.sequence_code_1
         _nef_peak.residue_name_1
         _nef_peak.atom_name_1
         _nef_peak.chain_code_2
         _nef_peak.sequence_code_2
         _nef_peak.residue_name_2
         _nef_peak.atom_name_2
         _nef_peak.ccpn_figure_of_merit
         _nef_peak.ccpn_linked_integral
         _nef_peak.ccpn_annotation
         _nef_peak.ccpn_comment


         1   1    .  .  791958.375   .  8.598275966  .  133.2694881  .  A   74   VAL  H  A   74   VAL  N  1  .  .  .  1
         2   2    .  .  946877.625   .  8.930837068  .  131.3918342  .  @-  @2   .    H  @-  @2   .    N  1  .  .  .  1
         3   3    .  .  723607.875   .  9.676128405  .  130.7622721  .  A   24   ILE  H  A   24   ILE  N  1  .  .  .  1

         # ... more loop data
    stop_

    # ... more saveframes
save_
```

| Element | What it is                                                                     |
|---|--------------------------------------------------------------------------------|
| Saveframe namespace | `nef` (first token of the category, before its first `_`)                      |
| Saveframe category | `nef_nmr_spectrum` (the `.sf_category` value — authoritative)                  |
| Saveframe name | `hsqc` (the part of the framecode after the category)                          |
| Saveframe index | `` `1` `` (CCPN backtick extension — see §7)                                   |
| Tag `num_dimensions` | tag ns = `nef` (inherited from frame; bare attribute has no registered prefix) |
| Tag `ccpn_positive_contour_count` | column ns = `ccpn` (attribute starts with the registered prefix `ccpn`)        |
| Implication for a non-CCPN task | every `ccpn_*` tag is pass-through — leave it alone                            |

A second frame in the same file, `save_ccpn_substance_Sec5.None`, illustrates the `.identity` suffix:
namespace = `ccpn`, category = `ccpn_substance`, name = `Sec5`, identity = `None`. All its tags inherit the
`ccpn` namespace because none carry a different registered prefix.

The Entry name is `Sec5Part4` (from the `data_` block).
The loop defined is the `peak` loop in the `nef` namespace

Note. the nef_peak ccpn loop has columns whicg are part of the nef namespace (e.g. `position_1`) and columns which are
part of the ccpn namespace (e.g. `ccpn_annotation`) — this is a common pattern for loops with software-specific
extensions.

---

## 1. Entries
NEF files MUST contain exactly one `data_` block, which serves as the top-level container for all saveframes
and data. This is a strict requirement to ensure consistency across NEF files and simplify parsing.

> **Note:** NEF doesn't use the following STAR features:
> * `global_` sections
> * nested saveframes or loops
> * loops or tags at entry level
>
> **NEF-Pipelines commands:**
> * Change the entry name: `nef entry rename <new-name>` [NEF-Pipelines often uses the entry name as part of
>   output filenames]
> * View file structure (frames → loops → tags): `nef entry tree`

## 2. The Namespace and Category System
NEF organizes data into a hierarchy of ownership and type.

### 2.1 Namespaces
A **Namespace** is a string containing **no underscores** (`_`).
*   **Identification:** In a namespaced string (like a tag or framecode), the Namespace is identified by all
    characters up to the **second underscore** excluding the initial _.
*   **Ownership:** The namespace identifies the software package (e.g., `nef`, `aria`, `ccpn`, `xplor`) that "owns"
    the saveframe, loop or tag.
*   **Complexity:** How namespaces are defined and interact is complicated and discussed further in the sections on
    extending frames loops and tags with inheritance below.
*   **Pass-Through Rule:** Parsers MUST preserve non-core namespaces as opaque blobs to prevent data loss in
    multi-step pipelines.

> **NEF-Pipelines commands:**
> Use `nef namespace list` to see which namespaces are present in a NEF file [verbose mode lists every thing's
> namespace by frame, loop, category and tag].
> Use `nef namespace catalog` to list all currently registered namespaces from a local cache or the NEF website.

### 2.2 Categories
A **Category** defines the data schema (e.g., `nmr_spectrum`, `sequence`). Categories always exist within a
Namespace.

---

## 3. NEF Saveframe Architecture
NEF expands the definition of saveframes to encode Namespaces, Categories, and Names.

> **NEF-Pipelines commands:**
> * List frames with categories: `nef frames list`
> * Inspect a frame's tags and loops: `nef frames tabulate <selector>`
> * Filter frames to specific tags only: `nef frames display --tags <tag-pattern> <frame-selector>`
> * Display the logical structure of a nef file: `nef entry tree` including filtering on namespaces frames and
>   categories: `nef entry tree --namespaces nef --categories nmr_spectrum`
> * Display part of a frame's loops and tag values: `nef frames display --tags <tag-pattern> <frame-selector>`

### 3.1 Decomposition Algorithm
Saveframe headers SHOULD follow this pattern:`` save_<NAMESPACE>_<CATEGORY>[_<NAME>][`INDEX`|.identity] ``

*   **NAMESPACE:** All characters preceding the **second underscore** (e.g., in `save_nef_...`, the Namespace
    component is `nef`).
*   **CATEGORY:** The data type identifier following the Namespace.
*   **NAME:** (Optional) A descriptive name.
*   **INDEX:** (Optional; CCPN extension) An integer surrounded by literal backticks, e.g., `` `1` ``.
    > **Note:** Treating this as an index is not strictly part of the official NEF definition but is widely used by
      the **CCPN software suite** and other packages, and is fully supported by **NEF-Pipelines**.
*   **.identity:** (Optional; CCPN Extension) A literal suffix indicating a reference or template frame.

### 3.2 Identification Tags (The .sf Tags)
Every saveframe MUST contain these identity tags to confirm its type and name:
*   `_<namespace>_<category>.sf_category`: Must match the Category (e.g., `nef_nmr_spectrum`).
*   `_<namespace>_<category>.sf_framecode`: Must match the full header string (the identifier after the `save_`
    keyword).

> **The `.sf_category` tag is authoritative.** When you need the category of a frame you see in command
> output, read its `.sf_category` value rather than splitting the header string yourself. This avoids
> tripping over CCPN-style backtick indices and `.identity` suffixes embedded in the framecode (§7).

### 3.3 Singleton Logic
Saveframes like `nef_nmr_meta_data` and `nef_molecular_system` are **Singletons** [`sf_category` == `sf_framecode`]
and they lack the `<NAME>` and `<INDEX>` components. Only one instance is permitted per data block / file [frame names
must be unique in a datablock and are an invariant which is enforced by NEF-Pipelines],

---

## 4. Tag Dialects
NEF generally uses a hierarchical naming convention where the Namespace and Category precede the tag name, separated
by a full stop (`.`); for exceptions see the section on inheritance.

### 4.1 Saveframe-level Tags
The Namespace and Category are repeated in every tag within the saveframe.
Pattern: `_<NAMESPACE>_<CATEGORY>.<ATTRIBUTE>`

**Example:**
```STAR
_nef_nmr_meta_data.format_name      nmr_exchange_format
_nef_nmr_meta_data.format_version   1.1
_nef_nmr_meta_data.program_name     AnalysisAssign
_nef_nmr_meta_data.program_version  3.3.4
```

### 4.2 Loop-level Tags (Column Headers)
Tags that define columns within a `loop_` follow the same pattern:
`_<NAMESPACE>_<CATEGORY>.<COLUMN_NAME>`

*   **Logic:** This ensures the Namespace/Category remains intrinsic to the column even if extracted.
*   **Flatness:** Unlike generic STAR, NEF loops are always flat (one level deep) within a saveframe.

---

## 5. Annotated Example
This and following examples show how the core NEF specification is extended in practice by real software
(in this case, CCPN AnalysisAssign) and how to understand which piece of software owns what.

```STAR
data_ExtensionExample

   # 1. DECOMPOSED SAVEFRAME (Section 3.1)
   # Namespace='nef', Category='nmr_spectrum', Name='hsqc', Index='1'
   # Namespace is 'nef' (precedes the second underscore)
   save_nef_nmr_spectrum_hsqc`1`

      # 2. SAVEFRAME TAG DIALECT (Section 4.1)
      _nef_nmr_spectrum.sf_category       nef_nmr_spectrum
      _nef_nmr_spectrum.sf_framecode      nef_nmr_spectrum_hsqc`1`
      _nef_nmr_spectrum.num_dimensions    2

      # 3. LOOP TAG DIALECT (Section 4.2)
      loop_
         _nef_peak.peak_id
         _nef_peak.position_1

         # 4. FOUR-STRING IDENTIFIER (see nef://nmr-data resource)
         _nef_peak.chain_code_1
         _nef_peak.sequence_code_1
         _nef_peak.residue_name_1
         _nef_peak.atom_name_1

         1  8.521  A  10  HIS  H
      stop_
   save_

   # 5. PASS-THROUGH EXTENSION (Section 2.1)
   save_aria_parameters
      _aria_parameters.sf_category   aria_parameters
      _aria_parameters.weight        0.5
   save_
```

## 6. Extension and Inheritance Model
NEF allows software to extend core structures by mixing namespaces in Saveframes and Loops. Ownership of saveframes,
loops, and tags is determined by an inheritance model.

### 6.1 Namespace Identification

**Extraction algorithm** (`_extract_namespace`):
1. If the string starts with `_`, strip it.
2. Split on `_` once (taking only the first split).
3. The result before the split is the namespace prefix if it is a registered namespace, otherwise the namespace is
   inherited. Registered namespaces are available from `nef namespace catalog`.
4. If there is no `_` separator, the prefix is `""` (null — invalid in well-formed NEF).

Examples:
* `_nef_sequence` → `nef`
* `nef_molecular_system` → `nef`
* `ccpn_assignment` → `ccpn`
* `nefpls_value` → `nefpls`.

A namespace prefix is only **active** if it is **Registered** (e.g., `nef`, `ccpn`, `aria`, `nefpls`). Unknown prefixes
cause the item to inherit its namespace from its parent container. Every saveframe in a valid NEF file MUST have a
registered namespace — a saveframe with no registered namespace prefix is not correct and is hard to understand but
won't prevent parsing.

> **NEF-Pipelines commands:**
> See exactly which frames, loops, and tags carry each namespace: `nef namespace list --verbose`
> This is handy when inheritance results aren't obvious from visual inspection.

### 6.2 Inheritance Rules

**Resolution algorithm:**
```
resolve_namespace(X, parent=None):
  prefix = _extract_namespace(X)

  if X is a Saveframe:
    return prefix                          # always its own prefix (must be registered)

  if X is a Loop:
    if prefix is Registered: return prefix
    else: return parent.namespace          # inherit from parent saveframe

  if X is a Tag:
    # Tags have TWO namespace levels — see section 6.4:
    #   Loop namespace:   from _<NAMESPACE>_<CATEGORY> (the category part, before the dot)
    #   Column namespace: from the ATTRIBUTE part after the dot (e.g. nefpls_predicted_value → nefpls)
    # _extract_namespace is called on the bare attribute name (after the dot):
    if prefix is Registered: return prefix # explicit column namespace
    else: return parent.namespace          # inherit from loop or saveframe
    if no parent: return "nef"             # isolation default
```

*   **Structural Tags:** `sf_category` and `sf_framecode` are owned by the NEF implementation and may appear
    in any saveframe without a namespace prefix [they could be viewed as having the namespace sf but this isn't
    documented otherwise they should be treated as a special case].

### 6.3 Loops with mixed loop namespaces and categories are illegal
A loop can only have one category and namespace; this is defined by the first tag in the loop and repeated for all
others. STAR parsers reject mixed loops at parse time, so a NEF file you receive will never legally contain one — but
you should still recognise the constraint when interpreting tag names. The following loop, for example, is not
allowed because it has tags with different **loop** namespaces and categories:

```STAR
   # assume the namespaces nefpls and nef are defined

   loop_
     _nef_chemical_shift.chain_code
     _nef_chemical_shift.sequence_code
     _nef_chemical_shift.residue_name
     _nef_chemical_shift.atom_name
     _nef_chemical_shift.value
     _nfpls_chemical_shift_predictions.value # ILLEGAL: Different category/namespace

      A 1 TYR H 8.521  8.123
      A 2 MET H 7.321  7.654
   stop_
```

To write out this data in a loop with a different category, you would need to define two separate loops:

```STAR

   # assume the namespaces nefpls and nef are defined

   loop_
     _nef_chemical_shift.chain_code
     _nef_chemical_shift.sequence_code
     _nef_chemical_shift.residue_name
     _nef_chemical_shift.atom_name
     _nef_chemical_shift.value

      A 1 TYR H 8.521
      A 2 MET H 7.321
   stop_

   loop_
     _nfpls_chemical_shift_predictions.chain_code
     _nfpls_chemical_shift_predictions.sequence_code
     _nfpls_chemical_shift_predictions.residue_name
     _nfpls_chemical_shift_predictions.atom_name
     _nfpls_chemical_shift_predictions.value

        A 1 TYR H 8.123
        A 2 MET H 7.654
   stop_
```

However, it is quite legal to add an extra COLUMN-TAG with a different namespace to the first loop as discussed below.

### 6.4 Loop Column Extension with Example

Tags in a loop have **two namespace levels**:

*   **Loop namespace**: determined by `_<NAMESPACE>_<CATEGORY>` (the part before the dot). ALL columns in a loop
    MUST share the same loop namespace and category — STAR parsers enforce this at parse time.
*   **Column (attribute) namespace**: determined by the attribute name after the dot (e.g., `nefpls_predicted_value`
    → `nefpls`). Columns in the same loop MAY have different attribute namespaces.

*   **Practical Example:**
```STAR
   # assume the namespaces nefpls and nef are defined

   loop_
     _nef_chemical_shift.chain_code              # loop ns=nef ; column ns=nef (inherited)
     _nef_chemical_shift.value                   # loop ns=nef ; column ns=nef (inherited)
     _nef_chemical_shift.nefpls_predicted_value  # loop ns=nef ; column ns=nefpls (explicit)

      A 1 TYR H 8.521  8.123
      A 2 MET H 7.321  7.654
   stop_
```
All three columns share the loop namespace `nef` (from `_nef_chemical_shift`). The third column's attribute
`nefpls_predicted_value` carries an explicit `nefpls` column namespace; the first two inherit `nef` from the loop.

### 6.5 Adding a new Loop to a Saveframe
To add a new data table to an existing saveframe, define a new `loop_` with a unique category within the saveframe.
You should use your software's own Namespace for the new loop (e.g., `_myprog_new_data`) to ensure it is handled
correctly by the Pass-Through Rule.

**Example:**
```STAR
   # assume the namespaces nefpls and nef are defined
   save_nef_nmr_meta_data
      ...
      loop_
         _nefpls_processing_history.step_index
         _nefpls_processing_history.details

         1 'Data converted from Sparky'
         2 'Chemical shifts refined'
      stop_
   save_
```

### 6.6 Adding a new Tag to a Saveframe
To add a new data item (tag-value pair) to an existing saveframe, append the list of tags in the saveframe body. The tag
MUST include the Namespace and Category of the parent saveframe, but SHOULD use its own Namespace.

**Example:**
```STAR
   # assume the namespaces nefpls and nef are defined

   save_nef_nmr_meta_data
      _nef_nmr_meta_data.sf_category          nef_nmr_meta_data
      _nef_nmr_meta_data.format_version       1.1
      _nef_nmr_meta_data.nefpls_process_id    42   # Software-specific extension in the nefpls namespace
   save_
```

## 7. CCPN Extensions You Will Encounter in Real NEF Files

CCPN Analysis (AnalysisAssign) is a common source of NEF files in practice. It introduces several
extensions beyond the core NEF spec that NEF-Pipelines handles transparently but that you will see frequently:

**Backtick index** `` `<INDEX>` ``: Appended to a framecode to distinguish multiple instances of the same
category/name, e.g. `save_nef_nmr_spectrum_hsqc`1``. The index is an integer surrounded by literal backtick
characters. NEF-Pipelines parses and preserves these.

**`.identity` suffix**: Appended to disambiguate save frames by an additional name rather than an index, e.g.
`save_ccpn_substance_Sec5.None`. The dot and word after it form the identity qualifier. NEF-Pipelines parses
and preserves these.

**`ccpn` namespace tags and frames**: CCPN adds many extension frames and tags in the `ccpn` namespace, such
as `ccpn_assignment`, `ccpn_additional_data`, `ccpn_substance_*`. These are generally pass-through opaque data for
non-CCPN software though in some cases NEF-Pipelines may analyse them or modify them.

**Combined example** (from a real AnalysisAssign output):
```STAR
    save_nef_nmr_spectrum_hsqc`1`          # backtick index: second instance if there were a first
       _nef_nmr_spectrum.sf_framecode   nef_nmr_spectrum_hsqc`1`
       ...
    save_

    save_ccpn_substance_Sec5.None          # .identity suffix: reference frame for substance Sec5
       _ccpn_substance.sf_category      ccpn_substance
       _ccpn_substance.sf_framecode     ccpn_substance_Sec5.None
       ...
    save_
```

> **NEF-Pipelines commands:**
> Framecodes containing `` `N` `` or `.identity` appear verbatim in `nef frames list` output — pass them
> unchanged to selector arguments. Frame selectors support glob patterns, so `nef_nmr_spectrum_hsqc*` will
> match across backtick variants.

---

## 8. Common Tag Values and Names

NEF uses standard value conventions across many tags:

**Sentinels (missing/unknown values):**
*   `.` - used by NEF as a None value which indicates the value isn't defined or is unknown (e.g., an unassigned peak:
    `chain_code_1` = `.`)
*   `?` — this is not typically used in NEF files [which uses .] but may be used by a user as an unknown value or to
    indicate uncertainty.

**Column tags [headings]**
*   `index` a monotonic index [values may be missing]
*   `serial` a monotonic index with no missing values which is generally not reused across a project (e.g. for peaks)
*   `chain_code`, `sequence_code`, `residue_name` and `atom_name`, — the 4-string identifier for molecular addressing
    (see below). Because multiple atoms can refer to one piece of data they are often suffixed with `_1`, `_2` etc. to
    distinguish them (e.g. `chain_code_1` and `chain_code_2` in a distance restraint loop).
*  `element` the chemical element symbol (e.g. `C`, `N`, `H`) as defined by IUPAC these are case-sensitive.
*  `isotope_number` the isotope number (e.g. `1`, `2`, `13`, `15`) of an element, it should accompany an element tag.
*  `comment` a free text field for user comments, maybe in the `nef` or other namespaces.
*  `value` a measured value such as a chemical shift
*  `value_uncertainty` the statistical uncertainty of a measured value such as a chemical shift
*  `merit`/ `figure_of_merit` etc. a measure of the quality of a measurement, prediction or fit; typically 0.0..1.0
*  `<SAVEFRAME-NAME>` a tag which defines cross reference to another saveframe with aggregate or mapping data e.g.
   `_nef_nmr_spectrum.chemical_shift_list`
*  `axis_unit` the unit of measurement for a spectrum axis or other data axis (e.g. `ppm`, `Hz`, `/s` etc.)
*  `axis_code` the name of a spectrum axis (e.g. `1H`, `15N` etc.) should be unique within a spectrum
*  `spectrometer_frequency` the spectrometer frequency for a spectrum in MHz for an axis (e.g. 600.13 MHz for ¹H).
    Technically ambiguous for an axis without an element and axis code but in practice this is usually clear from
    context and the fact that ¹H are usually in multiples of 50MHz and gyromagnetic ratios limit the frequencies of
    other isotopes.
*   `spectral_width` width of a spectrum axis in unit defined by `axis_unit` (e.g. `20.0` ppm or 1200Hz etc)
*   `volume` the integrated volume of a peak
*   `volume_uncertainty` the statistical uncertainty of a peak volume
*   `height` the height of a peak [often more accurate as it's more robust to peak overlap than a volume measurement if
     peak widths are all roughly the same]
*    `height_uncertainty` the statistical uncertainty of a peak height measurement
*    `peak_id` an identifier for a peak in combination with a spectrum name derived from its saveframe's name.
      In the CCPN software suite and some other programs such as NMRView peak ids are not reused in a peak list; they
      are temporally stable identifiers.
*    `annotation` a text field with meaningful scientific data about a value
*    `experiment_classification` / `experiment_type` information about an experiment type, they are currently not
     well-defined.
*    `restraint_id` a unique identifier for a restraint in combination with a restraint list name
     derived from its saveframe's name.
*    `<type>_combination_id` an identifier across multiple restraints or values which indicates that they should be
     viewed in combination (e.g. a set of distance restraints that should be viewed together as a group, or a set of
     atom names that apply to the same peak). The meaning is context dependent but an example would be ambiguous
     distance restraints that need to 1/r⁶ averaged together.

> Note: **Molecular addressing and NMR data:**
> For the **4-string identifier** (chain_code, sequence_code, residue_name, atom_name), molecular structure,
> NMR data types (shifts, peaks, restraints), and assignment linking, see the **`nmr-data` resource**
> (`nef://nmr-data`).

---

## 9. NEF-Pipelines Relaxed Constraints

*   **Relaxed Validation:** `nef-pipelines` does **NOT** require "Valid NEF" (i.e., mandatory meta_data or shift
    frames) in its internal streams or intermediate outputs, as this is often too restrictive for modular
    processing. Final user-facing outputs should however be validated for standard compliance. However see section 11
    on validation and dictionaries below for more details on this topic.

> **NEF-Pipelines commands:**
> Add a missing `nef_nmr_meta_data` frame to a stream: `nef header [<entry-name>]`

---

## 10. Common Mistakes to Avoid

These are easy traps when reasoning about NEF files and choosing which NEF-Pipelines commands to run.

*   **Recommending the user delete unknown-namespace frames or tags.** Items in `aria_*`, `xplor_*`,
    `ccpn_*` etc. are not noise — they are pass-through data owned by other software in the user's
    pipeline (§2.1). Don't suggest a `frames delete` or namespace-strip operation unless the user
    explicitly asks for it.
*   **Treating `Sec5.None` or `` `hsqc`1` `` as malformed when you see them in `frames list` output.** The
    `.identity` suffix and the backtick index are legal CCPN extensions and appear in most real NEF files
    (§7). Use them verbatim as frame selectors — don't try to "clean them up".
*   **Reading the category off the framecode visually.** When you need to know a frame's category, prefer
    its `.sf_category` value (or use `frames tabulate` which shows it directly). Visual decomposition can
    misfire on names that themselves contain underscores.
*   **Confusing loop namespace with column namespace.** A column tag has *two* namespace levels: the
    loop-level prefix (shared by every column in a loop) and the column-level prefix from the attribute
    after the dot (may differ — e.g. `_nef_chemical_shift.ccpn_merit`). When you ask "what namespace owns
    this column?", you usually mean the column level. See §6.4.
*   **Saveframes whose first token isn't a registered namespace** (e.g. `nef`, `ccpn`, `aria`, `nefpls`, ...; §6.1).
    The file will still parse — treat the first underscored token as the namespace — but namespace-aware analysis on
    its tags and loops may be unreliable. A near-miss to a registered namespace probably indicates a typo. Flag it to
    the user; don't reject the file or guess the intended namespace.
*   **Hard-coding a registered-namespace list from this document.** The list grows over time. Query what
    namespaces are listed using `nef namespace catalog` and the namespaces present using `nef namespace list`
*   **Assuming a "valid NEF" file in mid-pipeline.** NEF-Pipelines streams may legitimately omit the
    standard meta_data / molecular_system / chemical_shift_list frames during intermediate steps (§9).
    Don't insist on adding them unless the user is producing a final output.
*  **avoid metacharacters in tag and values**: Because NEF is a text format, characters like `#`, `;`,
   in  values and tag names can cause parsing problems and may lead to the need for escaping [commands that need escaping
   will report this an error and ask you to use an escaping flag e.g. `--escape-values` etc]
*  **Some metacharacters are inescapable** NEF / CCPN use `s to surround indices and #'s and @'s are used to define
   unassigned chains. **These are not problems** and are properly handled by NEF-Pipelines. Don't try to "clean" them up
   or flag them as errors.
*  **Spectrum frames are peak lists** a 'nef_nmr_spectrum' frame is not a spectrum definition but a peak list.
   This is a common source of confusion because in other contexts a "spectrum" might be expected to contain the
   information about just a measured NMR spectrum.

---

## 11. Dictionaries and Validation
*   **NEF Dictionary:** The official NEF mmcif dictionary defines the core saveframes, tags, and their expected data
    types. However, NEF-Pipelines currently can't currently read this dictionary or validate against it.
*   **Mandatory Saveframes, Loops and Tags** The NEF dictionary defines some saveframes, loops and tags as mandatory
    for a valid NEF file. Other saveframes, loops and tags are non madatory or optional so two Saveframes will not
    always have the same set of tags and loops. The only way to detemine if a Daveframe, Loop or tag is mandatory is to
    read the dictionary.
    > Note: `NEF-Pipelines` does not currently enforce the presence of mandatory saveframes, loops or tags.
---

# 12. Online resources
*   **NEF website:** https://github.com/NMRExchangeFormat/NEF/tree/master/specification — the official specification,
    annotated example and dictionary. versions are listed as v1_0, v1_1 etc. Versions under development have  extra
    text after the version number e.g. v1_2_under_review and can be ignored. The most Important documents are

    1. `Overview_v1_1.md` - the overview document
    2. `mmcif_nef_v1_1.dic` - the definitive mmcif dictionary defining the core NEF saveframes and tags
    3. `Commented_Example_v1_1.nef` - a fully annotated example file many core `nef` saveframes, loops and tags

*   **CCPN NEF documentation:** [CCPN NEF webpage for users](https://www.ccpn.ac.uk/manual/v3/NEF.html) — CCPN's
    showing how nef is used an defined.

*  **NEF Paper:** [The NMR Exchange Format (NEF): Specification and Applications](
   https://www.biorxiv.org/content/10.64898/2026.04.22.715536v1) — provides the latest publication on the NEF format
   including its design principles, applications, and examples of use in the field of NMR spectroscopy. This is a good
   resource for understanding the rationale behind NEF and its practical implications. There is also a
   [supplementary material file](https://www.biorxiv.org/content/10.64898/2026.04.22.715536v1.supplementary-material)
*  **NEF Proposal for NMR Relaxation Data:** [NEF Proposal for NMR Relaxation Data](https://github.com/NMRExchangeFormat/NEF/blob/master/specification/Proposal%20For%20Incorporating%20NMR%20Relaxation%20Data%20In%20NEF.pdf)
   - a proposal for extending NEF to cover NMR relaxation data [rates], which is a common type of NMR data that is not
   currently covered by the core NEF specification. This is an in development specification but the NEF-Pipeline tools
     - `series build` - building a series of relaxation data points from a set of NEF spectrum frames
     - `series table` - build a nef data table for a series of save frames with relaxation data points
     - `nef fit exponential` - fitting exponential decay curves to relaxation data and extract rates
   support it in the `nefpls` namespace.
