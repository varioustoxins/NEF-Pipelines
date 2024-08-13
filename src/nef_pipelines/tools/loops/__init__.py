import typer

from nef_pipelines import nef_app

loops_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        loops_app,
        name="loops",
        help="- carry out operations on loops in nef frames",
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.loops.trim  # noqa: F401
