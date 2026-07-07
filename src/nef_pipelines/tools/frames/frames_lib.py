from nef_pipelines.lib.structures import NEFPipelinesException


class NEFFramesException(NEFPipelinesException):
    """Base exception for frames operations."""

    ...


class NEFFrameAlreadyExistsException(NEFFramesException):
    """Exception raised when attempting to create a frame that already exists."""

    def __init__(self, existing_name: str, entry_id: str, source_name: str):
        self.existing_name = existing_name
        self.entry_id = entry_id
        self.source_name = source_name
        super().__init__(
            f"frame '{existing_name}' already exists in entry '{entry_id}'"
        )
