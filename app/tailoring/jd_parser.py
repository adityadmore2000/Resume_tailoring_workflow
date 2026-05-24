from __future__ import annotations

from app.jd_analyzer import analyze_jd
from app.llm import OllamaClient
from app.schemas import JDAnalysis


def parse_jd(jd_text: str, llm: OllamaClient) -> JDAnalysis:
    return analyze_jd(jd_text, llm)

