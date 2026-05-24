from __future__ import annotations

import json
from pathlib import Path

from app.llm import LLMError
from app.rag.retriever import retrieve


class NoEmbedLLM:
    def generate_text(self, *, system: str, user: str) -> str:  # pragma: no cover
        return "{}"

    def generate_json(self, *, system: str, user: str, schema, max_retries: int = 1, allow_fallback: bool = True):  # pragma: no cover
        raise RuntimeError("not used")

    def embed_text(self, text: str) -> list[float]:
        raise LLMError("no embeddings")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise LLMError("no embeddings")


def test_retriever_scopes_to_selected_bank(tmp_path: Path):
    vec_dir = tmp_path / "vector"
    vec_dir.mkdir(parents=True, exist_ok=True)
    idx = vec_dir / "index.jsonl"
    rows = [
        {"chunk_id": "c1", "text": "python validation pipeline", "embedding": None, "metadata": {"bank_folder_name": "bank_a"}},
        {"chunk_id": "c2", "text": "kubernetes deployment", "embedding": None, "metadata": {"bank_folder_name": "bank_b"}},
    ]
    idx.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    llm = NoEmbedLLM()
    out = retrieve(
        query="python validation",
        bank_folder_name="bank_a",
        vector_store_dir=vec_dir,
        llm=llm,
        top_k=5,
    )
    assert out
    assert all(c.metadata.get("bank_folder_name") == "bank_a" for c in out)
