import typer

from nef_pipelines import nef_app

simulate_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(simulate_app, name="simulate", help="- simulate data")

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.simulate.peaks  # noqa: F401
    import nef_pipelines.tools.simulate.unlabelling  # noqa: F401
