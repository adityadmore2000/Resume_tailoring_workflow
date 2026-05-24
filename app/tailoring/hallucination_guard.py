from __future__ import annotations

import re


def contains_new_numbers(original: str, candidate: str) -> bool:
    num_re = re.compile(r"(?<!\\)\b\d+(?:\.\d+)?%?\b")
    return not set(num_re.findall(candidate)).issubset(set(num_re.findall(original)))


def enforce_no_evidence_no_bullet(evidence_ids: list[str]) -> bool:
    return bool(evidence_ids)

