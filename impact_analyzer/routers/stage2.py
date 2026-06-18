"""
Stage 2 router — placeholder until Stage 2 is implemented.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/stage2", tags=["Stage 2 — Coming Soon"])

_COMING_SOON = {"detail": "Stage 2 — Integration Impact is not yet available. Coming in a future release."}


@router.post("/upload", summary="Stage 2 Upload — Coming Soon")
async def stage2_upload():
    return JSONResponse(status_code=501, content=_COMING_SOON)


@router.post("/run", summary="Stage 2 Run — Coming Soon")
async def stage2_run():
    return JSONResponse(status_code=501, content=_COMING_SOON)


@router.get("/status/{session_id}", summary="Stage 2 Status — Coming Soon")
async def stage2_status(session_id: str):
    return JSONResponse(status_code=501, content=_COMING_SOON)


@router.get("/report/{session_id}", summary="Stage 2 Report — Coming Soon")
async def stage2_report(session_id: str):
    return JSONResponse(status_code=501, content=_COMING_SOON)
