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
    CRITICAL = "critical"
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


class ImpactedIntegration(BaseModel):
    integration_name: str
    integration_type: str = Field(..., description="API|Spark|VaultToVault|FTP|Other")
    severity: ImpactSeverity
    notes: Optional[str] = None


class ImpactedObject(BaseModel):
    object_name: str
    object_type: str = Field(default="standard_object", description="standard_object|document_type|workflow|integration|report|role|ui_rule")
    impacted_fields: list[ImpactedField] = []
    impacted_integrations: list[ImpactedIntegration] = []
    overall_severity: ImpactSeverity = ImpactSeverity.MEDIUM
    description: str = ""
    recommendations: list[str] = []
    # New agent format — raw impacted_areas passed through for the frontend
    impacted_areas: list[dict] = []
    # New agent format extras
    change_type: Optional[str] = None
    field_name: Optional[str] = None
    field_label: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None


class AnalysisMetadata(BaseModel):
    data_model_doc_name: Optional[str] = None
    config_report_name: Optional[str] = None
    analyzed_at: Optional[str] = None
    vault_name: Optional[str] = None


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
    analysis_metadata: Optional[AnalysisMetadata] = None
    summary: Optional[AnalysisSummary] = None
    impacted_objects: list[ImpactedObject] = []
    no_impact_confirmed: list[str] = []
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
