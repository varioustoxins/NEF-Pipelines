import typer

import nef
from nef import nef_app

frames_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        frames_app,
        name="frames",
        help="-  carry out operations on frames in nef frames",
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef.tools.frames.delete  # noqa: F401
    import nef.tools.frames.insert  # noqa: F401
    import nef.tools.frames.list  # noqa: F401
    import nef.tools.frames.tabulate  # noqa: F401
