"""
Stage 1 router.

Endpoints:
  POST /stage1/upload          – upload Data Model Changes Document
  POST /stage1/run             – trigger analysis
  GET  /stage1/report/{sid}    – fetch the completed report
  GET  /stage1/status/{sid}    – lightweight status poll
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse

from models.schemas import (
    AnalysisStatus,
    Stage1Report,
    Stage1RunResponse,
)
from services import analysis_service
from utils.file_utils import save_upload, validate_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stage1", tags=["Stage 1 — Data Model Impact"])


# ─── Upload ───────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload Data Model Changes Document")
async def upload_data_model_doc(
    file: UploadFile = File(..., description="PDF, DOCX, or TXT document"),
    session_id: str | None = Form(None, description="Reuse an existing session"),
):
    """
    Upload the Data Model Changes Document.

    - Creates a new session if `session_id` is not provided.
    - Returns the `session_id` to be used in subsequent calls.
    """
    content = await file.read()

    try:
        validate_upload(file.filename or "upload", len(content))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not session_id:
        session_id = analysis_service.create_session()

    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        # Session ID provided by client doesn't exist — create fresh
        session_id = analysis_service.create_session()
        session = analysis_service.get_session(session_id)

    file_path = save_upload(session_id, "data_model_doc", file.filename or "upload", content)
    session.uploaded_files["data_model_doc"] = file_path
    session.metadata["data_model_doc_name"] = file.filename or "upload"

    return {
        "session_id": session_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "message": "Data model document uploaded successfully. Call /stage1/run to start analysis.",
    }


# ─── Run ──────────────────────────────────────────────────────────────────────

@router.post("/run", response_model=Stage1RunResponse, summary="Run Stage 1 Analysis")
async def run_stage1(
    session_id: str = Form(..., description="session_id from /stage1/upload"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Trigger the Stage 1 analysis pipeline.

    The pipeline runs **synchronously** in this implementation and returns
    the completed report in a single response.  For long-running documents,
    swap to background_tasks + polling via /stage1/status/{session_id}.
    """
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if "data_model_doc" not in session.uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="No data model document in session. Call /stage1/upload first.",
        )

    existing = session.stage1_report
    if existing and existing.status == AnalysisStatus.RUNNING:
        return Stage1RunResponse(
            session_id=session_id,
            status=AnalysisStatus.RUNNING,
            message="Analysis already in progress.",
        )

    try:
        report = await analysis_service.run_stage1(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Stage 1 pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    return Stage1RunResponse(
        session_id=session_id,
        status=report.status,
        message="Stage 1 analysis completed successfully.",
        report=report,
    )


# ─── Status ───────────────────────────────────────────────────────────────────

@router.get("/status/{session_id}", summary="Poll Stage 1 Analysis Status")
async def get_stage1_status(session_id: str):
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    report = session.stage1_report
    if not report:
        return {"session_id": session_id, "status": "not_started"}

    return {
        "session_id": session_id,
        "status": report.status,
        "created_at": report.created_at,
        "error": report.error,
    }


# ─── Report ───────────────────────────────────────────────────────────────────

@router.post("/chat", summary="Stage 1 Chat — skeleton placeholder")
async def stage1_chat(
    session_id: str = Form(...),
    message: str = Form(...),
):
    """Skeleton endpoint. Returns a placeholder string until LLM is wired in."""
    return {
        "session_id": session_id,
        "message": message,
        "response": "Placeholder response — LLM will be connected here in the next iteration.",
    }


@router.get("/report/{session_id}", response_model=Stage1Report, summary="Get Stage 1 Report")
async def get_stage1_report(session_id: str):
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    report = session.stage1_report
    if not report:
        raise HTTPException(
            status_code=404,
            detail="Stage 1 report not found. Run the analysis first.",
        )

    return report
