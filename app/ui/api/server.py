from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from app.ui.api.experience_banks_api import ExperienceBankAPIError, list_bank_files, read_bank_file


app = FastAPI(title="Resume Tailoring KB API", version="0.1")


class BankFilesResponse(BaseModel):
    files: list[dict]


class BankFileContentResponse(BaseModel):
    path: str
    title: str
    content: str


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

