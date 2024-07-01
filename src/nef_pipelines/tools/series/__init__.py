import typer

from nef_pipelines import nef_app

series_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        series_app, name="series", help="- carry out operations on a data series"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.series.build  # noqa: F401
    import nef_pipelines.tools.series.table  # noqa: F401
