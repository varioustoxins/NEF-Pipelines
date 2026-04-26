from strenum import LowercaseStrEnum


class TableOutputFormat(LowercaseStrEnum):
    """Shared output format for tabular data across NEF-Pipelines commands.

    Each member carries both the tabulate format string and a human-readable
    description, used to auto-generate CLI help text.
    """

    def __new__(cls, value: str, tablefmt: str, description: str):
        """Create a new enum member storing the tabulate format and description."""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.tablefmt = tablefmt
        obj.description = description
        return obj

    SIMPLE = ("simple", "simple", "plain text table (default)")
    PRETTY = ("pretty", "pretty", "boxed table")
    MARKDOWN = ("markdown", "pipe", "Markdown pipe table (human-readable)")
    AI = ("ai", "pipe", "optimised for AI / MCP tools (recommended for AI use)")
    HTML = ("html", "html", "HTML table")
