"""Dummy Typer app that fails - for meta-testing run_and_report().

This file is used by test_test.py to test error handling in run_and_report().
It doesn't start with 'test_' so pytest won't collect it.
"""

import sys

import typer

app = typer.Typer()


@app.command()
def main():
    """Command that intentionally fails."""
    print("This is stdout output")
    print("This is stderr output", file=sys.stderr)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
