"""
Chat / Q&A router.

Endpoints:
  POST /chat/ask  – ask a question about a Stage 1 or Stage 2 report
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse
from services import analysis_service, llm_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Q&A — Report Assistant"])


@router.post("/ask", response_model=ChatResponse, summary="Ask a question about the report")
async def ask_question(request: ChatRequest):
    """
    Ask any question about the impact analysis report.

    - `stage=1` → grounds the answer in the Stage 1 impact report.
    - `stage=2` → grounds the answer in the Stage 2 final report.
    - `history` → optionally pass prior turns for multi-turn conversation.

    Returns a clear answer plus 2–3 suggested follow-up questions.
    """
    try:
        session = analysis_service.get_session(request.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {request.session_id}")

    if request.stage == 1:
        report = session.stage1_report
        if not report:
            raise HTTPException(
                status_code=404,
                detail="Stage 1 report not found. Run Stage 1 analysis first.",
            )
        context = llm_service.stage1_report_to_context(report)

    elif request.stage == 2:
        report = session.stage2_report
        if not report:
            raise HTTPException(
                status_code=404,
                detail="Stage 2 report not found. Run Stage 2 analysis first.",
            )
        context = llm_service.stage2_report_to_context(report)

    else:
        raise HTTPException(status_code=400, detail="stage must be 1 or 2")

    try:
        answer, follow_ups = await llm_service.answer_question(
            question=request.question,
            report_context=context,
            history=request.history,
        )
    except Exception as exc:
        logger.error("Q&A failed for session %s: %s", request.session_id, exc)
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}")

    return ChatResponse(
        session_id=request.session_id,
        answer=answer,
        suggested_follow_ups=follow_ups,
    )
