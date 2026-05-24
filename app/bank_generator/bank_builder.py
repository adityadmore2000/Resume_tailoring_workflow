from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.bank_generator.bank_registry import BankRegistry, BankRegistryEntry
from app.bank_generator.capability_mapper import map_capabilities_from_resume
from app.bank_generator.evidence_extractor import build_experience_bank_index
from app.bank_generator.folder_manager import BankFolderError, create_bank_directories, get_bank_paths
from app.bank_generator.markdown_writer import write_bank_markdown
from app.bank_generator.schemas import ExperienceBankIndex
from app.bank_generator.validator import BankValidationResult, validate_experience_bank
from app.config import AppConfig, DEFAULT_CONFIG
from app.llm import OllamaClient
from app.rag.ingest import ingest_experience_bank
from app.resume_parser.latex_parser import parse_latex_resume
from app.resume_parser.text_parser import parse_plain_text_resume


@dataclass(frozen=True)
class BankBuildResult:
    bank_folder_name: str
    paths_created: bool
    index: ExperienceBankIndex | None
    validation: BankValidationResult
    vector_records: int = 0
    messages: list[str] = field(default_factory=list)


def generate_experience_bank(
    *,
    resume_tex: str,
    bank_folder_name: str,
    llm: OllamaClient,
    cfg: AppConfig = DEFAULT_CONFIG,
    overwrite: bool = False,
    source_format: str = "latex",
) -> BankBuildResult:
    data_root = Path(cfg.data_root)
    messages: list[str] = []

    paths = get_bank_paths(data_root, bank_folder_name)
    try:
        create_bank_directories(paths, overwrite=overwrite)
    except BankFolderError as e:
        return BankBuildResult(
            bank_folder_name=paths.bank_folder_name,
            paths_created=False,
            index=None,
            validation=BankValidationResult(ok=False, errors=[str(e)], warnings=[]),
            vector_records=0,
            messages=[],
        )

    # Save uploaded resume
    uploads_resume_path = paths.uploads_dir / "resume.tex"
    uploads_resume_path.write_text(resume_tex, encoding="utf-8")

    # Store a template snapshot inside the EXPERIENCE_BANK so tailoring does not need the uploaded resume.
    # This is still "source of truth" because it's derived from the uploaded master resume.
    (paths.experience_bank_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (paths.experience_bank_dir / "metadata" / ("master_resume.tex" if source_format != "text" else "master_resume.txt")).write_text(
        resume_tex, encoding="utf-8"
    )
    if source_format != "text":
        # Best-effort split into preamble/body header so we can reassemble with familiar styling.
        begin_tok = "\\begin{document}"
        end_tok = "\\end{document}"
        bi = resume_tex.find(begin_tok)
        ei = resume_tex.rfind(end_tok)
        if bi != -1 and ei != -1 and ei > bi:
            preamble = resume_tex[:bi]
            body = resume_tex[bi + len(begin_tok) : ei]
            # Keep anything before the first section as "body_header" (often contains name/contact).
            first_sec = body.find("\\section")
            body_header = body[:first_sec] if first_sec != -1 else body
            (paths.experience_bank_dir / "metadata" / "template_preamble.tex").write_text(preamble, encoding="utf-8")
            (paths.experience_bank_dir / "metadata" / "template_body_header.tex").write_text(body_header, encoding="utf-8")
        else:
            messages.append("Could not confidently split LaTeX into preamble/body; stored full master_resume.tex only.")

    # Parse resume (latex or plain text). Tailoring later does not require re-upload.
    if source_format == "text":
        parsed_text = parse_plain_text_resume(resume_tex)
        messages.extend(parsed_text.warnings)
        # Build a minimal ParsedResume-like index from text: one evidence claim per non-empty line.
        from app.schemas import ParsedResume, ResumeSection, SectionName, Bullet
        bullets = []
        idx = 0
        for line in parsed_text.raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            bid = f"b_text_{idx}"
            bullets.append(
                Bullet(
                    id=bid,
                    section=SectionName.other,
                    index=idx,
                    latex=line,
                    plain=line,
                    span_start=0,
                    span_end=0,
                )
            )
            idx += 1
        parsed = ParsedResume(
            source_tex=resume_tex,
            sections=[ResumeSection(name=SectionName.other, title_raw="Other", span_start=0, span_end=len(resume_tex), bullets=bullets, raw_text=resume_tex)],
            bullets=bullets,
            extracted_tools=[],
            extracted_skills=[],
            warnings=messages,
        )
    else:
        parsed = parse_latex_resume(resume_tex).parsed_resume
        messages.extend(parsed.warnings)

    # Persist unchanged EDUCATION block for deterministic final layout.
    if source_format != "text":
        # Persist unchanged SUMMARY block for deterministic final layout.
        summary_sections = [s for s in parsed.sections if s.name.value.casefold() == "summary"]
        if summary_sections:
            summary_raw = summary_sections[0].raw_text
            (paths.experience_bank_dir / "metadata" / "summary_section.tex").write_text(summary_raw, encoding="utf-8")
        else:
            messages.append("SUMMARY section not found; a placeholder SUMMARY will be used during tailoring.")
            (paths.experience_bank_dir / "metadata" / "summary_section.tex").write_text(
                "\\section{SUMMARY}\n\\small{Unclear from resume.}\n", encoding="utf-8"
            )

        edu_sections = [s for s in parsed.sections if s.name.value.casefold() == "education"]
        if edu_sections:
            edu_raw = edu_sections[0].raw_text
            if "\\end{document}" in edu_raw:
                edu_raw = edu_raw.split("\\end{document}", 1)[0].rstrip() + "\n"
            (paths.experience_bank_dir / "metadata" / "education_section.tex").write_text(edu_raw, encoding="utf-8")
        else:
            messages.append("EDUCATION section not found; final resume will omit education unless added later.")

    # Build structured bank index (schema-driven, evidence-grounded)
    index = build_experience_bank_index(parsed, bank_folder_name=paths.bank_folder_name, source_format=source_format)
    index = map_capabilities_from_resume(index, extracted_skills=parsed.extracted_skills)

    validation = validate_experience_bank(index)
    if validation.warnings:
        messages.extend(validation.warnings)
    if not validation.ok:
        messages.extend(validation.errors)
        return BankBuildResult(
            bank_folder_name=paths.bank_folder_name,
            paths_created=True,
            index=index,
            validation=validation,
            vector_records=0,
            messages=messages,
        )

    # Write markdown bank
    write_bank_markdown(paths.experience_bank_dir, index)

    # Ingest into vector store (best-effort embeddings)
    recs, ingest_warnings = ingest_experience_bank(
        bank_folder_name=paths.bank_folder_name,
        experience_bank_dir=paths.experience_bank_dir,
        vector_store_dir=paths.vector_store_dir,
        llm=llm,
        embedding_model=cfg.ollama_embedding_model,
    )
    messages.extend(ingest_warnings)

    # Update registry
    registry = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
    entry = BankRegistryEntry(
        bank_folder_name=paths.bank_folder_name,
        original_resume_path=str(uploads_resume_path),
        experience_bank_path=str(paths.experience_bank_dir),
        vector_store_path=str(paths.vector_store_dir),
        source_format="latex",
        status="generated",
        notes="",
    )
    registry.upsert(entry)

    return BankBuildResult(
        bank_folder_name=paths.bank_folder_name,
        paths_created=True,
        index=index,
        validation=validation,
        vector_records=recs,
        messages=messages,
    )


def list_banks(cfg: AppConfig = DEFAULT_CONFIG) -> list[BankRegistryEntry]:
    data_root = Path(cfg.data_root)
    registry = BankRegistry(data_root / "experience_bank" / "banks_registry.json")
    return sorted(registry.load(), key=lambda e: e.updated_at, reverse=True)
