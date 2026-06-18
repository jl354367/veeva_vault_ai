"""
Chat / Q&A router — placeholder until LLM is wired in.

The active chat endpoint is currently /stage1/chat (skeleton stub in stage1.py).
This router will be expanded when the full Q&A feature is implemented.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/chat", tags=["Q&A — Coming Soon"])

_COMING_SOON = {"detail": "Full Q&A chat is not yet available. Use /stage1/chat for the skeleton stub."}


@router.post("/ask", summary="Q&A Ask — Coming Soon")
async def ask_question():
    return JSONResponse(status_code=501, content=_COMING_SOON)
