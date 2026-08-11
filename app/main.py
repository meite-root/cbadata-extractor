from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.pipeline import run_pipeline


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="CBA Data Extractor", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class ProcessRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    step: int = Field(ge=1, le=11)


class ExportRequest(BaseModel):
    result: dict


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/process")
def process_contract(payload: ProcessRequest):
    try:
        return JSONResponse(run_pipeline(payload.text, payload.step))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export/json")
def export_json(payload: ExportRequest):
    content = json.dumps(payload.result, indent=2, ensure_ascii=False)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="cba_extraction.json"'},
    )


@app.post("/api/export/clauses")
def export_clauses(payload: ExportRequest):
    clauses = payload.result.get("clauses", [])
    fields = [
        "sentence_id", "section_id", "section_heading", "text", "subject", "verb", "object",
        "agent", "modal", "modal_type", "negated", "voice", "clause_type",
        "worker_right_topic", "classification_rule", "topic_rule",
    ]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(clauses)
    return StreamingResponse(
        io.BytesIO(stream.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="classified_clauses.csv"'},
    )

