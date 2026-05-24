from __future__ import annotations

import json
from pathlib import Path

from app.ui.api.experience_banks_api import list_bank_items


def test_list_bank_items_returns_human_readable_summaries(tmp_path: Path):
    data_root = tmp_path / "data"
    bank = "bank1"
    bank_dir = data_root / "experience_bank" / bank
    (bank_dir / "metadata").mkdir(parents=True, exist_ok=True)

    idx = {
        "bank_folder_name": bank,
        "source_format": "latex",
        "sections": [],
        "evidence_claims": [
            {
                "evidence_id": "ev1",
                "claim_text": "Built a computer vision pipeline.",
                "source_section": "EXPERIENCE",
                "source_text": r"Built a CV pipeline in PyTorch.",
                "tools": ["PyTorch"],
                "metrics": ["2x faster"],
                "notes": "",
            }
        ],
        "work_experience": [
            {
                "entry_id": "work_abc",
                "role_title": "AI/ML Engineer",
                "employment_type_or_label": "",
                "company": "Neilsoft",
                "display_title": "AI/ML Engineer $|$ Neilsoft",
                "subtitle": "Computer Vision Engineering",
                "start_date": "07/2023",
                "end_date": "07/2024",
                "location": "Pune, India",
                "source_text": "",
                "evidence_ids": ["ev1"],
            }
        ],
        "projects": [
            {
                "project_id": "proj_x",
                "name": "Math Mentor AI",
                "description": "A math tutoring assistant.",
                "evidence_ids": ["ev1"],
                "tools": ["FastAPI"],
            }
        ],
        "capabilities": [
            {
                "capability_id": "cap_cv",
                "name": "Computer Vision",
                "evidence_ids": ["ev1"],
                "tools": ["YOLOX"],
                "domains": ["computer_vision"],
            }
        ],
        "deployments": [],
        "metrics": [],
        "reusable_bullets": [],
    }
    (bank_dir / "metadata" / "experience_bank_index.json").write_text(json.dumps(idx), encoding="utf-8")

    items = list_bank_items(bank, data_root=data_root)
    types = {i.type for i in items}
    assert {"work_experience", "project", "capability"} <= types

    w = next(i for i in items if i.type == "work_experience")
    assert w.title == "Neilsoft \u2014 AI/ML Engineer"
    assert w.raw_path == "work_experience/work_abc.md"
    assert "PyTorch" in w.tools
    assert w.date_range == "07/2023 - 07/2024"
    assert w.location == "Pune, India"

    p = next(i for i in items if i.type == "project")
    assert p.title == "Math Mentor AI"
    assert p.raw_path == "projects/proj_x.md"

    c = next(i for i in items if i.type == "capability")
    assert c.title == "Computer Vision"
    assert c.raw_path == "capabilities/cap_cv.md"
    assert "computer_vision" in c.domains

