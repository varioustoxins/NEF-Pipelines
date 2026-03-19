from nef_pipelines import nef_app
from nef_pipelines.lib.util import get_version


@nef_app.app.command(rich_help_panel="Housekeeping")
def version():
    """- display the current version of NEF-Pipelines"""
    print(get_version())
