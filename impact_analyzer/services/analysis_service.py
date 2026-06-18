"""
Analysis orchestration service.

Owns the in-memory session store and coordinates:
  - Document parsing
  - AWS agent triggering (with local LLM fallback)
  - Report building and persistence
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from config import settings
from models.schemas import (
    AnalysisSummary,
    AnalysisStatus,
    ImpactedField,
    ImpactedObject,
    ImpactSeverity,
    SessionState,
    Stage1Report,
)
from services import aws_service, document_parser, llm_service

logger = logging.getLogger(__name__)

# ─── In-memory session store ──────────────────────────────────────────────────
# Replace with Redis or DynamoDB for production.
_sessions: dict[str, SessionState] = {}


def create_session() -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = SessionState(session_id=session_id)
    _purge_expired_sessions()
    return session_id


def get_session(session_id: str) -> SessionState:
    session = _sessions.get(session_id)
    if session is None:
        raise KeyError(f"Session not found: {session_id}")
    return session


def _purge_expired_sessions() -> None:
    cutoff = datetime.utcnow() - timedelta(hours=settings.session_ttl_hours)
    expired = [sid for sid, s in _sessions.items() if s.created_at < cutoff]
    for sid in expired:
        del _sessions[sid]


# ─── Stage 1 ──────────────────────────────────────────────────────────────────

async def run_stage1(session_id: str) -> Stage1Report:
    """
    Full Stage 1 pipeline:
    1. Load uploaded data-model document from session.
    2. Fetch config report from S3 (or mock).
    3. Optionally trigger AWS agent (placeholder).
    4. Run local LLM analysis via Claude.
    5. Parse result → Stage1Report, persist in session.
    """
    session = get_session(session_id)

    doc_path = session.uploaded_files.get("data_model_doc")
    if not doc_path:
        raise ValueError("No data model document found in session. Upload a file first.")

    doc_name = session.metadata.get("data_model_doc_name", "unknown")

    # Mark running
    report = Stage1Report(
        session_id=session_id,
        status=AnalysisStatus.RUNNING,
        data_model_doc_name=doc_name,
        config_report_source="s3" if settings.s3_config_bucket else "mock",
    )
    session.stage1_report = report

    try:
        # Step 1: parse document
        logger.info("[%s] Parsing data model document", session_id)
        data_model_text = document_parser.extract_text(doc_path)
        if not data_model_text:
            raise ValueError("Extracted document text is empty.")

        # Step 2: fetch config report
        logger.info("[%s] Fetching config report", session_id)
        config_report = await aws_service.fetch_config_report_from_s3()
        report.config_report_source = config_report.get("source", "s3")

        # Step 3: trigger AWS agent (placeholder — result used if available)
        logger.info("[%s] Triggering AWS agent (placeholder)", session_id)
        agent_result = await aws_service.trigger_aws_agent(
            payload={
                "session_id": session_id,
                "stage": 1,
                "doc_name": doc_name,
            },
            stage=1,
        )
        logger.info("[%s] AWS agent response: %s", session_id, agent_result.get("status"))

        # Step 4: LLM analysis
        logger.info("[%s] Running LLM analysis", session_id)
        analysis = await llm_service.run_stage1_analysis(data_model_text, config_report)

        # Step 5: build typed report
        report.raw_llm_analysis = json.dumps(analysis)
        report.summary = _build_summary(analysis.get("summary", {}))
        report.impacted_objects = _build_impacted_objects(analysis.get("impacted_objects", []))
        report.status = AnalysisStatus.COMPLETED

        logger.info(
            "[%s] Stage 1 complete — %d objects impacted",
            session_id,
            len(report.impacted_objects),
        )
    except Exception as exc:
        logger.error("[%s] Stage 1 failed: %s", session_id, exc)
        report.status = AnalysisStatus.FAILED
        report.error = str(exc)
        raise

    session.stage1_report = report
    return report


# ─── Data builders ────────────────────────────────────────────────────────────

def _build_summary(raw: dict[str, Any]) -> AnalysisSummary:
    return AnalysisSummary(
        total_impacted_objects=raw.get("total_impacted_objects", 0),
        high_severity_count=raw.get("high_severity_count", 0),
        medium_severity_count=raw.get("medium_severity_count", 0),
        low_severity_count=raw.get("low_severity_count", 0),
        key_findings=raw.get("key_findings", []),
    )


def _build_impacted_objects(raw_list: list[dict[str, Any]]) -> list[ImpactedObject]:
    objects = []
    for raw in raw_list:
        fields = [
            ImpactedField(
                field_name=f.get("field_name", ""),
                old_definition=f.get("old_definition"),
                new_definition=f.get("new_definition"),
                change_type=f.get("change_type", "MODIFIED"),
                severity=ImpactSeverity(f.get("severity", "medium").lower()),
                notes=f.get("notes"),
            )
            for f in raw.get("impacted_fields", [])
        ]
        objects.append(
            ImpactedObject(
                object_name=raw.get("object_name", ""),
                object_type=raw.get("object_type", "Entity"),
                overall_severity=ImpactSeverity(raw.get("overall_severity", "medium").lower()),
                description=raw.get("description", ""),
                recommendations=raw.get("recommendations", []),
                impacted_fields=fields,
            )
        )
    return objects


