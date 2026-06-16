"""
Claude (Anthropic) LLM service.

Responsibilities:
  - Stage 1 analysis: data model changes + config report → impact report
  - Stage 2 analysis: stage 1 report + integration spec → final report
  - Q&A chat: answer user questions grounded in a specific report
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from config import settings
from models.schemas import (
    AnalysisSummary,
    ChatMessage,
    ImpactedField,
    ImpactedObject,
    ImpactSeverity,
    IntegrationImpact,
    Stage1Report,
    Stage2Report,
)

logger = logging.getLogger(__name__)

# Set MOCK_LLM=true in .env to skip real API calls and use canned demo responses
MOCK_LLM = settings.mock_llm

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ─── Stage 1 ──────────────────────────────────────────────────────────────────

STAGE1_SYSTEM = """You are an expert data architect and impact analysis specialist.

Your task is to analyse a DATA MODEL CHANGES DOCUMENT against a CONFIGURATION REPORT
and produce a precise, structured impact analysis.

Rules:
- Identify every object (table / entity / API object) that is affected by the changes.
- For each affected object list the specific fields that are impacted.
- Classify each impact as ADDED, MODIFIED, or REMOVED.
- Rate severity: HIGH (breaking change, data loss risk), MEDIUM (non-breaking but requires
  consumer updates), LOW (cosmetic / additive with no downstream risk).
- Provide clear, actionable recommendations.
- Return ONLY valid JSON — no markdown fences, no prose outside the JSON.

Output schema (strict):
{
  "summary": {
    "total_impacted_objects": <int>,
    "high_severity_count": <int>,
    "medium_severity_count": <int>,
    "low_severity_count": <int>,
    "key_findings": [<string>, ...]
  },
  "impacted_objects": [
    {
      "object_name": <string>,
      "object_type": <string>,
      "overall_severity": "high" | "medium" | "low",
      "description": <string>,
      "recommendations": [<string>, ...],
      "impacted_fields": [
        {
          "field_name": <string>,
          "old_definition": <string | null>,
          "new_definition": <string | null>,
          "change_type": "ADDED" | "MODIFIED" | "REMOVED",
          "severity": "high" | "medium" | "low",
          "notes": <string | null>
        }
      ]
    }
  ]
}
"""

STAGE2_SYSTEM = """You are an expert integration architect and impact analysis specialist.

You will receive:
1. A STAGE 1 IMPACT REPORT that identifies which data model objects and fields changed.
2. An INTEGRATION SPECIFICATION DOCUMENT that describes how various integrations consume the data.

Your task is to produce a final integration impact report.

Rules:
- For each integration in the specification, determine whether it is affected by the data model
  changes identified in Stage 1.
- List the specific endpoints / events / jobs that need to change.
- List the specific fields involved.
- Indicate whether the change is backward-compatible.
- Provide a prioritised list of migration steps.
- Return ONLY valid JSON — no markdown fences, no prose outside the JSON.

Output schema (strict):
{
  "summary": {
    "total_impacted_objects": <int>,
    "high_severity_count": <int>,
    "medium_severity_count": <int>,
    "low_severity_count": <int>,
    "key_findings": [<string>, ...]
  },
  "integration_impacts": [
    {
      "integration_name": <string>,
      "integration_type": <string>,
      "affected_endpoints": [<string>, ...],
      "affected_fields": [<string>, ...],
      "severity": "high" | "medium" | "low",
      "description": <string>,
      "recommended_changes": [<string>, ...],
      "backward_compatible": <bool>
    }
  ],
  "migration_steps": [<string>, ...]
}
"""

QA_SYSTEM = """You are a helpful assistant who specialises in explaining impact analysis reports.

You have access to the full report shown in the CONTEXT block.  Answer the user's question
clearly, referencing specific objects, fields, or integrations from the report where relevant.
If the answer is not in the report, say so explicitly — do not guess.

After your answer, suggest 2–3 relevant follow-up questions the user might want to ask.
Format:

ANSWER:
<your answer here>

