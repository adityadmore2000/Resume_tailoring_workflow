from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from app.config import AppConfig
from app.schemas import VerificationFlag


_NUM_RE = re.compile(r"(?<!\\)\b\d+(?:\.\d+)?%?\b")


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    flags: list[VerificationFlag]


def _balanced_braces(s: str) -> bool:
    depth = 0
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def latex_safety_check(candidate: str, cfg: AppConfig) -> VerificationFlag:
    if not _balanced_braces(candidate):
        return VerificationFlag(name="latex_balanced_braces", ok=False, detail="Unbalanced { } braces.")
    for cmd in cfg.forbidden_latex_commands:
        if cmd in candidate:
            return VerificationFlag(name="latex_forbidden_command", ok=False, detail=f"Contains forbidden command: {cmd}")
    return VerificationFlag(name="latex_safety", ok=True, detail="")


def section_modification_check(candidate_latex: str) -> VerificationFlag:
    """
    Bullet rewrites must not inject structural LaTeX that could alter the template/sections.
    """
    structural = (r"\section", r"\subsection", r"\begin{", r"\end{", r"\item")
    found = [t for t in structural if t in candidate_latex]
    if found:
        return VerificationFlag(
            name="section_modification",
            ok=False,
            detail=f"Injected structural LaTeX tokens: {found}",
        )
    return VerificationFlag(name="section_modification", ok=True, detail="")


def tool_hallucination_check(candidate_plain: str, allowed: list[str]) -> VerificationFlag:
    allowed_set = {a.casefold() for a in allowed}
    # Heuristic: treat TitleCase / ALLCAPS tokens as tools-ish, plus some common tech tokens.
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9\.\+\#-]{1,30}\b", candidate_plain)
    suspects = []
    for t in tokens:
        t_cf = t.casefold()
        if t_cf in allowed_set:
            continue
        if t_cf in {"a", "an", "and", "or", "the", "to", "of", "for", "with", "in"}:
            continue
        # Don't flag generic verbs/nouns
        if t_cf in {"built", "implemented", "designed", "developed", "shipped", "led", "improved", "reduced", "increased"}:
            continue
        # Flag a small list of common tool-like tokens when not allowed.
        if t_cf in {"kubernetes", "terraform", "airflow", "spark", "aws", "gcp", "azure"}:
            suspects.append(t)
    if suspects:
        return VerificationFlag(name="tool_hallucination", ok=False, detail=f"New tool-like tokens not in resume skills: {sorted(set(suspects))[:6]}")
    return VerificationFlag(name="tool_hallucination", ok=True, detail="")


def fake_metric_check(original_plain: str, candidate_plain: str) -> VerificationFlag:
    orig_nums = set(_NUM_RE.findall(original_plain))
    cand_nums = set(_NUM_RE.findall(candidate_plain))
    new_nums = sorted([n for n in cand_nums if n not in orig_nums])
    if new_nums:
        return VerificationFlag(name="fake_metrics", ok=False, detail=f"Introduced new numeric claims: {new_nums[:6]}")
    return VerificationFlag(name="fake_metrics", ok=True, detail="")


def keyword_stuffing_check(candidate_plain: str, jd_keywords: list[str], cfg: AppConfig) -> VerificationFlag:
    words = re.findall(r"[A-Za-z0-9\+\#-]+", candidate_plain.casefold())
    if not words:
        return VerificationFlag(name="keyword_stuffing", ok=True, detail="")

    kw = [k.casefold() for k in jd_keywords if k.strip()]
    hits = 0
    repeated: list[str] = []
    for k in kw:
        if not k:
            continue
        c = sum(1 for w in words if w == k)
        hits += c
        if c > cfg.max_keyword_repetition:
            repeated.append(f"{k}x{c}")

    density = hits / max(1, len(words))
    if repeated or density > cfg.max_keyword_density:
        return VerificationFlag(
            name="keyword_stuffing",
            ok=False,
            detail=f"Keyword density {density:.2f}; repeated: {repeated[:6]}",
        )
    return VerificationFlag(name="keyword_stuffing", ok=True, detail=f"density={density:.2f}")


def bullet_length_check(candidate_plain: str, cfg: AppConfig) -> VerificationFlag:
    words = re.findall(r"[A-Za-z0-9\+\#-]+", candidate_plain)
    if len(words) > cfg.max_bullet_words:
        return VerificationFlag(name="bullet_length", ok=False, detail=f"{len(words)} words (max {cfg.max_bullet_words}).")
    return VerificationFlag(name="bullet_length", ok=True, detail=f"{len(words)} words")


def semantic_drift_check(original_plain: str, candidate_plain: str, cfg: AppConfig) -> VerificationFlag:
    ratio = difflib.SequenceMatcher(a=original_plain.casefold(), b=candidate_plain.casefold()).ratio()
    ok = ratio >= cfg.semantic_drift_warn_ratio
    return VerificationFlag(name="semantic_drift_ratio", ok=ok, detail=f"ratio={ratio:.2f}")


def verify_bullet_rewrite(
    *,
    original_latex: str,
    original_plain: str,
    candidate_latex: str,
    candidate_plain: str,
    jd_keywords: list[str],
    allowed_tools_and_skills: list[str],
    cfg: AppConfig,
) -> VerificationResult:
    flags: list[VerificationFlag] = []
    flags.append(latex_safety_check(candidate_latex, cfg))
    flags.append(section_modification_check(candidate_latex))
    flags.append(tool_hallucination_check(candidate_plain, allowed_tools_and_skills))
    flags.append(fake_metric_check(original_plain, candidate_plain))
    flags.append(keyword_stuffing_check(candidate_plain, jd_keywords, cfg))
    flags.append(bullet_length_check(candidate_plain, cfg))
    flags.append(semantic_drift_check(original_plain, candidate_plain, cfg))
    ok = all(f.ok for f in flags if f.name not in {"semantic_drift_ratio"})
    # semantic drift is warning-only by default (non-blocking)
    return VerificationResult(ok=ok, flags=flags)


def latex_to_plain_for_checks(text: str) -> str:
    # Minimal converter for verifier.
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
