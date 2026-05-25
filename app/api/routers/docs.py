from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/docs", tags=["docs"])

_DOCS_DIR = (Path(__file__).resolve().parents[3] / "docs").resolve()


def _slug_for_path(p: Path) -> str:
    return p.stem


def _title_for_markdown(text: str, *, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


@router.get("")
def api_list_docs() -> dict:
    if not _DOCS_DIR.exists():
        return {"docs": []}
    docs = []
    for p in sorted(_DOCS_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        docs.append({"slug": _slug_for_path(p), "title": _title_for_markdown(text, fallback=p.stem), "path": str(p.name)})
    return {"docs": docs}


@router.get("/{slug}")
def api_get_doc(slug: str) -> dict:
    if not re.fullmatch(r"[a-z0-9\\-]+", slug):
        raise HTTPException(status_code=400, detail="Invalid slug")
    p = _DOCS_DIR / f"{slug}.md"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Doc not found")
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"slug": slug, "title": _title_for_markdown(text, fallback=slug), "content": text}
