# Changelog

## Version 0.1.0b (development)

initial version which supports the following (to some extents; note the beta designation)

### tools

- listing renaming and cloning molecular chains
- deleting, inserting, listing and pretty printin (tabulate) save-frames
- producing a NEF header with correct UUID
- streaming nef files into a pipeline
- testing itself

#### transcoders
- __fasta__
  - sequence [read and write]
- __mars__
  - shifts [write]
- __nmrpipe__
  - sequences [read]
  - shifts [read]
  - peaks [read]
- __nmrview__ / __nmrfx__
  - peaks [read and write]
  - sequence [read]
  - shifts [read]
- __pales__
  - rdc restraints [write]
  - rdc restraints template [write]
- __pdb__
  - sequence [read]


## Version 0.1.21 (development)

Initial release to pypi with changes for better compatability with windows and
linux

The `nef test` command was disabled for this release as pytest and the tests
were not working well with the pyscaffold based release pipeline.

There were no changes in the tools and transcoders provided in this release,
as this release was mostly about removing technical debt

## Version 0.1.22 (development)

The `nef test` command is once again available.

A reliance on caching stdin was removed

There were no changes in the tools and transcoders provided in this release,
other than the test subcommand, as this release was focused on testing.

## Version 0.1.23 (development)

supports reading xplor distance restraints [but currently only single atom selections]

adds xplor nih dihedral restraints

read sequences from xplor psf files

minor improvements to help text and error messages

note: the xplor support includes a proper parser for xplor nested restraint selections
including SEGIDentifier RESIDue and NAME including proper literal abbreviations.

## Version 0.1.24 (development)

added support for import of RDCs from a csv file

added support for segment codes to pales / dc when exporting rdcs

added support for exporting neff rdc restraints to xplor legacy format

## Version 0.1.25 (development)

added missing test files

## Version 0.1.26 (development)

corrected an error in how test files are searched for

## version 0.1.27

added support for reading MARS shift files


## version 0.1.28

added an about command for information about the project

added support for export xcamshift chemical shift restraint files

added export of mars connected pseudo residue file

## version 0.1.29

correct error in mars export fragments (mars connected pseudo residue file)

## version 0.1.30

add support for writing sparky peak lists

## version 0.1.31

add rudimentary rpf shift list exporter

add a sparky peak list importer [alpha no tests]

## version 0.1.32

patches to rpf exporter

##  version 0.1.33

add the ability to rename nef frames

add a verbose option to about [lists os and python versions]

add the ability to suppress assignment height and volume columns in sparky peak export

## version 0.1.34

shifts make peaks now has test suite

## version 0.1.35

minor cleanups

## version 0.1.36

initial support for RNA and DNA added (only surfaced in the sparky importers)

sparky sequence import including RNA and DNA

sparky peak import fully supported with all fields shown in the spark manual

## version 0.1.37

improved sparky assignment parsing which is also refactored into a reusable
library

## version 0.1.38

initial experiments support for echidna peaks files

## version 0.1.39

fixed a bug in frames list (verbose option was ignored)

## version 0.1.40

fix a bug: make peaks faaled on generating empty peak lists

## version 0.1.41

add importers for xeasy [flya dialect] sequences, peaks and shifts
a  number of bug fixes in the sparky and echidna tools

## version 0.1.42

add the ability to unassign frames in general with support for different sequence_code
unassignment strategies and the ability to choose what is unassigned (chain_code, sequence_code
residue_name atom_name)

## version 0.1.43
fasta input tool can read RNA/DNA sequences
improvemenets to the xplor distance restraint reader to suppport CNS

## version 0.1.44
correct error in naming frames in restraint lists produced by xplor import distance

## version 0.1.45
removed bug in reading input streams in nmrview peak reader and updated tests

## version 0.1.46
initial support for talos [export of shifts]

## version 0.1.47

support for reading talos PHI PSI restraints into NEF

## version 0.1.48

complete support for talos including
- sequences that don't start at residue 1
- support for oxidised cys and protonated his variants
- import of secondary structure to nef
- import of S2 values to nef
- support of chi restraints

improved testing to cover all new features
bug fixes for talos

## version 0.1.49 - withdrawn [non functional release]

- rename can now edit frame names
- --pipe is now --in
- output to csv files is supported using tabulate
- the pdbx subcommand is now rcsb and supports mmcif
- remove use of biopython
- use new lighter weight mmcif pdb and fasta parsers

## version 0.1.50
release is the same as 0.1.49 but...
- added missing packages required for installation

## version 0.1.51
- added support for reading NMR-STAR shifts and sequences
- various bug fixes

## version 0.1.52
release is the same as 0.1.51 but...
- added missing packages required for installation
  - annotated-types
  - hjson
  - pydantic

## version 0.1.53
release is the same as 0.1.51 but...
- added missing packages required for installation
  - cache_tools

## version 0.1.54
- added support for reading NMR-STAR projects from disk or the web
  - including reading shifts and sequences
  - supports direct download from the bmrb just using an accession code

## version 0.1.55
- shifts make peaks now supports non ccpn peak lists for triple resonance spectra†

† ccpn peak lists when incompletely assigned use @xx-1 to indicate the previous residue
  and this was supported in the previous release but raw peak numbers weren't!

## version 0.1.56
- bmrb accession codes are now supported as raw numbers as well as bmrXXXXX in the nmrstar project subcommand

- improve shifty output, by default it now
  1. infills missing residues
  2. selects a single assigned chain to output if present
  3. outputs to a templated file name

## version 0.1.57
- upgrade pyparsing and pynmrstar
  1. pyparsing was triggering a deprication warning
  2. pynmrstar had a bug in renaming frames

## version 0.1.58
- corrected a bug in Linking lookup in the nmrstar project subcommand that affected some python versions

## version 0.1.59
- corrected a bug in fasta sequence importer that affected files with spaces between residues
- improve handling of figures of merit especially for MARS peak imports
- correct spectrum dimension transfers were not correct in peak imports
