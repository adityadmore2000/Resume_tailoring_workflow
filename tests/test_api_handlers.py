from __future__ import annotations

from fastapi import HTTPException

from app.api.routers import docs as docs_router
from app.api.routers import health as health_router


def test_health_handler_ok_shape():
    data = health_router.health()
    assert data["ok"] is True
    assert "qdrant" in data
    assert "ok" in data["qdrant"]


def test_docs_list_and_get_handlers():
    data = docs_router.api_list_docs()
    assert "docs" in data
    assert isinstance(data["docs"], list)

    slugs = [d["slug"] for d in data["docs"]]
    assert "getting-started" in slugs

    doc = docs_router.api_get_doc("getting-started")
    assert doc["slug"] == "getting-started"
    assert "content" in doc and isinstance(doc["content"], str)


def test_docs_get_rejects_bad_slug():
    try:
        docs_router.api_get_doc("../x")
    except HTTPException as e:
        assert e.status_code == 400
    else:
        raise AssertionError("Expected HTTPException")

