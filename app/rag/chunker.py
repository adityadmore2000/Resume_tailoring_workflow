from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    metadata: dict[str, object]


def chunk_markdown_file(path: Path, *, base_metadata: dict[str, object]) -> list[Chunk]:
    """
    Simple semantic-ish chunking:
    - Split by top-level headings to keep context coherent.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    chunks: list[Chunk] = []
    buf: list[str] = []
    current_title = "chunk"

    def flush() -> None:
        nonlocal buf, current_title
        t = "\n".join(buf).strip()
        if not t:
            buf = []
            return
        chunk_id = f"{path.name}:{current_title}:{len(chunks)}"
        md = dict(base_metadata)
        md["source_file"] = str(path)
        md["title"] = current_title
        # Extract evidence IDs and basic flags from chunk text itself (metadata is helper only).
        ev_ids = sorted(set(re.findall(r"\bev_[a-f0-9]{12}\b", t)))
        if ev_ids:
            md["evidence_ids"] = ev_ids
        md["metrics_available"] = bool(re.search(r"\bMetrics:\b|\b92\\.7%\\b|\bAP\\b|\bmAP\\b", t))
        chunks.append(Chunk(chunk_id=chunk_id, text=t, metadata=md))
        buf = []

    for line in lines:
        if line.startswith("# "):
            flush()
            current_title = line[2:].strip() or "section"
            buf.append(line)
        else:
            buf.append(line)
    flush()
    return chunks
