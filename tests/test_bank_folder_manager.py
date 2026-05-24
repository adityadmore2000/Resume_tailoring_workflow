from __future__ import annotations

import pytest

from app.bank_generator.folder_manager import (
    BankFolderError,
    get_bank_paths,
    slugify_bank_folder_name,
    validate_bank_folder_name,
)
from app.config import AppConfig


def test_slugify_bank_folder_name_is_lower_and_safe():
    assert slugify_bank_folder_name(" Aditya AI Master Resume ") == "aditya_ai_master_resume"
    assert slugify_bank_folder_name("My/Bad\\Name") == "mybadname"


def test_validate_bank_folder_name_rejects_empty_and_traversal():
    with pytest.raises(BankFolderError):
        validate_bank_folder_name("")
    with pytest.raises(BankFolderError):
        validate_bank_folder_name("../x")
    with pytest.raises(BankFolderError):
        validate_bank_folder_name("a/b")


def test_get_bank_paths_stays_within_data_root(tmp_path):
    cfg = AppConfig(data_root=str(tmp_path / "data"))
    paths = get_bank_paths(tmp_path / "data", "Test Bank")
    assert str(paths.uploads_dir).startswith(str((tmp_path / "data").resolve()))

