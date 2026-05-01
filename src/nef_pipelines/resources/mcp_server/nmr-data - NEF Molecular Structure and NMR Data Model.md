# NEF Molecular Structure and NMR Data Model

This document describes how NEF represents molecular structure and NMR experimental data, and how they link together.
This is **domain knowledge** about NMR and molecular systems, distinct from the NEF STAR dialect syntax covered in the
main `nef` resource.

## The Four-String Identifier (Primary Key)

All NMR data in NEF (chemical shifts, peaks, restraints, RDCs, relaxation parameters) links back to the molecular
structure via a **4-string identifier**. This is the case-sensitive primary key:

1. **`chain_code`** — identifies the molecular chain (typically `A`, `B`, etc.; can be any string)
2. **`sequence_code`** — residue number (integer or integer+insertion code, e.g. `42`, `42A`)
3. **`residue_name`** — standard IUPAC 3-letter code (e.g. `ALA`, `HIS`, `CYS`)
4. **`atom_name`** — IUPAC atom name with NEF extensions (e.g. `CA`, `HN`, `HB%` for methyl wildcard)

### How It Works

Every experimental observation (a chemical shift, a peak position, an NOE distance) carries these four strings to
identify which atom(s) it refers to. For example:

```STAR
loop_
   _nef_chemical_shift.chain_code
   _nef_chemical_shift.sequence_code
   _nef_chemical_shift.residue_name
   _nef_chemical_shift.atom_name
   _nef_chemical_shift.value

   A  10  HIS  H   8.521
   A  10  HIS  N  119.832
   A  11  MET  H   7.321
stop_
```

Each row uniquely identifies an atom (`A/10/HIS/H` = the amide proton of histidine 10 in chain A) and associates a
measured value (8.521 ppm) with it.

### Assignments and Arbitrary Four-String Identifiers
The four strings are address labels, not assertions. Any combination of legal strings is syntactically valid in NEF and
CCPN data — the file will parse. They become an *assignment* only when the chain_code, sequence_code, residue_name and
atom_name resolve against a residue/atom in `nef_molecular_system`. Mismatches are not parse errors; they're semantic
warnings.
> note: the `residue_name` is effectively optional — if `chain_code` and `sequence_code` match a residue in the
> molecular system then the `residue_name` can be derived from it.


### Atom Name Extensions

NEF distinguishes three cases on top of the standard IUPAC atom names. Knowing which form
you are looking at matters: each implies a different relationship to the underlying atom set.

**1. Stereospecific assignments** use the standard IUPAC name unchanged
(e.g. `HB2`, `HB3` for the two Hβ atoms of arginine).

**2. Non-stereospecific, non-degenerate assignments** swap the distinguishing digit for
`x`/`y` (e.g. `HBx`, `HBy` — the two Hβ atoms are resolved as separate signals but the
stereochemistry has not been determined).

**3. Equivalent / accidentally degenerate atoms** use a wildcard:

| Wildcard | Matches | Example |
|---|---|---|
| `%` | any sequence of digits — regex `[0-9]+` | `HB%` = all three Hβ methyl protons of alanine |
| `*` | any whitespace-free string, including empty — regex `\S*` | `H*` = all hydrogens; `H5'*` = the DNA/RNA H5' / H5'' pair |


**Wildcard rules:**
- Prefer `%` over `*` whenever the only difference is digits — `*` is reserved for cases
  `%` cannot express (`H*`, `C*`, `*`, or names like `H5'*` where the differing characters
  are not digits).
- Use the minimum number of wildcards. `%%` is disallowed.
- The wildcard may only stand in for the characters that actually differ between the
  alternative names. Isoleucine δ-methyl protons must be `HD1%` (not `HD%`), because
  `HD%` would also match δ2 atoms that don't exist on Ile.

**Pseudoatoms (`MB`, `MG`, `QB`, `QG`, `QD`, ...) are not the same as wildcards.**
They name a single geometric centroid (zero van der Waals radius), not a set of atoms.
NEF allows pseudoatoms to coexist with wildcards but recommends the wildcard form because:

