from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Enumerations ─────────────────────────────────────────────────────────────

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ImpactSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ─── Shared building blocks ────────────────────────────────────────────────────

class ImpactedField(BaseModel):
    field_name: str
    old_definition: Optional[str] = None
    new_definition: Optional[str] = None
    change_type: str = Field(..., description="ADDED | MODIFIED | REMOVED")
    severity: ImpactSeverity
    notes: Optional[str] = None


class ImpactedObject(BaseModel):
    object_name: str
    object_type: str = Field(..., description="e.g. Table, Entity, API Object")
    impacted_fields: list[ImpactedField] = []
    overall_severity: ImpactSeverity
    description: str
    recommendations: list[str] = []


class AnalysisSummary(BaseModel):
    total_impacted_objects: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    key_findings: list[str] = []


# ─── Stage 1 ──────────────────────────────────────────────────────────────────

class Stage1Report(BaseModel):
    session_id: str
    status: AnalysisStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    data_model_doc_name: str
    config_report_source: str = Field(
        description="S3 path or 'mock' when using placeholder"
    )
    summary: Optional[AnalysisSummary] = None
    impacted_objects: list[ImpactedObject] = []
    raw_llm_analysis: Optional[str] = None
    error: Optional[str] = None


class Stage1RunResponse(BaseModel):
    session_id: str
    status: AnalysisStatus
    message: str
    report: Optional[Stage1Report] = None


# ─── Session state (in-memory store shape) ────────────────────────────────────

class SessionState(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    stage1_report: Optional[Stage1Report] = None
    uploaded_files: dict[str, str] = Field(
        default_factory=dict,
        description="label -> local file path"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
