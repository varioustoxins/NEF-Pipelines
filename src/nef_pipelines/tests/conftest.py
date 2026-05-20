import os
from random import seed

import pytest


@pytest.fixture
def fixed_seed():
    seed(42)


@pytest.fixture(autouse=True)
def _fixed_terminal_size(monkeypatch):
    # os.get_terminal_size() calls ioctl(FD1, TIOCGWINSZ) at the OS level, bypassing COLUMNS env var.
    # Under pytest -s, FD 1 is the real terminal so ioctl succeeds and returns the actual wide width,
    # causing column-layout tests to produce more columns than expected. Patching the Python function
    # is the only reliable fix — env vars and CliRunner(env=...) cannot override the kernel ioctl.
    monkeypatch.setattr(
        os, "get_terminal_size", lambda *a, **k: os.terminal_size((80, 24))
    )


def pytest_configure(config):
    from nef_pipelines.nef_app_runner import create_nef_app

    create_nef_app()