FOLLOW-UP QUESTIONS:
1. <question>
2. <question>
3. <question>
"""


# ─── Public API ───────────────────────────────────────────────────────────────

async def run_stage1_analysis(
    data_model_text: str,
    config_report: dict[str, Any],
) -> dict[str, Any]:
    if MOCK_LLM:
        logger.info("MOCK_LLM=true — returning mock Stage 1 analysis")
        return _mock_stage1_result(data_model_text, config_report)
    return await _real_stage1_analysis(data_model_text, config_report)


async def _real_stage1_analysis(
    data_model_text: str,
    config_report: dict[str, Any],
) -> dict[str, Any]:
    """
    Call Claude to analyse data model changes against the config report.
    Returns the parsed JSON dict matching the Stage 1 output schema.
    """
    user_prompt = f"""## DATA MODEL CHANGES DOCUMENT

{data_model_text}

---

## CONFIGURATION REPORT

{json.dumps(config_report, indent=2)}

---

Analyse the changes and return the impact report JSON.
"""
    raw = _chat(STAGE1_SYSTEM, user_prompt)
    return _parse_json_response(raw)


async def run_stage2_analysis(
    integration_spec_text: str,
    stage1_report: Stage1Report,
) -> dict[str, Any]:
    if MOCK_LLM:
        logger.info("MOCK_LLM=true — returning mock Stage 2 analysis")
        return _mock_stage2_result(stage1_report)
    return await _real_stage2_analysis(integration_spec_text, stage1_report)


async def _real_stage2_analysis(
    integration_spec_text: str,
    stage1_report: Stage1Report,
) -> dict[str, Any]:
    """
    Call Claude to analyse the integration spec against the Stage 1 impact report.
    Returns the parsed JSON dict matching the Stage 2 output schema.
    """
    stage1_summary = stage1_report.model_dump(
        include={"summary", "impacted_objects"},
        mode="json",
    )
    user_prompt = f"""## STAGE 1 IMPACT REPORT

{json.dumps(stage1_summary, indent=2)}

---

## INTEGRATION SPECIFICATION DOCUMENT

{integration_spec_text}

---

Analyse the integration impacts and return the final report JSON.
"""
    raw = _chat(STAGE2_SYSTEM, user_prompt)
    return _parse_json_response(raw)


async def answer_question(
    question: str,
    report_context: str,
    history: list[ChatMessage],
) -> tuple[str, list[str]]:
    if MOCK_LLM:
        logger.info("MOCK_LLM=true — returning mock Q&A answer")
        return _mock_qa_answer(question, report_context)
    return await _real_answer_question(question, report_context, history)


async def _real_answer_question(
    question: str,
    report_context: str,
    history: list[ChatMessage],
) -> tuple[str, list[str]]:
    """
    Answer a user question grounded in the provided report text.
    Returns (answer, follow_up_questions).
    """
    system = QA_SYSTEM + f"\n\n## CONTEXT\n\n{report_context}"

    messages: list[dict[str, str]] = []
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=messages,
    )
    raw_answer = response.content[0].text.strip()
    return _parse_qa_response(raw_answer)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _chat(system: str, user_content: str) -> str:
    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text.strip()


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Strip any accidental markdown fences and parse JSON."""
    text = raw
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first and last fence lines
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned non-JSON response: %s", raw[:500])
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc


def _parse_qa_response(raw: str) -> tuple[str, list[str]]:
    """Split the structured Q&A response into (answer, follow_ups)."""
    answer = raw
    follow_ups: list[str] = []

    if "FOLLOW-UP QUESTIONS:" in raw:
        parts = raw.split("FOLLOW-UP QUESTIONS:", 1)
        answer_part = parts[0].replace("ANSWER:", "").strip()
        fq_part = parts[1].strip()
        answer = answer_part
        for line in fq_part.splitlines():
            line = line.strip()
            if line and line[0].isdigit():
                # strip leading "1. " etc.
                follow_ups.append(line.split(". ", 1)[-1])
    elif "ANSWER:" in raw:
        answer = raw.replace("ANSWER:", "").strip()

    return answer, follow_ups


