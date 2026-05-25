from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from app.bank_generator.folder_manager import BankFolderError, get_bank_paths, safe_join
from app.config import DEFAULT_CONFIG
from app.ui.api.bank_preview_api import EXPECTED_DIRS, tree_for_expected_dirs
from app.tailoring.resume_assembler import load_bank_index


class ExperienceBankAPIError(ValueError):
    pass


_ALLOWED_PREVIEW_EXTS = {".md", ".json"}


@dataclass(frozen=True)
class BankFile:
    path: str
    folder: str
    filename: str
    title: str
    type: str  # markdown|json


@dataclass(frozen=True)
class BankItemSummary:
    id: str
    type: str  # work_experience|project|capability|deployment|metric|summary
    title: str
    raw_path: str
    domains: list[str]
    tools: list[str]
    date_range: str = ""
    location: str = ""


def _extract_title_from_markdown(text: str) -> str:
    # First H1 heading
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _display_title(path: Path) -> str:
    name = path.name
    # If filename looks hash-like (e.g., proj_deadbeef1234.md), try reading H1.
    if re.search(r"_[a-f0-9]{8,}\.md$", name):
        try:
            t = path.read_text(encoding="utf-8", errors="replace")
            h1 = _extract_title_from_markdown(t)
            if h1:
                return h1
        except Exception:
            return ""
    return ""


def list_bank_files(bank_folder_name: str, *, data_root: Path | None = None) -> list[BankFile]:
    """
    Returns files available for preview inside `data/experience_bank/<bank>/`.
    Security:
    - Only reads under experience_bank directory for that bank
    - Only returns .md/.json
    - Never touches data/uploads
    """
    data_root = data_root or Path(DEFAULT_CONFIG.data_root)
    paths = get_bank_paths(data_root, bank_folder_name)
    bank_dir = paths.experience_bank_dir
    if not bank_dir.exists():
        raise ExperienceBankAPIError(f"Bank not found: {paths.bank_folder_name}")

    tree = tree_for_expected_dirs(bank_dir)
    files: list[BankFile] = []
    for folder in EXPECTED_DIRS:
        for p in tree.get(folder, []):
            if p.suffix.lower() not in _ALLOWED_PREVIEW_EXTS:
                continue
            rel = str(p.relative_to(bank_dir))
            title = _display_title(p)
            typ = "markdown" if p.suffix.lower() == ".md" else "json"
            files.append(BankFile(path=rel, folder=folder, filename=p.name, title=title, type=typ))
    return files


def _work_title(w) -> str:
    """
    Prefer a recruiter-friendly label: `Company — Role`.
    Falls back to a reasonable parse of `display_title` when needed.
    """
    company = (getattr(w, "company", "") or "").strip()
    role = (getattr(w, "role_title", "") or "").strip()
    subtitle = (getattr(w, "subtitle", "") or "").strip()
    display = (getattr(w, "display_title", "") or "").strip()

    if not company and "$|$" in display:
        left, right = [x.strip() for x in display.split("$|$", 1)]
        # Common format: "Role $|$ Company"
        if right:
            company = right
        if left and (not role or role.casefold().startswith("unclear")):
            role = left

    primary = company or (display.split("$|$", 1)[-1].strip() if "$|$" in display else display) or "Unclear from resume"
    secondary = role if role and not role.casefold().startswith("unclear") else subtitle
    secondary = secondary or "Unclear from resume"
    return f"{primary} \u2014 {secondary}"


