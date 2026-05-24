from __future__ import annotations

import json
from pathlib import Path

from app.bank_generator.schemas import ExperienceBankIndex


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bank_markdown(bank_dir: Path, index: ExperienceBankIndex) -> None:
    """
    Writes a modular EXPERIENCE_BANK folder. LLM never writes these directly;
    these are derived from validated JSON structures.
    """
    # Required structure
    subdirs = [
        "work_experience",
        "projects",
        "capabilities",
        "deployment",
        "metrics",
        "reusable_resume_blocks",
        "summaries",
        "metadata",
    ]
    for sd in subdirs:
        (bank_dir / sd).mkdir(parents=True, exist_ok=True)

    # Machine-readable index
    _write(bank_dir / "metadata" / "experience_bank_index.json", json.dumps(index.model_dump(), indent=2))

    # Evidence claims
    ev_md = ["# Evidence Claims", ""]
    for e in index.evidence_claims[:5000]:
        ev_md.append(f"## {e.evidence_id}")
        ev_md.append(f"- Source section: {e.source_section}")
        ev_md.append(f"- Claim: {e.claim_text}")
        ev_md.append(f"- Source text (LaTeX): `{e.source_text}`")
        if e.metrics:
            ev_md.append(f"- Metrics: {', '.join(e.metrics)}")
        ev_md.append("")
    _write(bank_dir / "metadata" / "evidence_claims.md", "\n".join(ev_md))

    # Work experience
    for w in index.work_experience:
        md = [
            f"# {w.title} @ {w.company}",
            "",
            "## Overview",
            f"- Date range: {w.date_range}",
            f"- Location: {w.location}",
            "",
            "## Evidence (from resume)",
        ]
        for eid in w.evidence_ids:
            md.append(f"- {eid}")
        md.append("")
        md.extend(
            [
                "## Resume-ready reusable bullets",
                "- (Generated later; must reference evidence_ids)",
                "",
                "## Limitations / unclear areas",
                "- Unclear from resume (if applicable)",
                "",
            ]
        )
        _write(bank_dir / "work_experience" / f"{w.entry_id}.md", "\n".join(md))

    # Projects
    for p in index.projects:
        md = [
            f"# {p.name}",
            "",
            "## Overview",
            p.description or "",
            "",
            "## Technologies/tools explicitly mentioned",
            "- " + ("\n- ".join(p.tools) if p.tools else "(not extracted)"),
            "",
            "## Evidence (from resume)",
        ]
        for eid in p.evidence_ids:
            md.append(f"- {eid}")
        md.append("")
        md.extend(
            [
                "## Resume-ready reusable bullets",
                "- (Generated later; must reference evidence_ids)",
                "",
                "## Limitations / unclear areas",
                "- Unclear from resume (if applicable)",
                "",
            ]
        )
        _write(bank_dir / "projects" / f"{p.project_id}.md", "\n".join(md))

    # Capabilities
    for c in index.capabilities:
        md = [
            f"# Capability: {c.name}",
            "",
            "## Overview",
            f"- Name: {c.name}",
            "",
            "## Related domains",
            "- " + ("\n- ".join(c.domains) if c.domains else "(not specified)"),
            "",
            "## Technologies/tools explicitly mentioned",
            "- " + ("\n- ".join(c.tools) if c.tools else "(not extracted)"),
            "",
            "## Evidence (from resume)",
        ]
        for eid in c.evidence_ids[:200]:
            md.append(f"- {eid}")
        md.append("")
        _write(bank_dir / "capabilities" / f"{c.capability_id}.md", "\n".join(md))

    # Metrics
    if index.metrics:
        md = ["# Metrics", "", "## Metrics explicitly present in resume", ""]
        for m in index.metrics[:5000]:
            md.append(f"- {m.metric_text} (evidence: {m.evidence_id})")
        _write(bank_dir / "metrics" / "metrics.md", "\n".join(md))
