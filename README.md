<!-- These are examples of badges you might want to add to your README:
     please update the URLs accordingly

[![Built Status](https://api.cirrus-ci.com/github/<USER>/nef_pipelines.svg?branch=main)](https://cirrus-ci.com/github/<USER>/nef_pipelines)
[![ReadTheDocs](https://readthedocs.org/projects/nef_pipelines/badge/?version=latest)](https://nef_pipelines.readthedocs.io/en/stable/)
[![Coveralls](https://img.shields.io/coveralls/github/<USER>/nef_pipelines/main.svg)](https://coveralls.io/r/<USER>/nef_pipelines)
[![Conda-Forge](https://img.shields.io/conda/vn/conda-forge/nef_pipelines.svg)](https://anaconda.org/conda-forge/nef_pipelines)
[![Twitter](https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter)](https://twitter.com/nef_pipelines)
-->

[![PyPI-Server](https://img.shields.io/pypi/v/nef_pipelines.svg)](https://pypi.org/project/nef_pipelines/)
[![Monthly Downloads](https://pepy.tech/badge/nef_pipelines/month)](https://pepy.tech/project/nef_pipelines)
[![Project generated with PyScaffold](https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold)](https://pyscaffold.org/)


# NEF-Pipelines

__*Tools for Manipulating NEF [NMR Exchange Format] Files and Foreign File Access*__

NEF-Pipelines is a set of command line (currently... there maybe a gui later!) tools for maniulating [NEF])(https://github.com/NMRExchangeFormat/NEF) or NMR
Exchange Format files which can be used to move NMR meta data [peaks, shifts, sequences etc] between NMR data processing
programs.The programs provide basic tools for manipulating nef files:

> Please note NEF-Pipelines continues to be developed so if you do find problems put in an issue on the
  [issue tracker]. Even better if you can help improve the software do get in touch, there is much to do!

* __molecular chains__: listing, renaming and cloning molecular chains
* __save-frames [tables]__: deleting, inserting, listing and pretty printing (tabulate)
* __headers__ creation / updating NEF headers with correct UUIDs and history
* __streaming__: NEF files into a pipeline
* __testing__: self testing of NEF pipelines

It also provides tools for importing and exporting non NEF files from the following programs [transcoding / translators]

R = Read / import to NEF, W = write / export from NEF, 🐍=  supported in python code, α =  alpha quality code [few tests]
<table style="width:100%;table-layout=fixed" border="0">
<tbody>
 <tr>
  <td style="width:20.00%">
    <b>xplor</b><br>
    <br>
    dihedrals R<br>
    distances R<br>
    sequence R<br>
    rdcs W<br>
  </td>
  <td style="width:20.00%">
    <b>csv</b><br>
    <br>
    peaks R 🐍<br>
    rdcs R 🐍<br>
    <br>
    <br>
  </td>
  <td style="width:20.00%">
    <b>deep</b><br>
    <br>
    peaks R α 🐍<br>
    <br>
    <br>
    <br>
  </td>
  <td style="width:20.00%">
    <b>nmrpipe</b><br>
    <br>
    peaks R 🐍<br>
    sequence R 🐍<br>
    shifts R 🐍<br>
    <br>
  </td>
  <td style="width:20.00%">
    <b>nmrview</b><br>
    <br>
    peaks RW 🐍<br>
    sequence R<br>
    shifts RW 🐍<br>
    sequences W 🐍<br>
  </td>
 </tr>
 <tr>
  <td>
    <b>fasta</b><br>
    <br>
    sequence RW 🐍<br>
    <br>
    <br>
    <br>
    <br>
    <br>
  </td>
  <td>
    <b>echidna</b><br>
    <br>
    peaks R 🐍<br>
    <br>
    <br>
    <br>
    <br>
    <br>
  </td>
  <td>
    <b>sparky</b><br>
    <br>
    shifts R 🐍<br>
    peaks RW 🐍<br>
    sequence R 🐍<br>
    <br>
    <br>
    <br>
  </td>
  <td>
    <b>mars</b><br>
    <br>
    fixed W 🐍<br>
    fragments W 🐍<br>
    input W 🐍<br>
    sequence RW 🐍<br>
    shifts RW 🐍<br>
    peaks R 🐍<br>
  </td>
  <td>
    <b>modelfree</b><br>
    <br>
    data W α 🐍<br>
    <br>
    <br>
    <br>
    <br>
    <br>
  </td>
 </tr>
 <tr>
  <td>
    <b>pales</b><br>
    <br>
    rdcs RW 🐍<br>
    template W<br>
  </td>
  <td>
    <b>rcsb</b><br>
    <br>
    sequence R<br>
    <br>
  </td>
  <td>
    <b>rpf</b><br>
    <br>
    shifts W α 🐍<br>
    <br>
  </td>
  <td>
    <b>shifty</b><br>
    <br>
    shifts W 🐍<br>
    <br>
  </td>
  <td>
    <b>shiftx2</b><br>
    <br>
    shifts R α 🐍<br>
    <br>
  </td>
 </tr>
 <tr>
  <td>
    <b>nmrstar</b><br>
    <br>
    project R α<br>
    rdcs R α 🐍<br>
    sequence R α 🐍<br>
    shifts R α 🐍<br>
    <br>
  </td>
  <td>
    <b>talos</b><br>
    <br>
    order-parameters R 🐍<br>
    restraints R α 🐍<br>
    secondary-structure R 🐍<br>
    sequence R 🐍<br>
    shifts W α 🐍<br>
  </td>
  <td>
    <b>xcamshift</b><br>
    <br>
    shifts W 🐍<br>
    <br>
    <br>
    <br>
    <br>
  </td>
  <td>
    <b>xeasy</b><br>
    <br>
    peaks R 🐍<br>
    sequence R 🐍<br>
    shifts R 🐍<br>
    <br>
    <br>
  </td>
 </tr>
</tbody>
</table>


## Installation

The easiest way to install NEF-Pipelines is using the tool [uv]( https://docs.astral.sh/uv/) provided by
[astral](astral.sh). You can do this either [using the script installation_scripts/install.sh](https://github.com/varioustoxins/NEF-Pipelines/blob/master/install_scripts/install.sh)
from the NEF-Pipelines distribution [on macos or a linux] as shown below or alternatively using uv manually
[macos, windows and linux] as shown further down

### macOS or Linux Using the Script install.sh

```bash

curl -sL https://raw.githubusercontent.com/varioustoxins/NEF-Pipelines/refs/heads/master/install_scripts/install.sh | sh
```
### Manual installation on macOS or Linux using uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install nef-pipelines --with rich --with streamfitter --python 3.11
```
> note: currently it is recommended to install with a python version <= 3.11 on macOS as there is a bug in installing
> a dependency call pydantic on some version of the OS

### Manual Installation on Windows using uv
```powershell
# note: changing the execution policy is required for  running a script from the internet.
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv tool install nef-pipelines --with rich
```
> note: not all of NEF-Pipelines is working on Windows currently, we are working on it!


after the installation has completed you can type

```bash
nef
```
## Checking NEF-Pipelines is Installed

type
```bash
nef
```
and should see output that starts

```
Usage: nef [OPTIONS] COMMAND [ARGS]...                                                                                                                                                                                        ✔ ╱ took 14s  ╱ nef_pipelines  ╱ at 23:29:36 

Options:
...
```
## Older installations methods
Some [older installation methods](README_other_installation_methods.md) using a script in ccpn assign or pip are
deprocated but still provided for completenes

## Updating NEF-Pipelines
You can use the same tools you used to in stall NEF-Pipelines to upgrade it
### Updating NEF-Pipelines on macOS or Linux Using the Script install.sh

running the following script again
```bash
curl -sL https://raw.githubusercontent.com/varioustoxins/NEF-Pipelines/refs/heads/master/install_scripts/install.sh | sh
```
will update NEF-Pipelines to the latest version

### Updating NEF-Pipelines on macOS, Windows or Linux Manually Using UV
again now you have UV installed upgrading NEF-Piplines manually should be easy
```bash
uv tool upgrade nef-pipelines --python 3.11
```

## Using NEF-Pipelines on the command line

### The Basic `nef` Command

The entry point to NEF-Pipelines is the command `nef` used on its own as seen under installation
it will list a set of top level commands and gives there descriptions.

```bash
nef
Usage: nef [OPTIONS] COMMAND [ARGS]...

 ...

Commands:
  chains     - carry out operations on chains
  csv        - read [rdcs]
  deep       - read deep [peaks]
  echidna    - read echidna data [peaks]
  entry      - carry out operations on the nef file entry
  fasta      - read and write fasta sequences
  fit        - carry out fitting operations [alpha]
  frames     - carry out operations on frames in nef files
  globals    - add global options to the pipeline [use save as your last...
  header     - add a header to the stream
  help       - help on the nef pipelines tools and their usage
  loops      - carry out operations on loops in nef frames
  mars       - read and write mars [shifts and sequences]
  ...
 ```
Some of these commands such as `frames` and `entity` deal with components of a NEF file. Then there are a series of top levels
that deal with common SaveFrames related to NMR data such as `chains` and `shifts` and finally there
are many commands named after file formats and programs such as `talos`, `xplor` `nmrpipe` and `nmrview`
which provide entry points to the import and export of data.

### Invoking and Finding Sub-commands
NEF-Piplines uses hierarchical commands. So foir example the the toip level command `mars` which deals
with the import and export of data from the `mars` auto assignment program has two sub-commands `import` ane `export`
which not suprising deal with the import and export of data for the program to and from NEF. Then below these commands
are further sub commands deaing with `shifts`, `sequences` etc. An easy way to see the sub commands for a format is to
use the `nef help commands` tool which provides a tree display of the available commands. Typing
`nef help commands` on its own produces output for all commands which can be overwhelming so lets
filter it down to just talos commands by adding a filter. To do this we type `nef help commands mars`
which gives the following output

```bash
nef
└── mars
    ├── export
    │   ├── fixed [P]
    │   ├── fragments [P]
    │   ├── input [P]
    │   ├── sequence
    │   └── shifts [P]
    └── import
        ├── peaks [P]
        ├── sequence [P]
        └── shifts [P]

key: [X] has a python function [P]ipe / [C]md
     [α] alpha feature
```
here we can see that we can import peaks, shifts and sequencdes from mars and that we export  fixed assignments,
fragments, inputs [an input file], sequences and shifts to mars. Each individual file sub-command also has help text and
a series of options. So to see the options for exproting shift we can type`nef mars export shifts --help`
which will show

```bash
nef mars export shifts --help
Usage: nef mars export shifts [OPTIONS] [SHIFT_FRAME_SELECTORS]...

  - write a mars chemical shift file

Arguments:
  [SHIFT_FRAME_SELECTORS]...  selector for the shift restraint frames to use,
                              can be called multiple times and include wild
                              cards

Options:
  -i, --input |PIPE|           input to read NEF data from [- is stdin]
                               [default: -]
  -c, --chain <CHAIN-CODE>     chain to export [# and @ and the 1st chain code
                               in the project if the is only one]
  -o, --out <MARS_SHIFT_FILE>  file name to output to [default
                               <entry_id>_shifts.tab] for stdout use -
  -f, --force                  force overwrite of output file if it exists and
                               isn't empty
  --help                       Show this message and exit.
```
However, mostly you don't need to worry about many of the optiosn as the defaults are well chosen.
It should be noted also that many commands also take arguments in the case of `mars export shifts`
the default is the default chemical shift frame (again a well chosen default).


### Common Options of Sub-commands

many commands also have common options, the most well used ones are

| option                    | description                                                                                    |
|---------------------------|------------------------------------------------------------------------------------------------|
| -i / --input  <FILE-PATH> | the path to a file to read NEF data from which becomes the stream running through the pipeline |
| -h / --help               | help for the particular sub command                                                            |                                                           |
| -o / --out   <FILE-PATH>  | a filename or a template file name to write output to [usually native files not NEF] <br/>          |
| -c / --chain <CHAIN>      | a chain or list of chains to output, multiple invocations add more chains and the argument <CHAINS> can also be comma separated list [don't add any spaces!]|
| -f / --force              | force overwriting files if newly generated files would overwite old ones|
| -v / --verbose            | provide verbose information on the STDERR stream, in some cases repeating the option gives more output, e.g -vv gives more output the -v'|

> Note 1. It should be noted that many options that take multiple values can be repeated to add more values or can
> or can take comma separated lists of values [no spaces] so
>
> ```bash
> command --chain A --chain B```
> ```
> selects chains A and B as does
>
> ```bash
> command --chains A,B
> ```
> Note 2. Many arguments take wild cards, so when selecting frames you can use +'s and *
> when choosing the frame name or category to select multiple frames. Furthermore all
> frame names are typically treated as being surrounded by *s when it is reasonable
> to make selecting frames easier
>
> Note 3. When selecting frames there is usually an explicit option to allow differentiation
> between frame names or categories. However, by default it is off and searches for frames are based on
> both names and categories the same time
>

### Using Individual NEF-Pipelines Commands

Individual nef pipeline components can be used standalone with NEF files. To read in a nef fileo or fiel for conversion
into a command when using it standalone you can use the `--in` option
read a foreign file for translators or read a NEF file for commands that manipulate NEF files. So for example to lists
the frames in NEF frame you can type

```bash
nef frames list --in test_data/pales_test_1.nef
```
will list all the Saveframes in the file test_data/pales_test_1.nef and the entry name of the
nef file as follows

```bash
entry pales_test

nef_molecular_system  nef_rdc_restraint_list_test_1
```

as a short cut the following command also work for `nef frames list`

```bash
nef frames list test_data/pales_test_1.nef
```



### Using NEF-Pipelin commands in pipelines
The real power in NEF-Pipelines comes from combining pipeline commands together or with command line tools.
For example the following command

```bash
nef header                                   \
| nef fasta import sequence tailin1.fasta    \
| src/nef nmrview import shifts tailin1.out  \
| src/nef nmrview import peaks tailin1.out   \
> tailin1.nef
```

will create a valid NEF header followed by the tailin1 sequence as a molecular system and then import shifts and peaks
for talin1 from `nmrview` before writing a new NEF file `tailin1.nef`


### Command Line Completion

As discussed above the commands provided by NEF-Pipelines are hierarchical in nature. All commands are accessed from the
root `nef` command but there many are sub commands so for example to import a sequence from a pdb file you would type
`nef rcsb import sequence` followed  by the name of a PDB / MMCIF file and relevant options. This can look long
winded but NEF-Pipelines support command completion. This is is installed for your shell by typing
`nef --install completion <SHELL-NAME>` and the restarting your shell, so fro example for the bash shell

```bash
nef --install-completion bash
```

The after restarting you shell,  typing a double tab will list all available sub commands.

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

> note: currently I find this works better with the bash shell rather than the zsh but your mileage may vary...

### Using NEF-Pipelines as Python Library

NEF-Pipelines maybe used as library of routines that are acessible in python using


### NEF-Piplines workflows

in development...


### More Information on NEF

The origional [NEF paper] is not a good description of the format more an outline of ideals and needs. The [CCPN]
website has a good [guide to nef]and development takes place on [github] via the [NEF consortium repository] which
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
