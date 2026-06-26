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
    AnalysisMetadata,
    AnalysisSummary,
    AnalysisStatus,
    ImpactedField,
    ImpactedIntegration,
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
        # Step 1: invoke the Bedrock Agent. Claude handles tool calls and
        # returns the analysis as JSON (when asked) which we extract here.
        logger.info("[%s] Invoking Bedrock Agent", session_id)
        agent_result = await aws_service.invoke_agent(
            session_id=session_id,
            user_message="Analyze the data model changes and return the structured JSON export.",
        )

        structured = aws_service.try_extract_report_json(agent_result.get("response", ""))
        if structured:
            logger.info("[%s] Bedrock Agent returned complete analysis", session_id)
            analysis = structured
            report.config_report_source = "bedrock-agent"

        else:
            # ── Fallback: direct S3 fetch + local LLM ─────────────────────────
            # Used when Bedrock Agent is not configured or returned an error.
            # Parses the locally uploaded file and fetches Config Report from S3,
            # then calls the local LLM (mock or Anthropic Claude).
            logger.info("[%s] Agent fallback — parsing local doc + fetching S3 config report",
                        session_id)
            data_model_text = document_parser.extract_text(doc_path)
            if not data_model_text:
                raise ValueError("Extracted document text is empty.")
            config_report = await aws_service.fetch_config_report_from_s3()
            report.config_report_source = config_report.get("source", "mock")

            # ── LLM INTEGRATION POINT ──────────────────────────────────────────
            # To switch from mock to real Claude (Anthropic API):
            #   1. Set ANTHROPIC_API_KEY in .env
            #   2. Set MOCK_LLM=false in .env
            # ──────────────────────────────────────────────────────────────────
            logger.info("[%s] Running LLM analysis (mock=%s)", session_id, settings.mock_llm)
            analysis = await llm_service.run_stage1_analysis(data_model_text, config_report)

        # Step 5: build typed report
        report.raw_llm_analysis = json.dumps(analysis)
        report.analysis_metadata = _build_metadata(analysis.get("metadata", {}))
        report.summary = _build_summary(analysis.get("summary", {}))
        report.impacted_objects = _build_impacted_objects(analysis.get("impacted_objects", []))
        report.no_impact_confirmed = analysis.get("no_impact_confirmed", [])
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

def _build_metadata(raw: dict[str, Any]) -> AnalysisMetadata:
    return AnalysisMetadata(
        data_model_doc_name=raw.get("data_model_doc_name"),
        config_report_name=raw.get("config_report_name"),
        analyzed_at=raw.get("analyzed_at"),
        vault_name=raw.get("vault_name"),
    )


def _build_summary(raw: dict[str, Any]) -> AnalysisSummary:
    return AnalysisSummary(
        total_impacted_objects=raw.get("total_impacted_objects", 0),
        high_severity_count=raw.get("high_severity_count", 0),
        medium_severity_count=raw.get("medium_severity_count", 0),
        low_severity_count=raw.get("low_severity_count", 0),
        key_findings=raw.get("key_findings", []),
    )


_RISK_ORDER = ["critical", "high", "medium", "low"]
_CHANGE_TYPE_TO_OBJECT_TYPE = {
    "ADD_OBJECT": "standard_object", "DELETE_OBJECT": "standard_object",
    "ADD_FIELD": "standard_object",  "MODIFY_FIELD": "standard_object",
    "DELETE_FIELD": "standard_object", "ADD_RELATIONSHIP": "standard_object",
    "ADD_PICKLIST": "standard_object", "UPDATE_WORKFLOW": "workflow",
    "UPDATE_INTEGRATIONRULE": "integration", "UPDATE_PAGELAYOUT": "pagelayout",
}


def _safe_severity(value: str) -> ImpactSeverity:
    """Map a raw risk/severity string to ImpactSeverity, defaulting to MEDIUM."""
    v = (value or "medium").lower().strip()
    try:
        return ImpactSeverity(v)
    except ValueError:
        return ImpactSeverity.MEDIUM


def _max_severity(risks: list[str]) -> ImpactSeverity:
    """Return the highest severity from a list of risk strings."""
    low = [r.lower() for r in risks]
    for level in _RISK_ORDER:
        if level in low:
            return _safe_severity(level)
    return ImpactSeverity.MEDIUM


def _build_impacted_objects(raw_list: list[dict[str, Any]]) -> list[ImpactedObject]:
    objects = []
    for raw in raw_list:
        areas = raw.get("impacted_areas", [])

        if areas:
            # ── New agent format: impacted_areas[] ────────────────────────────
            sev = _max_severity([a.get("risk", "medium") for a in areas])
            description = (
                raw.get("description")
                or (areas[0].get("description", "") if areas else "")
                or f"{raw.get('change_type', '')} on {raw.get('field_name') or raw.get('object_name', '')}"
            )
            recs = [a["recommendation"] for a in areas if a.get("recommendation")]

            # Derive ImpactedField from the change itself (if it's a field-level change)
            fields: list[ImpactedField] = []
            if raw.get("field_name") and raw.get("change_type", "").upper() in (
                "ADD_FIELD", "MODIFY_FIELD", "DELETE_FIELD"
            ):
                fields = [ImpactedField(
                    field_name=raw.get("field_name", ""),
                    old_definition=raw.get("old_value"),
                    new_definition=raw.get("new_value"),
                    change_type=raw.get("change_type", "MODIFIED"),
                    severity=sev,
                )]

            # Derive ImpactedIntegration from integration/api areas
            integrations: list[ImpactedIntegration] = [
                ImpactedIntegration(
                    integration_name=a.get("area_name", ""),
                    integration_type=a.get("area_type", "Other"),
                    severity=_safe_severity(a.get("risk", "medium")),
                    notes=a.get("description"),
                )
                for a in areas if a.get("area_type") in ("integration", "api")
            ]

            object_type = (
                raw.get("object_type")
                or _CHANGE_TYPE_TO_OBJECT_TYPE.get(raw.get("change_type", ""), "standard_object")
            )

        else:
            # ── Old agent format: impacted_fields[] / impacted_integrations[] ──
            fields = [
                ImpactedField(
                    field_name=f.get("field_name", ""),
                    old_definition=f.get("old_definition"),
                    new_definition=f.get("new_definition"),
                    change_type=f.get("change_type", "MODIFIED"),
                    severity=_safe_severity(f.get("severity", "medium")),
                    notes=f.get("notes"),
                )
                for f in raw.get("impacted_fields", [])
            ]
            integrations = [
                ImpactedIntegration(
                    integration_name=i.get("integration_name", ""),
                    integration_type=i.get("integration_type", "Other"),
                    severity=_safe_severity(i.get("severity", "medium")),
                    notes=i.get("notes"),
                )
                for i in raw.get("impacted_integrations", [])
            ]
            sev = _safe_severity(raw.get("overall_severity", "medium"))
            description = raw.get("description", "")
            recs = raw.get("recommendations", [])
            object_type = raw.get("object_type", "standard_object")

        objects.append(ImpactedObject(
            object_name=raw.get("object_name", ""),
            object_type=object_type,
            overall_severity=sev,
            description=description,
            recommendations=recs,
            impacted_fields=fields,
            impacted_integrations=integrations,
            impacted_areas=areas,
            change_type=raw.get("change_type"),
            field_name=raw.get("field_name"),
            field_label=raw.get("field_label"),
            old_value=raw.get("old_value"),
            new_value=raw.get("new_value"),
        ))
    return objects


