import typer
import nef_app
frames_app = typer.Typer()



if nef_app.app:
    nef_app.app.add_typer(frames_app, name='frames', help='-  carry out operations on frames in nef frames')

    # import of specific importers must be after app creation to avoid circular imports
    import tools.frames.list
    import tools.frames.tabulate