# ─── Report → readable text (for Q&A context) ─────────────────────────────────

def stage1_report_to_context(report: Stage1Report) -> str:
    lines = [
        f"# Stage 1 Impact Analysis Report",
        f"Session: {report.session_id}",
        f"Document: {report.data_model_doc_name}",
        "",
    ]
    if report.summary:
        s = report.summary
        lines += [
            "## Summary",
            f"- Total impacted objects: {s.total_impacted_objects}",
            f"- High severity: {s.high_severity_count}",
            f"- Medium severity: {s.medium_severity_count}",
            f"- Low severity: {s.low_severity_count}",
            "",
            "### Key Findings",
        ]
        for finding in s.key_findings:
            lines.append(f"- {finding}")
        lines.append("")

    for obj in report.impacted_objects:
        lines += [
            f"## {obj.object_name} ({obj.object_type}) — {obj.overall_severity.upper()}",
            obj.description,
            "",
            "### Impacted Fields",
        ]
        for field in obj.impacted_fields:
            lines.append(
                f"- **{field.field_name}** [{field.change_type}] ({field.severity})"
                + (f": {field.notes}" if field.notes else "")
            )
        if obj.recommendations:
            lines += ["", "### Recommendations"]
            for rec in obj.recommendations:
                lines.append(f"- {rec}")
        lines.append("")

    return "\n".join(lines)


def stage2_report_to_context(report: Stage2Report) -> str:
    lines = [
        "# Stage 2 Final Integration Impact Report",
        f"Session: {report.session_id}",
        f"Document: {report.integration_spec_doc_name}",
        "",
    ]
    if report.summary:
        s = report.summary
        lines += [
            "## Summary",
            f"- Total impacted integrations: {s.total_impacted_objects}",
            f"- High severity: {s.high_severity_count}",
            f"- Medium severity: {s.medium_severity_count}",
            f"- Low severity: {s.low_severity_count}",
            "",
            "### Key Findings",
        ]
        for finding in s.key_findings:
            lines.append(f"- {finding}")
        lines.append("")

    for impact in report.integration_impacts:
        lines += [
            f"## {impact.integration_name} ({impact.integration_type}) — {impact.severity.upper()}",
            impact.description,
            f"Backward compatible: {'Yes' if impact.backward_compatible else 'No'}",
            "",
        ]
        if impact.affected_endpoints:
            lines.append("**Affected endpoints/topics:**")
            for ep in impact.affected_endpoints:
                lines.append(f"- {ep}")
        if impact.affected_fields:
            lines.append("**Affected fields:**")
            for f in impact.affected_fields:
                lines.append(f"- {f}")
        if impact.recommended_changes:
            lines.append("**Recommended changes:**")
            for rc in impact.recommended_changes:
                lines.append(f"- {rc}")
        lines.append("")

    if report.migration_steps:
        lines += ["## Migration Steps"]
        for i, step in enumerate(report.migration_steps, 1):
            lines.append(f"{i}. {step}")

    return "\n".join(lines)


# ─── Mock responses (MOCK_LLM=true) ──────────────────────────────────────────

