import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_ai_test_session():
    """One-time AI test session setup: initialise sandbox, NEF app, and audit hook."""
    if sys.version_info >= (3, 10):
        from nef_pipelines.tools.ai.mcp_lib import create_nef_pipelines_app
        from nef_pipelines.tools.ai.sandbox_audit import install_audit_hook
        from nef_pipelines.tools.ai.sandbox_lib import (
            init_sandbox_instance_with_generated_id,
        )

        # Command modules are already imported (at app startup); @setup_sandbox recorded
        # their setups as pending. init_sandbox_instance drains that pending list,
        # creating cache dirs and registering commands against _TMP_BASE.
        init_sandbox_instance_with_generated_id(prefix="TEST-PID")

        create_nef_pipelines_app()
        install_audit_hook()
