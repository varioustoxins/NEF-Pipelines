from typer import Typer

from nef_pipelines.lib.util import ToolCategory
from nef_pipelines.main import nef_app

ai_app = Typer()

nef_app.app.add_typer(
    ai_app,
    name="ai",
    help="- AI tools for NEF pipelines",
    rich_help_panel=ToolCategory.GENERAL,
)

from nef_pipelines.tools.ai import server  # noqa: F401, E402
