import typer

import nef_app

chains_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        chains_app, name="chains", help="-  carry out operations on chains"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import tools.chains.clone  # noqa: F401
    import tools.chains.list  # noqa: F401
    import tools.chains.rename  # noqa: F401
