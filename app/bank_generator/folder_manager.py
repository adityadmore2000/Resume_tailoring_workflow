from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class BankFolderError(ValueError):
    pass


_ALLOWED_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def slugify_bank_folder_name(name: str) -> str:
    if name is None:
        return ""
    s = name.strip().casefold()
    # Replace whitespace with underscores, drop disallowed chars.
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_-]+", "", s)
    s = re.sub(r"_+", "_", s).strip("_-")
    return s


def validate_bank_folder_name(slug: str) -> None:
    if not slug or not slug.strip():
        raise BankFolderError("Bank folder name is empty.")
    if ".." in slug or "/" in slug or "\\" in slug:
        raise BankFolderError("Bank folder name contains invalid path characters.")
    if not _ALLOWED_RE.match(slug):
        raise BankFolderError("Bank folder name must match: lowercase letters, numbers, hyphens, underscores.")


@dataclass(frozen=True)
class BankPaths:
    bank_folder_name: str
    uploads_dir: Path
    experience_bank_dir: Path
    vector_store_dir: Path


def safe_join(root: Path, *parts: str) -> Path:
    candidate = (root / Path(*parts)).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        raise BankFolderError("Path traversal detected.")
    return candidate


def get_bank_paths(data_root: Path, bank_folder_name: str) -> BankPaths:
    slug = slugify_bank_folder_name(bank_folder_name)
    validate_bank_folder_name(slug)
    uploads = safe_join(data_root / "uploads", slug)
    bank = safe_join(data_root / "experience_bank", slug)
    vec = safe_join(data_root / "vector_store", slug)
    return BankPaths(bank_folder_name=slug, uploads_dir=uploads, experience_bank_dir=bank, vector_store_dir=vec)


def check_existing_bank(paths: BankPaths) -> bool:
    return paths.experience_bank_dir.exists() or paths.vector_store_dir.exists()


def create_bank_directories(paths: BankPaths, *, overwrite: bool = False) -> None:
    if check_existing_bank(paths) and not overwrite:
        raise BankFolderError(f"Bank '{paths.bank_folder_name}' already exists. Pass overwrite=True to replace.")
    paths.uploads_dir.mkdir(parents=True, exist_ok=True)
    paths.experience_bank_dir.mkdir(parents=True, exist_ok=True)
    paths.vector_store_dir.mkdir(parents=True, exist_ok=True)

