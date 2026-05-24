from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.bank_generator.folder_manager import BankFolderError, get_bank_paths, safe_join
from app.config import DEFAULT_CONFIG
from app.ui.api.bank_preview_api import EXPECTED_DIRS, tree_for_expected_dirs


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
