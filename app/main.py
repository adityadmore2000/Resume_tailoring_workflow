from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running via `python app/main.py` (when `app/` is sys.path[0]).
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import DEFAULT_CONFIG
from app.latex_rebuilder import rebuild_latex
from app.llm import LLMError, OllamaClient
from app.parser import parse_latex_resume
from app.pipeline import PipelineOptions, run_pipeline
from app.schemas import SuggestionStatus


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Controlled local-LLM resume tailoring (pipeline + review artifacts).")
    p.add_argument("--resume", required=True, help="Path to master resume .tex")
    p.add_argument("--jd", required=True, help="Path to job description .txt")
    p.add_argument("--out", required=True, help="Path to output tailored .tex")
    p.add_argument("--model", default=DEFAULT_CONFIG.ollama_model, help="Ollama model name")
    p.add_argument("--ollama-url", default=DEFAULT_CONFIG.ollama_base_url, help="Ollama base URL")
    p.add_argument("--no-eval", action="store_true", help="Disable evaluator stage")
    p.add_argument(
        "--auto-approve-safe",
        action="store_true",
        help="AUTO-APPROVES suggestions that pass verifier (not recommended). Default is no auto-apply.",
    )
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    resume_path = Path(args.resume)
    jd_path = Path(args.jd)
    out_path = Path(args.out)

    resume_tex = _read_text(resume_path)
    jd_text = _read_text(jd_path)

    llm = OllamaClient(base_url=args.ollama_url, model=args.model)
    options = PipelineOptions(run_evaluator=not args.no_eval)

    try:
        parsed = parse_latex_resume(resume_tex)
        result = run_pipeline(jd_text=jd_text, resume_tex=resume_tex, llm=llm, options=options)
    except LLMError as e:
        raise SystemExit(f"LLM error: {e}")
    except ValueError as e:
        raise SystemExit(f"Input error: {e}")

    # By default, do not apply changes. Output original resume and artifacts for review.
    suggestions = result.change_report.suggestions
    if args.auto_approve_safe:
        for s in suggestions:
            if s.suggested_latex is not None and s.status != SuggestionStatus.rejected:
                s.status = SuggestionStatus.approved

    tailored = rebuild_latex(parsed, suggestions)
    _write_text(out_path, tailored)

    _write_text(out_path.with_suffix(".change_report.json"), json.dumps(result.change_report.model_dump(), indent=2))
    if result.evaluation_report is not None:
        _write_text(out_path.with_suffix(".evaluation.json"), json.dumps(result.evaluation_report.model_dump(), indent=2))
    _write_text(out_path.with_suffix(".artifacts.json"), json.dumps(result.artifacts.model_dump(), indent=2))

    print(f"Wrote: {out_path}")
    print(f"Wrote: {out_path.with_suffix('.change_report.json')}")
    print(f"Wrote: {out_path.with_suffix('.artifacts.json')}")
    if result.evaluation_report is not None:
        print(f"Wrote: {out_path.with_suffix('.evaluation.json')}")
    if not args.auto_approve_safe:
        print("Note: No changes were auto-applied. Use UI to approve changes, or pass --auto-approve-safe (not recommended).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
