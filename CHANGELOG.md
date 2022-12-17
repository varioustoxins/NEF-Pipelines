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
