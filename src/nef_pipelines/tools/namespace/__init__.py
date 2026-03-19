from typer import Typer

from nef_pipelines.main import nef_app

namespace_app = Typer()

nef_app.app.add_typer(
    namespace_app,
    name="namespace",
    help="- manipulate namespaces",
    rich_help_panel="Data analysis & manipulation",
)

from nef_pipelines.tools.namespace import list  # noqa: F401, E402
