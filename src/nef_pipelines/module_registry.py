"""Module imports for NEF Pipelines.

This file contains the list of all tool and transcoder modules that should be
loaded at startup. Each module self-registers its commands when imported.

To add a new tool or transcoder:
1. Add the module path to the MODULES list below
2. Ensure the module's __init__.py imports all command submodules

Note: The test_command_registration.py test will verify that all modules
with commands are included in this list.
"""

# TODO update so we can just find top level modules


def get_registerd_modules():
    return _MODULES


_MODULES = [
    # Tools
    "nef_pipelines.tools.ai",
    "nef_pipelines.tools.chains",
    "nef_pipelines.tools.entry",
    "nef_pipelines.tools.fit",
    "nef_pipelines.tools.frames",
    "nef_pipelines.tools.globals",
    "nef_pipelines.tools.header",
    "nef_pipelines.tools.help",
    "nef_pipelines.tools.columns",
    "nef_pipelines.tools.loops",
    "nef_pipelines.tools.namespace",
    "nef_pipelines.tools.peaks",
    # "nef_pipelines.tools.plot",
    "nef_pipelines.tools.save",
    "nef_pipelines.tools.series",
    "nef_pipelines.tools.shifts",
    "nef_pipelines.tools.simulate",
    "nef_pipelines.tools.sink",
    "nef_pipelines.tools.stream",
    "nef_pipelines.tools.test",
    "nef_pipelines.tools.version",
    # Transcoders
    "nef_pipelines.transcoders.csv",
    "nef_pipelines.transcoders.deep",
    "nef_pipelines.transcoders.echidna",
    "nef_pipelines.transcoders.fasta",
    "nef_pipelines.transcoders.mars",
    "nef_pipelines.transcoders.modelfree",
    "nef_pipelines.transcoders.nmrpipe",
    "nef_pipelines.transcoders.nmrstar",
    "nef_pipelines.transcoders.nmrview",
    "nef_pipelines.transcoders.pales",
    "nef_pipelines.transcoders.rcsb",
    "nef_pipelines.transcoders.rpf",
    "nef_pipelines.transcoders.shifty",
    "nef_pipelines.transcoders.shiftx2",
    "nef_pipelines.transcoders.sparky",
    "nef_pipelines.transcoders.talos",
    "nef_pipelines.transcoders.ucbshift",
    "nef_pipelines.transcoders.xcamshift",
    "nef_pipelines.transcoders.xeasy",
    "nef_pipelines.transcoders.xplor",
]
