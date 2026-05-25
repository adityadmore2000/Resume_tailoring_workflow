from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.config import DEFAULT_CONFIG
from app.rag.qdrant_store import QdrantConfig, count_points_for_bank, get_client
from app.tailoring.resume_assembler import load_bank_index


@dataclass(frozen=True)
class BankStats:
    total_files: int
    total_md_files: int
    total_chunks: int
    total_evidence_claims: int
    metrics_available: bool
    tools_found: list[str]
    supported_domains: list[str]


EXPECTED_DIRS: tuple[str, ...] = (
    "work_experience",
    "projects",
    "capabilities",
    "deployment",
    "metrics",
    "reusable_resume_blocks",
    "summaries",
    "metadata",
)


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def tree_for_expected_dirs(bank_dir: Path) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    for d in EXPECTED_DIRS:
        p = bank_dir / d
        if not p.exists():
            out[d] = []
            continue
        out[d] = sorted([x for x in p.rglob("*") if x.is_file()])
    return out


def compute_stats(bank_dir: Path, vector_dir: Path, bank_folder_name: str) -> BankStats:
    files = iter_files(bank_dir)
    md_files = [p for p in files if p.suffix.lower() == ".md"]

    total_chunks = 0
    qdrant_url = (DEFAULT_CONFIG.qdrant_url or "").strip()
    if qdrant_url:
        try:
            qc = QdrantConfig(url=qdrant_url, collection=DEFAULT_CONFIG.qdrant_collection)
            client = get_client(qc)
            total_chunks = count_points_for_bank(client=client, collection=qc.collection, bank_folder_name=bank_folder_name)
        except Exception:
            total_chunks = 0

    try:
        bank_index = load_bank_index(bank_dir)
        evidence_claims = bank_index.evidence_claims
        metrics_available = bool(bank_index.metrics)
        tools = [c.name for c in bank_index.capabilities if c.name]
        domains = []
        for c in bank_index.capabilities:
            domains.extend([d for d in c.domains if d])
    except Exception:
        evidence_claims = []
        metrics_available = False
        tools = []
        domains = []

    tools_top = [t for t, _ in Counter([t.casefold() for t in tools]).most_common(30)]
    domains_top = [d for d, _ in Counter([d.casefold() for d in domains]).most_common(30)]

    return BankStats(
        total_files=len(files),
        total_md_files=len(md_files),
        total_chunks=total_chunks,
        total_evidence_claims=len(evidence_claims),
        metrics_available=metrics_available,
        tools_found=tools_top,
        supported_domains=domains_top,
    )