- A distance restraint to `HB%` is computed by 1/r⁶ averaging across the matching atoms.
- A distance restraint to `MB` is to a single virtual point — the implied distance limit
  must be different to obtain the same physical result.
- `ALA MB` and `ALA HB%` therefore behave differently in structure calculation; do not
  silently rewrite one as the other.

**Common pseudoatoms (reference):**

| Residue | Pseudoatom | Atoms represented |
|---|---|---|
| Gly | `QA` | α-methylene |
| Ala | `MB` | β-methyl |
| Val | `MG1`, `MG2` | γ1-, γ2-methyl |
| Val | `QG` | all six γ-methyl |
| Ile | `MG`, `MD` | γ2-, δ1-methyl |
| Ile | `QG` | γ1-methylene |
| Leu | `MD1`, `MD2` | δ1-, δ2-methyl |
| Leu | `QB` | β-methylene |
| Leu | `QD` | all six δ-methyl |
| Pro | `QB`, `QG`, `QD` | β-, γ-, δ-methylene |
| Ser, Asp, Cys, His, Trp | `QB` | β-methylene |
| Thr | `MG` | γ2-methyl |
| Asn | `QB` / `QD` | β-methylene / δ2-amido |
| Glu, Gln | `QB`, `QG` | β-, γ-methylene |
| Gln | `QE` | ε2-amido |
| Lys | `QB`, `QG`, `QD`, `QE` | β-, γ-, δ-, ε-methylene |
| Lys | `QZ` | ζ-amino |
| Arg | `QB`, `QG`, `QD` | β-, γ-, δ-methylene |
| Arg | `QH1`, `QH2` | η11/η12 and η21/η22 |
| Arg | `QH` | all four η-guanidino |
| Met | `QB`, `QG` | β-, γ-methylene |
| Met | `ME` | ε-methyl |
| Phe, Tyr | `QB` | β-methylene |
| Phe, Tyr | `QD`, `QE` | δ1/δ2-ring, ε1/ε2-ring |
| Phe, Tyr | `QR` | all ring |
| β-D-ribose | `Q5'` | 5'-methylene |
| 2'-β-D-deoxyribose | `Q2'`, `Q5'` | 2'-, 5'-methylene |
| A | `Q6` | 6-amino |
| C | `Q4` | 4-amino |
| G | `Q2` | 2-amino |
| T | `M7` | 7-methyl |


---

## CCPN Extensions to the Addressing System

### CCPN Offset Sequence Codes

The `sequence_code` is normally an integer residue number, but CCPN extends it with `±N` offsets:
`4-1`, `4-3`, `4+2` mean residues 3, 1, 6. The offset says "the residue *N* positions before/after
this one" — used when assigning peaks in HNCA, HN(CA)CO, NOESY etc. NEF-Pipelines supports the syntax.

### Pseudo Residues and Connected Chains in CCPN

CCPN tags unassigned spin systems with `@N` labels, using the same `±N` offset notation as above.
Two conventions matter:

- **Pseudo-residue IDs (`@N`)** — `@23` is "spin system 23"; the number is just an ID, not a
  sequence position. Offsets compose: `@23-1` is the residue immediately before `@23`. Once `@23`
  is assigned to `sequence_code` 56, `@23-1` resolves to 55.
- **Chains `@-` and `#N`** — fresh pseudo residues live in `@-` (the default unassigned chain).
  Once a run of them is known to be sequentially adjacent in the real sequence, CCPN moves them
  into a *connected chain* `#N` (the integer `N` is an arbitrary grouping label — no sequence
  meaning). Membership in the same `#N` chain *asserts* the ordering, so `@33-1` ≡ `@22` once
  `@22` and `@33` sit adjacent in `#5`. Chains beginning with `#` are containers for pseudo
  residues only.

