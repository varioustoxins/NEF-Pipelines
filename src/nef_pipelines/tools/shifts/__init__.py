import typer

from nef_pipelines import nef_app

shifts_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        shifts_app, name="shifts", help="- carry out operations on shifts [average]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.shifts.average  # noqa: F401
