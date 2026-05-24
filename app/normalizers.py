from __future__ import annotations

from typing import Any


def _is_empty_scalar(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip().casefold()
        return s in {"", "none", "null", "n/a", "na", "nil"}
    return False


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def _to_str_list(v: Any) -> list[str]:
    if _is_empty_scalar(v):
        return []
    if isinstance(v, str):
        s = v.strip()
        return [s] if s else []
    if isinstance(v, dict):
        # Preserve info by flattening dict into "k: v" strings.
        out: list[str] = []
        for k, val in v.items():
            line = f"{_to_str(k)}: {_to_str(val)}".strip(": ").strip()
            if line:
                out.append(line)
        return out
    if isinstance(v, (list, tuple, set)):
        out: list[str] = []
        for x in v:
            if _is_empty_scalar(x):
                continue
            s = _to_str(x)
            if s:
                out.append(s)
        return out
    s = _to_str(v)
    return [s] if s else []


def _dict_to_readable_string(v: dict[str, Any]) -> str:
    # Turn a dict into a short, readable summary string.
    parts: list[str] = []
    for k, val in v.items():
        ks = _to_str(k)
        vs = _to_str(val)
        if ks and vs:
            parts.append(f"{ks}: {vs}")
        elif ks:
            parts.append(ks)
    return "; ".join(parts).strip()


def normalize_jd_analysis(raw: Any) -> dict[str, Any]:
    """
    Normalizes LLM output to match JDAnalysis expectations.
    """
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}
    for k in [
        "required_skills",
        "preferred_skills",
        "role_focus",
        "important_keywords",
        "low_priority_keywords",
        "experience_signals",
        "deployment_signals",
        "rejection_risks",
    ]:
        out[k] = _to_str_list(raw.get(k))
    return out


def normalize_rewrite_plan(raw: Any) -> dict[str, Any]:
    """
    Normalizes LLM output to match RewritePlan expectations.
    - Coerces missing/invalid lists to empty lists.
    - Coerces changes entries into dicts with required keys when possible.
    """
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {
        "changes": [],
        "reorder_bullet_ids": _to_str_list(raw.get("reorder_bullet_ids")),
        "notes": _to_str_list(raw.get("notes")),
    }

    changes = raw.get("changes")
    if isinstance(changes, dict):
        changes = [changes]
    if not isinstance(changes, list):
        changes = []

    for item in changes:
        if not isinstance(item, dict):
            continue
        bullet_id = _to_str(item.get("bullet_id"))
        action = _to_str(item.get("action")).lower()
        if action not in {"keep", "rewrite", "remove"}:
            action = "keep"
        reason = _to_str(item.get("reason")) or "No reason provided."
        priority = item.get("priority")
        try:
            priority_i = int(priority)
        except Exception:
            priority_i = 3
        priority_i = min(5, max(1, priority_i))
        if not bullet_id:
            continue
        out["changes"].append(
            {
                "target_type": "bullet",
                "bullet_id": bullet_id,
                "action": action,
                "reason": reason,
                "priority": priority_i,
            }
        )

    return out


def normalize_bullet_rewrite(raw: Any) -> dict[str, Any]:
    """
    Normalizes per-bullet rewrite output.
    Expected: { suggested_latex: str, rationale: str }
    """
    raw = raw if isinstance(raw, dict) else {}
    suggested = raw.get("suggested_latex")
    if isinstance(suggested, dict):
        # Sometimes models nest it.
        suggested = suggested.get("text") or suggested.get("latex") or _dict_to_readable_string(suggested)
    rationale = raw.get("rationale") or raw.get("reason") or raw.get("explanation")
    if isinstance(rationale, dict):
        rationale = _dict_to_readable_string(rationale)
    return {
        "suggested_latex": _to_str(suggested),
        "rationale": (_to_str(rationale) or "Rewrite suggested."),
    }


def normalize_evaluation_report(raw: Any) -> dict[str, Any]:
    """
    Normalizes evaluator output to match EvaluationReport expectations.
    - Coerces keyword_match_reality dict->string summary.
    - Coerces unnecessary_or_weak_content_remaining to list[str].
    - Coerces ats_match_score to int 0..100.
    """
    raw = raw if isinstance(raw, dict) else {}

    score = raw.get("ats_match_score")
    try:
        score_i = int(float(score))  # accept "72" or 72.0
    except Exception:
        score_i = 0
    score_i = min(100, max(0, score_i))

    decision = _to_str(raw.get("decision")).upper()
    if decision not in {"SHORTLISTED", "REJECTED"}:
        decision = "REJECTED"

    kmr = raw.get("keyword_match_reality")
    if isinstance(kmr, dict):
        kmr = _dict_to_readable_string(kmr)
    kmr_s = _to_str(kmr) or "Not provided."

    uweak = raw.get("unnecessary_or_weak_content_remaining")
    uweak_list = _to_str_list(uweak)

    return {
        "ats_match_score": score_i,
        "decision": decision,
        "recruiter_impression": _to_str(raw.get("recruiter_impression")) or "Not provided.",
        "strongest_signals": _to_str_list(raw.get("strongest_signals")),
        "weakest_signals": _to_str_list(raw.get("weakest_signals")),
        "keyword_match_reality": kmr_s,
        "human_readability_verdict": _to_str(raw.get("human_readability_verdict")) or "Not provided.",
        "unnecessary_or_weak_content_remaining": uweak_list,
    }


def normalize_for_schema(schema_name: str, raw: Any) -> dict[str, Any]:
    if schema_name == "JDAnalysis":
        return normalize_jd_analysis(raw)
    if schema_name == "RewritePlan":
        return normalize_rewrite_plan(raw)
    if schema_name == "BulletRewriteOut":
        return normalize_bullet_rewrite(raw)
    if schema_name == "EvaluationReport":
        return normalize_evaluation_report(raw)
    return raw if isinstance(raw, dict) else {}

