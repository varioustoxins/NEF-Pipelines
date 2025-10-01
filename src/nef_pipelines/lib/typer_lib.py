from typer.core import TyperGroup


class FilteredHelpGroup(TyperGroup):
    """
    A filter to handle Rich markdown formatting automatically.

    When rich markup mode is enabled, it escapes dashes in help strings
    that would become bullet points.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-process help strings when commands are added
        self._preprocess_help_strings()

    def _preprocess_help_strings(self):
        """Process existing commands when the group is created"""
        if hasattr(self, "commands") and self._should_escape_help_strings():
            for cmd in self.commands.values():
                if hasattr(cmd, "help") and cmd.help:
                    cmd.help = self._escape_help_string(cmd.help)

    def _should_escape_help_strings(self):
        """Check if we should escape dashes (rich is available)"""

        # note we will import from a partially initialised module unless we
        # hide this in a function
        from nef_pipelines.main import rich_available

        return rich_available

    def _escape_help_string(self, help_str):
        """Escape dashes at the start of help strings that would become bullets"""

        help_str = help_str.lstrip()  # in case we added any spaces by mistake!
        if help_str.startswith("- "):
            help_str = "\\" + help_str

        return help_str
