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
