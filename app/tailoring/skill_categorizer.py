from __future__ import annotations

import re
from dataclasses import dataclass

from app.bank_generator.schemas import CapabilityEntry
from app.schemas import JDAnalysis


@dataclass(frozen=True)
class CategorizedSkill:
    name: str
    evidence_ids: list[str]
    jd_relevant: bool


@dataclass(frozen=True)
class SkillCategory:
    name: str
    skills: list[CategorizedSkill]


_BANNED_CATEGORY_NAMES = {"relevant", "other", "misc", "additional", "miscellaneous"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _is_generic_category(name: str) -> bool:
    n = _norm(name).casefold()
    if not n:
        return True
    if n in _BANNED_CATEGORY_NAMES:
        return True
    # Avoid "Relevant Skills", "Other Tools", etc.
    for bad in _BANNED_CATEGORY_NAMES:
        if re.fullmatch(rf"{re.escape(bad)}\s+\w+", n):
            return True
    return False


def _term_match(term: str, text: str) -> bool:
    term = (term or "").strip()
    if not term:
        return False
    return bool(re.search(rf"(?i)\b{re.escape(term)}\b", text))


def _escape_latex_text(s: str) -> str:
    """
    Escape LaTeX-special characters for plain-text fields.
    We keep this conservative: only escape characters that commonly break resumes.
    Avoid double-escaping when the character is already escaped.
    """
    s = s or ""
    # Escape ampersands unless already escaped.
    s = re.sub(r"(?<!\\)&", r"\\&", s)
    # Percent and underscores are also common culprits in resume skills.
    s = re.sub(r"(?<!\\)%", r"\\%", s)
    s = re.sub(r"(?<!\\)_", r"\\_", s)
    return s


def _skill_themes(skill: str) -> list[str]:
    """
    Extract high-level semantic themes from a skill token.
    This is deterministic and evidence-grounded: it only uses the skill string itself.
    """
    s = (skill or "").casefold()
    themes: list[str] = []

    def has(*subs: str) -> bool:
        return any(x in s for x in subs)

    # The following are *theme labels* (not fixed output category names).
    if has("yolo", "opencv", "computer vision", "object detection", "segmentation", "ocr", "tracking", "instance segmentation"):
        themes.append("Computer Vision")
    if has("pytorch", "deep learning", "cuda", "onnx", "torchserve", "model training", "inference"):
        themes.append("Deep Learning")
    if has("llm", "generative", "transformers", "hugging face", "openai", "prompt"):
        themes.append("Generative AI")
    if has("rag", "retrieval", "vector", "embedding", "semantic search", "llamaindex", "bm25"):
        themes.append("Retrieval")
    if has("mlflow", "dvc", "docker", "kubernetes", "deployment", "model serving", "experiment"):
        themes.append("MLOps")
    if has("pandas", "numpy", "data", "dataset", "preprocessing", "analysis"):
        themes.append("Data")
    if has("fastapi", "api", "backend", "rest"):
        themes.append("Backend")
    if has("react native", "react", "frontend", "mobile", "ui"):
        themes.append("Frontend")
    if has("git", "github", "ci/cd", "cicd", "testing", "debug"):
        themes.append("Collaboration")

    return themes


def _category_name_from_themes(themes: list[str]) -> str:
    """
    Build a recruiter-friendly category name from one or more semantic themes.
    This avoids hardcoding a fixed category list while still producing stable names.
    """
    uniq: list[str] = []
    for t in themes:
        if t not in uniq:
            uniq.append(t)

    # Deterministic combine rules.
    if "Computer Vision" in uniq and "Deep Learning" in uniq:
        return "Computer Vision & Deep Learning"
    if "Generative AI" in uniq and "Retrieval" in uniq:
        return "Generative AI & Retrieval Systems"
    if "MLOps" in uniq and ("Backend" in uniq or "Deployment" in uniq):
        return "MLOps & Deployment"

    # Default: join first 2 themes; rename some single themes into recruiter labels.
    if not uniq:
        return "Software Engineering Tools"
    if len(uniq) == 1:
        single = uniq[0]
        rename = {
            "Retrieval": "Retrieval & RAG Systems",
            "Generative AI": "Generative AI & LLM Systems",
            "Data": "Data Processing & Analysis",
            "Collaboration": "Development & Collaboration",
            "Backend": "Backend & APIs",
            "Frontend": "Frontend & Mobile Development",
            "MLOps": "MLOps & Deployment",
        }
        return rename.get(single, single)
    return " & ".join(uniq[:2])


def categorize_skills(
    *,
    capabilities: list[CapabilityEntry],
    used_evidence_ids: list[str],
    jd: JDAnalysis,
    max_skills_per_category: int = 14,
) -> list[SkillCategory]:
    """
    Group skills semantically and generate recruiter-friendly category labels.

    Hard constraints:
    - every skill must be supported by at least one evidence_id in `used_evidence_ids`
    - no duplicates across categories
    - no generic category names ("Relevant", "Other", "Misc", ...)
    """
    used = set([x for x in used_evidence_ids if isinstance(x, str) and x])

    # Build supported skill list (evidence-grounded).
    by_key: dict[str, CategorizedSkill] = {}
    jd_terms = [t for t in (jd.required_skills + jd.important_keywords + jd.preferred_skills) if t and t.strip()]
    for cap in capabilities:
        name = _norm(getattr(cap, "name", ""))
        if not name:
            continue
        ev = [eid for eid in (cap.evidence_ids or []) if eid in used]
        if not ev:
            continue
        key = name.casefold()
        merged = sorted(set(ev + (by_key.get(key).evidence_ids if key in by_key else [])))
        jd_rel = any(_term_match(t, name) for t in jd_terms[:200])
        by_key[key] = CategorizedSkill(name=name, evidence_ids=merged, jd_relevant=jd_rel)

    skills = list(by_key.values())
    if not skills:
        return []

    # Assign to theme-based buckets (skills appear in only one bucket).
    buckets: dict[str, list[CategorizedSkill]] = {}
    for sk in skills:
        themes = _skill_themes(sk.name)
        cat_name = _category_name_from_themes(themes)
        if _is_generic_category(cat_name):
            # Last-resort deterministic non-generic bucket.
            cat_name = "Software Engineering Tools"
        buckets.setdefault(cat_name, []).append(sk)

    categories: list[SkillCategory] = []
    for name, items in buckets.items():
        # Deterministic ordering within categories: JD-relevant first, then alpha.
        items_sorted = sorted(items, key=lambda s: (s.jd_relevant, s.name.casefold()), reverse=True)
        categories.append(SkillCategory(name=name, skills=items_sorted[:max_skills_per_category]))

    # Order categories by JD relevance (how many JD-relevant skills they contain), then stable name.
    def cat_score(c: SkillCategory) -> tuple[int, str]:
        return (sum(1 for s in c.skills if s.jd_relevant), c.name.casefold())

    categories.sort(key=cat_score, reverse=True)

    # Validation: no empty categories, no duplicates.
    seen: set[str] = set()
    out: list[SkillCategory] = []
    for c in categories:
        if not c.skills:
            continue
        if _is_generic_category(c.name):
            raise ValueError(f"Generated a generic skill category name: {c.name}")
        deduped: list[CategorizedSkill] = []
        for s in c.skills:
            k = s.name.casefold()
            if k in seen:
                continue
            if not s.evidence_ids:
                continue
            deduped.append(s)
            seen.add(k)
        if deduped:
            out.append(SkillCategory(name=c.name, skills=deduped))

    return out


def render_skills_latex(categories: list[SkillCategory]) -> str:
    """
    Render a recruiter-friendly SKILLS block using deterministic LaTeX formatting.
    """
    lines: list[str] = []
    lines.append("\\section{SKILLS}")
    lines.append("\\begin{itemize}[leftmargin=0in, label={}]")
    lines.append("\\small{\\item{")
    for c in categories:
        skills = ", ".join([_escape_latex_text(s.name) for s in c.skills])
        if not skills.strip():
            continue
        lines.append(f"\\textbf{{{_escape_latex_text(c.name)}:}} {{{skills}}} \\\\")
    lines.append("}}")
    lines.append("\\end{itemize}")
    return "\n".join(lines).strip() + "\n"
