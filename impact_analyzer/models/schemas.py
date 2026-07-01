"""
Data shapes (schemas) used across the app.

These Pydantic models are pure contracts — they say what a piece of data
must look like. No logic lives here. The rest of the code imports these
to validate inputs, structure responses, and shape the in-memory session
store.

Two important shapes:
  • Stage1Report      — a full impact analysis result (goes to the UI)
  • SessionState      — one entry in the in-memory session dictionary
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Enumerations ─────────────────────────────────────────────────────────────
# Fixed sets of allowed string values — used so we don't accept typos or
# unexpected values from the agent's JSON response.

class AnalysisStatus(str, Enum):
    """Where a Stage 1 analysis stands right now."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ImpactSeverity(str, Enum):
    """Risk levels attached to each impacted item."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ─── Shared building blocks ────────────────────────────────────────────────────
# Small pieces used inside ImpactedObject. Kept simple on purpose so both
# the old and new agent-response shapes can be handled without breaking.

class ImpactedField(BaseModel):
    """One field-level impact (legacy agent shape). Rarely used today —
    the new agent format stores per-area impacts inside `impacted_areas`."""
    field_name: str
    old_definition: Optional[str] = None
    new_definition: Optional[str] = None
    change_type: str = Field(..., description="ADDED | MODIFIED | REMOVED")
    severity: ImpactSeverity
    notes: Optional[str] = None


class ImpactedIntegration(BaseModel):
    """One integration-level impact (legacy agent shape). Same story as
    ImpactedField — the new format uses `impacted_areas` instead."""
    integration_name: str
    integration_type: str = Field(..., description="API|Spark|VaultToVault|FTP|Other")
    severity: ImpactSeverity
    notes: Optional[str] = None


class ImpactedObject(BaseModel):
    """
    One row in the impact report. Holds BOTH shapes:
      • Legacy fields (impacted_fields, impacted_integrations, overall_severity,
        description, recommendations) — used when the agent returns the
        older schema.
      • New fields (impacted_areas, change_type, field_name, old_value,
        new_value) — used when the agent returns the new richer schema.
    The frontend understands both.
    """
    object_name: str
    object_type: str = Field(default="standard_object", description="standard_object|document_type|workflow|integration|report|role|ui_rule")
    # Legacy shape — filled from older responses:
    impacted_fields: list[ImpactedField] = []
    impacted_integrations: list[ImpactedIntegration] = []
    overall_severity: ImpactSeverity = ImpactSeverity.MEDIUM
    description: str = ""
    recommendations: list[str] = []
    # New agent format — pass-through dicts so the frontend can render
    # richer per-area details (workflow / integration / layout / etc.)
    impacted_areas: list[dict] = []
    # New format's extra scalars — used by the report panel:
    change_type: Optional[str] = None
    field_name: Optional[str] = None
    field_label: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class AnalysisMetadata(BaseModel):
    """Filenames + when-analyzed info shown at the top of the report card."""
    data_model_doc_name: Optional[str] = None
    config_report_name: Optional[str] = None
    analyzed_at: Optional[str] = None
    vault_name: Optional[str] = None


class AnalysisSummary(BaseModel):
    """Totals shown as the stat cards at the top of the report panel."""
    total_impacted_objects: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    key_findings: list[str] = []


# ─── Stage 1 ──────────────────────────────────────────────────────────────────
# The full result of an impact analysis. This is what the frontend
# receives (as JSON) and renders in the report panel.

class Stage1Report(BaseModel):
    session_id: str
    status: AnalysisStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    data_model_doc_name: str
    config_report_source: str = Field(
        description="S3 path or 'mock' when using placeholder"
    )
    analysis_metadata: Optional[AnalysisMetadata] = None
    summary: Optional[AnalysisSummary] = None
    impacted_objects: list[ImpactedObject] = []
    no_impact_confirmed: list[str] = []
    # Full agent output as JSON string — kept for debugging / re-render
    raw_llm_analysis: Optional[str] = None
    error: Optional[str] = None


class Stage1RunResponse(BaseModel):
    """Shape returned by the older /stage1/run endpoint (API-only)."""
    session_id: str
    status: AnalysisStatus
    message: str
    report: Optional[Stage1Report] = None


# ─── Session state (in-memory store shape) ────────────────────────────────────
# One SessionState per user upload. Lives inside the `_sessions` dict in
# analysis_service.py. Not persisted to disk — restarts wipe it.

class SessionState(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    stage1_report: Optional[Stage1Report] = None
    # label → local file path (e.g. "data_model_doc" → "storage/uuid/data_model_doc.xlsx")
    uploaded_files: dict[str, str] = Field(
        default_factory=dict,
        description="label -> local file path"
    )
    # Freeform bag for anything the router wants to remember across turns —
    # notably the Bedrock session id, uploaded filename, mode of last turn.
    metadata: dict[str, Any] = Field(default_factory=dict)
