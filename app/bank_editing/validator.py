from __future__ import annotations

import re

from app.bank_editing.models import ValidationResult


_BULLETS_H = "## Resume-ready reusable bullets"


def _split_bullets_section(md: str) -> tuple[str, str, str] | None:
    """Split markdown into (pre, bullets_section, post) around the reusable bullets section."""

    idx = md.find(_BULLETS_H)
    if idx < 0:
        return None
    after_h = md.find("\n", idx)
    if after_h < 0:
        after_h = len(md)
    # Find next section header.
    m = re.search(r"^##\s+", md[after_h + 1 :], flags=re.MULTILINE)
    if m:
        next_idx = after_h + 1 + m.start()
    else:
        next_idx = len(md)
    pre = md[: after_h + 1]
    bullets = md[after_h + 1 : next_idx]
    post = md[next_idx:]
    return pre, bullets, post


def extract_evidence_ids(md: str) -> list[str]:
    in_ev = False
    out: list[str] = []
    for line in md.splitlines():
        if line.strip() == "## Evidence (from resume)":
            in_ev = True
            continue
        if in_ev and line.startswith("## "):
            break
        if in_ev:
            m = re.match(r"^\s*-\s*(\S+)\s*$", line)
            if m:
                out.append(m.group(1).strip())
    return out


_RISKY_TERMS = {
    "aws",
    "azure",
    "gcp",
    "google cloud",
    "kubernetes",
    "docker",
    "terraform",
    "helm",
    "spark",
    "databricks",
    "snowflake",
}


def validate_proposed_change(*, old_content: str, new_content: str, evidence_ids: list[str]) -> ValidationResult:
    immutable_field_changes: list[str] = []
    unsupported_claims: list[str] = []
    warnings: list[str] = []

    old_split = _split_bullets_section(old_content)
    new_split = _split_bullets_section(new_content)
    if not old_split or not new_split:
        return ValidationResult(
            status="failed",
            unsupported_claims=[],
            immutable_field_changes=["Missing 'Resume-ready reusable bullets' section"],
            warnings=[],
        )

    old_pre, old_bullets, old_post = old_split
    new_pre, new_bullets, new_post = new_split

    if old_pre != new_pre or old_post != new_post:
        immutable_field_changes.append("Non-bullets sections changed (immutable)")

    if not evidence_ids:
        warnings.append("No evidence_ids supplied for proposed change")

    # Reject new numeric metrics unless already present.
    old_nums = set(re.findall(r"\d+(?:[.,]\d+)?%?", old_content))
    new_nums = set(re.findall(r"\d+(?:[.,]\d+)?%?", new_bullets))
    introduced_nums = sorted([n for n in new_nums if n not in old_nums])
    if introduced_nums:
        unsupported_claims.append(f"Introduced new metrics/numbers: {', '.join(introduced_nums[:8])}")

    allow_text = (old_content + "\n" + old_bullets).casefold()
    for term in sorted(_RISKY_TERMS):
        if term in new_bullets.casefold() and term not in allow_text:
            unsupported_claims.append(f"Unsupported tool/platform claim: {term}")

    status: str
    if immutable_field_changes or unsupported_claims:
        status = "failed"
    elif warnings:
        status = "needs_review"
    else:
        status = "passed"

    return ValidationResult(
        status=status, unsupported_claims=unsupported_claims, immutable_field_changes=immutable_field_changes, warnings=warnings
    )

