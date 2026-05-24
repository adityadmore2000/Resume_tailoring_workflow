from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.ui.api.experience_banks_api import ExperienceBankAPIError, list_bank_files, read_bank_file
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


app = FastAPI(title="Resume Tailoring KB API", version="0.1")


class BankFilesResponse(BaseModel):
    files: list[dict]


class BankFileContentResponse(BaseModel):
    path: str
    title: str
    content: str


class ResumeLatexResponse(BaseModel):
    resume_id: str
    latex: str
    updated_at: str


class PutLatexRequest(BaseModel):
    latex: str


class CompileRequest(BaseModel):
    latex: str | None = None


@app.get("/api/experience-banks/{bank_folder_name}/files", response_model=BankFilesResponse)
def api_list_files(bank_folder_name: str):
    try:
        files = list_bank_files(bank_folder_name)
        return {"files": [f.__dict__ for f in files]}
    except ExperienceBankAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/experience-banks/{bank_folder_name}/files/content", response_model=BankFileContentResponse)
def api_read_file(bank_folder_name: str, path: str = Query(..., description="Relative path inside the bank folder")):
    try:
        rel, title, content = read_bank_file(bank_folder_name, path)
        return {"path": rel, "title": title, "content": content}
    except ExperienceBankAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/resumes/{resume_id}/latex", response_model=ResumeLatexResponse)
def api_get_latex(resume_id: str):
    try:
        r = get_latex(resume_id)
        return r.__dict__
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/resumes/{resume_id}")
def api_get_resume_metadata(resume_id: str):
    try:
        return get_resume_metadata(resume_id)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/resumes/{resume_id}/latex")
def api_put_latex(resume_id: str, body: PutLatexRequest):
    try:
        return put_latex(resume_id, body.latex)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/resumes/{resume_id}/compile")
def api_compile(resume_id: str, body: CompileRequest):
    try:
        return compile_latex(resume_id, body.latex)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/resumes/{resume_id}/pdf")
def api_get_pdf(resume_id: str):
    try:
        b = read_pdf_bytes(resume_id)
        return Response(content=b, media_type="application/pdf")
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/resumes/{resume_id}/export/pdf")
def api_export_pdf(resume_id: str):
    try:
        b = read_pdf_bytes(resume_id)
        headers = {"Content-Disposition": f'attachment; filename="{resume_id}.pdf"'}
        return Response(content=b, media_type="application/pdf", headers=headers)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/resumes/{resume_id}/markdown")
def api_get_markdown(resume_id: str):
    try:
        return get_markdown(resume_id)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/resumes/{resume_id}/text")
def api_get_text(resume_id: str):
    try:
        return get_text(resume_id)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/resumes/{resume_id}/traceability")
def api_get_traceability(resume_id: str):
    try:
        return get_traceability(resume_id)
    except ResumeAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))