def _mock_stage1_result(data_model_text: str, config_report: dict[str, Any]) -> dict[str, Any]:
    """Return a realistic Stage 1 analysis without calling the real LLM."""
    objects = config_report.get("objects", [])
    obj_names = [o["name"] for o in objects[:5]] if objects else ["Customer", "Order", "Product"]

    return {
        "summary": {
            "total_impacted_objects": len(obj_names),
            "high_severity_count": 2,
            "medium_severity_count": len(obj_names) - 3 if len(obj_names) > 3 else 1,
            "low_severity_count": 1,
            "key_findings": [
                f"{obj_names[0]} has a breaking field type change that will affect all downstream consumers",
                f"{obj_names[1] if len(obj_names) > 1 else 'Order'} status enum has deprecated values used by 3 integrations",
                "2 new required fields added without default values — existing records will fail validation",
                "Total of 11 field-level changes detected across the data model",
            ],
        },
        "impacted_objects": [
            {
                "object_name": obj_names[0],
                "object_type": "Entity",
                "overall_severity": "high",
                "description": f"{obj_names[0]} has critical field changes including a type change and a new required field with no default.",
                "recommendations": [
                    "Migrate existing data before deploying the type change",
                    "Add a default value for the new required field or make it optional",
                    "Notify all downstream API consumers of the breaking change",
                ],
                "impacted_fields": [
                    {
                        "field_name": "id",
                        "old_definition": "String(36)",
                        "new_definition": "UUID",
                        "change_type": "MODIFIED",
                        "severity": "high",
                        "notes": "Type change from String to UUID is breaking — consumers storing as plain string will fail",
                    },
                    {
                        "field_name": "tier",
                        "old_definition": None,
                        "new_definition": "Enum(BRONZE, SILVER, GOLD) REQUIRED",
                        "change_type": "ADDED",
                        "severity": "high",
                        "notes": "New required field with no default — existing rows will violate the constraint",
                    },
                    {
                        "field_name": "email",
                        "old_definition": "String NULLABLE",
                        "new_definition": "String NOT NULL",
                        "change_type": "MODIFIED",
                        "severity": "medium",
                        "notes": "Nullability change — records with null email will fail validation",
                    },
                ],
            },
            {
                "object_name": obj_names[1] if len(obj_names) > 1 else "Order",
                "object_type": "Entity",
                "overall_severity": "high",
                "description": "Status picklist has deprecated values that active integrations depend on.",
                "recommendations": [
                    "Map deprecated status values to new equivalents in all integration connectors",
                    "Run a data migration script to update existing records before go-live",
                ],
                "impacted_fields": [
                    {
                        "field_name": "status",
                        "old_definition": "Enum(PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED, DRAFT)",
                        "new_definition": "Enum(PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED)",
                        "change_type": "MODIFIED",
                        "severity": "high",
                        "notes": "DRAFT value removed — any record or integration using DRAFT will fail",
                    },
                    {
                        "field_name": "totalAmount",
                        "old_definition": "total (Decimal)",
                        "new_definition": "totalAmount (Decimal)",
                        "change_type": "MODIFIED",
                        "severity": "medium",
                        "notes": "Field renamed — all queries using old name will break",
                    },
                ],
            },
            {
                "object_name": obj_names[2] if len(obj_names) > 2 else "Product",
                "object_type": "Entity",
                "overall_severity": "medium",
                "description": "New optional fields added for taxonomy v2. Non-breaking but requires consumer updates.",
                "recommendations": [
                    "Update ETL pipelines to populate new taxonomy fields",
                    "Add mapping rules in the product catalog integration",
                ],
                "impacted_fields": [
                    {
                        "field_name": "categoryCode",
                        "old_definition": None,
                        "new_definition": "String NULLABLE",
                        "change_type": "ADDED",
                        "severity": "low",
                        "notes": "New optional field — additive, no immediate breakage",
                    },
                    {
                        "field_name": "sku",
                        "old_definition": "String NULLABLE",
                        "new_definition": "String NOT NULL UNIQUE",
                        "change_type": "MODIFIED",
                        "severity": "medium",
                        "notes": "Now required and unique — existing nulls and duplicates must be resolved",
                    },
                ],
            },
        ] + [
            {
                "object_name": name,
                "object_type": "Entity",
                "overall_severity": "low",
                "description": f"{name} has minor additive changes — new optional fields only.",
                "recommendations": ["Update API documentation to reflect new optional fields"],
                "impacted_fields": [
                    {
                        "field_name": "updatedAt",
                        "old_definition": None,
                        "new_definition": "DateTime NULLABLE",
                        "change_type": "ADDED",
                        "severity": "low",
                        "notes": "Audit timestamp — additive, no breakage",
                    }
                ],
            }
            for name in obj_names[3:]
        ],
    }


