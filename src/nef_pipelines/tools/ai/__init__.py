from typer import Typer

from nef_pipelines import nef_app
from nef_pipelines.lib.util import ToolCategory

ai_app = Typer()

nef_app.app.add_typer(
    ai_app,
    name="ai",
    help="- AI tools for NEF pipelines",
    rich_help_panel=ToolCategory.GENERAL,
)

import nef_pipelines.tools.ai.sandbox  # noqa: F401, E402
import nef_pipelines.tools.ai.server  # noqa: F401, E402
