"""測試共用 fixtures。"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """建立 FastAPI TestClient。"""
    from app.main import app

    with TestClient(app) as c:
        yield c
