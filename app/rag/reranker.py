from __future__ import annotations

from dataclasses import dataclass

from app.rag.retriever import RetrievedChunk


@dataclass(frozen=True)
class RerankConfig:
    rrf_k: int = 60


def rrf_rerank(*runs: list[RetrievedChunk], cfg: RerankConfig = RerankConfig()) -> list[RetrievedChunk]:
    """
    Reciprocal Rank Fusion (RRF) reranker.
    Useful when combining multiple retrieval runs (semantic + lexical + metadata filtered).
    """
    score_by_id: dict[str, float] = {}
    item_by_id: dict[str, RetrievedChunk] = {}
    for run in runs:
        for rank, item in enumerate(run):
            if not item.chunk_id:
                continue
            item_by_id[item.chunk_id] = item
            score_by_id[item.chunk_id] = score_by_id.get(item.chunk_id, 0.0) + 1.0 / (cfg.rrf_k + rank + 1)

    merged = []
    for cid, sc in score_by_id.items():
        it = item_by_id[cid]
        merged.append(RetrievedChunk(chunk_id=it.chunk_id, text=it.text, score=sc, metadata=it.metadata))
    merged.sort(key=lambda x: x.score, reverse=True)
    return merged

