"""Global pytest isolation hooks preventing cross-module dependency_overrides pollution."""

import pytest
from app.main import app


@pytest.fixture(scope="module", autouse=True)
def isolate_app_dependency_overrides():
    """Snapshot and restore FastAPI app.dependency_overrides around every test module."""
    saved = app.dependency_overrides.copy()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
