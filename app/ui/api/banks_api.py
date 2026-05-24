from __future__ import annotations

from app.bank_generator.bank_builder import list_banks


def get_bank_options() -> list[str]:
    return [b.bank_folder_name for b in list_banks()]

