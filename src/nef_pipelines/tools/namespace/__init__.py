from typer import Typer

from nef_pipelines.main import nef_app

namespace_app = Typer()

nef_app.app.add_typer(
    namespace_app,
    name="namespace",
    help="- display, filter, delete and rename namespaces [only display currently implemented]",
    rich_help_panel="NEF manipulation",
)

from nef_pipelines.tools.namespace import defined  # noqa: F401, E402
from nef_pipelines.tools.namespace import list  # noqa: F401, E402
