import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_ai_test_session():
    """One-time AI test session setup: initialise the NEF app and install the audit hook."""
    if sys.version_info >= (3, 10):
        from nef_pipelines.tools.ai.mcp_lib import create_nef_pipelines_app
        from nef_pipelines.tools.ai.sandbox_audit import install_audit_hook

        create_nef_pipelines_app()
        install_audit_hook()
