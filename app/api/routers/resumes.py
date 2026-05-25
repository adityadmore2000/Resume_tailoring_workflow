from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.ui.api.resumes_api import (
    ResumeAPIError,
    compile_latex,
    get_latex,
    get_markdown,
    get_resume_metadata,
    get_text,
    get_traceability,
    put_latex,
    read_pdf_bytes,
)

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


class ResumeLatexResponse(BaseModel):
    resume_id: str
    latex: str
    updated_at: str


class PutLatexRequest(BaseModel):
    latex: str


class CompileRequest(BaseModel):
    latex: str | None = None


@router.get("/{resume_id}")
def api_get_resume_metadata(resume_id: str):
    try:
        return get_resume_metadata(resume_id)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{resume_id}/latex", response_model=ResumeLatexResponse)
def api_get_latex(resume_id: str):
    try:
        r = get_latex(resume_id)
        return r.__dict__
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{resume_id}/latex")
def api_put_latex(resume_id: str, body: PutLatexRequest):
    try:
        return put_latex(resume_id, body.latex)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{resume_id}/compile")
def api_compile(resume_id: str, body: CompileRequest):
    try:
        return compile_latex(resume_id, body.latex)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{resume_id}/pdf")
def api_get_pdf(resume_id: str):
    try:
        b = read_pdf_bytes(resume_id)
        return Response(content=b, media_type="application/pdf")
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{resume_id}/export/pdf")
def api_export_pdf(resume_id: str):
    try:
        b = read_pdf_bytes(resume_id)
        headers = {"Content-Disposition": f'attachment; filename="{resume_id}.pdf"'}
        return Response(content=b, media_type="application/pdf", headers=headers)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{resume_id}/markdown")
def api_get_markdown(resume_id: str):
    try:
        return get_markdown(resume_id)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{resume_id}/text")
def api_get_text(resume_id: str):
    try:
        return get_text(resume_id)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{resume_id}/traceability")
def api_get_traceability(resume_id: str):
    try:
        return get_traceability(resume_id)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))

