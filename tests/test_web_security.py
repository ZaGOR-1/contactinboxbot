from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("jinja2")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from app.db.database import get_db_session
from app.web.main import create_app
from tests.helpers import TestSettings


async def fake_db_session():
    yield object()


def make_client(settings: TestSettings | None = None) -> TestClient:
    app = create_app(settings or TestSettings())
    app.dependency_overrides[get_db_session] = fake_db_session
    return TestClient(app, follow_redirects=False)


def test_protected_get_routes_require_login() -> None:
    client = make_client()

    for path in ["/", "/messages", "/messages/1", "/users", "/users/1"]:
        response = client.get(path)
        assert response.status_code == 403


def test_post_routes_require_session_and_csrf() -> None:
    client = make_client()

    for path in [
        "/logout",
        "/messages/1/read",
        "/users/1/reply",
        "/users/1/block",
        "/users/1/unblock",
        "/users/1/read",
    ]:
        response = client.post(path, data={})
        assert response.status_code == 403


def test_production_disables_openapi_docs() -> None:
    client = make_client(TestSettings(app_env="production"))

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_service_endpoints_include_security_headers() -> None:
    client = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
