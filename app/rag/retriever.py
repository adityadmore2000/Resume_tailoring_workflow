from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from app.llm import LLMProvider


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, object]


def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9\+\#-]{2,}", (s or "").casefold()))


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na**0.5) * (nb**0.5))


def retrieve(
    *,
    query: str,
    bank_folder_name: str,
    vector_store_dir: Path,
    llm: LLMProvider,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    """
    Hybrid retrieval (best-effort):
    - semantic cosine similarity if embeddings available
    - keyword overlap score always
    Scoped to a single bank folder by construction (per-bank vector store path).
    """
    idx_path = vector_store_dir / "index.jsonl"
    if not idx_path.exists():
        return []

    q_tokens = _tokenize(query)
    q_emb: list[float] | None = None
    try:
        q_emb = llm.embed_text(query[:4000])
    except Exception:
        q_emb = None

    scored: list[RetrievedChunk] = []
    for line in idx_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        md = row.get("metadata") if isinstance(row, dict) else None
        if not isinstance(md, dict):
            md = {}
        if md.get("bank_folder_name") != bank_folder_name:
            continue
        text = row.get("text", "")
        if not isinstance(text, str):
            continue
        tokens = _tokenize(text)
        overlap = len(tokens & q_tokens) / max(1, len(q_tokens))
        emb_score = 0.0
        emb = row.get("embedding")
        if q_emb is not None and isinstance(emb, list):
            try:
                emb_score = _cosine(q_emb, [float(x) for x in emb])
            except Exception:
                emb_score = 0.0
        score = (0.65 * emb_score) + (0.35 * overlap)
        scored.append(RetrievedChunk(chunk_id=row.get("chunk_id", ""), text=text, score=score, metadata=md))

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]