def list_bank_items(bank_folder_name: str, *, data_root: Path | None = None) -> list[BankItemSummary]:
    """
    Human-readable item index for a bank (used by the Preview UI).
    Default audience: recruiter/human reader.
    """
    data_root = data_root or Path(DEFAULT_CONFIG.data_root)
    paths = get_bank_paths(data_root, bank_folder_name)
    bank_dir = paths.experience_bank_dir
    if not bank_dir.exists():
        raise ExperienceBankAPIError(f"Bank not found: {paths.bank_folder_name}")

    idx = load_bank_index(bank_dir)
    claims_by_id = {c.evidence_id: c for c in idx.evidence_claims}

    def _tools_for_eids(eids: list[str]) -> list[str]:
        tools: list[str] = []
        for eid in eids:
            c = claims_by_id.get(eid)
            if not c:
                continue
            tools.extend([t for t in (c.tools or []) if isinstance(t, str)])
        # stable de-dupe
        return list(dict.fromkeys([t.strip() for t in tools if t and t.strip()]))

    def _domains_for_eids(eids: list[str]) -> list[str]:
        domains: list[str] = []
        for cap in idx.capabilities:
            if not cap.evidence_ids:
                continue
            if set(cap.evidence_ids) & set(eids):
                domains.extend([d for d in (cap.domains or []) if isinstance(d, str)])
        return list(dict.fromkeys([d.strip() for d in domains if d and d.strip()]))

    items: list[BankItemSummary] = []

    for w in idx.work_experience:
        eids = list(w.evidence_ids or [])
        date_range = f"{w.start_date} - {w.end_date}".strip()
        if date_range == "-":
            date_range = ""
        items.append(
            BankItemSummary(
                id=w.entry_id,
                type="work_experience",
                title=_work_title(w),
                raw_path=f"work_experience/{w.entry_id}.md",
                domains=_domains_for_eids(eids),
                tools=_tools_for_eids(eids),
                date_range=date_range,
                location=(w.location or "").strip(),
            )
        )

    for p in idx.projects:
        eids = list(p.evidence_ids or [])
        tools = list(dict.fromkeys([t.strip() for t in (p.tools or []) if isinstance(t, str) and t.strip()]))
        items.append(
            BankItemSummary(
                id=p.project_id,
                type="project",
                title=(p.name or "Unclear from resume").strip(),
                raw_path=f"projects/{p.project_id}.md",
                domains=_domains_for_eids(eids),
                tools=tools or _tools_for_eids(eids),
            )
        )

    for c in idx.capabilities:
        eids = list(c.evidence_ids or [])
        tools = list(dict.fromkeys([t.strip() for t in (c.tools or []) if isinstance(t, str) and t.strip()]))
        domains = list(dict.fromkeys([d.strip() for d in (c.domains or []) if isinstance(d, str) and d.strip()]))
        items.append(
            BankItemSummary(
                id=c.capability_id,
                type="capability",
                title=(c.name or "Unclear from resume").strip(),
                raw_path=f"capabilities/{c.capability_id}.md",
                domains=domains or _domains_for_eids(eids),
                tools=tools or _tools_for_eids(eids),
            )
        )

    return items


def read_bank_file(bank_folder_name: str, rel_path: str, *, data_root: Path | None = None) -> tuple[str, str, str]:
    """
    Read a markdown/json file in the bank safely.
    Returns: (path, title, content)
    """
    data_root = data_root or Path(DEFAULT_CONFIG.data_root)
    paths = get_bank_paths(data_root, bank_folder_name)
    bank_dir = paths.experience_bank_dir
    if not bank_dir.exists():
        raise ExperienceBankAPIError(f"Bank not found: {paths.bank_folder_name}")

    # Safe join ensures traversal is rejected.
    try:
        abs_path = safe_join(bank_dir, rel_path)
    except BankFolderError as e:
        raise ExperienceBankAPIError(str(e)) from e

    if abs_path.suffix.lower() not in _ALLOWED_PREVIEW_EXTS:
        raise ExperienceBankAPIError("Only markdown/json files can be previewed.")
    if not abs_path.exists() or not abs_path.is_file():
        raise ExperienceBankAPIError("File not found.")

    content = abs_path.read_text(encoding="utf-8", errors="replace")
    title = _extract_title_from_markdown(content) if abs_path.suffix.lower() == ".md" else abs_path.name
    return (str(Path(rel_path)), title, content)


def write_bank_file(
    bank_folder_name: str,
    rel_path: str,
    *,
    content: str,
    data_root: Path | None = None,
) -> str:
    """
    Write a markdown/json file in the bank safely.
    - Prevents traversal (safe_join)
    - Only allows .md/.json
    - Validates JSON if writing .json
    - Creates a timestamped backup next to the original before overwrite
    Returns: normalized relative path
    """
    data_root = data_root or Path(DEFAULT_CONFIG.data_root)
    paths = get_bank_paths(data_root, bank_folder_name)
    bank_dir = paths.experience_bank_dir
    if not bank_dir.exists():
        raise ExperienceBankAPIError(f"Bank not found: {paths.bank_folder_name}")

    try:
        abs_path = safe_join(bank_dir, rel_path)
    except BankFolderError as e:
        raise ExperienceBankAPIError(str(e)) from e

    if abs_path.suffix.lower() not in _ALLOWED_PREVIEW_EXTS:
        raise ExperienceBankAPIError("Only markdown/json files can be edited.")
    if not abs_path.exists() or not abs_path.is_file():
        raise ExperienceBankAPIError("File not found.")

    if abs_path.suffix.lower() == ".json":
        try:
            json.loads(content or "")
        except Exception as e:
            raise ExperienceBankAPIError(f"Invalid JSON: {e}") from e

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = abs_path.with_name(abs_path.name + f".bak.{ts}")
    try:
        backup_path.write_text(abs_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    except Exception:
        # Backup is best-effort; don't block writes if it fails.
        pass

    abs_path.write_text(content, encoding="utf-8")
    return str(Path(rel_path))
