from typer.core import TyperGroup


def patch_rich_code_theme():
    """Patch Rich to use a light-friendly code theme instead of black background.

    This monkey-patches both:
    1. Typer's Markdown rendering to use the 'friendly' Pygments theme
    2. Rich's theme styles to remove black backgrounds from inline code

    Makes code readable on both light and dark terminals.
    """
    try:
        from rich.markdown import Markdown as OriginalMarkdown
        from rich.theme import Theme
        from typer import rich_utils

        # Create a wrapper that forces the friendly theme for both blocks and inline code
        class LightThemedMarkdown(OriginalMarkdown):
            def __init__(
                self, markup, *args, code_theme=None, inline_code_theme=None, **kwargs
            ):
                # Always use 'friendly' theme for both code blocks and inline code
                # This removes black backgrounds from both ```code``` and `inline`
                super().__init__(
                    markup,
                    *args,
                    code_theme="friendly",
                    inline_code_theme="friendly",
                    **kwargs,
                )

        # Replace Markdown in rich_utils with our wrapper
        rich_utils.Markdown = LightThemedMarkdown

        # Also patch the Rich theme to remove black background from markdown.code
        # The default is "bold cyan on black" which gives inline code a black background
        # We need to create a console with a custom theme that overrides this
        original_get_console = rich_utils._get_rich_console

        def patched_get_console():
            console = original_get_console()
            # Create a custom theme that overrides markdown.code to have no background
            # Just specify foreground color (bold cyan) without any background
            custom_theme = Theme(
                {
                    "markdown.code": "bold cyan",
                    "markdown.code_block": "dim cyan",
                }
            )
            console.push_theme(custom_theme)
            return console

        rich_utils._get_rich_console = patched_get_console

    except (ImportError, AttributeError) as e:
        # If Rich/Typer don't have the expected structure warn and skip
        warn(f"failed to patch rich code string formats {e}")


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
