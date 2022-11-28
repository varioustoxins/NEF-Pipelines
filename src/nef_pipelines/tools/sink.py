from nef_pipelines import nef_app

if nef_app:
    # noinspection PyUnusedLocal
    @nef_app.app.command()
    def sink():
        """- read the current stream and don't write anything"""
        ...
