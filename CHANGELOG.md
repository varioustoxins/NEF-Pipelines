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
