import typer

from nef_pipelines import nef_app

fit_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        fit_app, name="fit", help="- carry out fitting operations [alpha]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.fit.exponential  # noqa: F401
    import nef_pipelines.tools.fit.ratio  # noqa: F401
