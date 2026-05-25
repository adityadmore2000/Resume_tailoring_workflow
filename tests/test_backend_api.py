from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok():
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_docs_list_and_get():
    client = TestClient(create_app())
    r = client.get("/api/docs")
    assert r.status_code == 200
    data = r.json()
    assert "docs" in data
    assert isinstance(data["docs"], list)

    # At least one doc exists in repo.
    slugs = [d["slug"] for d in data["docs"]]
    assert "getting-started" in slugs

    r2 = client.get("/api/docs/getting-started")
    assert r2.status_code == 200
    doc = r2.json()
    assert doc["slug"] == "getting-started"
    assert "content" in doc and isinstance(doc["content"], str)


def test_banks_list_shape():
    client = TestClient(create_app())
    r = client.get("/api/banks")
    assert r.status_code == 200
    data = r.json()
    assert "banks" in data
    assert isinstance(data["banks"], list)
