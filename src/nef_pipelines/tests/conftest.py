from random import seed

import pytest


@pytest.fixture
def fixed_seed():
    seed(42)


def pytest_configure(config):
    from nef_pipelines.main import create_nef_app

    create_nef_app()