**Example:** with `@21`, `@22`, `@22-1`, `@33`, `@33-1`, `@54`, `@54-1` placed in `#5` in that order,
assigning `@22` to A96 gives `@22-1` = A95, `@33` = A97, `@33-1` = A96, `@54` = A98, `@54-1` = A97.

NEF-Pipelines supports this convention; transcoders from other software normalise to CCPN's notation
on import.

### Where Connected-Chain Order Is Recorded — `ccpn_assignment`

The order of pseudo residues in a connected chain (`#N`) is **not** derivable from the 4-string
identifier alone. CCPN records it in the `ccpn_assignment` saveframe via two loops: `nmr_chain`
(one row per chain) and `nmr_residue` (one row per pseudo residue or pseudo-residue offset).
An AI working with CCPN-derived NEF cannot reconstruct connected-chain ordering without these.

**`nmr_chain` columns**

| Column | Meaning |
|---|---|
| `short_name` | Chain identifier as used in the 4-string addressing — `@-`, `#5`, `A`, ... |
| `serial` | Stable integer ID, not reused in the project. For connected chains the serial matches the digits in the label (`#5` → serial 5). |
| `label` | For connected chains and `@-`: same as `short_name`. For real molecular-system chains: `@<serial>` (e.g. chain `A` with serial 8 → label `@8`). |
| `is_connected` | `true` only for `#N` chains; the row order in `nmr_residue` defines the sequential adjacency. `false` for `@-` (order undefined) and real chains (order defined by `nef_molecular_system`). |
| `comment` | Free-text. |

**`nmr_residue` columns**

| Column | Meaning |
|---|---|
| `chain_code` | Chain identifier — same as 4-string `chain_code` (`A`, `B`, `#5`, `@-`, ...). |
| `sequence_code` | Same as 4-string `sequence_code` — integer, integer+insertion, offset, or `@N` ID (`10`, `42A`, `3-1`, `@23`). |
| `residue_name` | A free-form label string — like the rest of the 4-string identifier, not a constrained type code. Any legal string works: a 3-letter code (`HIS`), a comma-separated list (`SER,THR`), or arbitrary user-chosen text. Pseudo residues in `@-` and `#N` chains may carry labels too. `.` only on offset rows (`3-1`, `3+1`) — those are pointers to other residues, not residues in their own right. |
| `serial` | Stable integer ID for the nmr residue, not reused in the project. |
| `comment` | Free-text. |

> **NEF-Pipelines support:** NEF-Pipelines does not currently parse `nmr_chain` / `nmr_residue`.
> They are pass-through opaque data — content is preserved on round-trip but not interpreted.


---

## The Molecular System

### Chain Ends and Small Molecule Complexes

The molecular system records each residue's **linking type** in a chain-end column:

- `start` / `end` — chain termini (e.g. N- and C-terminus for a protein)
- `middle` — interior residues
- `cyclic` — first and last residues both set to `cyclic` mark a closed loop with no termini
- `single` — ions, small-molecule ligands, anything not part of a polymer chain
- `dummy` — a residue that isn't part of a real molecule (e.g. a tensor frame for RDC calculation)
- `break` — a sequence break, used to build chimeric molecules; rare to extinct in practice

Chain codes themselves are conventional, not constrained: typically `A`, `B`, ..., but they can be
any string — single-letter PDB codes, XPLOR `segid`s, or anything else.

### Atom Removal and Covalent Connections
The molecular system has a column which lists a series of atoms that have been added to or removed from the canonical
structure of a residue or chemical component. This is used to represent chemical modifications, ionisation,
phosphorylation, etc. In combination with the linking information in the `nef_covalent_links` loop it can be used to
define cross-links between biomolecular chains and links to prosthetic groups or covalently bound ligands.

### Why This Matters for an AI

When you inspect NEF data (via `nef frames tabulate` or user-provided excerpts), you'll see these four columns
repeatedly across shift lists, peak lists, restraint lists, etc. They are **not arbitrary labels** — they form a
relational key linking all experimental data to the molecular sequence defined in the `nef_molecular_system` frame.

