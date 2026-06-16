"""
Stage 2 router.

Endpoints:
  POST /stage2/upload          – upload Integration Specification Document
  POST /stage2/run             – trigger final report generation
  GET  /stage2/report/{sid}    – fetch the completed final report
  GET  /stage2/status/{sid}    – lightweight status poll
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from models.schemas import (
    AnalysisStatus,
    Stage2Report,
    Stage2RunResponse,
)
from services import analysis_service
from utils.file_utils import save_upload, validate_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stage2", tags=["Stage 2 — Integration Impact"])


# ─── Upload ───────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload Integration Specification Document")
async def upload_integration_spec(
    file: UploadFile = File(..., description="PDF, DOCX, or TXT integration specification"),
    session_id: str = Form(..., description="session_id from Stage 1"),
):
    """
    Upload the Integration Specification Document.

    Requires a valid `session_id` from a completed Stage 1 run.
    """
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not session.stage1_report or session.stage1_report.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Stage 1 must be completed before uploading Stage 2 documents.",
        )

    content = await file.read()

    try:
        validate_upload(file.filename or "upload", len(content))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    file_path = save_upload(session_id, "integration_spec_doc", file.filename or "upload", content)
    session.uploaded_files["integration_spec_doc"] = file_path
    session.metadata["integration_spec_doc_name"] = file.filename or "upload"

    return {
        "session_id": session_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "message": "Integration spec uploaded successfully. Call /stage2/run to generate the final report.",
    }


# ─── Run ──────────────────────────────────────────────────────────────────────

@router.post("/run", response_model=Stage2RunResponse, summary="Run Stage 2 Analysis")
async def run_stage2(
    session_id: str = Form(..., description="session_id from Stage 1"),
):
    """
    Trigger Stage 2 analysis.

    Combines the Stage 1 impact report with the uploaded Integration
    Specification to produce the final integration impact report.
    """
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not session.stage1_report or session.stage1_report.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Stage 1 must be completed before running Stage 2.",
        )

    if "integration_spec_doc" not in session.uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="No integration spec document in session. Call /stage2/upload first.",
        )

    existing = session.stage2_report
    if existing and existing.status == AnalysisStatus.RUNNING:
        return Stage2RunResponse(
            session_id=session_id,
            status=AnalysisStatus.RUNNING,
            message="Stage 2 analysis already in progress.",
        )

    try:
        report = await analysis_service.run_stage2(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Stage 2 pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    return Stage2RunResponse(
        session_id=session_id,
        status=report.status,
        message="Stage 2 analysis completed. Final report is ready.",
        report=report,
    )


# ─── Status ───────────────────────────────────────────────────────────────────

@router.get("/status/{session_id}", summary="Poll Stage 2 Analysis Status")
async def get_stage2_status(session_id: str):
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    report = session.stage2_report
    if not report:
        return {"session_id": session_id, "status": "not_started"}

    return {
        "session_id": session_id,
        "status": report.status,
        "created_at": report.created_at,
        "error": report.error,
    }


# ─── Report ───────────────────────────────────────────────────────────────────

@router.get("/report/{session_id}", response_model=Stage2Report, summary="Get Final Report")
async def get_stage2_report(session_id: str):
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    report = session.stage2_report
    if not report:
        raise HTTPException(
            status_code=404,
            detail="Stage 2 report not found. Run the analysis first.",
        )

    return report