def _mock_stage2_result(stage1_report: Stage1Report) -> dict[str, Any]:
    """Return a realistic Stage 2 integration impact analysis without calling the real LLM."""
    impacted = [o.object_name for o in stage1_report.impacted_objects]

    return {
        "summary": {
            "total_impacted_objects": 4,
            "high_severity_count": 2,
            "medium_severity_count": 1,
            "low_severity_count": 1,
            "key_findings": [
                "Order Management API will break on status DRAFT — active in 2 integration flows",
                f"{impacted[0] if impacted else 'Customer'} API consumers will receive UUID where String was expected",
                "Billing sync reads totalAmount field by old name 'total' — will return null",
                "1 integration is backward-compatible and requires no immediate changes",
            ],
        },
        "integration_impacts": [
            {
                "integration_name": "Order Management API",
                "integration_type": "REST",
                "affected_endpoints": ["/api/v1/orders", "/api/v1/orders/{id}", "/api/v1/orders/{id}/status"],
                "affected_fields": ["status", "totalAmount"],
                "severity": "high",
                "description": "The OMS connector sends DRAFT status which is now removed. The totalAmount rename will return null in all order value calculations.",
                "recommended_changes": [
                    "Map DRAFT → PENDING in the OMS-to-backend connector config",
                    "Update field mapping: 'total' → 'totalAmount' in the order sync transformer",
                    "Add fallback handling for null totalAmount during the transition window",
                ],
                "backward_compatible": False,
            },
            {
                "integration_name": "Billing Sync",
                "integration_type": "REST",
                "affected_endpoints": ["/api/v1/payments", "/api/v1/payments/{id}/refund"],
                "affected_fields": ["totalAmount", "id"],
                "severity": "high",
                "description": "Billing reads order totals using the old field name 'total'. The UUID change on customer ID will also break the customer lookup join in billing reports.",
                "recommended_changes": [
                    "Update billing ETL query: replace `total` with `totalAmount`",
                    "Cast UUID to VARCHAR in the billing DB join or update schema to accept UUID type",
                    "Re-run reconciliation report after migration to catch any missed records",
                ],
                "backward_compatible": False,
            },
            {
                "integration_name": "Product Catalog Sync",
                "integration_type": "REST",
                "affected_endpoints": ["/api/v1/products", "/api/v1/products/{id}"],
                "affected_fields": ["sku", "categoryCode"],
                "severity": "medium",
                "description": "SKU is now required and unique — products without SKU will be rejected. The new categoryCode field is optional but should be mapped for full taxonomy support.",
                "recommended_changes": [
                    "Add SKU generation logic in the product catalog integration before sync",
                    "Add categoryCode to the product sync field mapping",
                    "Run a pre-migration SKU deduplication check",
                ],
                "backward_compatible": False,
            },
            {
                "integration_name": "Order Events Stream",
                "integration_type": "Event",
                "affected_endpoints": ["order.created", "order.updated"],
                "affected_fields": ["updatedAt"],
                "severity": "low",
                "description": "The new optional updatedAt field will be included in order events. Consumers can safely ignore it — no breaking changes.",
                "recommended_changes": [
                    "Update event schema documentation",
                    "Optionally consume updatedAt for improved event deduplication",
                ],
                "backward_compatible": True,
            },
        ],
        "migration_steps": [
            "Step 1 — Run pre-migration validation: identify all records with null SKU, null email, and DRAFT order status",
            "Step 2 — Patch data: assign SKUs, set email defaults, migrate DRAFT orders to PENDING",
            "Step 3 — Deploy schema changes to staging; run integration test suite against staging",
            "Step 4 — Update OMS connector: remap DRAFT→PENDING, rename total→totalAmount in field mappings",
            "Step 5 — Update Billing ETL query: replace `total` with `totalAmount`, update customer ID join to handle UUID",
            "Step 6 — Update Product Catalog sync: add SKU generation and categoryCode mapping",
            "Step 7 — Deploy to production in a maintenance window; verify each integration health check",
            "Step 8 — Monitor for 24h post-deployment; run reconciliation reports to confirm data integrity",
        ],
    }


