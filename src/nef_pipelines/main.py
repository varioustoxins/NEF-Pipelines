#!/usr/bin/env python3

# Note: there are lazy imports lower down in this file in function calls

import sys

MINIMUM_VERSION = (3, 9)
if sys.version_info < MINIMUM_VERSION:
    print(
        f"Error: minimum Python version required is "
        f"{MINIMUM_VERSION[0]}.{MINIMUM_VERSION[1]} [python 2 is not supported]",
        file=sys.stderr,
    )
    print("exiting...", file=sys.stderr)
    sys.exit(2)


def main():
    try:
        import click  # noqa: F401  # lazy
        import typer  # noqa: F401  # lazy
    except ImportError as e:
        print(
            "Initialisation error: one of the core libraries [click/typer] is missing "
            f"from your environment ({e}).\n"
            "Install with: pip install typer click\n"
            "exiting...",
            file=sys.stderr,
        )
        sys.exit(2)

    # Safe to import the runner only after core dependencies are confirmed available
    from nef_pipelines.nef_app_runner import run  # lazy

    run()


if __name__ == "__main__":
    main()
