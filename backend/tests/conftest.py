from typing import Generator

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient fixture for FastAPI app."""

    with TestClient(app) as c:
        yield c
