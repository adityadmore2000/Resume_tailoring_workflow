from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.tailor_service import TailorError, tailor_resume_from_bank

router = APIRouter(prefix="/api", tags=["tailor"])


class TailorRequest(BaseModel):
    bank_name: str = Field(min_length=1)
    jd_text: str = Field(min_length=1)


class TailorResponse(BaseModel):
    bank_folder_name: str
    resume_id: str
    messages: list[str] = Field(default_factory=list)


@router.post("/tailor", response_model=TailorResponse)
def api_tailor(body: TailorRequest):
    try:
        res = tailor_resume_from_bank(bank_folder_name=body.bank_name, jd_text=body.jd_text)
        return TailorResponse(bank_folder_name=res.bank_folder_name, resume_id=res.resume_id, messages=res.messages)
    except TailorError as e:
        raise HTTPException(status_code=400, detail=str(e))
