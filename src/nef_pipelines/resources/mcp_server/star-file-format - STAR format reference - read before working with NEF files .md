# STAR Format Reference

> **Read this before the `nef` resource.** STAR is the foundational text-file syntax; the `nef` resource layers
> an ontology (namespaces, categories, the 4-string identifier) on top. You consume STAR through NEF-Pipelines
> MCP commands — you don't parse files yourself or generate raw STAR text. The job of this document is to give
> you enough syntactic vocabulary to read command output and to understand the constraints the `nef` resource
> assumes.

## 1. Logical Structure

The **Self-defining Text Archive and Retrieval (STAR)** format is a sequential file of ASCII characters organized into
a hierarchy of data blocks and saveframes.

> Note: It is defined by the following papers:
> * Hall, S. R. (1991) *J. Chem. Inf. Comput. Sci.* **31**, 326. — original STAR specification.
> * Hall, S. R. & Spadaccini, N. (1994) *J. Chem. Inf. Comput. Sci.* **34**, 505. - detailed specifications and
>   EBNF grammar.
> * Spadaccini, N. & Hall, S. R. (2012) *J. Chem. Inf. Model.* **52**, 1901. — current STAR2 specification some
>   features desscribed are not implimented [IUAPC, """ strings, beel escapes etc] but it disucsses the format well.

### Keywords

Keywords are defined as the **strictly lowercase** literal terminals `data_`, `loop_`, `global_`,
`save_`, and `stop_`. They may not be used for data item specification. To use them as data names or values,
they must be quoted.

### Lexical Tokens
1.  **Tags (Data Names):** A sequence of one or more non-white space characters starting with an underscore `_`.
2.  **Data Values:** Text strings that **do not** start with an underscore.
      * **Unquoted:** Single words. Must not start with a keyword sequence.
      * **Quoted:** Enclosed in `'` or `"`. These **can** contain keyword sequences or start with underscores.
      * **Semicolon-bounded multi-line text**. The string opens with a semicolon `;` in column 1 of a line. The
        multi-line string continues until another line is encountered that starts with a semicolon in column 1.
        The multi-line string may contain any characters, including keywords and whitespace. If the string needs to
        contain a semicolon at the start of a line all lines must be indented consistently to avoid early string
        termination.

3.  **Whitespace:** Space, Horizontal Tab, Newline, and Form Feed. Used only as delimiters.
4.  **Comments:** Initiated by a `#`; continues to the end of the line and is generally ignored by the STAR parser.

### Structural Hierarchy
*   **Data Block (`data_`):** The top-level container. All content following `data_<id>` belongs to that block until
    the next data block starting with `data_` is encountered or EOF.
*   **Saveframe (`save_`):** A sub-container for grouping data.
    *   **Initiator:** `save_` followed by a unique `<id>`.
    *   **Terminator:** The standalone keyword `save_`.
    *   **Nesting:** You will never see nested saveframes in NEF-Pipelines output, though the STAR format allows it.
*   **Loop (`loop_`):** Tabular data structure contained by a Saveframe.
    *   **Structure** consists of a `loop_` keyword, a list of `tags` which define the columns, a series of data values defining the
        column data, and a terminating `stop_` keyword [this is optional in the basic STAR syntax].
    *   **Nested loops:** STAR allows loop nesting and loops at data block level. These are not supported by NEF.
    *   **Column layout logic:** The number of values following the loop's tags must be an exact multiple of the number
        of tags in the loop header; these values make up the loop.

### Example STAR file:
Note: STAR files are ascii text files as is this example.
```STAR
# 1. DATA BLOCK: Initiates the highest organizational unit.
# Must start with 'data_' (lowercase reserved word).
data_minimal_nef_star_example

    # 2. SAVEFRAME INITIATOR: Starts a grouping.
    # Matches 'save_<identifier>'. Reserved lowercase keyword.
    save_nef_nmr_meta_data

        # 3. TAG-VALUE PAIRS: Single data items.
        # TAGS MUST start with '_'
        _nef_nmr_meta_data.sf_category      nef_nmr_meta_data
        _nef_nmr_meta_data.sf_framecode     nef_nmr_meta_data
        _nef_nmr_meta_data.format_version   1.1

        # 4. QUOTED VALUES: Strings with spaces or special characters must be quoted.
        _nef_nmr_meta_data.program_name     'Analysis Assign'

        # 5. SEMICOLON-BOUNDED MULTI-LINE TEXT:
        # Starts with ';' at column 1, ends with ';' at column 1 on a new line.
        _nef_nmr_meta_data.ccpn_comment
;
This is a multi-line string.
It can contain keywords like data_ or save_
because they are protected by the boundaries.
it can contain comment characters e.g. #, other quotes and keywords like loop_
they are a pain to use and should be avoided.
;

        # 6. LOOPS: Tabular data structures.
        # Initiated by the loop_ reserved keyword.
        loop_
            _nef_program_script.program_name # Column 1 header
            _nef_program_script.script_name  # Column 2 header
            _nef_program_script.script       # Column 3 header
            _nef_program_script.comment      # Column 4 header

            # 7. DATA VALUES: Flat list of values mapped to the headers above.
            # Number of values must be a multiple of the number of tags.
            # #'s keywords and quotes must be protected by quotes
            '#CcpNmr'  'loop_'  . "this isn't a problem"

            # 8. LOOP TERMINATOR: Specifically used in STAR to close a loop.
            # While optional in some STAR applications, NEF requires it.
        stop_

    # 9. SAVEFRAME TERMINATOR: Standalone keyword.
    # Logical boundary; no nesting of saveframes is permitted in NEF.
    save_

    # 10. multiple SAVEFRAMES are allowed in a STAR file
    save_nef_chemical_shift_list_default

        _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
        _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_default

        loop_
            _nef_chemical_shift.chain_code
            _nef_chemical_shift.sequence_code
            _nef_chemical_shift.residue_name


            A   1   HIS
            A   2   MET
        stop_

        # 11. Frame level TAGS must be unique within a SAVEFRAME but can be defined anywhere in the frame.
        # However it is conventional to define them at the top of the SAVEFRAME [unlike this example]
        _nef_extra_tag   .

        # 12. SAVEFRAMES can have multiple LOOPS, in a STAR file the TAG names in the second loop can be
        # the same as those in the first loop this is _not_ allowed in NEF files as the start of the
        # tag defines a loop category and each loop must have its own distinct category
        loop_
            _ccpn_chemical_shift.chain_code
            _ccpn_chemical_shift.sequence_code
            _ccpn_chemical_shift.residue_name

            A   1   HIS
            A   2   MET
        stop_

    save_

# 13. Multiple DATA BLOCKS are allowed in STAR files but not in NEF files.
# Each STAR file must contain exactly one DATA BLOCK.

#NOTE: we usually indent STAR files to improve readability but this is not required by the STAR syntax.
The only position requirement is that ;'s in multi line strings must be in column 1.
```