def _mock_qa_answer(question: str, report_context: str) -> tuple[str, list[str]]:
    """Return a contextual mock answer for the Q&A panel."""
    q = question.lower()

    if any(w in q for w in ["high", "critical", "severe", "worst", "biggest"]):
        answer = (
            "The two highest-severity findings are:\n\n"
            "1. Field type change (String → UUID) — this is a breaking change for any consumer storing or comparing the ID as a plain string. All database joins and API clients must be updated.\n\n"
            "2. Removed status value 'DRAFT' — the Order Management integration actively sends DRAFT status. Without a remapping layer, order sync will fail with a validation error as soon as the change is deployed.\n\n"
            "Both require action before go-live."
        )
        follow_ups = [
            "What is the safest order to deploy these changes?",
            "Which integration is most at risk if we deploy without changes?",
            "Can we make the UUID change backward-compatible?",
        ]
    elif any(w in q for w in ["uuid", "id", "string", "type"]):
        answer = (
            "The UUID change on the customer ID field is rated HIGH because it is a data type change at the persistence layer.\n\n"
            "Any system that stores the ID as VARCHAR and does a string comparison will continue to work during a transition period, but any system that does a typed JOIN or casts the value will break immediately.\n\n"
            "The Billing Sync is specifically affected — it joins on customer ID to build billing reports, and that join will fail once the ID is stored as a native UUID type.\n\n"
            "Recommended fix: cast UUID to VARCHAR in the billing DB join, or migrate the billing schema to also store UUID type."
        )
        follow_ups = [
            "How do I update the Billing Sync to handle UUIDs?",
            "Which other integrations use the customer ID field?",
            "Is there a way to run both old and new ID formats during transition?",
        ]
    elif any(w in q for w in ["draft", "status", "order", "oms"]):
        answer = (
            "The DRAFT status removal is critical for the Order Management integration.\n\n"
            "The OMS connector currently sends `status: DRAFT` for orders in the initial creation phase. Once DRAFT is removed from the enum, the backend API will reject these payloads with a validation error.\n\n"
            "The fix is straightforward: update the OMS connector config to map DRAFT → PENDING before the payload is sent. This is a connector-level config change, not a code change.\n\n"
            "Timeline risk: if this is deployed before the connector is updated, order creation will fail in production immediately."
        )
        follow_ups = [
            "Where exactly do I change the OMS connector mapping?",
            "Are there existing DRAFT orders in the database that need migration?",
            "What happens to in-flight orders during deployment?",
        ]
    elif any(w in q for w in ["fix", "remediat", "step", "how", "migration", "deploy"]):
        answer = (
            "Here is the recommended remediation order:\n\n"
            "1. Run pre-migration validation to find all null SKUs, null emails, and DRAFT-status orders\n"
            "2. Patch the data (assign SKUs, set email defaults, move DRAFT → PENDING)\n"
            "3. Update the OMS connector mapping (DRAFT→PENDING, total→totalAmount)\n"
            "4. Update the Billing ETL query (field rename + UUID join fix)\n"
            "5. Deploy to staging and run full integration test suite\n"
            "6. Deploy to production in a maintenance window\n"
            "7. Monitor for 24h and run reconciliation reports\n\n"
            "Steps 1–4 can be done in parallel by different teams."
        )
        follow_ups = [
            "What does the pre-migration validation script look like?",
            "How long should the maintenance window be?",
            "Which team owns the OMS connector update?",
        ]
    else:
        answer = (
            "Based on the impact analysis report:\n\n"
            "The data model changes affect multiple objects and integrations. "
            "The most critical items are the UUID type change and the removal of the DRAFT order status — "
            "both require updates to downstream integrations before the changes can be safely deployed.\n\n"
            "You can ask me about specific objects, fields, integrations, or remediation steps and I'll give you a detailed answer."
        )
        follow_ups = [
            "Which changes are high severity and why?",
            "What is the recommended migration order?",
            "Which integrations will break if deployed without changes?",
        ]

    return answer, follow_ups