**Common tasks:**
- Verify that all referenced atoms exist in `nef_molecular_system`: use `nef chains validate` (α)
- List chains: `nef chains list`
- Inspect sequence: `nef frames tabulate nef_molecular_system`

### Molecular System Structure

The `nef_molecular_system` saveframe defines the reference structure for all 4-string identifiers. It contains:

- **Sequence loops** (`_nef_sequence`): list of residues with `chain_code`, `sequence_code`, `residue_name`
- **Chain metadata**: start/end residues, chain type (protein/DNA/RNA/ligand)
- **Linking information**: whether residues are covalently linked, cyclic chains, etc.

All other NEF data (shifts, peaks, restraints) must reference atoms that exist in this molecular system.

---

## NMR Data Types in NEF

NEF organizes experimental NMR data into typed saveframes. Each type has a standard category and defined loop structure:

### Chemical Shifts (`nef_chemical_shift_list`)

Records resonance frequencies (in ppm) for assigned atoms.

**Saveframe category:** `nef_chemical_shift_list`
**Loop category:** `_nef_chemical_shift`
**Key columns:** `chain_code`, `sequence_code`, `residue_name`, `atom_name`, `value`, `value_uncertainty`

### Peak Lists (`nef_nmr_spectrum`)

Records peak positions, intensities, and assignments from NMR spectra.

**Saveframe category:** `nef_nmr_spectrum`
**Loop category:** `_nef_peak`
**Key columns:** `peak_id`, `position_1`, `position_2`, ..., `chain_code_1`, `sequence_code_1`, `atom_name_1`, ...
  (one set per dimension), `height`, `volume`


Peaks can be unassigned (4-string fields are `.` or `?`) or assigned to one or more atoms.

### Distance Restraints (`nef_distance_restraint_list`)

NOE-derived distance restraints for structure calculation.

**Saveframe category:** `nef_distance_restraint_list`
**Loop categories:** `_nef_distance_restraint`, `_nef_distance_restraint_atom` (linked by `restraint_id`)

### Dihedral Restraints (`nef_dihedral_restraint_list`)

Backbone/sidechain torsion angle restraints (often from TALOS or J-couplings).

**Saveframe category:** `nef_dihedral_restraint_list`
**Loop category:** `_nef_dihedral_restraint`

### RDC Restraints (`nef_rdc_restraint_list`)

Residual dipolar coupling data (for alignment tensors, structure refinement).

**Saveframe category:** `nef_rdc_restraint_list`
**Loop category:** `_nef_rdc_restraint`

---

## Assignment Status

Peaks and other data can be:
- **Fully assigned:** all 4-string fields populated
- **Partially assigned:** some dimensions assigned, others `.`
- **Unassigned:** the 4-string fields are `.`, or contain any string that doesn't resolve against
  `nef_molecular_system`. Because the four strings are just labels, a user can put any legal string in
  them — `?`, `?not sure what this is?`, or any other free-form placeholder — none of which constitutes an
  assignment.
- **Inconsistent:** all four strings are populated and `chain_code` / `sequence_code` / `atom_name` resolve against
  `nef_molecular_system`, but the `residue_name` disagrees with what the molecular system says for that position
  (e.g. `A 10 HIS H` where A/10 is actually ALA). The atom is still uniquely identified — `chain_code` +
  `sequence_code` + `atom_name` are sufficient and `residue_name` is redundant — so a `.` here is harmless. A *wrong*
  `residue_name` usually means stale data carried over from a previous assignment, or that the `sequence_code` itself is
  wrong. Not a parse error; flag it as a warning. See *Assignments and Arbitrary Four-String Identifiers*.

The presence of assignments is what distinguishes raw peak lists from assigned/integrated data suitable for structure
calculation.

> **NEF-Pipelines commands:**
> Filter by assignment status: `nef frames filter --assigned` / `--unassigned`

---

## Cross-References

For NEF STAR syntax (namespaces, saveframes, loops, tags), see the main `nef` resource (`nef://nef`).

For foundational STAR format rules, see the `star` resource (`nef://star`).
