import typer

from nef_pipelines import nef_app

frames_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        frames_app,
        name="frames",
        help="-  carry out operations on frames in nef frames",
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.frames.delete  # noqa: F401
    import nef_pipelines.tools.frames.filter  # noqa: F401
    import nef_pipelines.tools.frames.insert  # noqa: F401
    import nef_pipelines.tools.frames.list  # noqa: F401
    import nef_pipelines.tools.frames.rename  # noqa: F401
    import nef_pipelines.tools.frames.tabulate  # noqa: F401
    import nef_pipelines.tools.frames.unassign  # noqa: F401
