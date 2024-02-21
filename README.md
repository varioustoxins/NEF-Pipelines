<!-- These are examples of badges you might want to add to your README:
     please update the URLs accordingly

[![Built Status](https://api.cirrus-ci.com/github/<USER>/nef_pipelines.svg?branch=main)](https://cirrus-ci.com/github/<USER>/nef_pipelines)
[![ReadTheDocs](https://readthedocs.org/projects/nef_pipelines/badge/?version=latest)](https://nef_pipelines.readthedocs.io/en/stable/)
[![Coveralls](https://img.shields.io/coveralls/github/<USER>/nef_pipelines/main.svg)](https://coveralls.io/r/<USER>/nef_pipelines)
[![PyPI-Server](https://img.shields.io/pypi/v/nef_pipelines.svg)](https://pypi.org/project/nef_pipelines/)
[![Conda-Forge](https://img.shields.io/conda/vn/conda-forge/nef_pipelines.svg)](https://anaconda.org/conda-forge/nef_pipelines)
[![Monthly Downloads](https://pepy.tech/badge/nef_pipelines/month)](https://pepy.tech/project/nef_pipelines)
[![Twitter](https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter)](https://twitter.com/nef_pipelines)
-->

[![Project generated with PyScaffold](https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold)](https://pyscaffold.org/)

# NEF-Pipelines

__*Tools for Manipulating NEF [NMR Exchange Format] Files and Foreign File Access*__

NEF-Pipelines is a set of command line (currently... there maybe a gui later!) tools for maniulating [NEF] or NMR
Exchange Format files which can be used to move NMR meta data [peaks, shifts, sequences etc] between NMR data processing
programs.The programs provide basic tools for manipulating nef files:

> Please note NEF-Pipelines is beta software and is quite new so if you do find problems put in an issue on the
  [issue tracker]. Even better if you can help improve the software do get in touch, there is much to do!

* __molecular chains__: listing, renaming and cloning molecular chains
* __save-frames [tables]__: deleting, inserting, listing and pretty printing (tabulate)
* __headers__ creation / updating NEF headers with correct UUIDs and history
* __streaming__: NEF files into a pipeline
* __testing__: self testing of NEF pipelines

It also provides tools for importing and exporing non NEF files from the following programs [transcoding / translators]

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
- __pdbx__
  - sequence [read]
- __xplor__
  - sequence [read]
  - dihedral restraints [read]
  - distance restraints 'single atom selections [read]

## Installation

NEF-Pipelines can be installed using pip and pipx

Firstly install pipx if you need to, using the commands for your OS ...

#### OSX

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```
#### Windows using WSL2

follow the instruction for linux distro of choice inside WSL2...

#### Ubuntu / Mint

```bash
sudo apt install pipx python3-venv
```

#### Fedora / RHEL / Centos/ ROCKY Linux / AlmaLinux

```bash
sudo dnf install pipx
```

#### openSUSE
```bash
sudo zypper install python3-pipx
```

#### Then to install NEF-Pipelines
```bash
python3 -m pipx install nef-pipelines
```
after the install has completed you can type

```bash
nef
```

and should see output that starts

```
Usage: nef [OPTIONS] COMMAND [ARGS]...                                                                                                                                                                                        ✔ ╱ took 14s  ╱ nef_pipelines  ╱ at 23:29:36 

Options:
...
```

## Updating NEF-Pipelines

```bash
python3 -m pip install --user -U pipx
```

## Pipelines and Standalone Use
 All commands also have a
help options triggered using `--help` or when no input is detected. So for example the `nef` command on its own produces

```
Usage: nef [OPTIONS] COMMAND [ARGS]...

Options:
  --install-completion [bash|zsh|fish|powershell|pwsh]
                                  Install completion for the specified shell.
  --show-completion [bash|zsh|fish|powershell|pwsh]
                                  Show completion for the specified shell, to
                                  copy it or customize the installation.

  --help                          Show this message and exit.

Commands:
  chains   - carry out operations on chains
  fasta    - read and write fasta sequences
  frames   - carry out operations on frames in nef frames
  header   - add a header to the stream
  mars     - export mars [shifts and sequences]
  nmrpipe  - read nmrpipe [peaks shifts & sequencess]
  nmrview  - read and write nmrview [peaks, sequences & shifts]
  pales    - read and write pales/dc [rdcs]
  pdb      - read pdb [sequences]
  stream   - stream a nef file
  test     - run the test suite

```

Individual nef pipeline componenets can be used standalone by using the `--in` or `--pipe` parameter which will either
read a foreign file for translators or read a NEF file for commands that manipulate NEF files. So for example to lists
the frames in NEF frame you can type

```bash
nef frames list --in test_data/pales_test_1.nef
```

this will produce

```bash
entry pales_test

nef_molecular_system  nef_rdc_restraint_list_test_1
```

which shows  the entry name followed by the frames in the file `test_data/pales_test_1.nef`. However,  the real
power in NEF-Pipelines comes from combining pipeline commands together or with command line tools. For example

```bash
nef header                                   \
| nef fasta import sequence tailin1.fasta    \
| src/nef nmrview import shifts tailin1.out  \
| src/nef nmrview import peaks tailin1.out   \
> tailin1.nef
```

will create a valid NEF header followed by the tailin1 sequence as a molecular system and then import shifts and peaks
for talin1 before writing a new NEF file `tailin1.nef`

The commands provided by NEF-Pipelines are hierarchical in nature. All commands are call by the NEF command but there
are sub commands so for example to import a sequence froma pdb file tou would type  `nef psb import sequence` followed
by the name of the PDB file and relevant options. This can look lomng winded bu NEF-Pipelines support command completion
so typing a double tab will list all availabe sub commands.

For example
``` bash
nef<tab><tab>
```
shows

```
chains   fasta    frames   header   mars     nmrpipe  nmrview  pales    pdb      stream   test
```

and

```bash
nef nmrview import<tab<tab>
```

shows

```
peaks sequence shifts
```

## More information on NEF

The origional [NEF paper] is not a good description of the format more an outline of ideals and needs. The [CCPN]
website has a good [guide to nef] and development takes place on [github] via the [NEF consortium repository] which
includes an [annotated NEF example] and a [dictionary defining the format]. NEF is a [STAR format] which means it has
similarities to [NMRStar] files used by the [BMRB] and [PDBx / mmCIF] used by the [RCSB / PDB] because its uses the same
underling format. However, its is not directly interchangeable with these file formats as it has a different syntax and
intention / underlying use easy and accurate NMR data interchange] as opposed to archiving for example.



[NEF paper]: https://www.nature.com/articles/nsmb.3041
[guide to nef]: https://www.ccpn.ac.uk/manual/v3/NEF.html
[CCPN]: https://ccpn.ac.uk
[github]: https://github.com
[NEF consortium repository]: https://github.com/NMRExchangeFormat/NEF
[annotated NEF example]: https://github.com/NMRExchangeFormat/NEF/blob/master/specification/Commented_Example_v1_1.nef
[dictionary defining the format]: https://github.com/NMRExchangeFormat/NEF/blob/master/specification/mmcif_nef_v1_1.dic
[STAR format]: https://en.wikipedia.org/wiki/Self-defining_Text_Archive_and_Retrieval
[NMRStar]: https://bmrb.io/standards/
[PDBx / mmCIF]: https://pdb101.rcsb.org/learn/guide-to-understanding-pdb-data/beginner’s-guide-to-pdb-structures-and-the-pdbx-mmcif-format
[RCSB / PDB]: https://www.rcsb.org
[BMRB]: https://bmrb.io
[issue tracker]: https://github.com/varioustoxins/NEF-Pipelines/issues
