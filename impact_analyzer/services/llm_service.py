"""
Claude (Anthropic) LLM service.

Responsibilities:
  - Stage 1 analysis: data model changes + config report → impact report
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from config import settings

logger = logging.getLogger(__name__)

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
    # If the config report came from S3 as parsed Excel text, use that directly.
    # Otherwise fall back to JSON serialisation of the dict (mock / legacy path).
    config_content = config_report.get("report_text") or json.dumps(config_report, indent=2)

    user_prompt = f"""## DATA MODEL CHANGES DOCUMENT

{data_model_text}

---

## CONFIGURATION REPORT

{config_content}

---

Analyse the changes and return the impact report JSON.
"""
    raw = _chat(STAGE1_SYSTEM, user_prompt)
    return _parse_json_response(raw)


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
    text = raw
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned non-JSON response: %s", raw[:500])
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc


# ─── Mock responses (MOCK_LLM=true) ──────────────────────────────────────────

def _mock_stage1_result(data_model_text: str, config_report: dict[str, Any]) -> dict[str, Any]:
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
