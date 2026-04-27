### NEF: Logical Definition and Formatting
   
    The **NMR Exchange Format (NEF)** is a restricted application of STAR that provides a unified ontology for NMR experimental data.
   
    ### Global Constraints
    *   **Single Block:** A NEF file must contain **exactly one** `data_` block.
    *   **Mandatory Saveframes:** A valid file requires:
        1.  `_nef_nmr_meta_data`: Versioning and software provenance.
        2.  `_nef_molecular_system`: The chemical composition (chains, residues).
        3.  `_nef_chemical_shift_list`: Resonance frequencies.
    *   **HOWEVER** Nef-Pipelines doesn't require valid NEF files in its streams or output as this is too restrictive



    ### NAMESSPACES
    * NEF SAVEFRAMES, FRAME-TAGS, LOOPS, and COLUMN-TAGS can all start with a NAMESPACE which is a single block of text uninterrupted
      by _'s which says which program owns the SAVEFRAMES, FRAME-TAGS, LOOPS, and COLUMN-TAGS. 
    * Examples of NAMESPACES include nef, aria, ccpn etc the nef command `namspaces defined` will list the currently know NAMESPACES
    * NAMESPACES can be used to extend SAVEFRAMES, LOOPS etc with data from other programs
    * How NAMESPACES are defined and interact is complicated and discussed in the `namespaces` resocurce

    ### CATEGORIES
    * NEF defines CATEGORIES on LOOPS and SAVEFRAMES which describe what sort of data they contain such as nef_chemical_shift_list,    nef_molecular_system, nef_spectrum etc. 
    * NEF defines CATEGORIES in NAMESPACES so a CATEGORY will start with its NAMESPACE


    ### Identifying SAVEFRAME names categories and indices
    NEF expands the definition of SAVEFRAMES so they have NAMESPACES, CATEGORIES, NAMES and INDICES

    * The Structure of a NEF SAVEFRAME TAG can be 

     `_save_<NAMESPACE>_<CATEGORY>[_NAME][`INDEX`|.identity]`

     here [_NAME][`INDEX`|.identity] are optional

     The NAMESPSACE and CATEGORY can be identified by looking for the .sf_category tag inside the save frame, so for example  for the deinition


      ```STAR
         save_nef_nmr_spectrum_hncacb`1`

            _nef_nmr_spectrum.sf_category                   nef_nmr_spectrum
            _nef_nmr_spectrum.sf_framecode                  nef_nmr_spectrum_hncacb`1`
            _nef_nmr_spectrum.num_dimensions                3

            # rest of the saveframe definition... 
      ```

      the `_nef_nmr_spectrum.sf_category` FRAME-TAG identifies the NAMESPACE and CATEGORY of the frame as being `nef_nmr_spectrum`
      the NAMESPACE can be identified as `nef` as it is the first _ separated set of charcters in the framecode. 
      the CATEGORY can be identified as `nmr_spectrum` as this is what is left after the namespace is removed
      the SAVEFRAME NAMESPACE and CATEGORY proceeed all of the SAVEFRAME-TAGS and are separated from the tag by a .


      The complete name of the SAVEFRAME can be found in the FRAME-TAG `sf_framecode` which in this case is `nef_nmr_spectrum_hncacb\`1\``
      The name of the SAVEFRAME is `hncacb\`1\`` which in this case conists of a name `hncacb` and an INDEX `1`. 
      Treating `1` as an index is not part of the NEF definiton but is wisely used by CCPN software suite and other software and is supported by NEF-Pipelines.
      It should be noted that the NAMESPACE and CATEGORY are repeated before all the SAVEFRAME-TAGS in the `nef` NAMESPACE
      It should, however, be noted that NAMESPACE definitions are a little complicated and appear to involve inheritance, see the 
      custom NAMESPACES section.

   * Singleton SAVEFRAMES

      Some SAVEFRAMES are singletons and only one of them can be prsent in a file. Standard DAVEFRAMES that are singletons are 
      `_nef_nmr_meta_data` and  `_nef_molecular_system` 
      Singleton SAVEFRAMES are identified by having only a NAMESPACE and CATEGORY and no NAME or INDEX parts
      An example of a singleton `_nef_nmr_meta_data`. SAVEFRAME definitions is shown below.
      

      ```STAR
         save_nef_nmr_meta_data
            _nef_nmr_meta_data.sf_category      nef_nmr_meta_data
            _nef_nmr_meta_data.sf_framecode     nef_nmr_meta_data
            _nef_nmr_meta_data.format_name      nmr_exchange_format

         # rest of the saveframe definition... 

      ```

      ### Indentifying LOOP NAMESPACES, CATEGORIES and TAGS

      LOOPS can also include NAMESPACES, CATEGORIES and TAGS
      The LOOPS CATEGORY and NAMESPACE proceed its COLUMN-TAG for each tag. 
      Here is an example of a `nef_sequence` LOOP ansd its COLUMN-TAGS inside a `nef_molecular-system`


      ```STAR
         save_nef_molecular_system

            _nef_molecular_system.sf_category   nef_molecular_system
            _nef_molecular_system.sf_framecode  nef_molecular_system

               loop_
                  _nef_sequence.index
                  _nef_sequence.chain_code
                  _nef_sequence.sequence_code
                  _nef_sequence.residue_name
                  _nef_sequence.linking
                  _nef_sequence.residue_variant
                  _nef_sequence.cis_peptide

                  1   A  1   HIS  start   .  .  .  
                  2   A  2   MET  middle  .  .  .  
                  3   A  3   ARG  middle  .  .  .  

                  # # rest of the loop definition... 
            stop_
         save_
      ```

      In the case above the LOOP `nef_sequence` is nested in the SAVEFRAME `nef_molecular_system`
      The COLUMN_TAGS are `index`, `chain_code`, `sequence_code`,  `residue_name`, `linking`, `residue_variant` and `cis_peptide`

    

   
    ### The Logical Identification Key
    NEF relies on a **Four-String Identifier** to link all data (shifts, peaks, restraints) to the molecular system:
    1.  **Chain Code**
    2.  **Sequence Code** (Residue Number)
    3.  **Residue Name**
    4.  **Atom Name** (Standardized to IUPAC; uses `%` for ambiguous methyls).
   
    ### Relational Logic (ID Linking)
    Instead of deep nesting, NEF uses cross-reference IDs:
    *   **`peak_id`:** Unique within a spectrum saveframe.
    *   **`restraint_id`:** Unique within a restraint saveframe.
    *   **`_nef_restraint_links`:** A specific loop that maps a `restraint_id` back to its originating `peak_id` and spectrum name, preserving experimental provenance.
   
    ### The Pass-Through Rule
    Software-specific NAMESPACES (e.g., `_aria_`, `_ccpn_`, `_xplor_`) are permitted.
    *   **Logic:** A NEF-compliant reader **must** preserve any tags, loops or saveframes with NAMESPACES listed outside the `nef` namespace. It should treat them as opaque "blobs" and write them back to the file unchanged during save operations.