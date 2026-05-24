from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    ollama_base_url: str = "http://localhost:11434"
    # Default to a small model that can run on modest hardware (e.g., ~4GB VRAM).
    # You can override via:
    # - CLI: `python -m app.main ... --model <model>`
    # - UI: sidebar "Ollama model"
    ollama_model: str = "llama3.2:3b"

    # Rewrite / safety defaults
    max_bullet_words: int = 28
    max_keyword_repetition: int = 3
    max_keyword_density: float = 0.25  # fraction of words that are JD keywords
    semantic_drift_warn_ratio: float = 0.45  # difflib ratio; warn if below

    # LaTeX safety
    forbidden_latex_commands: tuple[str, ...] = (
        r"\input",
        r"\include",
        r"\write18",
        r"\openout",
        r"\read",
        r"\catcode",
        r"\usepackage",
        r"\newcommand",
        r"\renewcommand",
    )

    # Experience bank + RAG
    data_root: str = "data"
    # Prefer a dedicated embedding model. If unavailable, the system falls back to keyword-only retrieval.
    ollama_embedding_model: str = "nomic-embed-text"


DEFAULT_CONFIG = AppConfig()
