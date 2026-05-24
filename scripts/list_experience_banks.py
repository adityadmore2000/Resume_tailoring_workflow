from __future__ import annotations

import argparse

from app.bank_generator.bank_builder import list_banks


def main() -> int:
    ap = argparse.ArgumentParser(description="List available experience banks.")
    ap.parse_args()
    banks = list_banks()
    if not banks:
        print("No banks found.")
        return 0
    for b in banks:
        print(f"- {b.bank_folder_name} | status={b.status} | updated_at={b.updated_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

