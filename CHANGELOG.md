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
  1. pyparsing was triggering a deprecation warning
  2. pynmrstar had a bug in renaming frames

## version 0.1.58
- corrected a bug in Linking lookup in the nmrstar project subcommand that affected some python versions

## version 0.1.59
- corrected a bug in fasta sequence importer that affected files with spaces between residues
- improve handling of figures of merit especially for MARS peak imports
- spectrum dimension transfers were not correct in peak imports

## version 0.1.60
- add support for c detect spectra for idps in peak simulation code

## version 0.1.61
- use requests to download bmrb files from the web

## version 0.1.62
- use urllib3 <= / == 1.26.15 to avoid a security warning

## version 0.1.63
- remove dependance on Levenshtein which was causing compilation errors

## version 0.1.64
- update to fyeah to try to make windows installation work

## version 0.1.65
- fixed a bug in export of CO shifts reported by Pete Simpson

## version 0.1.66

Major release with many new features and bug fixes

- Relaxation
  - Added initial support for fitting [using [Streamfitter](https://github.com/varioustoxins/Streamfitter)] this uses the NEF provisional data series format  [command: series build]
  - Added a tool to build a NEF [provisional] data series format from spectra [aka peak lists] [command: series build]

- Multi file streams
  - Added the ability to save a series of NEF files from a multi entry stream [command save]
  - Added the ability to stream multiple NEF files from BMRB entries [command nmrstar project]

- Documentation & Project
  - NEF-Pipelines has a citation record
  - Add an initial version of design doc for NEF-Pipelines describing the internals of the pipe commands within the pipeline
  - The project is now automatically tested on python 3.9-3.12 and Linux and MacOS as a matrix hsing GitHub Actions

- MARS and Fasta
  - Fasta output and input to NEF-Pipelines supports round tripping of chain ids [chain_codes] and chain starts via a custom header
  - Mars has a command to read in a sequence from its Fasta file [including round tripping if written by NEF-Pipelines]  [command mars import sequence]
  - Better support of a variety of Fasta headers (including PDB/RCSB headers)
  - Fasta input and output the entry_id of the NEF stream is saved as the entry name of the fasta file
  - Mars sequence exports has better error handling [command: mars export sequence]
  - Fasta has improvement to the sequence handling [molecule type per sequence] and provides a python pipe command

- Simulations
  - The command `simulate peaks` replaces the command `shifts make_peaks` [mostly a rename]
  - Types of spectra are now arguments to `simulate peaks` not options and the command has better error messages and case-insensitive matching of spectra names [where possible]
  - Simulation of unlabelling spectra added [command: simulate unlabelling]

- NMRStar and the BMRB
  - Add the ability to read BMRB sequences, shifts and projects [currently shifts and sequences] [commands: nmrstar import sequences and nmrstar import shifts]

## version 0.1.68

- add missing dependency on parse

## version 0.1.69

- StrEnum was imported from wrong package

## version 0.1.70

- handling fo the default file path in save wasn't working
- simulate unaleblling improved help text
- incosistent use of DataType in streamfitter and fit expoenetial was corrected
- DataType replaced with IntensityMeasuremenType

## version 0.1.71 & 0.1.72
improved error handling when `streamfitter` does load into `fit exponential`

## version 0.1.73

-  no major changes

## version 0.1.73

- erroneous release no major updates

## version 0.1.74
- better handling of NEF-Pipelines fasta headers for round tripping
- many more fasta format headers supported
- correct error in handling beta sheet records in pdb files
- pdbx reader takes sequence from SEQRES records as default
- add initial chemical shift averager [alpha quality]
- unassign supports creating ccpn style residue -1 entries e.g @32-1

## version 0.1.75
- peak dimesnions were incorrecly indexed causing a failure to import into CCPN suite of programs
